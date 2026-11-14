"""Utility module for database URI normalization, SSRF protection, and read-only connection probing."""

import asyncio
import ipaddress
import re
import socket
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode
from sqlalchemy import text
from app.database import get_target_engine

# Forbidden schemes that pose SSRF or local exploit vectors
ALLOWED_SCHEMES = {
    "postgres",
    "postgresql",
    "postgresql+asyncpg",
    "postgresql+psycopg",
    "postgresql+psycopg2",
    "sqlite",
    "sqlite+aiosqlite",
    "mysql",
    "mysql+aiomysql",
    "mysql+asyncmy",
}

# Cloud metadata addresses to prevent SSRF
BLOCKED_HOSTS = {
    "169.254.169.254",
    "metadata.google.internal",
    "169.254.169.253",
    "fd00:ec2::254",
}


def validate_ssrf_and_scheme(raw_uri: str) -> None:
    """Validate that the URI scheme is an authorized database protocol and protect against SSRF.

    Args:
        raw_uri: The raw database connection string provided by the user.

    Raises:
        ValueError: If scheme is forbidden, missing, or targets cloud metadata services.
    """
    cleaned = raw_uri.strip()
    if not cleaned:
        raise ValueError("Database connection URL cannot be empty.")

    # Split scheme
    parts = cleaned.split("://", 1)
    if len(parts) < 2:
        raise ValueError(
            "Invalid connection string format. Must include a protocol scheme, e.g. 'postgresql://...' or 'sqlite:///...'"
        )

    scheme = parts[0].lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ValueError(
            f"Unsupported or forbidden database protocol '{scheme}'. "
            "Supported protocols: PostgreSQL ('postgresql://', 'postgres://') and SQLite ('sqlite:///')."
        )

    # SQLite local URIs don't have network hostnames
    if "sqlite" in scheme:
        return

    # For network-based databases (PostgreSQL, MySQL), extract hostname
    parsed = urlsplit(cleaned)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Database connection URL must include a valid host.")

    lower_host = hostname.lower()
    if lower_host in BLOCKED_HOSTS:
        raise ValueError(f"Access to '{hostname}' is strictly blocked for security reasons (SSRF mitigation).")

    # Check for link-local and cloud metadata IP literals
    try:
        ip = ipaddress.ip_address(lower_host)
        if ip.is_link_local:
            raise ValueError(f"Access to link-local IP '{hostname}' is blocked for security reasons.")
    except ValueError as val_err:
        # If it was our own rejection message, re-raise it
        if "blocked for security reasons" in str(val_err):
            raise
        # Otherwise not an IP literal (a domain name like db.supabase.co or localhost)


def normalize_database_uri(raw_uri: str, dialect: Optional[str] = None) -> Tuple[str, str]:
    """Normalize a user-provided connection URI to an async SQLAlchemy driver format.

    Handles:
    - postgres:// and postgresql:// -> postgresql+asyncpg://
    - sqlite:// and sqlite:/// -> sqlite+aiosqlite:///
    - Mapping query params (e.g. sslmode=require -> ssl=require for asyncpg)
    - Inferring dialect ('postgresql' or 'sqlite') if omitted.

    Args:
        raw_uri: The raw user-supplied database URL.
        dialect: Optional dialect override.

    Returns:
        Tuple of (normalized_connection_uri, dialect)
    """
    validate_ssrf_and_scheme(raw_uri)
    uri = raw_uri.strip()

    # 1. Infer dialect if not specified
    inferred_dialect = dialect
    if not inferred_dialect:
        if uri.startswith("sqlite"):
            inferred_dialect = "sqlite"
        elif uri.startswith("mysql"):
            inferred_dialect = "mysql"
        else:
            inferred_dialect = "postgresql"

    # 2. SQLite Normalization
    if inferred_dialect == "sqlite":
        if uri.startswith("sqlite+aiosqlite://"):
            return uri, "sqlite"
        elif uri.startswith("sqlite:///"):
            return "sqlite+aiosqlite:///" + uri[10:], "sqlite"
        elif uri.startswith("sqlite://"):
            return "sqlite+aiosqlite://" + uri[9:], "sqlite"
        return f"sqlite+aiosqlite:///{uri}", "sqlite"

    # 3. PostgreSQL Normalization
    if inferred_dialect == "postgresql":
        # Convert standard sync drivers to asyncpg
        if uri.startswith("postgres://"):
            uri = "postgresql+asyncpg://" + uri[11:]
        elif uri.startswith("postgresql://"):
            uri = "postgresql+asyncpg://" + uri[13:]

        # Map sslmode parameter for asyncpg compatibility
        # asyncpg uses 'ssl=require' rather than 'sslmode=require'
        uri = re.sub(r"([?&])sslmode=", r"\1ssl=", uri)

        return uri, "postgresql"

    return uri, inferred_dialect


