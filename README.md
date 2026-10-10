# TestPilot AI

TestPilot AI is an automated web application testing platform powered by autonomous AI agents. Upload your software requirements specification, provide target web application credentials, and TestPilot AI plans comprehensive test scenarios, executes them in a real browser via Playwright, analyzes results, classifies product bugs vs test failures, captures screenshot evidence, and produces actionable interactive reports.

---

## Architecture Overview

```
                      +-----------------------------+
                      |   TestPilot Frontend (SPA)  |
                      |   React 19 + Tailwind CSS   |
                      |      Vite (Port 5173)       |
                      +--------------+--------------+
                                     | REST / JSON
                                     v
                      +-----------------------------+
                      |     FastAPI Backend API     |
                      |    (Uvicorn - Port 8000)    |
                      +-------+--------------+------+
                              |              |
                Redis Pub/Sub |              | SQLAlchemy Async
                & Token Limit |              | Asyncpg + pgvector
                              v              v
                      +---------------+  +---------------------+
                      |  Redis Server |  | PostgreSQL Database |
                      | (WSL2: 6379)  |  |  (Postgres 18: 5432)|
                      +---------------+  +---------------------+
                              ^
                              | Job Queue
                              v
                      +-----------------------------+
                      |  Autonomous Agent Worker    |
                      |  LangGraph Agent Pipeline   |
                      |  - Plan: Gemini Flash Lite  |
                      |  - Exec: Playwright Browser |
                      |  - Analysis: LLM Evaluator  |
                      +--------------+--------------+
                                     | Browser Automation
                                     v
                      +-----------------------------+
                      | Target App: SupportDesk CRM |
                      |    FastAPI (Port 8001)      |
                      +-----------------------------+
```

---

## Prerequisites (Windows 11)

- **OS**: Windows 11 (PowerShell)
- **Python**: Python 3.12 managed via `uv` (Astral `uv` v0.12+)
- **Node.js**: Node v20+ / v24+ and `npm`
- **Database**: PostgreSQL 18 with `pgvector` extension enabled locally on `testpilot` and `testpilot_test` databases
- **Cache & Queue**: Redis running inside WSL2 Ubuntu, reachable at `redis://localhost:6379/0`
- **Browser Automation**: Playwright Chromium binaries installed (`uv run playwright install chromium`)

> [!IMPORTANT]
> **Redis in WSL2**: Redis does not start automatically on Windows boot. Start Redis inside your WSL2 terminal before launching the backend:
> ```bash
> sudo service redis-server start
> ```

---

## Quick Start / Launching TestPilot AI

### 1. Environment Configuration

Copy `.env.example` to `.env` in the repository root:
```powershell
Copy-Item .env.example .env
```
Ensure your database credentials, Redis URL, encryption keys, and Google AI Studio API key (`GEMINI_API_KEY`) are populated.

### 2. Database Migrations & Demo Seeding

Run Alembic migrations to create all database tables and extensions:
```powershell
cd backend
uv run alembic upgrade head
```

Seed the demo environment with the pre-built SupportDesk project, test requirements, and encrypted agent credentials:
```powershell
uv run python scripts/seed_demo.py
```
This creates:
- **Demo User**: `demo@testpilot.ai` / `DemoPassword123!`
- **Demo Project**: SupportDesk (target URL from `SUPPORTDESK_URL`)
- **Credentials**: Encrypted Admin and Agent credentials loaded directly from root `.env`
- **Requirements Knowledge**: Indexed chunks from `SUPPORTDESK_REQUIREMENTS.md` in pgvector

### Reseeding SupportDesk & Synchronizing Target Credentials

When updating credentials in `.env` or resetting the demo application to a clean state, follow this exact sequence:

1. **Stop SupportDesk**: Stop any running process serving SupportDesk on port 8001.
2. **Reseed SupportDesk Database**:
   ```powershell
   cd supportdesk
   uv run python reseed.py
   ```
3. **Update Stored Demo Credentials**:
   ```powershell
   cd backend
   uv run python scripts/seed_demo.py
   ```
4. **Start Services**: Restart SupportDesk (`cd supportdesk; uv run uvicorn app.main:app --port 8001`), the backend API, the worker, and frontend.
5. **Verify Stored Credentials**:
   ```powershell
   cd backend
   uv run python scripts/check_target_login.py
   ```

### 3. Start SupportDesk Target Application (Port 8001)

In a new PowerShell terminal:
```powershell
cd supportdesk
uv run uvicorn app.main:app --port 8001
```

### 4. Start Backend API (Port 8000)

In a new PowerShell terminal:
```powershell
cd backend
uv run uvicorn app.main:app --port 8000
```

### 5. Start Background Agent Worker

In a new PowerShell terminal:
```powershell
cd backend
uv run python -m app.worker
```

### 6. Start Frontend Development Server (Port 5173)

In a new PowerShell terminal:
```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Visit **http://localhost:5173** in your browser.

---

## End-to-End Demo Script (PRD Section 9)

Follow these steps to experience the complete TestPilot AI workflow:

1. **Log In**:
   - Navigate to `http://localhost:5173/login`.
   - Sign in with `demo@testpilot.ai` / `DemoPassword123!`.

2. **Open SupportDesk Project**:
   - On the Projects Dashboard (`/`), click on the **SupportDesk** project card.
   - Observe the pre-seeded target URL (`http://localhost:8001`), the stored encrypted credentials (Admin & Agent), and the indexed requirements document `SUPPORTDESK_REQUIREMENTS.md`.

3. **Start Test Run**:
   - Click the green **Start Test Run** button.
   - You will be automatically redirected to the live Test Run monitoring page (`/projects/{id}/runs/{runId}`).

4. **Monitor Live Execution**:
   - Watch the 4-stage pipeline stepper:
     - `PLANNING`: RAG retrieval queries the vector store; Gemini synthesizes discrete test scenarios.
     - `EXECUTING`: Playwright launches Chromium, logs in as Agent/Admin, and executes actions with step-by-step screenshots.
     - `ANALYZING`: Evaluates observed UI states vs requirement specifications; flags defects.
     - `REPORTING`: Compiles aggregate statistics, severity levels, and actionable bug tickets.

5. **Review Comprehensive Report**:
   - Once completed, click **View Report** (or navigate to `/runs/{runId}/report`).
   - Review:
     - **Pass / Fail Metrics**: Total tests, pass rate, and execution duration.
     - **AI Summary**: Executive summary of system health and critical blockers.
     - **Bug Classification**: Clear breakdown of `PRODUCT_BUG` vs `FLAKY_ENVIRONMENT`.
     - **Failure Cards**: Expected vs observed behavior, source requirement citations, and remediation suggestions.
     - **Screenshot Evidence**: Click any screenshot thumbnail to expand and inspect the browser state at point of failure.

---

## Testing & Quality Assurance

TestPilot AI contains full test coverage across unit, integration, and security suites:

```powershell
# Backend Test Suite (88 tests)
cd backend
uv run pytest -m "not eval"

# SupportDesk CRM Tests
cd supportdesk
uv run pytest

# Frontend Unit & Component Tests (11 tests)
cd frontend
npm.cmd test

# Linter checks
cd backend; uv run ruff check .
cd frontend; npm.cmd run lint
```
