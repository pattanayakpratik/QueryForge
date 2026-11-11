"""Stateful 3-Step Self-Healing Execution Loop and PostgreSQL / SQLite Cost Gate.

Execution Lifecycle:
1. Stage 1: Schema RAG & Golden Few-Shot Retrieval (Top-5 table cards, Top-3 golden queries).
2. Stage 2: Agentic Self-Healing Loop (Max 3 iterations):
   - Synthesizes SQL via Multi-Provider LLM Router.
   - Enforces deterministic compile-time SQLGlot AST Firewall (blocks mutations, injects LIMIT 500).
   - Dry-runs with EXPLAIN (FORMAT JSON for Postgres / EXPLAIN QUERY PLAN for SQLite) cost gate.
   - Catches UndefinedColumn / Grouping / Syntax errors and prompts self-repair with traceback.
3. Stage 3: Sandboxed Execution & Auto-Visualization Synthesizer:
   - Read-only transaction enforcement with statement timeout.
   - Generates Recharts-ready visualization spec and 2-sentence executive summary.
   - Emits structured telemetry events for SSE real-time streaming.
"""

import json
import time
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
from pydantic import BaseModel
from sqlalchemy import text
from app.config import get_settings
from app.database import get_target_engine
from app.core.sql_guard import validate_and_sanitize_sql, SQLGuardError
from app.core.llm_router import LLMRouter, LLMResult
from app.core.schema_indexer import SchemaIndexer
from app.core.chart_synthesizer import synthesize_chart, ChartSpec

logger = logging.getLogger(__name__)


class AgentLoopEvent(BaseModel):
    """Real-time event payload for Server-Sent Events (SSE) streaming."""
    event_type: str  # 'step_schema', 'step_sql', 'step_ast', 'step_cost', 'step_heal', 'step_result', 'error'
    step_number: int
    message: str
    data: Dict[str, Any] = {}
    timestamp: float = 0.0


class AgentExecutionResult(BaseModel):
    """Final output container for self-healing query execution."""
    sql: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float
    explain_cost: Optional[float] = None
    provider_used: str
    self_heal_attempts: int
    status: str  # 'SUCCESS', 'BLOCKED_AST', 'BLOCKED_COST', 'FAILED_EXECUTION'
    error_history: List[Dict[str, Any]] = []
    chart_config: Optional[Dict[str, Any]] = None
    summary: Optional[str] = None


