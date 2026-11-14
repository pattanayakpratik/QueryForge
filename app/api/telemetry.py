"""Agent telemetry, execution metrics, and circuit breaker health reporting."""

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_metadata_db
from app.models.metadata import QueryAuditLog
from app.schemas.metadata import TelemetryResponse

router = APIRouter()


@router.get("/telemetry", response_model=TelemetryResponse)
async def get_telemetry_metrics(
    db: AsyncSession = Depends(get_metadata_db),
) -> TelemetryResponse:
    """Return aggregated system performance, pass rates, and model usage metrics."""
    result = await db.execute(select(QueryAuditLog))
    logs = result.scalars().all()

    total = len(logs)
    if total == 0:
        return TelemetryResponse(
            total_queries=0,
            success_rate=0.0,
            first_shot_pass_rate=0.0,
            self_healed_rate=0.0,
            avg_execution_time_ms=0.0,
            groq_count=0,
            gemini_count=0,
        )

    success_count = sum(1 for log in logs if log.status == "SUCCESS")
    first_shot_count = sum(1 for log in logs if log.status == "SUCCESS" and log.self_heal_attempts == 0)
    self_healed_count = sum(1 for log in logs if log.status == "SUCCESS" and log.self_heal_attempts > 0)
    total_time = sum((log.execution_time_ms or 0.0) for log in logs)
    groq_count = sum(1 for log in logs if (log.provider_used or "").upper() == "GROQ")
    gemini_count = sum(1 for log in logs if (log.provider_used or "").upper() == "GEMINI")

    return TelemetryResponse(
        total_queries=total,
        success_rate=round((success_count / total) * 100.0, 2),
        first_shot_pass_rate=round((first_shot_count / total) * 100.0, 2),
        self_healed_rate=round((self_healed_count / total) * 100.0, 2),
        avg_execution_time_ms=round(total_time / total, 2),
        groq_count=groq_count,
        gemini_count=gemini_count,
    )
