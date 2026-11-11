"""SQLAlchemy 2.0 models for QueryForge metadata and audit persistence."""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any
from sqlalchemy import (
    String,
    Integer,
    SmallInteger,
    Numeric,
    Text,
    DateTime,
    ForeignKey,
    Index,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base class for metadata models."""
    pass


class DataSource(Base):
    """External data sources registered for Text-to-SQL introspection."""

    __tablename__ = "data_sources"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    name: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
    )
    dialect: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="postgresql",
    )
    connection_uri_encrypted: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    tables_indexed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Relationships
    golden_queries: Mapped[List["GoldenQuery"]] = relationship(
        "GoldenQuery",
        back_populates="datasource",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    audit_logs: Mapped[List["QueryAuditLog"]] = relationship(
        "QueryAuditLog",
        back_populates="datasource",
        lazy="selectin",
    )


class GoldenQuery(Base):
    """Curated, human-verified natural language to SQL pairs for few-shot Schema RAG."""

    __tablename__ = "golden_queries"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    datasource_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("data_sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    natural_question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    verified_sql: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Relationships
    datasource: Mapped["DataSource"] = relationship(
        "DataSource",
        back_populates="golden_queries",
    )


class QueryAuditLog(Base):
    """Audit telemetry for executed queries, AST firewall blocks, costs, and self-heal iterations."""

    __tablename__ = "query_audit_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    datasource_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("data_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    generated_sql: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    self_heal_attempts: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        default=0,
    )
    error_history: Mapped[List[Any]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    explain_cost: Mapped[Optional[float]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )
    execution_time_ms: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    row_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    provider_used: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(24),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    # Relationships
    datasource: Mapped[Optional["DataSource"]] = relationship(
        "DataSource",
        back_populates="audit_logs",
    )

    __table_args__ = (
        Index("idx_audit_status_created", "status", "created_at"),
    )