async def test_database_connection_readonly(
    connection_uri: str,
    dialect: Optional[str] = None,
    timeout_seconds: float = 6.0,
) -> Dict[str, any]:
    """Perform a strictly read-only connection test probe against a target database.

    Enforces read-only transaction configuration:
    - PostgreSQL: 'SET LOCAL TRANSACTION READ ONLY;' & statement timeout.
    - SQLite: 'PRAGMA query_only = ON;'

    Fetches the list of initial tables to verify schema accessibility.

    Returns:
        Dict with keys: success, latency_ms, tables_found, dialect, message.
    """
    normalized_uri, detected_dialect = normalize_database_uri(connection_uri, dialect)
    start_time = time.perf_counter()
    tables: List[str] = []

    async def _probe():
        nonlocal tables
        engine = get_target_engine(normalized_uri)
        async with engine.connect() as conn:
            if detected_dialect == "postgresql":
                # Enforce strictly read-only transaction and statement timeout
                await conn.execute(text("SET LOCAL TRANSACTION READ ONLY;"))
                await conn.execute(text("SET LOCAL statement_timeout = '5000';"))
                res = await conn.execute(
                    text(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                          AND table_type = 'BASE TABLE'
                        ORDER BY table_name
                        LIMIT 30;
                        """
                    )
                )
                tables = [str(row[0]) for row in res.fetchall()]
            elif detected_dialect == "sqlite":
                # Enforce SQLite query-only PRAGMA
                await conn.execute(text("PRAGMA query_only = ON;"))
                res = await conn.execute(
                    text(
                        """
                        SELECT name
                        FROM sqlite_master
                        WHERE type = 'table'
                          AND name NOT LIKE 'sqlite_%'
                        ORDER BY name
                        LIMIT 30;
                        """
                    )
                )
                tables = [str(row[0]) for row in res.fetchall()]
            else:
                tables = []

    try:
        await asyncio.wait_for(_probe(), timeout=timeout_seconds)
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        return {
            "success": True,
            "latency_ms": latency_ms,
            "tables_found": tables,
            "tables_count": len(tables),
            "dialect": detected_dialect,
            "normalized_uri": normalized_uri,
            "message": (
                f"Successfully connected in read-only mode ({latency_ms}ms). "
                f"Discovered {len(tables)} tables."
            ),
        }
    except asyncio.TimeoutError:
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        return {
            "success": False,
            "latency_ms": latency_ms,
            "tables_found": [],
            "tables_count": 0,
            "dialect": detected_dialect,
            "normalized_uri": normalized_uri,
            "message": f"Connection timed out after {timeout_seconds}s. Verify host, port, and security groups/firewall.",
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        return {
            "success": False,
            "latency_ms": latency_ms,
            "tables_found": [],
            "tables_count": 0,
            "dialect": detected_dialect,
            "normalized_uri": normalized_uri,
            "message": f"Connection failed: {str(exc)}",
        }
