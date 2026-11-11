"""Query endpoints for natural language Text-to-SQL execution."""

import time
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_metadata_db, decrypt_connection_uri, get_target_engine
from app.models.metadata import DataSource, QueryAuditLog
from app.schemas.metadata import QueryAskRequest, QueryAskResponse
from app.core.sql_guard import validate_and_sanitize_sql, SQLGuardError
from app.core.llm_router import LLMRouter

router = APIRouter()
llm_router = LLMRouter()


@router.post("/ask", response_model=QueryAskResponse)
async def ask_query(
    payload: QueryAskRequest,
    db: AsyncSession = Depends(get_metadata_db),
) -> QueryAskResponse:
    """Execute natural language query through LLM router, AST firewall, and target database."""
    ds = await db.get(DataSource, payload.datasource_id)
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source '{payload.datasource_id}' does not exist.",
        )

    start_time = time.perf_counter()
    target_uri = decrypt_connection_uri(ds.connection_uri_encrypted)
    target_engine = get_target_engine(target_uri)

    # 1. Synthesize SQL via LLMRouter
    llm_result = await llm_router.generate_sql(prompt=payload.question)
    raw_sql = llm_result.cleaned_sql

    # 2. Compile-time AST Firewall check
    try:
        sanitized_sql = validate_and_sanitize_sql(raw_sql, dialect=ds.dialect)
    except SQLGuardError as guard_err:
        # Audit the AST block
        execution_time = (time.perf_counter() - start_time) * 1000.0
        audit_entry = QueryAuditLog(
            datasource_id=ds.id,
            user_question=payload.question,
            generated_sql=raw_sql,
            self_heal_attempts=0,
            error_history=[{"error": guard_err.message, "code": guard_err.code}],
            execution_time_ms=round(execution_time, 2),
            provider_used=llm_result.provider,
            status="BLOCKED_AST",
        )
        db.add(audit_entry)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": guard_err.message,
                "code": guard_err.code,
                "status": "BLOCKED_AST",
            },
        )

    # 3. Execute in sandboxed target engine
    rows_data: List[Dict[str, Any]] = []
    columns: List[str] = []

    try:
        async with target_engine.connect() as conn:
            cursor = await conn.execute(text(sanitized_sql))
            if cursor.returns_rows:
                columns = list(cursor.keys())
                fetched_rows = cursor.fetchall()
                for row in fetched_rows:
                    rows_data.append(dict(zip(columns, row)))

        execution_time = (time.perf_counter() - start_time) * 1000.0
        audit_entry = QueryAuditLog(
            datasource_id=ds.id,
            user_question=payload.question,
            generated_sql=sanitized_sql,
            self_heal_attempts=0,
            error_history=[],
            execution_time_ms=round(execution_time, 2),
            row_count=len(rows_data),
            provider_used=llm_result.provider,
            status="SUCCESS",
        )
        db.add(audit_entry)
        await db.commit()

        return QueryAskResponse(
            sql=sanitized_sql,
            columns=columns,
            rows=rows_data,
            row_count=len(rows_data),
            execution_time_ms=round(execution_time, 2),
            provider_used=llm_result.provider,
            self_heal_attempts=0,
            status="SUCCESS",
            summary=f"Query successfully returned {len(rows_data)} records.",
        )

    except Exception as exc:
        execution_time = (time.perf_counter() - start_time) * 1000.0
        audit_entry = QueryAuditLog(
            datasource_id=ds.id,
            user_question=payload.question,
            generated_sql=sanitized_sql,
            self_heal_attempts=0,
            error_history=[{"error": str(exc)}],
            execution_time_ms=round(execution_time, 2),
            provider_used=llm_result.provider,
            status="FAILED_EXECUTION",
        )
        db.add(audit_entry)
        await db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution error on target database: {str(exc)}",
        )
