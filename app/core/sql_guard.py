"""SQLGlot AST Firewall & Read-Only Sandbox.

Enforces deterministic compile-time SQL safety:
1. Ensures single-statement execution.
2. Rejects non-query statements (blocks DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, GRANT).
3. Detects and blocks forbidden system functions (pg_sleep, pg_read_file, dblink, etc.).
4. Automatically injects LIMIT 500 when missing to prevent database memory exhaustion.
"""

from typing import Set, Tuple, Optional, List, Dict, Any
from pydantic import BaseModel
import sqlglot
from sqlglot import exp
from app.config import get_settings


class MutationImpact(BaseModel):
    """Structured assessment of what a write query does and what is affected."""
    action_type: str  # 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', etc.
    target_tables: List[str] = []
    affected_columns: List[str] = []
    has_where_clause: bool = True
    where_clause_preview: Optional[str] = None
    risk_level: str = "MEDIUM"  # 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    description: str = ""
    estimated_affected_rows: Optional[int] = None


class SQLGuardError(Exception):
    """Exception raised when an SQL query violates the AST security firewall."""

    def __init__(self, message: str, code: str = "SECURITY_VIOLATION"):
        super().__init__(message)
        self.message = message
        self.code = code


# Set of prohibited system functions and execution vectors
FORBIDDEN_FUNCTIONS: Set[str] = {
    "pg_sleep",
    "pg_read_file",
    "pg_read_binary_file",
    "pg_write_file",
    "pg_write_binary_file",
    "pg_ls_dir",
    "pg_stat_file",
    "pg_terminate_backend",
    "pg_cancel_backend",
    "pg_reload_conf",
    "pg_rotate_logfile",
    "dblink",
    "dblink_exec",
    "query_to_xml",
    "query_to_xml_and_xmlschema",
    "cursor_to_xml",
    "lo_export",
    "lo_import",
    "lo_unlink",
    "lo_open",
    "lo_close",
    "load_extension",
    "readfile",
    "writefile",
    "edit",
    "system",
    "exec",
    "eval",
}

# Prohibited AST node types that indicate mutation or administrative operations
FORBIDDEN_NODE_TYPES: Tuple[type, ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Command,
    exp.Pragma,
    exp.Set,
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Into,
    exp.Lock,
    exp.Merge,
    exp.Copy,
)


def analyze_write_impact(root_expr: exp.Expression, dialect: str = "postgres") -> MutationImpact:
    """Analyze a write statement AST to detail affected tables, columns, risk, and user explanation."""
    action_type = root_expr.__class__.__name__.upper()
    tables = list(dict.fromkeys(t.name for t in root_expr.find_all(exp.Table) if t.name))

    where_arg = root_expr.args.get("where")
    has_where = where_arg is not None
    where_preview = where_arg.sql(dialect=dialect) if where_arg else None

    affected_cols: List[str] = []
    if isinstance(root_expr, exp.Update):
        for eq in root_expr.find_all(exp.EQ):
            if hasattr(eq.this, "name") and eq.this.name:
                affected_cols.append(eq.this.name)
    elif isinstance(root_expr, exp.Insert):
        for col in root_expr.find_all(exp.Column):
            if hasattr(col, "name") and col.name:
                affected_cols.append(col.name)
    affected_cols = list(dict.fromkeys(affected_cols))

    # Determine risk level and human-facing description
    if isinstance(root_expr, exp.Drop) or action_type in ("DROP", "TRUNCATE"):
        risk_level = "CRITICAL"
        description = (
            f"CRITICAL HAZARD: Will permanently {action_type} table(s) [{', '.join(tables)}]. "
            "This will permanently erase all associated data and schema definition."
        )
    elif isinstance(root_expr, exp.Delete):
        if not has_where:
            risk_level = "CRITICAL"
            description = (
                f"CRITICAL HAZARD: Deleting ALL records from table '{', '.join(tables)}' without any WHERE filter!"
            )
        else:
            risk_level = "HIGH"
            description = (
                f"Will permanently delete matching records from table '{', '.join(tables)}' "
                f"matching filter: {where_preview}."
            )
    elif isinstance(root_expr, exp.Update):
        if not has_where:
            risk_level = "CRITICAL"
            description = (
                f"CRITICAL HAZARD: Updating column(s) [{', '.join(affected_cols)}] across ALL rows in "
                f"'{', '.join(tables)}' without a WHERE filter!"
            )
        else:
            risk_level = "MEDIUM"
            description = (
                f"Will update column(s) [{', '.join(affected_cols)}] in table '{', '.join(tables)}' "
                f"for records matching: {where_preview}."
            )
    elif isinstance(root_expr, exp.Insert):
        risk_level = "LOW"
        description = f"Will insert new row(s) into table '{', '.join(tables)}'."
    elif isinstance(root_expr, exp.Create):
        risk_level = "LOW"
        description = f"Will create new database structure/table '{', '.join(tables)}'."
    elif isinstance(root_expr, exp.Alter):
        risk_level = "HIGH"
        description = f"Will alter schema structure of table(s) [{', '.join(tables)}]."
    else:
        risk_level = "MEDIUM"
        description = f"Will execute {action_type} on table(s) [{', '.join(tables)}]."

    return MutationImpact(
        action_type=action_type,
        target_tables=tables,
        affected_columns=affected_cols,
        has_where_clause=has_where,
        where_clause_preview=where_preview,
        risk_level=risk_level,
        description=description,
    )


