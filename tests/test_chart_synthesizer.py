"""Unit tests for Auto-Chart and Insight Synthesizer."""

import unittest
from app.core.chart_synthesizer import (
    synthesize_chart,
    detect_column_types,
    generate_executive_summary,
)


class TestChartSynthesizer(unittest.TestCase):
    """Unit tests verifying heuristic chart generation and insight summaries."""

    def test_kpi_card_detection(self):
        """Single row with single numeric column should generate a kpi_card."""
        columns = ["total_revenue_cents"]
        rows = [{"total_revenue_cents": 1250000}]
        spec = synthesize_chart(columns, rows, question="What is total revenue?")

        self.assertEqual(spec.chart_type, "kpi_card")
        self.assertEqual(spec.y_axis, "total_revenue_cents")
        self.assertIn("evaluated to", spec.summary)

    def test_area_chart_chronological_trend(self):
        """Datetime column combined with numeric metric should synthesize area_chart."""
        columns = ["signup_month", "active_users", "revenue"]
        rows = [
            {"signup_month": "2026-01-01", "active_users": 100, "revenue": 5000},
            {"signup_month": "2026-02-01", "active_users": 150, "revenue": 7500},
            {"signup_month": "2026-03-01", "active_users": 210, "revenue": 11000},
        ]
        spec = synthesize_chart(columns, rows, question="Monthly user growth")

        self.assertEqual(spec.chart_type, "area_chart")
        self.assertEqual(spec.x_axis, "signup_month")
        self.assertEqual(spec.y_axis, "active_users")
        self.assertIn("active_users", spec.series)
        self.assertIn("revenue", spec.series)
        self.assertIn("chronological trend", spec.summary)

    def test_bar_chart_categorical_breakdown(self):
        """Categorical dimension with numeric metric should synthesize bar_chart."""
        columns = ["country", "total_orders"]
        rows = [
            {"country": "US", "total_orders": 85},
            {"country": "UK", "total_orders": 42},
            {"country": "DE", "total_orders": 39},
            {"country": "CA", "total_orders": 28},
        ]
        spec = synthesize_chart(columns, rows, question="Orders by country")

        self.assertEqual(spec.chart_type, "bar_chart")
        self.assertEqual(spec.x_axis, "country")
        self.assertEqual(spec.y_axis, "total_orders")
        self.assertIn("US", spec.summary)
        self.assertIn("highest contributor", spec.summary)

    def test_pie_chart_proportions(self):
        """Small categorical set with share/pct indicator should synthesize pie_chart."""
        columns = ["status", "refund_pct"]
        rows = [
            {"status": "completed", "refund_pct": 82.5},
            {"status": "refunded", "refund_pct": 17.5},
        ]
        spec = synthesize_chart(columns, rows)
        self.assertEqual(spec.chart_type, "pie_chart")

    def test_empty_results_fallback(self):
        """Empty result lists should cleanly fallback to table mode."""
        spec = synthesize_chart(["id", "name"], [])
        self.assertEqual(spec.chart_type, "table")
        self.assertEqual(len(spec.data), 0)
        self.assertIn("Zero matching records", spec.summary)

    def test_column_type_detection(self):
        """detect_column_types correctly categorizes dates, numbers, and strings."""
        columns = ["created_at", "total_amount", "customer_name"]
        rows = [
            {"created_at": "2026-04-12T10:00:00", "total_amount": 99.95, "customer_name": "Alice"},
            {"created_at": "2026-04-13T12:00:00", "total_amount": 149.50, "customer_name": "Bob"},
        ]
        types = detect_column_types(columns, rows)
        self.assertEqual(types["created_at"], "datetime")
        self.assertEqual(types["total_amount"], "numeric")
        self.assertEqual(types["customer_name"], "categorical")


if __name__ == "__main__":
    unittest.main()
