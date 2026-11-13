"""Pydantic schemas and API contracts for QueryForge."""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator


class DataSourceCreate(BaseModel):
    """Payload to register a new external data source."""
    name: str = Field(..., min_length=2, max_length=128, description="Unique data source identifier")
    dialect: str = Field(default="postgresql", description="SQL dialect: 'postgresql', 'sqlite', etc.")
    connection_uri: str = Field(..., description="Target database connection string")

    @field_validator("connection_uri")
    @classmethod
    def validate_connection_scheme(cls, v: str) -> str:
        clean = v.strip()
        allowed = ("postgresql+asyncpg://", "postgresql://", "sqlite+aiosqlite://", "sqlite://")
        if not any(clean.lower().startswith(s) for s in allowed):
            raise ValueError(
                f"Invalid connection URI scheme. Must start with one of: {', '.join(allowed)}"
            )
        return clean


class DataSourceResponse(BaseModel):
    """Public data source metadata response (sensitive connection URI redacted)."""
    id: str
    name: str
    dialect: str
    tables_indexed: int
    last_synced_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GoldenQueryCreate(BaseModel):
    """Payload to create a verified few-shot query example."""
    datasource_id: str
    natural_question: str = Field(..., min_length=3)
    verified_sql: str = Field(..., min_length=5)


class GoldenQueryResponse(BaseModel):
    """Verified golden query response."""
    id: str
    datasource_id: str
    natural_question: str
    verified_sql: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QueryAskRequest(BaseModel):
    """Natural language query execution request."""
    datasource_id: str
    question: str = Field(..., min_length=3, description="Natural language question")


class QueryAskResponse(BaseModel):
    """Response containing executed query, results, and visualization spec."""
    sql: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float
    explain_cost: Optional[float] = None
    provider_used: str
    self_heal_attempts: int
    status: str
    chart_config: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None


class TelemetryResponse(BaseModel):
    """System-wide accuracy and routing telemetry metrics."""
    total_queries: int
    success_rate: float
    first_shot_pass_rate: float
    self_healed_rate: float
    avg_execution_time_ms: float
    groq_count: int
    gemini_count: int
