"""Auto-Chart & Insight Synthesizer for QueryForge.

Heuristically inspects column datatypes, cardinality, and distributions from query
result sets to dynamically generate Recharts-compliant visualization specifications
and a 2-sentence executive summary.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel


class ChartSpec(BaseModel):
    """Recharts-ready frontend chart configuration specification."""
    chart_type: str  # 'bar_chart', 'area_chart', 'line_chart', 'pie_chart', 'kpi_card', 'table'
    title: str
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    series: List[str] = []
    data: List[Dict[str, Any]] = []
    summary: str


def _is_datetime_value(val: Any) -> bool:
    """Check if value parses as a date or timestamp."""
    if isinstance(val, (datetime,)):
        return True
    if not isinstance(val, str) or len(val) < 4:
        return False
    # Common ISO-8601, YYYY-MM, or YYYY-MM-DD patterns
    if re.match(r"^\d{4}-\d{2}(-\d{2})?([ T]\d{2}:\d{2}(:\d{2})?)?", val):
        return True
    return False


def _is_numeric_value(val: Any) -> bool:
    """Check if value is numeric or numeric string."""
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return True
    if isinstance(val, str):
        try:
            float(val.replace(",", "").strip())
            return True
        except ValueError:
            return False
    return False


def detect_column_types(columns: List[str], rows: List[Dict[str, Any]]) -> Dict[str, str]:
    """Classify columns as 'datetime', 'numeric', or 'categorical'."""
    classified = {}
    sample_size = min(len(rows), 25)

    for col in columns:
        col_lower = col.lower()
        temporal_keywords = ("date", "month", "year", "day", "created_at", "signup_date", "timestamp", "time")
        if any(kw in col_lower for kw in temporal_keywords):
            classified[col] = "datetime"
            continue

        numeric_count = 0
        datetime_count = 0
        valid_samples = 0

        for r in rows[:sample_size]:
            val = r.get(col)
            if val is None:
                continue
            valid_samples += 1
            if _is_datetime_value(val):
                datetime_count += 1
            elif _is_numeric_value(val):
                numeric_count += 1

        if valid_samples > 0 and (datetime_count / valid_samples) >= 0.7:
            classified[col] = "datetime"
        elif valid_samples > 0 and (numeric_count / valid_samples) >= 0.7:
            classified[col] = "numeric"
        else:
            classified[col] = "categorical"

    return classified


def generate_executive_summary(
    columns: List[str],
    rows: List[Dict[str, Any]],
    chart_type: str,
    x_axis: Optional[str] = None,
    y_axis: Optional[str] = None,
) -> str:
    """Generate a clean, professional 2-sentence executive summary of the dataset."""
    if not rows:
        return "Query executed successfully but yielded no rows. Review filter criteria to expand results."

    row_count = len(rows)

    if chart_type == "kpi_card":
        col_name = columns[0]
        val = rows[0].get(col_name)
        formatted_val = f"{val:,}" if isinstance(val, (int, float)) else str(val)
        return (
            f"Key aggregate metric {col_name} evaluated to {formatted_val}. "
            "This reflects the current baseline calculated across all matching database records."
        )

    if chart_type in ("area_chart", "line_chart") and x_axis and y_axis:
        first_date = rows[0].get(x_axis)
        last_date = rows[-1].get(x_axis)
        return (
            f"Observed chronological trend across {row_count} recorded periods from {first_date} through {last_date}. "
            f"The primary metric ({y_axis}) exhibits continuous variation over the observed timeline."
        )

    if chart_type in ("bar_chart", "pie_chart") and x_axis and y_axis:
        try:
            top_record = max(rows, key=lambda r: float(r.get(y_axis, 0) or 0))
            top_label = top_record.get(x_axis)
            top_val = top_record.get(y_axis)
            formatted_top = f"{top_val:,}" if isinstance(top_val, (int, float)) else str(top_val)
            return (
                f"Breakdown across {row_count} unique {x_axis} segments highlights {top_label} as the highest contributor ({formatted_top}). "
                "Distribution patterns provide actionable segmentation signals for operational decision-making."
            )
        except Exception:
            pass

    return (
        f"Query execution aggregated {row_count} rows across {len(columns)} dimensional fields. "
        "Results have been shaped into an interactive data grid with immediate export readiness."
    )


def synthesize_chart(
    columns: List[str],
    rows: List[Dict[str, Any]],
    question: Optional[str] = None,
) -> ChartSpec:
    """Synthesize complete Recharts visualization configuration from result rows."""
    if not rows or not columns:
        return ChartSpec(
            chart_type="table",
            title=question or "Query Results",
            data=[],
            summary="Zero matching records returned for this query.",
        )

    col_types = detect_column_types(columns, rows)
    num_cols = [c for c, t in col_types.items() if t == "numeric"]
    date_cols = [c for c, t in col_types.items() if t == "datetime"]
    cat_cols = [c for c, t in col_types.items() if t == "categorical"]

    # 1. KPI Card: single scalar value or 1 row with 1 numeric metric
    if len(rows) == 1 and (len(columns) == 1 or (len(num_cols) == 1 and len(columns) <= 2)):
        metric_col = num_cols[0] if num_cols else columns[0]
        summary = generate_executive_summary(columns, rows, "kpi_card")
        return ChartSpec(
            chart_type="kpi_card",
            title=question or metric_col.replace("_", " ").title(),
            y_axis=metric_col,
            data=rows,
            summary=summary,
        )

    # 2. Area / Line Chart: 1 datetime column + at least 1 numeric column
    if date_cols and num_cols:
        x_axis = date_cols[0]
        y_axis = num_cols[0]
        summary = generate_executive_summary(columns, rows, "area_chart", x_axis=x_axis, y_axis=y_axis)
        return ChartSpec(
            chart_type="area_chart",
            title=question or f"{y_axis.replace('_', ' ').title()} Over Time",
            x_axis=x_axis,
            y_axis=y_axis,
            series=num_cols[:3],  # Up to 3 metrics
            data=rows,
            summary=summary,
        )

    # 3. Bar Chart: 1 categorical column + 1 numeric column
    if cat_cols and num_cols:
        x_axis = cat_cols[0]
        y_axis = num_cols[0]

        # Use pie chart if 6 or fewer categories and looks like share/proportion
        unique_cats = len({r.get(x_axis) for r in rows})
        chart_type = "pie_chart" if unique_cats <= 6 and ("share" in y_axis.lower() or "pct" in y_axis.lower()) else "bar_chart"

        summary = generate_executive_summary(columns, rows, chart_type, x_axis=x_axis, y_axis=y_axis)
        return ChartSpec(
            chart_type=chart_type,
            title=question or f"{y_axis.replace('_', ' ').title()} by {x_axis.replace('_', ' ').title()}",
            x_axis=x_axis,
            y_axis=y_axis,
            series=[y_axis],
            data=rows,
            summary=summary,
        )

    # 4. Fallback Table
    summary = generate_executive_summary(columns, rows, "table")
    return ChartSpec(
        chart_type="table",
        title=question or "Analytical Result Grid",
        data=rows,
        summary=summary,
    )
