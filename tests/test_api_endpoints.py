"""Integration tests for FastAPI REST API endpoints."""

import unittest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.models.metadata import Base, DataSource
from app.database import get_metadata_db, encrypt_connection_uri, init_metadata_db


class TestAPIEndpoints(unittest.IsolatedAsyncioTestCase):
    """End-to-end integration tests for REST routes."""

    async def asyncSetUp(self):
        """Set up in-memory SQLite session override for testing."""
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
        self.session_maker = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async def override_get_db():
            async with self.session_maker() as session:
                yield session

        app.dependency_overrides[get_metadata_db] = override_get_db
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://test")

    async def asyncTearDown(self):
        """Clean up test client and database."""
        app.dependency_overrides.clear()
        await self.client.aclose()
        await self.engine.dispose()

    async def test_health_and_root(self):
        """Root and health endpoints should return 200 OK."""
        res_root = await self.client.get("/")
        self.assertEqual(res_root.status_code, 200)
        self.assertEqual(res_root.json()["service"], "QueryForge")

        res_health = await self.client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["status"], "ok")

    async def test_datasource_registration_and_list(self):
        """POST /v1/datasources creates data source and redacts sensitive URI."""
        payload = {
            "name": "Analytics Warehouse",
            "dialect": "postgresql",
            "connection_uri": "postgresql+asyncpg://user:pass@localhost:5432/db",
        }
        res = await self.client.post("/v1/datasources", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["name"], "Analytics Warehouse")
        self.assertNotIn("connection_uri", data)
        ds_id = data["id"]

        # GET /v1/datasources
        list_res = await self.client.get("/v1/datasources")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(len(list_res.json()), 1)

        # GET /v1/datasources/{id}
        get_res = await self.client.get(f"/v1/datasources/{ds_id}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["name"], "Analytics Warehouse")

    async def test_golden_queries_crud(self):
        """Verify adding and retrieving golden few-shot query pairs."""
        # Create datasource first
        ds_payload = {
            "name": "Sales DB",
            "dialect": "sqlite",
            "connection_uri": "sqlite+aiosqlite:///test.db",
        }
        ds_res = await self.client.post("/v1/datasources", json=ds_payload)
        ds_id = ds_res.json()["id"]

        golden_payload = {
            "datasource_id": ds_id,
            "natural_question": "Total sales by region?",
            "verified_sql": "SELECT region, SUM(amount) FROM sales GROUP BY region",
        }
        create_res = await self.client.post("/v1/golden-queries", json=golden_payload)
        self.assertEqual(create_res.status_code, 201)
        golden_id = create_res.json()["id"]

        list_res = await self.client.get(f"/v1/golden-queries?datasource_id={ds_id}")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(len(list_res.json()), 1)

        del_res = await self.client.delete(f"/v1/golden-queries/{golden_id}")
        self.assertEqual(del_res.status_code, 204)

    async def test_telemetry_metrics_empty_and_populated(self):
        """GET /v1/metrics/telemetry returns system metrics."""
        res = await self.client.get("/v1/metrics/telemetry")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_queries"], 0)
        self.assertEqual(data["success_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
