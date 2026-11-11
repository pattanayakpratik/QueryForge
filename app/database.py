"""Database connection pooling, metadata session management, and URI encryption."""

import base64
import os
from typing import AsyncGenerator, Dict
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.config import get_settings
from app.models.metadata import Base

# Cache for dynamic target DB engines
_target_engine_pool: Dict[str, AsyncEngine] = {}

# Internal metadata engine and sessionmaker
settings = get_settings()

metadata_engine: AsyncEngine = create_async_engine(
    settings.metadata_database_url,
    echo=False,
    future=True,
)

async_session_maker = async_sessionmaker(
    bind=metadata_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


def _get_or_create_cipher() -> Fernet:
    """Retrieve or derive the Fernet symmetric cipher for encrypting connection strings."""
    key = settings.secret_encryption_key
    if not key:
        # Deterministic 32-byte key for local development
        default_seed = b"queryforge_32_byte_master_key_1!"
        key = base64.urlsafe_b64encode(default_seed).decode()
    elif len(key) != 44:
        # Ensure urlsafe base64 32-byte key
        padded = key.encode().ljust(32, b"0")[:32]
        key = base64.urlsafe_b64encode(padded).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_connection_uri(uri: str) -> str:
    """Encrypt a sensitive database connection string."""
    cipher = _get_or_create_cipher()
    return cipher.encrypt(uri.encode()).decode()


def decrypt_connection_uri(encrypted_uri: str) -> str:
    """Decrypt an encrypted database connection string."""
    cipher = _get_or_create_cipher()
    return cipher.decrypt(encrypted_uri.encode()).decode()


async def init_metadata_db() -> None:
    """Initialize metadata database tables if they do not exist."""
    async with metadata_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_metadata_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async metadata database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


def get_target_engine(connection_uri: str) -> AsyncEngine:
    """Retrieve or create an async engine for a target user database."""
    if connection_uri not in _target_engine_pool:
        # Configure pool with safe defaults
        engine = create_async_engine(
            connection_uri,
            pool_pre_ping=True,
            echo=False,
            future=True,
        )
        _target_engine_pool[connection_uri] = engine
    return _target_engine_pool[connection_uri]


async def close_target_engines() -> None:
    """Dispose of all cached target database engines during shutdown."""
    for uri, engine in list(_target_engine_pool.items()):
        await engine.dispose()
    _target_engine_pool.clear()
