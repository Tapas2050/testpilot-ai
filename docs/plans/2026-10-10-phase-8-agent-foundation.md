# Plan: Phase 8 - Agent Foundation (Stub Nodes)

## 1. Goal
Establish the end-to-end asynchronous test run lifecycle:
- Database models for `TestRun`, `TestCase`, `TestResult`, and `Failure` with Alembic migration.
- LangGraph orchestration with 5 stub nodes (`plan`, `execute`, `analyze`, `report`, `complete`).
- Postgres checkpointer for thread persistence.
- Asynchronous task worker (`arq`) and background execution.
- Project-scoped run lock in Redis preventing duplicate simultaneous runs.
- API endpoints for starting runs (`POST /projects/{id}/runs`), polling run status (`GET /runs/{id}`), listing runs (`GET /projects/{id}/runs`), and cancelling runs (`POST /runs/{id}/cancel`).
- Verification against tests T8.1 through T8.6 in `backend/tests/test_agent_foundation.py`.

---

## 2. Tasks and Files

### 2.1 Database Models
- File: `backend/app/models/test_run.py`
  - `TestRun`: UUID PK, project_id FK, status (QUEUED, PLANNING, EXECUTING, ANALYZING, REPORTING, COMPLETED, FAILED, CANCELLED), created_at, started_at, completed_at, error_message, cancel_requested, report (JSONB).
  - `TestCase`: UUID PK, run_id FK, title, description, source_requirement, target_role, status, order_index.
  - `TestResult`: UUID PK, test_case_id FK, status, steps (JSONB), error_message, screenshot_path, duration_seconds.
  - `Failure`: UUID PK, test_case_id FK, classification, severity, confidence, expected, observed, explanation, suggested_action.
- Export in `backend/app/models/__init__.py`.
- Alembic migration `create_test_runs_tables.py` and apply to both `testpilot` and test runner.

### 2.2 Agent State and LangGraph Graph
- File: `backend/app/agent/state.py`
  - TypedDict / Pydantic `AgentState` with `run_id`, `project_id`, `current_stage`, `test_cases`, `results`, `failures`, `error`, `cancel_requested`.
- File: `backend/app/agent/graph.py`
  - Five stub nodes with status updates in DB & Redis:
    1. `plan_node` (moves status to PLANNING)
    2. `execute_node` (moves status to EXECUTING)
    3. `analyze_node` (moves status to ANALYZING)
    4. `report_node` (moves status to REPORTING)
    5. `complete_node` (moves status to COMPLETED)
  - Postgres checkpointer integration (or fallback checkpointer for test runner).
  - Cancellation check at node boundaries.
  - Exception handler marking run as FAILED and preserving API responsiveness.

### 2.3 arq Worker & Redis Duplicate Lock
- File: `backend/app/worker.py`
  - `WorkerSettings` pointing to `get_settings().REDIS_URL`.
  - `run_agent_job(ctx, run_id: str)`.
- File: `backend/app/services/run_service.py`
  - Enqueue helper, Redis run lock (`project_run_lock:{project_id}`), cancel flag (`run_cancel:{run_id}`), and status cache.

### 2.4 API Routes
- File: `backend/app/api/runs.py`
  - `POST /projects/{project_id}/runs`: Instant return with `run_id` and `QUEUED`.
  - `GET /runs/{run_id}`: Run details with test cases, results, and stage.
  - `GET /projects/{project_id}/runs`: List runs for project.
  - `POST /runs/{run_id}/cancel`: Request cancellation.
- Mount router in `backend/app/main.py`.

### 2.5 Tests
- File: `backend/tests/test_agent_foundation.py`
  - `T8.1`: Start run returns `run_id` and `QUEUED` immediately.
  - `T8.2`: Stub run moves through every state in order to `COMPLETED` with timestamps.
  - `T8.3`: Forced exception in a node yields `FAILED` with error message; API stays responsive.
  - `T8.4`: Second start for same project while run is active is blocked (HTTP 409).
  - `T8.5`: Cancel stops the run and sets `CANCELLED`.
  - `T8.6`: Checkpoint exists for a run thread.
