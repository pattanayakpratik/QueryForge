"""Unit tests for Schema Introspection and Semantic Card Indexing."""

import unittest
from app.core.schema_indexer import SchemaIndexer, TableMetadata, ColumnMetadata
from scripts.seed_demo_ecommerce_db import seed_ecommerce_database
from app.database import close_target_engines


class TestSchemaIndexer(unittest.IsolatedAsyncioTestCase):
    """Integration tests verifying database catalog inspection and markdown cards."""

    async def asyncSetUp(self):
        """Use pre-seeded demo e-commerce database."""
        self.test_db_url = "sqlite+aiosqlite:///./ecommerce_demo.db"
        self.indexer = SchemaIndexer()

    async def asyncTearDown(self):
        """Clean up target test engine."""
        await close_target_engines()

    async def test_introspect_sqlite_tables_and_columns(self):
        """Schema indexer should discover all 5 e-commerce benchmark tables."""
        tables = await self.indexer.introspect_target_schema(self.test_db_url, dialect="sqlite")
        table_names = {t.table_name for t in tables}

        self.assertIn("customers", table_names)
        self.assertIn("products", table_names)
        self.assertIn("orders", table_names)
        self.assertIn("order_items", table_names)
        self.assertIn("refunds", table_names)

        # Verify customers table columns & sample values
        cust_tbl = next(t for t in tables if t.table_name == "customers")
        cust_cols = {c.name: c for c in cust_tbl.columns}

        self.assertTrue(cust_cols["id"].is_primary_key)
        self.assertIn("country", cust_cols)
        self.assertGreater(len(cust_cols["country"].sample_values), 0)

        # Verify foreign keys in orders
        orders_tbl = next(t for t in tables if t.table_name == "orders")
        order_cols = {c.name: c for c in orders_tbl.columns}
        self.assertTrue(any("customers.id" in str(fk.get("to")) for fk in orders_tbl.foreign_keys))

    async def test_markdown_card_generation(self):
        """Generated markdown card contains column types, keys, and relationships."""
        tables = await self.indexer.introspect_target_schema(self.test_db_url, dialect="sqlite")
        orders_tbl = next(t for t in tables if t.table_name == "orders")
        card = orders_tbl.markdown_card

        self.assertIn("### Table: `orders`", card)
        self.assertIn("`id` (INTEGER, PRIMARY KEY)", card)
        self.assertIn("Relationships:", card)

    async def test_index_and_retrieve_relevant_tables(self):
        """Querying for customer refunds should retrieve refunds, orders, and customers."""
        ds_id = "test-ds-uuid"
        count = await self.indexer.index_datasource(ds_id, self.test_db_url, dialect="sqlite")
        self.assertEqual(count, 5)

        retrieved = self.indexer.retrieve_relevant_tables(ds_id, "Show refund amounts for orders", top_k=2)
        self.assertEqual(len(retrieved), 2)
        combined_text = "\n".join(retrieved)
        self.assertTrue("refunds" in combined_text or "orders" in combined_text)

    def test_golden_query_storage_and_retrieval(self):
        """Golden verified questions should store and retrieve based on query overlap."""
        ds_id = "test-ds-uuid"
        self.indexer.save_golden_query(
            ds_id,
            question="What is the monthly refund rate?",
            sql="SELECT strftime('%Y-%m', created_at), COUNT(*) FROM refunds GROUP BY 1",
        )
        self.indexer.save_golden_query(
            ds_id,
            question="List top customers by total order spend",
            sql="SELECT customer_id, SUM(total_amount_cents) FROM orders GROUP BY 1 ORDER BY 2 DESC",
        )

        results = self.indexer.retrieve_golden_queries(ds_id, "Find customer spend on orders", top_k=1)
        self.assertEqual(len(results), 1)
        self.assertIn("spend", results[0]["question"].lower())


if __name__ == "__main__":
    unittest.main()
