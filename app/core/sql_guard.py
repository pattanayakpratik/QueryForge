"""SQLGlot AST Firewall & Read-Only Sandbox.

Enforces deterministic compile-time SQL safety:
1. Ensures single-statement execution.
2. Rejects non-query statements (blocks DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, GRANT).
3. Detects and blocks forbidden system functions (pg_sleep, pg_read_file, dblink, etc.).
4. Automatically injects LIMIT 500 when missing to prevent database memory exhaustion.
"""

from typing import Set, Tuple, Optional
import sqlglot
from sqlglot import exp
from app.config import get_settings


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
    "dblink",
    "dblink_exec",
    "query_to_xml",
    "load_extension",
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
)


def validate_and_sanitize_sql(
    sql_text: str,
    dialect: str = "postgres",
    default_limit: Optional[int] = None,
) -> str:
    """Parse, inspect, guardrail, and sanitize an SQL query using SQLGlot AST traversal.

    Args:
        sql_text: Raw SQL query string from LLM or user.
        dialect: SQL dialect for parsing (e.g. 'postgres', 'sqlite').
        default_limit: Row limit to enforce if missing (defaults to settings.default_row_limit).

    Returns:
        Guaranteed read-only, sanitized, limit-enforced SQL query string.

    Raises:
        SQLGuardError: If the statement violates read-only or safety constraints.
    """
    if not sql_text or not sql_text.strip():
        raise SQLGuardError("SQL query is empty or whitespace only.", code="EMPTY_QUERY")

    # Map dialect aliases if needed
    normalized_dialect = "postgres" if dialect in ("postgresql", "asyncpg", "postgres") else dialect

    # 1. Parse SQL statements
    try:
        parsed_statements = sqlglot.parse(sql_text, read=normalized_dialect)
    except Exception as exc:
        raise SQLGuardError(f"SQL parsing syntax error: {str(exc)}", code="SYNTAX_ERROR") from exc

    if not parsed_statements:
        raise SQLGuardError("No valid SQL statements found in input.", code="EMPTY_PARSED_QUERY")

    # 2. Strict single-statement check to block piggybacked queries
    # Filter out empty statements (like trailing semicolons)
    valid_statements = [stmt for stmt in parsed_statements if stmt is not None]
    if len(valid_statements) > 1:
        raise SQLGuardError(
            "Multi-statement execution is blocked by AST firewall.",
            code="MULTI_STATEMENT_ATTACK",
        )

    root_expr = valid_statements[0]

    # 3. Root Node Validation: Must be exp.Select or exp.Union
    # Note: WITH queries (CTEs) in SQLGlot are exp.Select with a `with` argument
    if not isinstance(root_expr, (exp.Select, exp.Union)):
        statement_type = root_expr.__class__.__name__
        raise SQLGuardError(
            f"Blocked operation: Only SELECT or UNION queries are permitted. Found: {statement_type}",
            code="NON_SELECT_ROOT",
        )

    # 4. Deep AST traversal: verify no forbidden AST node types exist anywhere in tree
    for node in root_expr.walk():
        if isinstance(node, FORBIDDEN_NODE_TYPES):
            raise SQLGuardError(
                f"Blocked operation: Forbidden statement or mutation node '{node.__class__.__name__}' detected.",
                code="MUTATION_NODE_DETECTED",
            )

        # 5. Check for dangerous function calls
        if isinstance(node, exp.Func):
            func_name = node.name.lower() if hasattr(node, "name") and node.name else ""
            if func_name in FORBIDDEN_FUNCTIONS:
                raise SQLGuardError(
                    f"Blocked operation: Forbidden system function call '{func_name}()' detected.",
                    code="FORBIDDEN_FUNCTION",
                )
        elif isinstance(node, exp.Anonymous):
            func_name = node.name.lower() if hasattr(node, "name") and node.name else ""
            if func_name in FORBIDDEN_FUNCTIONS:
                raise SQLGuardError(
                    f"Blocked operation: Forbidden system function call '{func_name}()' detected.",
                    code="FORBIDDEN_FUNCTION",
                )

    # 6. Row Limit Enforcement
    settings = get_settings()
    enforce_limit = default_limit if default_limit is not None else settings.default_row_limit

    # Check for LIMIT in Select or Union
    if isinstance(root_expr, exp.Select):
        limit_arg = root_expr.args.get("limit")
        if not limit_arg:
            root_expr = root_expr.limit(enforce_limit)
        else:
            # Check if existing limit exceeds enforce_limit
            try:
                # In SQLGlot, limit_arg.expression may be a literal or expression
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

    # 7. Generate dialect-specific SQL
    try:
        sanitized_sql = root_expr.sql(dialect=normalized_dialect, pretty=True)
    except Exception as exc:
        sanitized_sql = root_expr.sql(pretty=True)

    return sanitized_sql
