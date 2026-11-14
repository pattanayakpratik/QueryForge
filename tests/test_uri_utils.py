"""Unit tests verifying URI normalization, SSRF protection, and read-only connection probing."""

import unittest
from app.core.uri_utils import (
    normalize_database_uri,
    validate_ssrf_and_scheme,
    test_database_connection_readonly,
)
from app.database import close_target_engines, get_target_engine
from sqlalchemy import text


class TestURIUtils(unittest.IsolatedAsyncioTestCase):
    """Test suite for database URI normalization and security validation."""

    async def asyncTearDown(self):
        """Clean up connections."""
        await close_target_engines()

    def test_normalize_postgres_standard_uris(self):
        """Standard sync postgres URI schemes should be mapped to asyncpg driver."""
        uri1, dialect1 = normalize_database_uri("postgres://user:secret@db.supabase.co:5432/analytics")
        self.assertEqual(uri1, "postgresql+asyncpg://user:secret@db.supabase.co:5432/analytics")
        self.assertEqual(dialect1, "postgresql")

        uri2, dialect2 = normalize_database_uri("postgresql://user:pass@neon.tech:5432/neondb")
        self.assertEqual(uri2, "postgresql+asyncpg://user:pass@neon.tech:5432/neondb")
        self.assertEqual(dialect2, "postgresql")

    def test_normalize_postgres_ssl_params(self):
        """Cloud provider sslmode query parameters should be converted to asyncpg ssl."""
        raw = "postgresql://user:pass@ep-cool.neon.tech/neondb?sslmode=require&channel_binding=disable"
        normalized, dialect = normalize_database_uri(raw)
        self.assertIn("ssl=require", normalized)
        self.assertNotIn("sslmode=require", normalized)
        self.assertEqual(dialect, "postgresql")

    def test_normalize_sqlite_uris(self):
        """Standard sqlite URI schemes should be mapped to aiosqlite driver."""
        uri1, dialect1 = normalize_database_uri("sqlite:///data/store.db")
        self.assertEqual(uri1, "sqlite+aiosqlite:///data/store.db")
        self.assertEqual(dialect1, "sqlite")

        uri2, dialect2 = normalize_database_uri("sqlite://relative.db")
        self.assertEqual(uri2, "sqlite+aiosqlite://relative.db")
        self.assertEqual(dialect2, "sqlite")

    def test_ssrf_blocks_cloud_metadata_ips(self):
        """Direct connection attempts to cloud instance metadata IPs must be strictly rejected."""
        metadata_uris = [
            "postgresql://user:pass@169.254.169.254:5432/db",
            "postgresql://admin:secret@metadata.google.internal:5432/db",
            "postgres://user:pass@169.254.169.253:5432/db",
        ]
        for uri in metadata_uris:
            with self.assertRaises(ValueError) as ctx:
                validate_ssrf_and_scheme(uri)
            self.assertIn("security reasons", str(ctx.exception).lower())

    def test_ssrf_blocks_forbidden_schemes(self):
        """Disallow HTTP, FTP, file, and arbitrary URL schemes."""
        forbidden = [
            "http://127.0.0.1:8000/db",
            "https://evil.com/payload",
            "file:///etc/passwd",
            "ftp://host/file",
            "gopher://host:70/",
        ]
        for uri in forbidden:
            with self.assertRaises(ValueError):
                validate_ssrf_and_scheme(uri)

    async def test_probe_sqlite_connection_readonly(self):
        """Test read-only probe executes PRAGMA query_only and discovers tables."""
        test_db = "sqlite+aiosqlite:///./test_probe_db.sqlite"
        engine = get_target_engine(test_db)
        async with engine.begin() as conn:
            await conn.execute(text("CREATE TABLE IF NOT EXISTS test_users (id INT PRIMARY KEY, name TEXT);"))
            await conn.execute(text("CREATE TABLE IF NOT EXISTS test_orders (id INT PRIMARY KEY, total INT);"))

        result = await test_database_connection_readonly(test_db, dialect="sqlite")
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["tables_count"], 2)
        self.assertIn("test_users", result["tables_found"])
        self.assertIn("test_orders", result["tables_found"])
        self.assertIn("Successfully connected in read-only mode", result["message"])

        # Clean up
        async with engine.begin() as conn:
            await conn.execute(text("DROP TABLE IF EXISTS test_users;"))
            await conn.execute(text("DROP TABLE IF EXISTS test_orders;"))


if __name__ == "__main__":
    unittest.main()
