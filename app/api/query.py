"""Query endpoints for natural language Text-to-SQL execution and SSE live streaming."""

import json
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.database import get_metadata_db, decrypt_connection_uri, encrypt_connection_uri
from app.models.metadata import DataSource, QueryAuditLog
from app.schemas.metadata import (
    QueryAskRequest,
    QueryAskResponse,
    MutationConfirmRequest,
    MutationConfirmResponse,
)
from app.core.agent_loop import AgentLoop, AgentExecutionResult

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()
agent_loop = AgentLoop()


async def _get_or_create_datasource(db: AsyncSession, datasource_id: str) -> Optional[DataSource]:
    """Retrieve data source or auto-provision default-demo-db fallback."""
    ds = await db.get(DataSource, datasource_id)
    if not ds and datasource_id == "default-demo-db":
        dialect = "postgresql" if "postgres" in settings.target_database_url else "sqlite"
        ds = DataSource(
            id="default-demo-db",
            name="Demo SaaS & E-Commerce DB",
            dialect=dialect,
            connection_uri_encrypted=encrypt_connection_uri(settings.target_database_url),
            tables_indexed=5,
        )
        db.add(ds)
        try:
            await db.commit()
            await db.refresh(ds)
        except Exception:
            await db.rollback()
            ds = await db.get(DataSource, datasource_id)
    return ds


@router.post("/ask", response_model=QueryAskResponse)
async def ask_query(
    payload: QueryAskRequest,
    db: AsyncSession = Depends(get_metadata_db),
) -> QueryAskResponse:
    """Execute natural language query through Schema RAG, AST firewall, and self-healing loop."""
    ds = await _get_or_create_datasource(db, payload.datasource_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source '{payload.datasource_id}' does not exist.",
        )

    target_uri = decrypt_connection_uri(ds.connection_uri_encrypted)

    if ds.id == "default-demo-db" and not agent_loop.schema_indexer.get_indexed_table_names(ds.id):
        try:
            await agent_loop.schema_indexer.index_datasource(
                datasource_id=ds.id,
                connection_uri=target_uri,
                dialect=ds.dialect,
            )
        except Exception as exc:
            logger.warning(f"On-demand schema indexing of default-demo-db skipped: {exc}")

    result: AgentExecutionResult = await agent_loop.execute_query(
        datasource_id=ds.id,
        question=payload.question,
        connection_uri=target_uri,
        dialect=ds.dialect,
        mode=payload.mode,
    )

    # Persist execution telemetry to internal audit logs
    audit_entry = QueryAuditLog(
        datasource_id=ds.id,
        user_question=payload.question,
        generated_sql=result.sql,
        self_heal_attempts=result.self_heal_attempts,
        error_history=result.error_history,
        explain_cost=result.explain_cost,
        execution_time_ms=result.execution_time_ms,
        row_count=result.row_count,
        provider_used=result.provider_used,
        status=result.status,
    )
    db.add(audit_entry)
    await db.commit()

    if result.status == "BLOCKED_AST":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": result.summary,
                "status": "BLOCKED_AST",
                "sql": result.sql,
            },
        )
    elif result.status == "FAILED_EXECUTION":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": result.summary,
                "status": "FAILED_EXECUTION",
                "error_history": result.error_history,
            },
        )

    return QueryAskResponse(
        sql=result.sql,
        columns=result.columns,
        rows=result.rows,
        row_count=result.row_count,
        execution_time_ms=result.execution_time_ms,
        explain_cost=result.explain_cost,
        provider_used=result.provider_used,
        self_heal_attempts=result.self_heal_attempts,
        status=result.status,
        chart_config=result.chart_config,
        summary=result.summary,
        requires_confirmation=result.requires_confirmation,
        mutation_impact=result.mutation_impact,
    )


@router.post("/stream")
async def stream_query_execution(
    payload: QueryAskRequest,
    db: AsyncSession = Depends(get_metadata_db),
):
    """Server-Sent Events (SSE) streaming endpoint showing live step-by-step agent reasoning."""
    ds = await _get_or_create_datasource(db, payload.datasource_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source '{payload.datasource_id}' does not exist.",
        )

    target_uri = decrypt_connection_uri(ds.connection_uri_encrypted)

    if ds.id == "default-demo-db" and not agent_loop.schema_indexer.get_indexed_table_names(ds.id):
        try:
            await agent_loop.schema_indexer.index_datasource(
                datasource_id=ds.id,
                connection_uri=target_uri,
                dialect=ds.dialect,
            )
        except Exception as exc:
            logger.warning(f"On-demand schema indexing of default-demo-db skipped: {exc}")

    async def event_generator():
        async for event in agent_loop.execute_query_stream(
            datasource_id=ds.id,
            question=payload.question,
            connection_uri=target_uri,
            dialect=ds.dialect,
            mode=payload.mode,
        ):
            event_json = json.dumps(event.model_dump(), default=str)
            yield f"data: {event_json}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/confirm", response_model=MutationConfirmResponse)
async def confirm_mutation_execution(
    payload: MutationConfirmRequest,
    db: AsyncSession = Depends(get_metadata_db),
) -> MutationConfirmResponse:
    """Execute a human-confirmed mutation query and commit changes to the target database."""
    ds = await _get_or_create_datasource(db, payload.datasource_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source '{payload.datasource_id}' does not exist.",
        )

    target_uri = decrypt_connection_uri(ds.connection_uri_encrypted)
    try:
        result = await agent_loop.execute_confirmed_mutation(
            datasource_id=ds.id,
            connection_uri=target_uri,
            dialect=ds.dialect,
            sql=payload.sql,
        )

        # Audit log for confirmed mutation
        audit_entry = QueryAuditLog(
            datasource_id=ds.id,
            user_question="[HUMAN CONFIRMED MUTATION]",
            generated_sql=result["sql"],
            self_heal_attempts=0,
            error_history=[],
            explain_cost=None,
            execution_time_ms=result["execution_time_ms"],
            row_count=result.get("rows_affected", 0),
            provider_used="USER_CONFIRMED",
            status="MUTATION_COMMITTED",
        )
        db.add(audit_entry)
        await db.commit()

        return MutationConfirmResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to execute confirmed mutation: {str(exc)}",
        )
