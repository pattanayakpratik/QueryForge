"""Golden verified few-shot query management endpoints."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_metadata_db
from app.models.metadata import DataSource, GoldenQuery
from app.schemas.metadata import GoldenQueryCreate, GoldenQueryResponse

router = APIRouter()


@router.post("", response_model=GoldenQueryResponse, status_code=status.HTTP_201_CREATED)
async def create_golden_query(
    payload: GoldenQueryCreate,
    db: AsyncSession = Depends(get_metadata_db),
) -> GoldenQueryResponse:
    """Register a verified question-SQL pair into the few-shot RAG corpus."""
    ds = await db.get(DataSource, payload.datasource_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source '{payload.datasource_id}' does not exist.",
        )

    golden = GoldenQuery(
        datasource_id=payload.datasource_id,
        natural_question=payload.natural_question,
        verified_sql=payload.verified_sql,
    )
    db.add(golden)
    await db.commit()
    await db.refresh(golden)

    return GoldenQueryResponse.model_validate(golden)


@router.get("", response_model=List[GoldenQueryResponse])
async def list_golden_queries(
    datasource_id: str | None = None,
    db: AsyncSession = Depends(get_metadata_db),
) -> List[GoldenQueryResponse]:
    """Retrieve verified golden few-shot query examples."""
    query = select(GoldenQuery)
    if datasource_id:
        query = query.where(GoldenQuery.datasource_id == datasource_id)
    query = query.order_by(GoldenQuery.created_at.desc())

    result = await db.execute(query)
    records = result.scalars().all()
    return [GoldenQueryResponse.model_validate(item) for item in records]


@router.delete("/{golden_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_golden_query(
    golden_id: str,
    db: AsyncSession = Depends(get_metadata_db),
) -> None:
    """Remove a golden query from the training corpus."""
    golden = await db.get(GoldenQuery, golden_id)
    if not golden:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Golden query with ID '{golden_id}' not found.",
        )
    await db.delete(golden)
    await db.commit()
