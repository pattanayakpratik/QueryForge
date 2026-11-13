# QueryForge: Autonomous Text-to-SQL & Natural Language BI Engine

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12%2B-blue?logo=python" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi" alt="FastAPI"/>
  <img src="https://img.shields.io/badge/SQLGlot-AST%20Firewall-orange" alt="SQLGlot"/>
  <img src="https://img.shields.io/badge/Groq-LLaMA--3.3--70B-f55036" alt="Groq"/>
  <img src="https://img.shields.io/badge/Gemini-1.5%20Flash-4285F4?logo=google" alt="Gemini"/>
  <img src="https://img.shields.io/badge/Next.js-15%2F16%20App%20Router-black?logo=next.js" alt="Next.js"/>
  <img src="https://img.shields.io/badge/Tailwind-CSS-38B2AC?logo=tailwindcss" alt="Tailwind CSS"/>
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License"/>
</p>

QueryForge is a standalone AI microservice that transforms natural language questions into secure, optimized SQL queries and instant BI dashboards. It eliminates standard Text-to-SQL production failures using **Vector Schema RAG**, a **Deterministic SQLGlot AST Firewall**, **PostgreSQL Cost Gating**, and an **Agentic 3-Step Self-Healing State Machine**.

---

## ⚡ Key Architectural Features

1. **Context Window Optimization via Vector Schema RAG**
   - Automatically introspects database catalogs (`information_schema`) and stores semantic table cards in ChromaDB / pgvector.
   - Dynamically injects only the top-5 relevant table cards and top-3 verified few-shot queries into prompt context, slashing token consumption by 85%.

2. **Deterministic AST Firewall (`sqlglot`)**
   - Parses LLM output into an Abstract Syntax Tree.
   - Enforces strict read-only execution: permits only `exp.Select` or `exp.Union` roots.
   - Blocks dangerous commands (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `GRANT`, `TRUNCATE`).
   - Disallows dangerous functions (`pg_sleep`, `pg_read_file`, `dblink`, etc.).
   - Automatically injects `LIMIT 500` if the generated query lacks row boundaries.

3. **Multi-Provider LLM Router with Instant Failover**
   - Sub-300ms query synthesis using **Groq (LLaMA-3.3-70B-versatile)**.
   - Circuit-breaker with sub-2.5s timeout / 429 / 503 fallback to **Google Gemini 1.5 Flash**.

4. **Self-Healing Execution Loop & Cost Gating**
   - Executes queries within a sandboxed transaction (`SET LOCAL TRANSACTION READ ONLY; SET LOCAL statement_timeout = '5000';`).
   - Dry-runs with `EXPLAIN (FORMAT JSON)`:
     - Catches database errors (`UndefinedColumnError`, `GroupingError`) and feeds the error traceback to the LLM for automatic self-repair (up to 3 attempts).
     - Gated by cost threshold (Total Cost < 50,000) to protect database engines from unindexed sequential scans.

5. **Auto-Visualization & AI Analytics Studio**
   - Detects column types and cardinality to automatically generate Recharts-compatible specs (Bar, Area, Line, KPI cards).
   - Real-time Server-Sent Events (SSE) streaming of agent reasoning steps.

---

## 🏗️ Architecture Flow

```
User Query (Natural Language)
    │
    ▼
FastAPI Gateway & SSE Layer
    │
    ▼
Stage 1: Schema RAG & Golden Few-Shot Retriever (ChromaDB)
    │
    ▼
Stage 2: Self-Healing State Machine (Max 3 Iterations)
    ├── [1] SQL Generator: Groq LLaMA-3.3-70B (Fallback: Gemini 1.5 Flash)
    ├── [2] Deterministic AST Firewall: SQLGlot (LIMIT 500 injection, DDL/DML block)
    └── [3] Cost Gate & Dry-Run: EXPLAIN (FORMAT JSON)
    │
    ▼
Stage 3: Sandboxed Execution & Chart Synthesizer
    │
    ▼
SSE Stream: Telemetry + Formatted SQL + Result Rows + Recharts Config
```

---

## 📁 Repository Structure

```
QueryForge/
├── docs/                        # Architecture specs and project documentation
├── app/
│   ├── main.py                  # FastAPI initialization & lifespan
│   ├── config.py                # Pydantic Settings (Groq, Gemini, DB URLs, Cost caps)
│   ├── database.py              # Internal metadata DB session + Dynamic Target DB pool
│   ├── api/
│   │   ├── datasources.py       # DB registration & schema sync routes
│   │   ├── query.py             # /ask and /stream (SSE) Text-to-SQL endpoints
│   │   ├── golden.py            # Few-shot training pair CRUD
│   │   └── telemetry.py         # Agent performance & self-healing metrics
│   ├── core/
│   │   ├── llm_router.py        # Multi-provider router (Groq -> Gemini fallback)
│   │   ├── schema_indexer.py    # Schema introspection & vector indexing
│   │   ├── sql_guard.py         # SQLGlot AST firewall & LIMIT injection
│   │   ├── agent_loop.py        # Self-healing execution loop & cost gate
│   │   └── chart_synthesizer.py # Auto-detects chart config from result columns
│   ├── models/                  # SQLAlchemy 2.0 metadata models
│   └── schemas/                 # Pydantic v2 schemas
├── scripts/
│   └── seed_demo_ecommerce_db.py# Seeds 5-table SaaS/E-commerce benchmark DB
├── tests/                       # Test suites verifying AST guard, self-healing, etc.
└── dashboard/                   # Next.js 16 AI Analytics Studio UI
```

---

## 🚀 Quick Start

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/pattanayakpratik/QueryForge.git
cd QueryForge

# Using Python 3.12+
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e .
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
# Fill in your GROQ_API_KEY and GEMINI_API_KEY
```

### 3. Run Demo Seed & Tests

```bash
python scripts/seed_demo_ecommerce_db.py
python -m unittest discover -s tests -p "test_*.py"
```

### 4. Start QueryForge Microservice (Backend)

```bash
uvicorn app.main:app --reload --port 8000
```

### 5. Launch AI Analytics Studio (Frontend)

```bash
cd dashboard
npm install
npm run dev
# Open http://localhost:3000 to launch the Studio with 3 recruiter live demo scenarios
```

### 6. Or Run Full Stack with Docker Compose

```bash
docker compose up --build
# Starts PostgreSQL (metadata + demo target), ChromaDB, FastAPI Backend (:8000), and Next.js Studio (:3000)
```

---

## 🛡️ Security & Privacy Design
- **Zero Raw LLM Execution**: Every SQL string passes through AST traversal and rejection filters prior to reaching any database driver.
- **Connection Isolation**: Target connection URIs are stored encrypted.
- **Statement & Cost Guardrails**: Mandatory transaction timeouts and strict read-only modes prevent runaway analytical load.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
