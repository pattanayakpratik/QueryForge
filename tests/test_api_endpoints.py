"""Integration tests for FastAPI REST API endpoints."""

import unittest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.models.metadata import Base, DataSource
from app.database import get_metadata_db, encrypt_connection_uri, init_metadata_db, close_target_engines


class TestAPIEndpoints(unittest.IsolatedAsyncioTestCase):
    """End-to-end integration tests for REST routes."""

    async def asyncSetUp(self):
        """Set up in-memory SQLite session override for testing."""
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            echo=False,
        )
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
        await close_target_engines()

    async def test_health_and_root(self):
        """Root and health endpoints should return 200 OK."""
        res_root = await self.client.get("/")
        self.assertEqual(res_root.status_code, 200)
        self.assertEqual(res_root.json()["service"], "QueryForge")

        res_health = await self.client.get("/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertEqual(res_health.json()["status"], "ok")

    async def test_datasource_registration_and_list(self):
        """POST /datasources creates data source and redacts sensitive URI."""
        payload = {
            "name": "Analytics Warehouse",
            "dialect": "postgresql",
            "connection_uri": "postgresql+asyncpg://user:pass@localhost:5432/db",
        }
        res = await self.client.post("/datasources", json=payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["name"], "Analytics Warehouse")
        self.assertNotIn("connection_uri", data)
        ds_id = data["id"]

        # GET /datasources
        list_res = await self.client.get("/datasources")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(len(list_res.json()), 1)

        # GET /datasources/{id}
        get_res = await self.client.get(f"/datasources/{ds_id}")
        self.assertEqual(get_res.status_code, 200)
        self.assertEqual(get_res.json()["name"], "Analytics Warehouse")

        # DELETE /datasources/{id}
        del_res = await self.client.delete(f"/datasources/{ds_id}")
        self.assertEqual(del_res.status_code, 204)

        # Safeguard default-demo-db deletion
        del_default = await self.client.delete("/datasources/default-demo-db")
        self.assertEqual(del_default.status_code, 400)

    async def test_datasource_test_probe_endpoint(self):
        """POST /datasources/test verifies connection probe and table discovery."""
        test_probe_payload = {
            "name": "Local SQLite Probe",
            "dialect": "sqlite",
            "connection_uri": "sqlite+aiosqlite:///:memory:",
        }
        res = await self.client.post("/datasources/test", json=test_probe_payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["dialect"], "sqlite")
        self.assertIn("latency_ms", data)

    async def test_golden_queries_crud(self):
        """Verify adding and retrieving golden few-shot query pairs."""
        # Create datasource first
        ds_payload = {
            "name": "Sales DB",
            "dialect": "sqlite",
            "connection_uri": "sqlite+aiosqlite:///test.db",
        }
        ds_res = await self.client.post("/datasources", json=ds_payload)
        ds_id = ds_res.json()["id"]

        golden_payload = {
            "datasource_id": ds_id,
            "natural_question": "Total sales by region?",
            "verified_sql": "SELECT region, SUM(amount) FROM sales GROUP BY region",
        }
        create_res = await self.client.post("/golden-queries", json=golden_payload)
        self.assertEqual(create_res.status_code, 201)
        golden_id = create_res.json()["id"]

        list_res = await self.client.get(f"/golden-queries?datasource_id={ds_id}")
        self.assertEqual(list_res.status_code, 200)
        self.assertEqual(len(list_res.json()), 1)

        del_res = await self.client.delete(f"/golden-queries/{golden_id}")
        self.assertEqual(del_res.status_code, 204)

    async def test_telemetry_metrics_empty_and_populated(self):
        """GET /metrics/telemetry returns system metrics."""
        res = await self.client.get("/metrics/telemetry")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_queries"], 0)
        self.assertEqual(data["success_rate"], 0.0)

    async def test_query_stream_auto_provisions_default_demo_db(self):
        """POST /query/stream with 'default-demo-db' should auto-provision fallback and stream SSE."""
        payload = {
            "datasource_id": "default-demo-db",
            "question": "SELECT 1;",
        }
        res = await self.client.post("/query/stream", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertIn("text/event-stream", res.headers.get("content-type", ""))
        self.assertIn("data: ", res.text)

    async def test_query_ask_auto_provisions_default_demo_db(self):
        """POST /query/ask with 'default-demo-db' should auto-provision fallback and execute query."""
        payload = {
            "datasource_id": "default-demo-db",
            "question": "SELECT 1;",
        }
        res = await self.client.post("/query/ask", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "SUCCESS")
        self.assertIn("sql", data)

    async def test_query_ask_unknown_datasource_returns_404(self):
        """POST /query/ask with an unregistered uuid should return 404."""
        payload = {
            "datasource_id": "non-existent-uuid-12345",
            "question": "SELECT 1;",
        }
        res = await self.client.post("/query/ask", json=payload)
        self.assertEqual(res.status_code, 404)
        self.assertIn("does not exist", res.json()["detail"])


if __name__ == "__main__":
    unittest.main()
