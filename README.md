# TestPilot AI

TestPilot AI is an automated testing platform where an AI agent plans, runs, and reports browser tests from uploaded requirements documents.

## System Prerequisites

- **OS**: Windows 11 (PowerShell)
- **Python**: Python 3.12 managed via `uv` (system Python 3.14 must not be used)
- **Package Manager**: [uv](https://github.com/astral-sh/uv) (v0.12+)
- **Node.js**: Node v24+ and npm
- **Database**: PostgreSQL 18 with `pgvector` extension enabled locally on the `testpilot` database
- **Cache & Queue**: Redis running inside WSL2 Ubuntu, accessible from Windows at `redis://localhost:6379/0`

> **IMPORTANT**: Redis runs in WSL2 and does not start automatically on Windows boot. You must start Redis in your WSL2 terminal before running the backend:
> ```bash
> sudo service redis-server start
> ```

---

## Configuration

1. Copy `.env.example` to `.env` in the repository root:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Populate the required configuration values in `.env` (database connection, Redis URL, secrets).
3. **Security Note**: Never commit `.env` or paste secrets into version control. `.env` is ignored by `.gitignore`.

---

## Backend Setup & Run Commands

All backend commands must be run from the `backend/` directory using PowerShell:

```powershell
cd backend

# 1. Sync dependencies and create the virtual environment (Python 3.12)
uv sync

# 2. Verify Python version is 3.12.x
uv run python --version

# 3. Apply database migrations (ensures pgvector extension exists)
uv run alembic upgrade head

# 4. Start the FastAPI development server
uv run uvicorn app.main:app --reload --port 8000
```

The API will be available at:
- **API Root**: [http://localhost:8000](http://localhost:8000)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **Interactive OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### Backend Testing and Linting

```powershell
cd backend

# Run Phase 1 test suite
uv run pytest -v

# Run linter
uv run ruff check .
```

---

## Frontend Setup & Run Commands

Run from the `frontend/` directory using PowerShell:

```powershell
cd frontend

# 1. Install dependencies
npm.cmd install

# 2. Start the Vite development server
npm.cmd run dev
```

The frontend will be available at [http://localhost:5173](http://localhost:5173).

---

## Verification & Health Check

The `GET /health` endpoint inspects live connectivity to both PostgreSQL (checking pgvector status) and Redis:

```json
{
  "status": "ok",
  "api": "ok",
  "database": {
    "status": "healthy",
    "pgvector_enabled": true
  },
  "redis": {
    "status": "healthy"
  }
}
```

If either dependency is unreachable, the endpoint returns `"status": "degraded"` with details of the affected component without crashing.
