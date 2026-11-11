"""Integration tests for Stateful 3-Step Self-Healing Execution Loop."""

import unittest
from unittest.mock import AsyncMock, patch
from app.core.agent_loop import AgentLoop, AgentExecutionResult
from app.core.llm_router import LLMRouter, LLMResult
from app.core.schema_indexer import SchemaIndexer
from app.database import close_target_engines


class TestAgentLoop(unittest.IsolatedAsyncioTestCase):
    """Integration tests verifying query generation, AST gating, and self-healing repair."""

    async def asyncSetUp(self):
        """Set up test environment targeting pre-seeded benchmark database."""
        self.test_db_url = "sqlite+aiosqlite:///./ecommerce_demo.db"
        self.datasource_id = "test-agent-ds"

        self.schema_indexer = SchemaIndexer()
        await self.schema_indexer.index_datasource(
            self.datasource_id,
            self.test_db_url,
            dialect="sqlite",
        )

    async def asyncTearDown(self):
        """Clean up target engines."""
        await close_target_engines()

    async def test_successful_end_to_end_loop(self):
        """Agent should retrieve schema, validate SQL, execute against DB, and synthesize chart."""
        mock_llm = AsyncMock(spec=LLMRouter)
        mock_llm.generate_sql.return_value = LLMResult(
            content="SELECT country, COUNT(id) as total_users FROM customers GROUP BY country;",
            cleaned_sql="SELECT country, COUNT(id) as total_users FROM customers GROUP BY country;",
            provider="GROQ",
            model="llama-3.3-70b-versatile",
            latency_ms=120.0,
        )

        agent = AgentLoop(llm_router=mock_llm, schema_indexer=self.schema_indexer)
        result: AgentExecutionResult = await agent.execute_query(
            datasource_id=self.datasource_id,
            question="Show user count by country",
            connection_uri=self.test_db_url,
            dialect="sqlite",
        )

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.self_heal_attempts, 0)
        self.assertEqual(result.provider_used, "GROQ")
        self.assertGreater(result.row_count, 0)
        self.assertIsNotNone(result.chart_config)
        self.assertEqual(result.chart_config.get("chart_type"), "bar_chart")
        self.assertIn("country", result.columns)

    async def test_self_healing_column_auto_repair(self):
        """Attempt 1 fails with non-existent column, AgentLoop catches error and Attempt 2 succeeds."""
        mock_llm = AsyncMock(spec=LLMRouter)

        # First call generates bad column 'user_total_rev'
        # Second call generates repaired query with valid columns
        mock_llm.generate_sql.side_effect = [
            LLMResult(
                content="SELECT id, user_total_rev FROM customers;",
                cleaned_sql="SELECT id, user_total_rev FROM customers;",
                provider="GROQ",
                model="llama-3.3-70b-versatile",
                latency_ms=150.0,
            ),
            LLMResult(
                content="SELECT id, name FROM customers;",
                cleaned_sql="SELECT id, name FROM customers;",
                provider="GROQ",
                model="llama-3.3-70b-versatile",
                latency_ms=130.0,
            ),
        ]

        agent = AgentLoop(llm_router=mock_llm, schema_indexer=self.schema_indexer)
        result: AgentExecutionResult = await agent.execute_query(
            datasource_id=self.datasource_id,
            question="Query customers total revenue",
            connection_uri=self.test_db_url,
            dialect="sqlite",
        )

        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.self_heal_attempts, 1)
        self.assertEqual(len(result.rows), 50)  # 50 customers returned
        self.assertEqual(mock_llm.generate_sql.call_count, 2)

    async def test_ast_firewall_blocks_destructive_query(self):
        """Agent should intercept DROP TABLE commands at compile time without database execution."""
        mock_llm = AsyncMock(spec=LLMRouter)
        mock_llm.generate_sql.return_value = LLMResult(
            content="DROP TABLE orders;",
            cleaned_sql="DROP TABLE orders;",
            provider="GROQ",
            model="llama-3.3-70b-versatile",
            latency_ms=90.0,
        )

        agent = AgentLoop(llm_router=mock_llm, schema_indexer=self.schema_indexer)
        result: AgentExecutionResult = await agent.execute_query(
            datasource_id=self.datasource_id,
            question="DROP TABLE orders",
            connection_uri=self.test_db_url,
            dialect="sqlite",
        )

        self.assertEqual(result.status, "BLOCKED_AST")
        self.assertEqual(result.row_count, 0)
        self.assertIn("AST Firewall blocked", result.summary)


if __name__ == "__main__":
    unittest.main()
