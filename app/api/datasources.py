"""Data source registration, connection probing, and schema introspection endpoints."""

from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_metadata_db, encrypt_connection_uri, decrypt_connection_uri
from app.models.metadata import DataSource
from app.schemas.metadata import (
    DataSourceCreate,
    DataSourceResponse,
    DataSourceTestRequest,
    DataSourceTestResponse,
)
from app.core.schema_indexer import SchemaIndexer, get_schema_indexer
from app.core.uri_utils import normalize_database_uri, test_database_connection_readonly

router = APIRouter()
schema_indexer = get_schema_indexer()


@router.post("/test", response_model=DataSourceTestResponse)
async def test_datasource_connection(
    payload: DataSourceTestRequest,
) -> DataSourceTestResponse:
    """Test read-only connectivity and table discovery against an external database URL."""
    try:
        res = await test_database_connection_readonly(
            connection_uri=payload.connection_uri,
            dialect=payload.dialect,
        )
        return DataSourceTestResponse(
            success=res["success"],
            latency_ms=res["latency_ms"],
            tables_found=res["tables_found"],
            tables_count=res["tables_count"],
            dialect=res["dialect"],
            message=res["message"],
        )
    except Exception as exc:
        return DataSourceTestResponse(
            success=False,
            latency_ms=0.0,
            tables_found=[],
            tables_count=0,
            dialect=payload.dialect or "unknown",
            message=f"Validation failed: {str(exc)}",
        )


@router.post("", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def register_datasource(
    payload: DataSourceCreate,
    db: AsyncSession = Depends(get_metadata_db),
) -> DataSourceResponse:
    """Register an external database, encrypt credentials, and trigger schema introspection."""
    # Check if name is already taken
    existing = await db.execute(select(DataSource).where(DataSource.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Data source with name '{payload.name}' already exists.",
        )

    # Normalize URI and infer dialect
    normalized_uri, dialect = normalize_database_uri(payload.connection_uri, payload.dialect)

    # Encrypt connection string for secure at-rest storage
    encrypted_uri = encrypt_connection_uri(normalized_uri)

    datasource = DataSource(
        name=payload.name,
        dialect=dialect,
        connection_uri_encrypted=encrypted_uri,
        tables_indexed=0,
    )
    db.add(datasource)
    await db.commit()
    await db.refresh(datasource)

    # Automatic schema introspection & ChromaDB vector indexing
    try:
        indexed_count = await schema_indexer.index_datasource(
            datasource_id=datasource.id,
            connection_uri=normalized_uri,
            dialect=dialect,
        )
        datasource.tables_indexed = indexed_count
        datasource.last_synced_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(datasource)
    except Exception:
        # Retain registered datasource even if target DB is temporarily unreachable
        pass

    return DataSourceResponse.model_validate(datasource)


@router.get("", response_model=List[DataSourceResponse])
async def list_datasources(
    db: AsyncSession = Depends(get_metadata_db),
) -> List[DataSourceResponse]:
    """List all registered external databases."""
    result = await db.execute(select(DataSource).order_by(DataSource.created_at.desc()))
    datasources = result.scalars().all()
    return [DataSourceResponse.model_validate(ds) for ds in datasources]


@router.get("/{datasource_id}", response_model=DataSourceResponse)
async def get_datasource(
    datasource_id: str,
    db: AsyncSession = Depends(get_metadata_db),
) -> DataSourceResponse:
    """Get metadata for a specific registered data source."""
    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source with ID '{datasource_id}' not found.",
        )
    return DataSourceResponse.model_validate(ds)


@router.delete("/{datasource_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_datasource(
    datasource_id: str,
    db: AsyncSession = Depends(get_metadata_db),
) -> None:
    """Delete a registered data source and clean up its metadata."""
    if datasource_id == "default-demo-db":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default demo database.",
        )

    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source with ID '{datasource_id}' not found.",
        )

    await db.delete(ds)
    await db.commit()


@router.post("/{datasource_id}/sync", response_model=DataSourceResponse)
async def sync_datasource_schema(
    datasource_id: str,
    db: AsyncSession = Depends(get_metadata_db),
) -> DataSourceResponse:
    """Force re-introspection of database catalog and update ChromaDB vector store."""
    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source with ID '{datasource_id}' not found.",
        )

    target_uri = decrypt_connection_uri(ds.connection_uri_encrypted)
    try:
        indexed_count = await schema_indexer.index_datasource(
            datasource_id=ds.id,
            connection_uri=target_uri,
            dialect=ds.dialect,
        )
        ds.tables_indexed = indexed_count
        ds.last_synced_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(ds)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to synchronize schema from target database: {str(exc)}",
        )

    return DataSourceResponse.model_validate(ds)


@router.get("/{datasource_id}/schema", response_model=Dict[str, Any])
async def get_datasource_schema(
    datasource_id: str,
    db: AsyncSession = Depends(get_metadata_db),
) -> Dict[str, Any]:
    """Retrieve indexed tables, column types, and foreign key relations."""
    result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source with ID '{datasource_id}' not found.",
        )

    # Retrieve table cards
    cards = schema_indexer.retrieve_relevant_tables(datasource_id, query="", top_k=50)

    return {
        "datasource_id": ds.id,
        "name": ds.name,
        "dialect": ds.dialect,
        "tables_indexed": ds.tables_indexed,
        "last_synced_at": ds.last_synced_at,
        "table_cards": cards,
    }
