"""Pydantic schemas and API contracts for QueryForge."""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator
from app.core.uri_utils import validate_ssrf_and_scheme, normalize_database_uri


class DataSourceCreate(BaseModel):
    """Payload to register a new external data source."""
    name: str = Field(..., min_length=2, max_length=128, description="Unique data source identifier")
    dialect: str = Field(default="postgresql", description="SQL dialect: 'postgresql', 'sqlite', etc.")
    connection_uri: str = Field(..., description="Target database connection string")

    @field_validator("connection_uri")
    @classmethod
    def validate_connection_scheme(cls, v: str) -> str:
        clean = v.strip()
        validate_ssrf_and_scheme(clean)
        return clean


class DataSourceTestRequest(BaseModel):
    """Payload to test read-only connection and table discovery on an external database."""
    name: Optional[str] = "Database Probe"
    dialect: Optional[str] = None
    connection_uri: str = Field(..., description="Target database connection string to probe")


class DataSourceTestResponse(BaseModel):
    """Result of read-only connection test probe."""
    success: bool
    latency_ms: float
    tables_found: List[str] = []
    tables_count: int = 0
    dialect: str
    message: str


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
    mode: str = Field(default="read_only", description="'read_only' or 'read_write'")


class MutationConfirmRequest(BaseModel):
    """Payload to confirm execution of a human-reviewed write query."""
    datasource_id: str
    sql: str = Field(..., min_length=5, description="Confirmed SQL statement to commit")


class MutationConfirmResponse(BaseModel):
    """Response returned upon committing a confirmed mutation."""
    status: str
    sql: str
    rows_affected: Optional[int] = None
    action_type: str
    target_tables: List[str] = []
    execution_time_ms: float
    message: str


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
    requires_confirmation: bool = False
    mutation_impact: Optional[Dict[str, Any]] = None


class TelemetryResponse(BaseModel):
    """System-wide accuracy and routing telemetry metrics."""
    total_queries: int
    success_rate: float
    first_shot_pass_rate: float
    self_healed_rate: float
    avg_execution_time_ms: float
    groq_count: int
    gemini_count: int
