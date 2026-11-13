"""Dynamic Schema Introspection & Vector RAG.

Introspects target database catalogs (PostgreSQL information_schema or SQLite PRAGMAs),
generates semantic markdown table cards with column types, foreign key relationships,
and distinct sample values for categorical columns, and indexes them in ChromaDB.
"""

import os
import math
import logging
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from sqlalchemy import text
from app.config import get_settings
from app.database import get_target_engine

logger = logging.getLogger(__name__)


SAFE_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class ColumnMetadata(BaseModel):
    """Metadata describing a single table column."""
    name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    foreign_key_target: Optional[str] = None  # e.g. "customers.id"
    sample_values: List[str] = []


class TableMetadata(BaseModel):
    """Semantic card representation of an introspected database table."""
    table_name: str
    columns: List[ColumnMetadata] = []
    foreign_keys: List[Dict[str, str]] = []  # e.g. [{"from": "customer_id", "to": "customers.id"}]
    markdown_card: str = ""


class FastEmbeddingFunction:
    """Lightweight, deterministic hashing vector embedding for sub-millisecond offline schema RAG."""

    def name(self) -> str:
        return "fast_hashing_embedding"

    def __call__(self, input: List[str]) -> List[List[float]]:
        results = []
        for doc in input:
            vec = [0.0] * 64
            words = re.findall(r"\w+", doc.lower())
            for word in words:
                idx = abs(hash(word)) % 64
                vec[idx] += 1.0
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            results.append([x / norm for x in vec])
        return results


