"""Tests for SQLGlot AST Firewall and Read-Only Sandbox."""

import unittest
from app.core.sql_guard import validate_and_sanitize_sql, SQLGuardError


class TestSQLGuard(unittest.TestCase):
    """Unit tests verifying AST-level protection against mutation and injections."""

    def test_valid_select_query_allows_execution(self):
        """Standard SELECT queries should parse successfully and append LIMIT."""
        query = "SELECT id, name FROM customers WHERE country = 'US'"
        sanitized = validate_and_sanitize_sql(query, default_limit=500)
        self.assertIn("SELECT", sanitized.upper())
        self.assertIn("LIMIT 500", sanitized.upper())

    def test_valid_join_query(self):
        """Complex queries with JOINs and aggregations should pass."""
        query = """
        SELECT c.country, COUNT(o.id) as order_count, SUM(o.total_amount_cents) as total_rev
        FROM customers c
        JOIN orders o ON c.id = o.customer_id
        GROUP BY c.country
        ORDER BY total_rev DESC
        """
        sanitized = validate_and_sanitize_sql(query, default_limit=100)
        self.assertIn("JOIN", sanitized.upper())
        self.assertIn("LIMIT 100", sanitized.upper())

    def test_valid_cte_query(self):
        """Common Table Expressions (WITH ... SELECT) must be allowed."""
        query = """
        WITH high_value_orders AS (
            SELECT id, total_amount_cents FROM orders WHERE total_amount_cents > 10000
        )
        SELECT * FROM high_value_orders
        """
        sanitized = validate_and_sanitize_sql(query)
        self.assertIn("WITH", sanitized.upper())
        self.assertIn("LIMIT 500", sanitized.upper())

    def test_valid_union_query(self):
        """UNION and UNION ALL queries must be allowed."""
        query = "SELECT id FROM orders UNION SELECT id FROM refunds"
        sanitized = validate_and_sanitize_sql(query)
        self.assertIn("UNION", sanitized.upper())
        self.assertIn("LIMIT 500", sanitized.upper())

    def test_preserves_smaller_user_limit(self):
        """A smaller user-supplied LIMIT should not be inflated."""
        query = "SELECT * FROM products LIMIT 10"
        sanitized = validate_and_sanitize_sql(query, default_limit=500)
        self.assertIn("LIMIT 10", sanitized.upper())

    def test_clamps_excessive_user_limit(self):
        """An excessive LIMIT should be capped to the system limit."""
        query = "SELECT * FROM products LIMIT 50000"
        sanitized = validate_and_sanitize_sql(query, default_limit=500)
        self.assertIn("LIMIT 500", sanitized.upper())
        self.assertNotIn("LIMIT 50000", sanitized.upper())

    def test_blocks_drop_table(self):
        """DROP TABLE commands must be blocked immediately."""
        query = "DROP TABLE orders;"
        with self.assertRaises(SQLGuardError) as ctx:
            validate_and_sanitize_sql(query)
        self.assertEqual(ctx.exception.code, "NON_SELECT_ROOT")

    def test_blocks_delete_statement(self):
        """DELETE statements must be blocked."""
        query = "DELETE FROM customers WHERE id = 1"
        with self.assertRaises(SQLGuardError) as ctx:
            validate_and_sanitize_sql(query)
        self.assertEqual(ctx.exception.code, "NON_SELECT_ROOT")

    def test_blocks_update_statement(self):
        """UPDATE statements must be blocked."""
        query = "UPDATE products SET price_cents = 0 WHERE id = 1"
        with self.assertRaises(SQLGuardError) as ctx:
            validate_and_sanitize_sql(query)
        self.assertEqual(ctx.exception.code, "NON_SELECT_ROOT")

    def test_blocks_insert_statement(self):
        """INSERT statements must be blocked."""
        query = "INSERT INTO customers (name, email) VALUES ('Hacker', 'hacked@evil.com')"
        with self.assertRaises(SQLGuardError) as ctx:
            validate_and_sanitize_sql(query)
        self.assertEqual(ctx.exception.code, "NON_SELECT_ROOT")

    def test_blocks_alter_statement(self):
        """ALTER TABLE statements must be blocked."""
        query = "ALTER TABLE customers DROP COLUMN email"
        with self.assertRaises(SQLGuardError) as ctx:
            validate_and_sanitize_sql(query)
        self.assertEqual(ctx.exception.code, "NON_SELECT_ROOT")

    def test_blocks_multi_statement_piggyback_injection(self):
        """Multi-statement execution (e.g. SELECT followed by DROP) must be rejected."""
        query = "SELECT id FROM customers; DROP TABLE orders;"
        with self.assertRaises(SQLGuardError) as ctx:
            validate_and_sanitize_sql(query)
        self.assertEqual(ctx.exception.code, "MULTI_STATEMENT_ATTACK")

    def test_blocks_select_into_and_mutation_nodes(self):
        """SELECT INTO and row locking clauses must be rejected as mutation/locking nodes."""
        mutation_queries = [
            "SELECT * INTO new_table FROM customers;",
            "SELECT id, name FROM customers FOR UPDATE;",
            "SELECT id, name FROM customers FOR SHARE;",
        ]
        for query in mutation_queries:
            with self.subTest(query=query):
                with self.assertRaises(SQLGuardError) as ctx:
                    validate_and_sanitize_sql(query, dialect="postgres")
                self.assertEqual(ctx.exception.code, "MUTATION_NODE_DETECTED")

    def test_blocks_dangerous_functions(self):
        """PostgreSQL dangerous system functions must be rejected."""
        dangerous_queries = [
            "SELECT pg_sleep(10)",
            "SELECT * FROM customers WHERE id = pg_sleep(5)",
            "SELECT pg_read_file('/etc/passwd')",
            "SELECT dblink_exec('dbname=postgres', 'DROP DATABASE test')",
            "SELECT pg_terminate_backend(1234)",
            "SELECT pg_cancel_backend(1234)",
            "SELECT pg_reload_conf()",
            "SELECT lo_export(1234, '/tmp/malicious.bin')",
            "SELECT lo_import('/etc/shadow')",
        ]
        for query in dangerous_queries:
            with self.subTest(query=query):
                with self.assertRaises(SQLGuardError) as ctx:
                    validate_and_sanitize_sql(query)
                self.assertEqual(ctx.exception.code, "FORBIDDEN_FUNCTION")

    def test_empty_query_raises_error(self):
        """Empty queries or whitespace must raise an error."""
        with self.assertRaises(SQLGuardError) as ctx:
            validate_and_sanitize_sql("   ")
        self.assertEqual(ctx.exception.code, "EMPTY_QUERY")


if __name__ == "__main__":
    unittest.main()
