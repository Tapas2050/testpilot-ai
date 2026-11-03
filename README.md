# 🎯 TestPilot AI

> **Autonomous Agentic Web QA & Browser Verification Platform**  
> *Upload requirements, plan multi-role browser scenarios, execute in real Chromium via Playwright MCP, and verify assertions with deterministic proof.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.12](https://img.shields.io/badge/Python-3.12-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![FastAPI: 0.115](https://img.shields.io/badge/FastAPI-0.115-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React: 19](https://img.shields.io/badge/React-19-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![Vite: 6](https://img.shields.io/badge/Vite-6-646CFF.svg?logo=vite&logoColor=white)](https://vitejs.dev)
[![PostgreSQL: 18 + pgvector](https://img.shields.io/badge/PostgreSQL-18%20%2B%20pgvector-336791.svg?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Redis: 7+](https://img.shields.io/badge/Redis-7%2B-DC382D.svg?logo=redis&logoColor=white)](https://redis.io)
[![Playwright MCP: 1.0.12](https://img.shields.io/badge/Playwright%20MCP-1.0.12-45ba4b.svg?logo=playwright&logoColor=white)](https://playwright.dev)
[![Tests: 210 Passed](https://img.shields.io/badge/Tests-210%20Passed-success.svg)](#-evaluation--benchmark)

---

## 💡 Business Context & Problem

Manual QA testing is expensive, slow, and cannot scale with daily continuous deployment cycles. Traditional automated end-to-end testing frameworks (Selenium, Cypress, static Playwright scripts) suffer from **chronic test brittleness**:
- Fragile CSS/XPath selectors break on trivial UI refactors.
- Complex role-based authorization rules (e.g. Agent vs Admin permissions) are frequently missed or unverified.
- Automated tests frequently exhibit **self-delusion**: mistaking the absence of an element for successful enforcement of an access control rule.
- Writing and maintaining test scripts requires significant engineering overhead.

**🎯 The Goal**:  
TestPilot AI provides an autonomous, hallucination-resistant QA engineer. You upload your software specifications (Markdown, PDF, or JSON), define target credentials, and TestPilot AI:
1. Synthesizes discrete, single-role test scenarios using local RAG retrieval and Gemini Flash.
2. Launches a headless Chromium browser over a stdio Model Context Protocol (MCP) server.
3. Interactively clicks, fills inputs, and navigates target web applications.
4. Validates assertions with **deterministic per-check DOM evidence** and **active negative-check verification**.
5. Emits forensic failure reports with side-by-side screenshot evidence (final state + moment of failure).

---

## 🛠️ Technologies Used

| Category | Technology | Purpose & Scope |
|---|---|---|
| **Language & Runtime** | **Python 3.12** / **Node.js v20+** | Backend API, worker, scripts, and MCP client runtime |
| **Backend Framework** | **FastAPI 0.115** | Async REST API, Pydantic v2 schemas, and dependency injection |
| **Web Server** | **Uvicorn** | High-performance ASGI server for FastAPI |
| **Database & ORM** | **PostgreSQL 18** + **SQLAlchemy 2.0 Async** | Relational state store with `NullPool` async engine for tests |
| **Vector Search** | **pgvector 0.8.5** | High-dimensional embedding storage (384-dim) for RAG chunk search |
| **Embeddings** | **sentence-transformers** (`all-MiniLM-L6-v2`) | Local, CPU-efficient requirement chunk embedding generation |
| **Job Queue & Cache** | **Redis 7+** + **arq** | Distributed async job queue, progress pub/sub, and heartbeat tracking |
| **LLM Orchestration** | **LangGraph** + **Google AI Studio (Gemini 2.5 Flash Lite)** | State machine DAG, test planning, analysis, and OpenRouter fallback |
| **Browser Automation** | **@executeautomation/playwright-mcp-server** (v1.0.12) | Model Context Protocol browser automation over stdio |
| **Security & Cryptography** | **Argon2id** (`argon2-cffi`) + **Fernet (AES-256)** | Constant-time password hashing and encrypted target credentials |
| **Frontend Framework** | **React 19** + **Vite 6** | Modern SPA with custom hooks, routing, and live stepper polling |
| **Styling & Icons** | **Tailwind CSS** + **Lucide React** | Responsive design system with status badges and modal viewers |
| **Testing & Quality** | **pytest** + **pytest-asyncio** + **Vitest** + **Ruff** | 173 backend tests, 5 target tests, 32 vitest tests, and linting |
| **Demo Target** | **SupportDesk CRM** (FastAPI + SQLite) | Realistic target app with toggleable planted security/business defects |

---

## 🔄 Architecture & System Workflows

### 1. High-Level System Architecture

```
                       ┌─────────────────────────────────────────┐
                       │          TestPilot Frontend (SPA)       │
                       │          React 19 + Tailwind + Vite     │
                       └────────────────────┬────────────────────┘
                                            │ REST / JSON (Port 5173 -> 8000)
                                            ▼
                       ┌─────────────────────────────────────────┐
                       │           FastAPI Backend API           │
                       │        Uvicorn Server (Port 8000)       │
                       └──────┬───────────────────────────┬──────┘
                              │                           │
                Redis Pub/Sub │                           │ SQLAlchemy Async
                & Queue / Lock│                           │ Postgres + pgvector
                              ▼                           ▼
        ┌─────────────────────────────┐        ┌─────────────────────────────┐
        │        Redis Server         │        │     PostgreSQL Database     │
        │   Job Queue / Heartbeats    │        │  Users, Projects, Runs,     │
        │    (DB 0 Runtime, DB 1 Test)│        │  Test Cases, pgvector Chunks│
        └──────────────┬──────────────┘        └─────────────────────────────┘
                       │
                       │ arq background task
                       ▼
        ┌────────────────────────────────────────────────────────────┐
        │                  Autonomous Agent Worker                   │
        │                  LangGraph State Machine                   │
        │   Preflight ➔ Planning ➔ Execution ➔ Analysis ➔ Report     │
        └──────────────┬───────────────────────────┬─────────────────┘
                       │                           │
         Local Embeddings / Google Gemini API      │ stdio JSON-RPC
                       ▼                           ▼
        ┌─────────────────────────────┐  ┌───────────────────────────────────┐
        │  Gemini 2.5 Flash Lite LLM  │  │   Playwright MCP Server Subproc   │
        │  (OpenRouter Auto-Fallback) │  │  Headless Chromium Browser Driver │
        └─────────────────────────────┘  └─────────────────┬─────────────────┘
                                                           │ Browser Automation
                                                           ▼
                                         ┌───────────────────────────────────┐
                                         │    Target Application Web App     │
                                         │    SupportDesk CRM (Port 8001)    │
                                         └───────────────────────────────────┘
```

### 2. LangGraph Agent State Machine Pipeline

```
  ┌───────────────┐
  │ START TEST RUN│
  └───────┬───────┘
          │
          ▼
  ┌───────────────────────────┐     Fast Preflight Failed?
  │      PREFLIGHT NODE       ├──────────────────────────────┐
  │ - Decrypt target creds    │                              │
  │ - Ping target HTTP URL    │                              │
  │ - Initialize MCP Browser  │                              │
  └───────┬───────────────────┘                              │
          │ Preflight OK                                     │
          ▼                                                  ▼
  ┌───────────────────────────┐                    ┌──────────────────┐
  │       PLANNER NODE        │                    │  TERMINATE RUN   │
  │ - Local RAG pgvector query│                    │ - Status: FAILED │
  │ - Gemini Flash synthesis  │                    │ - Clean MCP proc │
  │ - Single-role test cases  │                    │ - Release lock   │
  │ - 1-4 checks per scenario │                    └──────────────────┘
  └───────┬───────────────────┘                              ▲
          │                                                  │
          ▼                                                  │
  ┌───────────────────────────┐                              │
  │    EXECUTOR NODE (Loop)   │                              │
  │ For each test case:       │                              │
  │ 1. Launch / reuse context │                              │
  │ 2. Authenticate role creds│                              │
  │ 3. Execute action budget  │                              │
  │ 4. Deterministic Check:   │                              │
  │    - DOM Quote match      │                              │
  │    - URL verification     │                              │
  │    - Negative check rule  │                              │
  │ 5. Dual Screenshot Capture│                              │
  │    - Final state .png     │                              │
  │    - Failure moment .png  │                              │
  └───────┬───────────────────┘                              │
          │ All Tests Finished                               │
          ▼                                                  │
  ┌───────────────────────────┐                              │
  │    FAILURE ANALYST NODE   │                              │
  │ - Evaluate failed tests   │                              │
  │ - Differentiate:          │                              │
  │   * PRODUCT_BUG           │                              │
  │   * ENVIRONMENT_FAILURE   │                              │
  │ - Cite requirement IDs    │                              │
  └───────┬───────────────────┘                              │
          │                                                  │
          ▼                                                  │
  ┌───────────────────────────┐                              │
  │       REPORT NODE         │                              │
  │ - Aggregate run metrics   │                              │
  │ - Persist run report JSON │                              │
  │ - Clean up worker Redis   │                              │
  └───────┬───────────────────┘                              │
          │                                                  │
          ▼                                                  │
  ┌───────────────────────────┐                              │
  │      COMPLETED STATE      │                              │
  │ - Status: COMPLETED       │                              │
  │ - Update DB & Redis status├──────────────────────────────┘
  └───────────────────────────┘
```

---

## ✨ Key Features

- **📑 Autonomous Requirement-to-Test Synthesis (RAG)**:  
  Upload software requirement specifications (SRS) in Markdown, PDF, TXT, or JSON. Documents are chunked, embedded locally with `sentence-transformers`, stored in PostgreSQL via `pgvector`, and synthesized into discrete test cases by Gemini Flash.

- **🛡️ Deterministic Per-Check Evidence Verification**:  
  No LLM self-delusion. When an agent finishes a test, every individual check assertion is verified against actual DOM text quotes and URL transitions. A test passes *only* if every check has verifiable evidence.

- **🚫 Active Negative-Check Protection**:  
  Detects the common LLM flaw of assuming missing buttons mean security enforcement. The executor actively attempts restricted actions (e.g., support agents attempting ticket deletion), inspects the post-action DOM and redirects, and deterministically forces a **FAILED** verdict if unauthorized actions succeed without explicit HTTP 403 or permission rejection keywords.

- **⚡ Cold-Start Resilient MCP Engine**:  
  Launches `@executeautomation/playwright-mcp-server` via Node.js stdio with automated 45s cold-start budgets, process-tree termination (`taskkill /F /T /PID` on Windows, SIGKILL on Unix), and automatic retry on cold boot.

- **🔐 Zero-Leak Credential Encryption**:  
  Target login credentials (Admin, Support Agent, Viewer) are encrypted at rest using AES-256 Fernet. Credentials are systematically sanitized from action logs, LLM traces, and frontend API payloads.

- **📸 Dual Forensic Screenshot Capture**:  
  Captures both `{test_case_id}.png` (final state) and `{test_case_id}-failure.png` (moment of check failure). Served through an authenticated API endpoint (`GET /runs/{run_id}/screenshots/{filename}`) with strict cross-user ownership isolation and directory traversal rejection.

- **🔄 Synchronized State Machine & Live Stepper**:  
  Single authoritative helper `update_run_stage_and_status` writes PostgreSQL row first and Redis live progress second, paired with `Cache-Control: no-store` to prevent stale browser polling.

- **🔍 Read-Only Run Review CLI (`review_run.py`)**:  
  Command-line evaluation tool to inspect run statistics, test case outcomes, screenshots, and compare findings against known ground-truth defect targets (`--expect-supportdesk-defects`).

---

## 📈 Evaluation & Benchmark

TestPilot AI was evaluated against **SupportDesk CRM**, a dedicated testbed application with 3 intentionally planted defects:

| Defect ID | Requirement | Description | Expected Behavior | Observed In Defective Mode | TestPilot Result |
|---|---|---|---|---|:---:|
| **DEF-01** | `REQ-SEC-02` | Agent attempts admin ticket deletion | Must return HTTP 403 / Access Denied | Ticket is deleted; redirects to ticket list | ❌ **FAILED** (Caught) |
| **DEF-02** | `REQ-TICK-03` | Ticket created with High priority | Must persist with High priority badge | Silently saved with Low priority | ❌ **FAILED** (Caught) |
| **DEF-03** | `REQ-TICK-04` | Search ticket by exact numeric ID | Must return matching ticket row | Returns empty result table | ❌ **FAILED** (Caught) |

### Detection Accuracy Benchmark

```
SupportDesk Ground Truth Defect Matrix:
┌───────────────────────────────┬─────────────────┬─────────────────┬──────────┐
│ Mode                          │ Planted Defects │ Defects Caught  │ Accuracy │
├───────────────────────────────┼─────────────────┼─────────────────┼──────────┤
│ Defective Mode (DEFECTS=on)   │ 3               │ 3 (100%)        │ 100%     │
│ Clean Mode (DEFECTS=off)      │ 0               │ 0 (0 false pos) │ 100%     │
└───────────────────────────────┴─────────────────┴─────────────────┴──────────┘
```

### Automated Test Suite Coverage

```
Test Suites Execution Summary:
✔ Backend Unit & Integration Tests:   173 passed, 1 skipped, 2 deselected
✔ SupportDesk Demo CRM Tests:          5 passed
✔ Frontend Vitest Suite:              32 passed across 8 test files
✔ Static Code Analysis (Ruff/Oxlint): Clean (0 errors)
Total Automated Verification:         210 passing tests
```

---

## 📁 Project Structure

```
testpilot/
├── .github/
│   └── workflows/
│       ├── backend-ci.yml         # GitHub Actions: Python 3.12, Postgres pgvector, Redis, Pytest
│       ├── frontend-ci.yml        # GitHub Actions: Node 20, Vitest, Oxlint
│       ├── supportdesk-ci.yml     # GitHub Actions: SupportDesk CRM tests
│       └── ci.yml                 # Unified multi-job CI runner
├── backend/
│   ├── alembic.ini                # Alembic database migration config
│   ├── pyproject.toml             # uv package manifest and dependencies
│   ├── app/
│   │   ├── agent/                 # LangGraph agent pipeline
│   │   │   ├── graph.py           # State machine graph nodes & routing
│   │   │   ├── preflight.py       # Fast target reachability & MCP handshake
│   │   │   ├── planner.py         # RAG retrieval & test case prompt synthesis
│   │   │   ├── executor.py        # Playwright MCP browser execution & actions
│   │   │   ├── negative_check.py  # Deterministic prohibited action verification
│   │   │   └── analyst.py         # Bug vs environment failure classification
│   │   ├── api/                   # FastAPI route endpoints
│   │   │   ├── auth.py            # User registration, login, logout, me
│   │   │   ├── projects.py        # Project CRUD & target credential management
│   │   │   ├── documents.py       # Requirements upload & vector indexing
│   │   │   └── runs.py            # Start run, live status, report, screenshots
│   │   ├── core/                  # Configuration, database engine, Redis
│   │   ├── models/                # SQLAlchemy models (User, Project, Run, TestCase)
│   │   ├── services/              # Screenshot storage, crypto, token management
│   │   └── worker.py              # arq distributed background worker process
│   ├── migrations/                # Alembic versions (pgvector, tables)
│   ├── scripts/                   # Evaluation scripts (review_run.py, seed_demo.py)
│   └── tests/                     # 173 backend pytest unit & integration tests
├── frontend/
│   ├── package.json               # Vite + React 19 dependencies
│   ├── src/
│   │   ├── components/            # Stepper, ScreenshotViewer, StatusBadge, Dialogs
│   │   ├── context/               # AuthContext & token management
│   │   ├── hooks/                 # useRunStatus live polling hook
│   │   ├── pages/                 # Dashboard, ProjectPage, TestRunPage, ReportPage
│   │   └── __tests__/             # 32 Vitest jsdom frontend test suites
├── mcp/
│   └── package.json               # Pinned @executeautomation/playwright-mcp-server (1.0.12)
├── supportdesk/                   # SupportDesk CRM testbed demo target
│   ├── app/                       # FastAPI + Jinja2 + SQLite ticketing system
│   ├── reseed.py                  # Database reset script (5 seed tickets)
│   ├── SUPPORTDESK_REQUIREMENTS.md# Specification document for RAG indexing
│   └── tests/                     # SupportDesk functionality & defect tests
└── README.md                      # Production showcase documentation
```

---

## ⚙️ Quickstart & Setup Guide

### Prerequisites
- **Operating System**: Windows 11 (PowerShell) or Linux / macOS
- **Python**: Python 3.12 managed via [Astral uv](https://docs.astral.sh/uv/)
- **Node.js**: Node v20+ or v24+ with `npm`
- **PostgreSQL**: PostgreSQL 18 with `pgvector` extension enabled
- **Redis**: Redis 7+ (running locally or inside WSL2)
- **Browser**: Playwright Chromium binaries (`uv run playwright install chromium`)

---

### Step 1: Clone & Configure Environment

```powershell
# Clone the repository
git clone https://github.com/Tapas2050/testpilot-ai.git
cd testpilot-ai

# Create local environment file
Copy-Item .env.example .env
```

Edit `.env` and configure your database and API keys:
```ini
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/testpilot
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/testpilot_test
REDIS_URL=redis://localhost:6379/0
TEST_REDIS_URL=redis://localhost:6379/1
JWT_SECRET=your-32-character-minimum-jwt-secret-here
ENCRYPTION_KEY=your-32-byte-base64-urlsafe-encryption-key
GEMINI_API_KEY=your-google-ai-studio-api-key
```

---

### Step 2: Ensure Redis & PostgreSQL are Running

On Windows 11 with Redis in WSL2:
```powershell
# Start Redis in WSL2 and keep WSL active
wsl -u root service redis-server restart
```

Verify Redis connectivity from Python:
```powershell
cd backend
uv run python -c "import redis; print(redis.Redis().ping())"
# Output: True
```

---

### Step 3: Run Database Migrations & Seed Demo Project

```powershell
cd backend
# Run Alembic migrations (creates tables and vector extension)
uv run alembic upgrade head

# Seed demo SupportDesk project with encrypted credentials and indexed requirements
uv run python scripts/seed_demo.py
```

This creates:
- **Demo User**: `demo@testpilot.ai` / `DemoPassword123!`
- **Target App**: SupportDesk on `http://localhost:8001`
- **Requirements Knowledge**: Chunks from `SUPPORTDESK_REQUIREMENTS.md` indexed into `pgvector`.

---

### Step 4: Launch TestPilot AI Services

Open separate terminal windows for each service:

**Terminal 1 — SupportDesk Target CRM (Port 8001):**
```powershell
cd supportdesk
uv run uvicorn app.main:app --port 8001
```

**Terminal 2 — TestPilot Backend API (Port 8000):**
```powershell
cd backend
uv run uvicorn app.main:app --port 8000
```
*Health check verify: `curl http://localhost:8000/health`*

**Terminal 3 — Background Agent Worker:**
```powershell
cd backend
uv run python -m app.worker
```

**Terminal 4 — Frontend React SPA (Port 5173):**
```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

---

## 🧪 Running Automated Tests

```powershell
# 1. Run Backend Unit & Integration Tests (173 tests)
cd backend
uv run pytest -m "not eval"

# 2. Run SupportDesk CRM Tests (5 tests)
cd supportdesk
uv run pytest

# 3. Run Frontend Vitest Suite (32 tests)
cd frontend
npm.cmd test -- --run

# 4. Run Linter Checks
cd backend; uv run ruff check .
cd frontend; npm.cmd run lint
```

---

## 📚 Core Concepts & Engineering Highlights

### 1. Hallucination-Resistant Verification Protocol
LLM agents frequently declare victory when a page doesn't crash. TestPilot AI combats this through **triangulated verification**:
- **DOM Quote Grounding**: Every planned check requires an exact textual quote from the DOM.
- **Negative Rejection Validation**: If a test specifies that an Agent cannot delete a ticket, TestPilot executes the delete action. If the server redirects with 303 or deletes the record without an explicit permission rejection (403, "Access Denied", "Forbidden"), the verdict is forced to **FAILED**.

### 2. Subprocess & Memory Safety in Constrained Environments
Designed to operate stably within **8 GB RAM**:
- **Process Singleton Embeddings**: `all-MiniLM-L6-v2` is pre-cached once in memory on worker startup with `local_files_only=True`, avoiding repeated downloads and unauthenticated rate limits.
- **Clean Subprocess Teardown**: MCP browser child processes are monitored with a monotonic run deadline. On timeout or cancellation, process trees are terminated using `taskkill /F /T /PID` (Windows) or POSIX `SIGKILL`.

### 3. Absolute Path Storage & Security Isolation
Screenshots are written to `storage/screenshots/{run_id}/` anchored strictly to the repository root directory. The screenshot endpoint requires bearer token authentication, verifies project ownership, validates filename regex (`^[a-zA-Z0-9_\-\.]+\.png$`), and strictly prevents directory traversal attacks.

---

## 🔧 Limitations & Roadmap

- **Concurrency**: Currently configured for single-run worker execution to respect 8GB RAM local laptop constraints. Multi-worker scaling via Kubernetes worker pools is planned.
- **Real-Time Streaming**: Live run status currently uses high-frequency monotonic HTTP polling (1.5s interval with `Cache-Control: no-store`). Server-Sent Events (SSE) streaming is slated for v1.2.
- **Cross-Browser Grid**: Chromium is the primary execution target. WebKit and Firefox support are being integrated into the MCP container matrix.

---

## 👨‍💻 Author & Contributions

Built with ❤️ by **Tapas** ([@Tapas2050](https://github.com/Tapas2050)).  
Contributions, bug reports, and feature requests are welcome! Please check [CONTRIBUTING.md](CONTRIBUTING.md) and our [Security Policy](SECURITY.md).

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

⭐ **If you find TestPilot AI useful for your autonomous QA workflows, please star this repository!** ⭐