class SchemaIndexer:
    """Manages schema introspection, markdown card compilation, and vector retrieval."""

    def __init__(self, persist_dir: Optional[str] = None):
        settings = get_settings()
        self.persist_dir = persist_dir or settings.chroma_persist_directory
        self._in_memory_cards: Dict[str, Dict[str, TableMetadata]] = {}
        self._golden_queries: Dict[str, List[Dict[str, str]]] = {}
        self._embedding_function = FastEmbeddingFunction()
        self._chroma_client = None
        self._init_chroma()

    def _init_chroma(self) -> None:
        """Attempt to initialize persistent ChromaDB client."""
        try:
            import chromadb
            os.makedirs(self.persist_dir, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=self.persist_dir)
        except Exception as exc:
            logger.warning(f"ChromaDB persistent client unavailable ({exc}); using in-memory semantic fallback.")
            self._chroma_client = None

    async def introspect_target_schema(
        self,
        connection_uri: str,
        dialect: str = "postgresql",
    ) -> List[TableMetadata]:
        """Query schema catalog from target engine and return structured table metadata."""
        engine = get_target_engine(connection_uri)
        tables: List[TableMetadata] = []

        is_sqlite = "sqlite" in dialect.lower() or "sqlite" in connection_uri.lower()

        async with engine.connect() as conn:
            if is_sqlite:
                tables = await self._introspect_sqlite(conn)
            else:
                tables = await self._introspect_postgres(conn)

            # Sample categorical column distinct values
            for tbl in tables:
                await self._sample_distinct_values(conn, tbl)
                tbl.markdown_card = self._build_markdown_card(tbl)

        return tables

    async def _introspect_sqlite(self, conn: Any) -> List[TableMetadata]:
        """Introspect SQLite tables, columns, and foreign keys."""
        tables_res = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        )
        table_names = [row[0] for row in tables_res.fetchall()]
        tables: List[TableMetadata] = []

        for name in table_names:
            clean_name = name.replace("'", "''")
            # Columns via PRAGMA table_info
            cols_res = await conn.execute(text(f"PRAGMA table_info('{clean_name}')"))
            # cid, name, type, notnull, dflt_value, pk
            cols_data = cols_res.fetchall()

            # Foreign keys via PRAGMA foreign_key_list
            fk_res = await conn.execute(text(f"PRAGMA foreign_key_list('{clean_name}')"))
            # id, seq, table, from, to, on_update, on_delete, match
            fk_data = fk_res.fetchall()

            fk_map = {}
            fks_list = []
            for fk in fk_data:
                fk_from = fk[3]
                fk_to = f"{fk[2]}.{fk[4]}"
                fk_map[fk_from] = fk_to
                fks_list.append({"from": fk_from, "to": fk_to})

            col_metas = []
            for col in cols_data:
                c_name = col[1]
                c_type = col[2] or "TEXT"
                is_pk = bool(col[5])
                is_null = not bool(col[3])
                fk_target = fk_map.get(c_name)

                col_metas.append(
                    ColumnMetadata(
                        name=c_name,
                        data_type=c_type.upper(),
                        is_nullable=is_null,
                        is_primary_key=is_pk,
                        foreign_key_target=fk_target,
                    )
                )

            tables.append(TableMetadata(table_name=name, columns=col_metas, foreign_keys=fks_list))

        return tables

    async def _introspect_postgres(self, conn: Any) -> List[TableMetadata]:
        """Introspect PostgreSQL information_schema."""
        tables_res = await conn.execute(
            text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        )
        table_names = [row[0] for row in tables_res.fetchall()]
        tables: List[TableMetadata] = []

        for name in table_names:
            # Columns
            cols_res = await conn.execute(
                text(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = :t_name
                    ORDER BY ordinal_position
                    """
                ),
                {"t_name": name},
            )
            cols_data = cols_res.fetchall()

            # Primary keys
            pk_res = await conn.execute(
                text(
                    """
                    SELECT kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                      AND tc.table_schema = 'public'
                      AND tc.table_name = :t_name
                    """
                ),
                {"t_name": name},
            )
            pk_cols = {row[0] for row in pk_res.fetchall()}

            # Foreign keys
            fk_res = await conn.execute(
                text(
                    """
                    SELECT kcu.column_name, ccu.table_name, ccu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                      ON tc.constraint_name = kcu.constraint_name
                    JOIN information_schema.constraint_column_usage ccu
                      ON ccu.constraint_name = tc.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_schema = 'public'
                      AND tc.table_name = :t_name
                    """
                ),
                {"t_name": name},
            )
            fks = []
            fk_map = {}
            for row in fk_res.fetchall():
                from_col, target_tbl, target_col = row[0], row[1], row[2]
                target_full = f"{target_tbl}.{target_col}"
                fk_map[from_col] = target_full
                fks.append({"from": from_col, "to": target_full})

            col_metas = []
            for col in cols_data:
                c_name, c_type, is_null = col[0], col[1], (col[2].upper() == "YES")
                col_metas.append(
                    ColumnMetadata(
                        name=c_name,
                        data_type=c_type.upper(),
                        is_nullable=is_null,
                        is_primary_key=(c_name in pk_cols),
                        foreign_key_target=fk_map.get(c_name),
                    )
                )

            tables.append(TableMetadata(table_name=name, columns=col_metas, foreign_keys=fks))

        return tables

    async def _sample_distinct_values(self, conn: Any, table: TableMetadata) -> None:
        """Sample distinct values for categorical and low-cardinality columns with sanitized identifiers."""
        if not SAFE_IDENTIFIER_PATTERN.match(table.table_name):
            return

        for col in table.columns:
            # Sample only for string/varchar/enum columns that aren't primary keys
            is_string_type = any(t in col.data_type for t in ("CHAR", "TEXT", "STRING", "VARCHAR"))
            if is_string_type and not col.is_primary_key and "id" not in col.name.lower():
                if not SAFE_IDENTIFIER_PATTERN.match(col.name):
                    continue

                try:
                    q = f'SELECT DISTINCT "{col.name}" FROM "{table.table_name}" WHERE "{col.name}" IS NOT NULL LIMIT 3'
                    res = await conn.execute(text(q))
                    samples = [str(r[0]) for r in res.fetchall() if r[0] is not None]
                    col.sample_values = samples
                except Exception:
                    pass

    def _build_markdown_card(self, table: TableMetadata) -> str:
        """Format table schema as a semantic markdown card."""
        lines = [f"### Table: `{table.table_name}`", "Columns:"]
        for c in table.columns:
            details = [c.data_type]
            if c.is_primary_key:
                details.append("PRIMARY KEY")
            if c.foreign_key_target:
                details.append(f"FOREIGN KEY -> {c.foreign_key_target}")
            if c.sample_values:
                samples_repr = ", ".join(repr(v) for v in c.sample_values)
                details.append(f"Sample values: [{samples_repr}]")

            lines.append(f"- `{c.name}` ({', '.join(details)})")

        if table.foreign_keys:
            lines.append("Relationships:")
            for fk in table.foreign_keys:
                lines.append(f"- `{fk['from']}` links to `{fk['to']}`")

        return "\n".join(lines)

    async def index_datasource(
        self,
        datasource_id: str,
        connection_uri: str,
        dialect: str = "postgresql",
    ) -> int:
        """Introspect target database and index cards into ChromaDB."""
        tables = await self.introspect_target_schema(connection_uri, dialect)

        # In-memory store
        self._in_memory_cards[datasource_id] = {t.table_name: t for t in tables}

        # Index in ChromaDB if available
        if self._chroma_client:
            try:
                collection_name = f"ds_{datasource_id.replace('-', '_')}"
                try:
                    collection = self._chroma_client.get_or_create_collection(
                        name=collection_name,
                        embedding_function=self._embedding_function,
                    )
                except Exception:
                    # Reset collection if schema/embedding function changed
                    try:
                        self._chroma_client.delete_collection(name=collection_name)
                    except Exception:
                        pass
                    collection = self._chroma_client.create_collection(
                        name=collection_name,
                        embedding_function=self._embedding_function,
                    )

                # Upsert table cards
                ids = [f"tbl_{t.table_name}" for t in tables]
                documents = [t.markdown_card for t in tables]
                metadatas = [{"table_name": t.table_name} for t in tables]

                collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas,
                )
            except Exception as exc:
                logger.warning(f"Failed to index in ChromaDB ({exc}); relying on in-memory store.")

        return len(tables)

    def retrieve_relevant_tables(
        self,
        datasource_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[str]:
        """Retrieve top-k relevant table markdown cards for a natural language question."""
        # 1. Try ChromaDB
        if self._chroma_client:
            try:
                collection_name = f"ds_{datasource_id.replace('-', '_')}"
                collection = self._chroma_client.get_collection(
                    name=collection_name,
                    embedding_function=self._embedding_function,
                )
                results = collection.query(query_texts=[query], n_results=top_k)
                docs = results.get("documents", [[]])[0]
                if docs:
                    return docs
            except Exception:
                pass

        # 2. In-memory semantic keyword scoring fallback
        cards_dict = self._in_memory_cards.get(datasource_id, {})
        if not cards_dict:
            return []

        query_tokens = set(re.findall(r"\w+", query.lower()))

        scored_tables = []
        for tbl_name, tbl_meta in cards_dict.items():
            card_text = tbl_meta.markdown_card.lower()
            card_tokens = set(re.findall(r"\w+", card_text))
            intersection = query_tokens.intersection(card_tokens)
            score = len(intersection)
            # Bonus if table name is in query
            if tbl_name.lower() in query.lower():
                score += 5
            scored_tables.append((score, tbl_meta.markdown_card))

        scored_tables.sort(key=lambda x: x[0], reverse=True)
        return [card for _, card in scored_tables[:top_k]]

    def save_golden_query(self, datasource_id: str, question: str, sql: str) -> None:
        """Store verified golden query for few-shot schema RAG."""
        if datasource_id not in self._golden_queries:
            self._golden_queries[datasource_id] = []
        self._golden_queries[datasource_id].append({"question": question, "sql": sql})

    def retrieve_golden_queries(
        self,
        datasource_id: str,
        query: str,
        top_k: int = 3,
    ) -> List[Dict[str, str]]:
        """Retrieve top verified question-SQL pairs matching query."""
        all_pairs = self._golden_queries.get(datasource_id, [])
        if not all_pairs:
            return []

        query_tokens = set(re.findall(r"\w+", query.lower()))
        scored = []
        for pair in all_pairs:
            p_tokens = set(re.findall(r"\w+", pair["question"].lower()))
            overlap = len(query_tokens.intersection(p_tokens))
            scored.append((overlap, pair))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:top_k]]

    def get_indexed_table_names(self, datasource_id: str) -> List[str]:
        """Return list of indexed table names for a datasource."""
        return list(self._in_memory_cards.get(datasource_id, {}).keys())