def inspect_and_sanitize_sql(
    sql_text: str,
    dialect: str = "postgres",
    default_limit: Optional[int] = None,
    mode: str = "read_only",
) -> Tuple[str, str, Optional[MutationImpact]]:
    """Inspect and sanitize SQL query, distinguishing READ from WRITE statements.

    Args:
        sql_text: Raw SQL query string from LLM or user.
        dialect: SQL dialect for parsing.
        default_limit: Row limit to enforce on SELECT queries.
        mode: 'read_only' (rejects mutations) or 'read_write' (inspects and prepares impact).

    Returns:
        Tuple of (sanitized_sql, statement_class, mutation_impact)
        - statement_class is 'READ' or 'WRITE'.
        - mutation_impact is populated only when statement_class == 'WRITE'.

    Raises:
        SQLGuardError: If syntax is invalid, multi-statement attack detected,
                       forbidden system functions called, or a write is attempted in read_only mode.
    """
    if not sql_text or not sql_text.strip():
        raise SQLGuardError("SQL query is empty or whitespace only.", code="EMPTY_QUERY")

    normalized_dialect = "postgres" if dialect in ("postgresql", "asyncpg", "postgres") else dialect

    # 1. Parse SQL statement
    try:
        parsed_statements = sqlglot.parse(sql_text, read=normalized_dialect)
    except Exception as exc:
        raise SQLGuardError(f"SQL parsing syntax error: {str(exc)}", code="SYNTAX_ERROR") from exc

    if not parsed_statements:
        raise SQLGuardError("No valid SQL statements found in input.", code="EMPTY_PARSED_QUERY")

    # 2. Strict single-statement check to block piggybacked queries
    valid_statements = [stmt for stmt in parsed_statements if stmt is not None]
    if len(valid_statements) > 1:
        raise SQLGuardError(
            "Multi-statement execution is blocked by AST firewall.",
            code="MULTI_STATEMENT_ATTACK",
        )

    root_expr = valid_statements[0]

    # 3. Check for dangerous administrative and exploit functions (blocked in ALL modes)
    for node in root_expr.walk():
        if isinstance(node, (exp.Func, exp.Anonymous)):
            func_name = node.name.lower() if hasattr(node, "name") and node.name else ""
            if func_name in FORBIDDEN_FUNCTIONS:
                raise SQLGuardError(
                    f"Blocked operation: Forbidden system function call '{func_name}()' detected.",
                    code="FORBIDDEN_FUNCTION",
                )

    # 4. Classify as READ or WRITE
    is_read = isinstance(root_expr, (exp.Select, exp.Union))

    if is_read:
        # Check that no mutation nodes were snuck in (e.g. SELECT INTO)
        for node in root_expr.walk():
            if isinstance(node, FORBIDDEN_NODE_TYPES):
                raise SQLGuardError(
                    f"Blocked operation: Forbidden mutation node '{node.__class__.__name__}' detected.",
                    code="MUTATION_NODE_DETECTED",
                )

        # Enforce row limit
        settings = get_settings()
        enforce_limit = default_limit if default_limit is not None else settings.default_row_limit

        if isinstance(root_expr, exp.Select):
            limit_arg = root_expr.args.get("limit")
            if not limit_arg:
                root_expr = root_expr.limit(enforce_limit)
            else:
                try:
                    current_limit_val = int(limit_arg.expression.this)
                    if current_limit_val > enforce_limit:
                        root_expr.set("limit", None)
                        root_expr = root_expr.limit(enforce_limit)
                except Exception:
                    pass
        elif isinstance(root_expr, exp.Union):
            limit_arg = root_expr.args.get("limit")
            if not limit_arg:
                root_expr = root_expr.limit(enforce_limit)

        try:
            sanitized_sql = root_expr.sql(dialect=normalized_dialect, pretty=True)
        except Exception:
            sanitized_sql = root_expr.sql(pretty=True)

        return sanitized_sql, "READ", None

    # Statement is a WRITE mutation
    if mode == "read_only":
        statement_type = root_expr.__class__.__name__
        raise SQLGuardError(
            f"Blocked operation: Only SELECT or UNION queries are permitted. Found: {statement_type}",
            code="NON_SELECT_ROOT",
        )

    # Mode is read_write: Analyze mutation impact
    impact = analyze_write_impact(root_expr, dialect=normalized_dialect)
    try:
        sanitized_sql = root_expr.sql(dialect=normalized_dialect, pretty=True)
    except Exception:
        sanitized_sql = root_expr.sql(pretty=True)

    return sanitized_sql, "WRITE", impact


def validate_and_sanitize_sql(
    sql_text: str,
    dialect: str = "postgres",
    default_limit: Optional[int] = None,
    mode: str = "read_only",
) -> str:
    """Parse, inspect, guardrail, and sanitize an SQL query using SQLGlot AST traversal.

    Maintains 100% backward compatibility for existing callers.
    """
    sanitized_sql, _, _ = inspect_and_sanitize_sql(
        sql_text=sql_text,
        dialect=dialect,
        default_limit=default_limit,
        mode=mode,
    )
    return sanitized_sql
