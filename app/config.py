"""Application configuration and environment settings for QueryForge."""

from functools import lru_cache
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """QueryForge system settings and environment variables."""

    # Application
    app_name: str = "QueryForge"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")
    debug: bool = Field(default=True, alias="DEBUG")

    # Database URLs
    # Internal metadata store (PostgreSQL in prod, SQLite for local dev/testing)
    metadata_database_url: str = Field(
        default="sqlite+aiosqlite:///./queryforge_metadata.db",
        alias="METADATA_DATABASE_URL",
    )
    # Target external database for demo & analytical queries
    target_database_url: str = Field(
        default="sqlite+aiosqlite:///./ecommerce_demo.db",
        alias="TARGET_DATABASE_URL",
    )

    # Encryption key for external database connection strings
    # 32-byte urlsafe base64 string for cryptography.fernet.Fernet
    secret_encryption_key: Optional[str] = Field(
        default=None,
        alias="SECRET_ENCRYPTION_KEY",
    )

    # LLM Providers & Keys
    groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, alias="GEMINI_API_KEY")

    # Model identifiers
    groq_model: str = Field(
        default="llama-3.3-70b-versatile",
        alias="GROQ_MODEL",
    )
    gemini_model: str = Field(
        default="gemini-1.5-flash",
        alias="GEMINI_MODEL",
    )

    # Circuit breaker & execution timeouts
    groq_timeout_seconds: float = Field(default=2.5, alias="GROQ_TIMEOUT_SECONDS")
    gemini_timeout_seconds: float = Field(default=8.0, alias="GEMINI_TIMEOUT_SECONDS")

    # Security & Execution limits
    max_execution_cost: float = Field(default=50000.0, alias="MAX_EXECUTION_COST")
    max_self_heal_attempts: int = Field(default=3, alias="MAX_SELF_HEAL_ATTEMPTS")
    statement_timeout_ms: int = Field(default=5000, alias="STATEMENT_TIMEOUT_MS")
    default_row_limit: int = Field(default=500, alias="DEFAULT_ROW_LIMIT")

    # Vector store / ChromaDB
    chroma_persist_directory: str = Field(
        default="./chroma_db",
        alias="CHROMA_PERSIST_DIRECTORY",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Retrieve cached singleton application settings."""
    return Settings()