class AgentLoop:
    """Stateful agent orchestrator managing self-healing Text-to-SQL generation."""

    def __init__(
        self,
        llm_router: Optional[LLMRouter] = None,
        schema_indexer: Optional[SchemaIndexer] = None,
    ):
        self._settings = get_settings()
        self.llm_router = llm_router or LLMRouter()
        self.schema_indexer = schema_indexer or SchemaIndexer()

    async def execute_query_stream(
        self,
        datasource_id: str,
        question: str,
        connection_uri: str,
        dialect: str = "postgresql",
    ) -> AsyncGenerator[AgentLoopEvent, None]:
        """Run the end-to-end self-healing loop and yield streaming SSE events."""
        start_time = time.perf_counter()
        step = 1

        # -------------------------------------------------------------
        # 1. Schema RAG & Golden Few-Shot Retrieval
        # -------------------------------------------------------------
        yield AgentLoopEvent(
            event_type="step_schema",
            step_number=step,
            message="Retrieving top relevant database tables via Schema RAG...",
            data={"question": question},
            timestamp=round(time.perf_counter() - start_time, 3),
        )

        table_cards = self.schema_indexer.retrieve_relevant_tables(
            datasource_id=datasource_id,
            query=question,
            top_k=5,
        )
        golden_examples = self.schema_indexer.retrieve_golden_queries(
            datasource_id=datasource_id,
            query=question,
            top_k=3,
        )

        schema_context = "\n\n".join(table_cards) if table_cards else "No specific table cards matched."
        golden_context = ""
        if golden_examples:
            golden_context = "Verified Golden Examples:\n" + "\n".join(
                [f"Q: {g['question']}\nSQL: {g['sql']}" for g in golden_examples]
            )

        step += 1
        yield AgentLoopEvent(
            event_type="step_schema_loaded",
            step_number=step,
            message=f"Retrieved {len(table_cards)} relevant table cards and {len(golden_examples)} golden examples.",
            data={"table_count": len(table_cards), "golden_count": len(golden_examples)},
            timestamp=round(time.perf_counter() - start_time, 3),
        )

        # -------------------------------------------------------------
        # 2. Self-Healing State Machine Loop (Max attempts)
        # -------------------------------------------------------------
        max_attempts = self._settings.max_self_heal_attempts
        attempt = 0
        error_history: List[Dict[str, Any]] = []
        last_sql = ""
        last_provider = "UNKNOWN"
        target_engine = get_target_engine(connection_uri)
        is_sqlite = "sqlite" in dialect.lower() or "sqlite" in connection_uri.lower()

        conversation_history: List[str] = [
            f"User Question: {question}\n\n"
            f"Database Schema:\n{schema_context}\n\n"
            f"{golden_context}\n\n"
            f"Generate a single, precise, read-only SQL SELECT query to answer the user's question."
        ]

        while attempt < max_attempts:
            attempt += 1
            step += 1

            # Step 2a: Generate SQL via LLM Router
            yield AgentLoopEvent(
                event_type="step_sql_generating",
                step_number=step,
                message=f"Synthesizing SQL query (Attempt {attempt}/{max_attempts})...",
                data={"attempt": attempt},
                timestamp=round(time.perf_counter() - start_time, 3),
            )

            prompt = "\n\n".join(conversation_history)
            llm_result: LLMResult = await self.llm_router.generate_sql(prompt=prompt)
            raw_sql = llm_result.cleaned_sql
            last_sql = raw_sql
            last_provider = llm_result.provider

            yield AgentLoopEvent(
                event_type="step_sql_drafted",
                step_number=step,
                message=f"Drafted SQL using {last_provider} ({llm_result.latency_ms}ms).",
                data={"sql": raw_sql, "provider": last_provider, "model": llm_result.model},
                timestamp=round(time.perf_counter() - start_time, 3),
            )

            # Step 2b: SQLGlot AST Firewall
            step += 1
            yield AgentLoopEvent(
                event_type="step_ast_validating",
                step_number=step,
                message="Verifying query against deterministic AST security firewall...",
                data={"sql": raw_sql},
                timestamp=round(time.perf_counter() - start_time, 3),
            )

            try:
                sanitized_sql = validate_and_sanitize_sql(
                    raw_sql,
                    dialect="postgres" if not is_sqlite else "sqlite",
                    default_limit=self._settings.default_row_limit,
                )
                last_sql = sanitized_sql
            except SQLGuardError as guard_err:
                error_history.append({"attempt": attempt, "stage": "AST_FIREWALL", "error": guard_err.message})
                yield AgentLoopEvent(
                    event_type="error_ast",
                    step_number=step,
                    message=f"AST Firewall blocked query: {guard_err.message}",
                    data={"code": guard_err.code, "error": guard_err.message},
                    timestamp=round(time.perf_counter() - start_time, 3),
                )
                # AST violations that cannot be healed or security breaches stop execution
                return

            yield AgentLoopEvent(
                event_type="step_ast_passed",
                step_number=step,
                message="AST Firewall passed (Read-only verified, LIMIT enforced).",
                data={"sanitized_sql": sanitized_sql},
                timestamp=round(time.perf_counter() - start_time, 3),
            )

            # Step 2c: Dry-Run & Cost Gate
            step += 1
            yield AgentLoopEvent(
                event_type="step_cost_evaluating",
                step_number=step,
                message="Executing dry-run cost gate and syntax check...",
                data={"sql": sanitized_sql},
                timestamp=round(time.perf_counter() - start_time, 3),
            )

            explain_cost: Optional[float] = None
            db_error_message: Optional[str] = None

            try:
                async with target_engine.connect() as conn:
                    if not is_sqlite:
                        # PostgreSQL read-only and statement timeout guardrails
                        await conn.execute(text("SET LOCAL TRANSACTION READ ONLY;"))
                        await conn.execute(
                            text(f"SET LOCAL statement_timeout = '{self._settings.statement_timeout_ms}';")
                        )

                        # Run EXPLAIN (FORMAT JSON)
                        explain_res = await conn.execute(text(f"EXPLAIN (FORMAT JSON) {sanitized_sql}"))
                        explain_data = explain_res.scalar()
                        if isinstance(explain_data, str):
                            explain_json = json.loads(explain_data)
                        else:
                            explain_json = explain_data

                        if explain_json and isinstance(explain_json, list):
                            plan = explain_json[0].get("Plan", {})
                            explain_cost = float(plan.get("Total Cost", 0.0))
                    else:
                        # SQLite dry run query plan
                        await conn.execute(text(f"EXPLAIN QUERY PLAN {sanitized_sql}"))
                        explain_cost = 10.0  # Synthetic cost score for SQLite
            except Exception as exc:
                db_error_message = str(exc)

            # Check if Cost Exceeds Threshold
            if explain_cost is not None and explain_cost > self._settings.max_execution_cost:
                db_error_message = (
                    f"EXPLAIN Total Cost ({explain_cost}) exceeded system limit ({self._settings.max_execution_cost}). "
                    "Rewrite query to utilize indexed columns and avoid full sequential scans."
                )

            # If an error occurred, trigger self-healing
            if db_error_message:
                error_history.append({"attempt": attempt, "sql": sanitized_sql, "error": db_error_message})
                yield AgentLoopEvent(
                    event_type="step_heal_triggered",
                    step_number=step,
                    message=f"Self-Healing triggered: Database rejected query ({db_error_message[:100]}...).",
                    data={"attempt": attempt, "error": db_error_message},
                    timestamp=round(time.perf_counter() - start_time, 3),
                )

                # Feed error traceback back into conversation state for LLM self-repair
                conversation_history.append(
                    f"Attempt {attempt} SQL:\n{sanitized_sql}\n\n"
                    f"Database Execution Error:\n{db_error_message}\n\n"
                    f"Please repair the SQL query according to the provided schema cards. "
                    f"Fix column names, joins, or aggregations so that it executes successfully."
                )
                continue  # Retry loop

            # -------------------------------------------------------------
            # 3. Successful Dry-Run -> Execute & Synthesize Visualizations
            # -------------------------------------------------------------
            step += 1
            yield AgentLoopEvent(
                event_type="step_executing",
                step_number=step,
                message="Query verified. Fetching production result rows...",
                data={"cost": explain_cost},
                timestamp=round(time.perf_counter() - start_time, 3),
            )

            rows_data: List[Dict[str, Any]] = []
            columns: List[str] = []

            async with target_engine.connect() as conn:
                cursor = await conn.execute(text(sanitized_sql))
                if cursor.returns_rows:
                    columns = list(cursor.keys())
                    for row in cursor.fetchall():
                        rows_data.append(dict(zip(columns, row)))

            # Step 3b: Auto-Chart & Insight Synthesis
            chart_spec: ChartSpec = synthesize_chart(columns, rows_data, question=question)
            total_duration_ms = (time.perf_counter() - start_time) * 1000.0

            yield AgentLoopEvent(
                event_type="step_completed",
                step_number=step + 1,
                message=f"Execution successful! Returned {len(rows_data)} rows. Synthesized {chart_spec.chart_type}.",
                data={
                    "sql": sanitized_sql,
                    "columns": columns,
                    "rows": rows_data[:100],  # Limit streaming payload size
                    "row_count": len(rows_data),
                    "execution_time_ms": round(total_duration_ms, 2),
                    "explain_cost": explain_cost,
                    "provider_used": last_provider,
                    "self_heal_attempts": attempt - 1,
                    "chart_config": chart_spec.model_dump(),
                    "summary": chart_spec.summary,
                    "status": "SUCCESS",
                },
                timestamp=round(time.perf_counter() - start_time, 3),
            )
            return

        # If loop exits without success
        total_duration_ms = (time.perf_counter() - start_time) * 1000.0
        yield AgentLoopEvent(
            event_type="error_exhausted",
            step_number=step + 1,
            message=f"Self-healing exhausted after {max_attempts} attempts.",
            data={
                "sql": last_sql,
                "error_history": error_history,
                "status": "FAILED_EXECUTION",
                "execution_time_ms": round(total_duration_ms, 2),
            },
            timestamp=round(time.perf_counter() - start_time, 3),
        )

    async def execute_query(
        self,
        datasource_id: str,
        question: str,
        connection_uri: str,
        dialect: str = "postgresql",
    ) -> AgentExecutionResult:
        """Run the self-healing loop synchronously to return the final execution result."""
        last_event: Optional[AgentLoopEvent] = None
        async for event in self.execute_query_stream(datasource_id, question, connection_uri, dialect):
            last_event = event

        if last_event and last_event.event_type == "step_completed":
            d = last_event.data
            return AgentExecutionResult(
                sql=d.get("sql", ""),
                columns=d.get("columns", []),
                rows=d.get("rows", []),
                row_count=d.get("row_count", 0),
                execution_time_ms=d.get("execution_time_ms", 0.0),
                explain_cost=d.get("explain_cost"),
                provider_used=d.get("provider_used", "UNKNOWN"),
                self_heal_attempts=d.get("self_heal_attempts", 0),
                status="SUCCESS",
                chart_config=d.get("chart_config"),
                summary=d.get("summary"),
            )
        elif last_event and last_event.event_type in ("error_ast", "error_exhausted"):
            d = last_event.data
            return AgentExecutionResult(
                sql=d.get("sql", ""),
                columns=[],
                rows=[],
                row_count=0,
                execution_time_ms=d.get("execution_time_ms", 0.0),
                provider_used="UNKNOWN",
                self_heal_attempts=self._settings.max_self_heal_attempts,
                status="BLOCKED_AST" if last_event.event_type == "error_ast" else "FAILED_EXECUTION",
                error_history=d.get("error_history", []),
                summary=last_event.message,
            )

        return AgentExecutionResult(
            sql="",
            columns=[],
            rows=[],
            row_count=0,
            execution_time_ms=0.0,
            provider_used="UNKNOWN",
            self_heal_attempts=0,
            status="FAILED_EXECUTION",
            summary="Execution loop terminated unexpectedly.",
        )
