# TestPilot AI — Backend API & Worker Subsystem

The backend subsystem of **TestPilot AI** is built with **FastAPI**, **SQLAlchemy 2.0 Async**, **PostgreSQL 18** with `pgvector`, and **arq** (Redis job queue).

---

## Directory Architecture

```
backend/
├── app/
│   ├── agent/                 # LangGraph Agent State Machine
│   │   ├── graph.py           # State machine graph nodes & edge conditions
│   │   ├── preflight.py       # Fast connectivity & MCP handshake checks
│   │   ├── planner.py         # RAG retrieval & test scenario prompt synthesis
│   │   ├── executor.py        # Playwright MCP browser action execution loop
│   │   ├── negative_check.py  # Deterministic prohibited action verification
│   │   └── analyst.py         # Failure classification & requirement citations
│   ├── api/                   # REST API Endpoints
│   │   ├── auth.py            # User registration, login, logout, current user
│   │   ├── projects.py        # Project CRUD, target URL validation, credential crypto
│   │   ├── documents.py       # Requirements upload, PDF/TXT/MD extraction, vector indexing
│   │   └── runs.py            # Start run, live polling, report JSON, authenticated screenshots
│   ├── core/                  # Settings, async database session factory, Redis client
│   ├── models/                # SQLAlchemy ORM models (User, Project, TestRun, TestCase, etc.)
│   ├── services/              # Screenshot storage, credential encryption, token handling
│   └── worker.py              # arq background worker process running the LangGraph agent
├── migrations/                # Alembic migration scripts
├── scripts/                   # Evaluation and diagnostic tools (review_run.py, seed_demo.py)
└── tests/                     # 173 pytest unit and integration tests
```

---

## Database Migrations

```bash
# Apply migrations to head
uv run alembic upgrade head

# Generate a new migration
uv run alembic revision --autogenerate -m "describe change"
```

---

## Running the Backend

```bash
# Start FastAPI Web Server on port 8000
uv run uvicorn app.main:app --port 8000

# Start arq Background Agent Worker
uv run python -m app.worker
```

---

## Running Pytest Suites

```bash
# Run unit & integration tests (excluding live eval)
uv run pytest -m "not eval"

# Run single test file
uv run pytest tests/test_agent_foundation.py
```
