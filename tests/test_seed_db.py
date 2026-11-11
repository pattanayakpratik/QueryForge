"""Tests verifying demo e-commerce schema seeding."""

import unittest
from sqlalchemy import text
from app.database import get_target_engine
from scripts.seed_demo_ecommerce_db import seed_ecommerce_database


class TestDemoSeedDatabase(unittest.IsolatedAsyncioTestCase):
    """Unit test for demo e-commerce seed script."""

    async def test_seed_ecommerce_database_populates_5_tables(self):
        """Seed script should create and populate customers, products, orders, items, and refunds."""
        test_db_url = "sqlite+aiosqlite:///./test_ecommerce_seed.db"
        await seed_ecommerce_database(target_url=test_db_url)

        engine = get_target_engine(test_db_url)
        async with engine.connect() as conn:
            # Check customers
            cust_res = await conn.execute(text("SELECT COUNT(*) FROM customers"))
            self.assertEqual(cust_res.scalar(), 50)

            # Check products
            prod_res = await conn.execute(text("SELECT COUNT(*) FROM products"))
            self.assertEqual(prod_res.scalar(), 10)

            # Check orders
            ord_res = await conn.execute(text("SELECT COUNT(*) FROM orders"))
            self.assertEqual(ord_res.scalar(), 200)

            # Check order items
            items_res = await conn.execute(text("SELECT COUNT(*) FROM order_items"))
            self.assertGreater(items_res.scalar(), 200)

            # Check refunds
            ref_res = await conn.execute(text("SELECT COUNT(*) FROM refunds"))
            self.assertGreater(ref_res.scalar(), 0)

        # Cleanup
        await engine.dispose()
        import os
        if os.path.exists("./test_ecommerce_seed.db"):
            try:
                os.remove("./test_ecommerce_seed.db")
            except Exception:
                pass


if __name__ == "__main__":
    unittest.main()
