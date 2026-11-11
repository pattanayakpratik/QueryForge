"""Tests for metadata models, encryption helpers, and database persistence."""

import unittest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models.metadata import Base, DataSource, GoldenQuery, QueryAuditLog
from app.database import encrypt_connection_uri, decrypt_connection_uri


class TestMetadataModels(unittest.IsolatedAsyncioTestCase):
    """Integration test suite for internal metadata store."""

    async def asyncSetUp(self):
        """Set up in-memory async SQLite engine."""
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        self.session_maker = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def asyncTearDown(self):
        """Dispose of the test database engine."""
        await self.engine.dispose()

    def test_connection_uri_encryption_roundtrip(self):
        """Sensitive URIs must encrypt and decrypt losslessly."""
        raw_uri = "postgresql+asyncpg://admin:super_secret_pw@db.internal:5432/analytics"
        encrypted = encrypt_connection_uri(raw_uri)
        self.assertNotEqual(raw_uri, encrypted)
        decrypted = decrypt_connection_uri(encrypted)
        self.assertEqual(raw_uri, decrypted)

    async def test_create_datasource_and_golden_query(self):
        """Verify DataSource creation and child GoldenQuery relationships."""
        ds_id = None
        async with self.session_maker() as session:
            ds = DataSource(
                name="Production Analytics DB",
                dialect="postgresql",
                connection_uri_encrypted=encrypt_connection_uri("sqlite+aiosqlite:///test.db"),
                tables_indexed=5,
            )
            session.add(ds)
            await session.commit()
            ds_id = ds.id

            golden = GoldenQuery(
                datasource_id=ds_id,
                natural_question="How many users signed up last month?",
                verified_sql="SELECT COUNT(*) FROM customers WHERE signup_date >= '2026-10-01'",
            )
            session.add(golden)
            await session.commit()

        # Query in fresh session with selectinload
        async with self.session_maker() as session:
            stmt = (
                select(DataSource)
                .options(selectinload(DataSource.golden_queries))
                .where(DataSource.id == ds_id)
            )
            result = await session.execute(stmt)
            fetched_ds = result.scalar_one()

            self.assertEqual(fetched_ds.name, "Production Analytics DB")
            self.assertEqual(len(fetched_ds.golden_queries), 1)
            self.assertEqual(
                fetched_ds.golden_queries[0].natural_question,
                "How many users signed up last month?",
            )

    async def test_query_audit_log_persistence(self):
        """Verify QueryAuditLog records execution attempts, costs, and statuses."""
        async with self.session_maker() as session:
            audit = QueryAuditLog(
                user_question="Top 5 products by revenue",
                generated_sql="SELECT p.name, SUM(oi.unit_price_cents * oi.quantity) FROM products p ...",
                self_heal_attempts=1,
                error_history=[{"error": "UndefinedColumnError: p.title does not exist"}],
                explain_cost=120.50,
                execution_time_ms=45.2,
                row_count=5,
                provider_used="GROQ",
                status="SUCCESS",
            )
            session.add(audit)
            await session.commit()
            await session.refresh(audit)

            stmt = select(QueryAuditLog).where(QueryAuditLog.id == audit.id)
            result = await session.execute(stmt)
            fetched = result.scalar_one()

            self.assertEqual(fetched.status, "SUCCESS")
            self.assertEqual(fetched.self_heal_attempts, 1)
            self.assertEqual(fetched.provider_used, "GROQ")
            self.assertEqual(len(fetched.error_history), 1)


if __name__ == "__main__":
    unittest.main()
