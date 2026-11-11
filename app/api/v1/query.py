"""Query endpoints for natural language Text-to-SQL execution and SSE live streaming."""

import json
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_metadata_db, decrypt_connection_uri
from app.models.metadata import DataSource, QueryAuditLog
from app.schemas.metadata import QueryAskRequest, QueryAskResponse
from app.core.agent_loop import AgentLoop, AgentExecutionResult

router = APIRouter()
agent_loop = AgentLoop()


@router.post("/ask", response_model=QueryAskResponse)
async def ask_query(
    payload: QueryAskRequest,
    db: AsyncSession = Depends(get_metadata_db),
) -> QueryAskResponse:
    """Execute natural language query through Schema RAG, AST firewall, and self-healing loop."""
    ds = await db.get(DataSource, payload.datasource_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source '{payload.datasource_id}' does not exist.",
        )

    target_uri = decrypt_connection_uri(ds.connection_uri_encrypted)

    result: AgentExecutionResult = await agent_loop.execute_query(
        datasource_id=ds.id,
        question=payload.question,
        connection_uri=target_uri,
        dialect=ds.dialect,
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
        status="SUCCESS",
        chart_config=result.chart_config,
        summary=result.summary,
    )


@router.post("/stream")
async def stream_query_execution(
    payload: QueryAskRequest,
    db: AsyncSession = Depends(get_metadata_db),
):
    """Server-Sent Events (SSE) streaming endpoint showing live step-by-step agent reasoning."""
    ds = await db.get(DataSource, payload.datasource_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source '{payload.datasource_id}' does not exist.",
        )

    target_uri = decrypt_connection_uri(ds.connection_uri_encrypted)

    async def event_generator():
        async for event in agent_loop.execute_query_stream(
            datasource_id=ds.id,
            question=payload.question,
            connection_uri=target_uri,
            dialect=ds.dialect,
        ):
            event_json = json.dumps(event.model_dump())
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
