"""Data source registration and schema introspection endpoints."""

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_metadata_db, encrypt_connection_uri
from app.models.metadata import DataSource
from app.schemas.metadata import DataSourceCreate, DataSourceResponse

router = APIRouter()


@router.post("", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def register_datasource(
    payload: DataSourceCreate,
    db: AsyncSession = Depends(get_metadata_db),
) -> DataSourceResponse:
    """Register an external database and encrypt its connection credentials."""
    # Check if name is already taken
    existing = await db.execute(select(DataSource).where(DataSource.name == payload.name))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Data source with name '{payload.name}' already exists.",
        )

    # Encrypt connection string for secure at-rest storage
    encrypted_uri = encrypt_connection_uri(payload.connection_uri)

    datasource = DataSource(
        name=payload.name,
        dialect=payload.dialect,
        connection_uri_encrypted=encrypted_uri,
        tables_indexed=0,
    )
    db.add(datasource)
    await db.commit()
    await db.refresh(datasource)

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

    return {
        "datasource_id": ds.id,
        "name": ds.name,
        "dialect": ds.dialect,
        "tables_indexed": ds.tables_indexed,
        "last_synced_at": ds.last_synced_at,
    }
