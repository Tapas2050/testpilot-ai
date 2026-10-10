# MEMORY: Project State for the Coding Agent

Purpose: this file is the coding agent's working memory between sessions. Read it at the start of every session, after RULES.md. Update it at the end of every session. Keep it short and current; compress old entries instead of letting it grow.

Only record facts the user stated, things verified by running code or reading documentation, and open questions. Never record API keys, passwords or tokens.

## 1. Project Summary
TestPilot AI: web platform where an AI agent plans, runs and reports browser tests from uploaded requirements. Demo target: SupportDesk with 3 planted defects. Stack: FastAPI, Postgres + pgvector, Redis, arq, LangGraph, Playwright MCP, React, uv. LLM: Google AI Studio primary, OpenRouter fallback. Embeddings: local sentence-transformers. No Docker for now.

## 2. Document Map
- PRD.md: what and why
- IMPLEMENTATION.md: architecture, schema, API, phases
- DESIGN.md: UI
- RULES.md: how to work, env variable names
- TASKS.md: checklist and status
- DECISIONS.md: decisions and their reasons
- TEST_PLAN.md: tests per phase
- SECURITY.md: threats and controls

## 3. Current State
- Current phase: Worker Timeout, Stuck-Run, and Cleanup Hardening (Parts 1-7 Complete)
- Status: All 7 parts implemented, tested, and committed with zero regressions
- Date of last update: 2026-10-10

## 4. Environment Facts (verified)
- Hardware: 8 GB RAM (about 83% used at idle), Intel Iris Xe integrated GPU, no dedicated GPU. Memory budget rules in D-018 respected throughout.
- Host OS: Windows 11. Postgres 18.6 installed locally; pgvector 0.8.5 installed and active in database `testpilot`. Alembic migrations applied to `testpilot`.
- Redis installed in WSL2 Ubuntu, reachable at `redis://localhost:6379/0` (app) and `redis://localhost:6379/1` (tests).
- Verified on host: uv 0.12.8, Python 3.12.14 pinned via `uv`, Node v24.19.0, npm 11.17.0, Git 2.55.0.
- Vite 8.3.4 + React in `frontend/`. Vitest jsdom tests: 16 passed (7 auth & project tests + 7 run and report tests + 2 error boundary & not-found tests).
- SupportDesk demo target in `supportdesk/`: FastAPI + SQLite, seeded demo credentials, toggleable planted defects via `SUPPORTDESK_DEFECTS`. All 3 tests (T7.1, T7.2, T7.3) pass cleanly.
- Worker Hardening and Cleanup (Parts 1-7):
  - Part 1 (fix-1): arq worker timeout set to `RUN_TIMEOUT_SECONDS + 300` (2100s), `max_tries = 1`, `retry_jobs = False`, and in-job graceful timeout via `asyncio.wait_for`.
  - Part 2 (fix-2): Shielded finalizer `_finalize_run` protecting against cancellation on any exit: updates status to FAILED/CANCELLED with human-readable error, marks unfinished tests BLOCKED, builds partial report, releases Redis lock, clears progress keys, closes MCP process.
  - Part 3 (fix-3): Non-blocking per-tool timeouts (45s nav, 30s actions/screenshots), Windows process tree termination via `taskkill /F /T /PID` (and POSIX SIGKILL), MCP restart on timeout, tests marked FAILED with ENVIRONMENT_FAILURE, clean teardown of child processes.
  - Part 4 (fix-4): Worker heartbeat in Redis (`worker_heartbeat:{run_id}`, TTL=60s, 15s refresh), auto-detection of dead workers (>90s without heartbeat marked FAILED with "Worker stopped responding") in GET /runs/{id} and startup sweep, frontend timer stopped on terminal states.
  - Part 5 (fix-5): Enqueue payload simplified to `run_id` only; worker uses its own configured `DATABASE_URL` instead of job payload; missing run skipped cleanly with single short warning; `TEST_REDIS_URL` in DB 1 prevents test pollution of production queue; verified safety of schema management.
  - Part 6 (fix-6): LLM per-request timeout configured (`LLM_REQUEST_TIMEOUT_SECONDS=60.0`), fast daily-quota 429 fallback bypassing retry loops, test marked BLOCKED with ENVIRONMENT_FAILURE on provider failure, run aborted early on 2 consecutive provider failures.
  - Part 7 (fix-7): Embedding model singleton in `_process_model_cache` loaded once per process, preloaded in `WorkerSettings.on_startup`.
- Test counts: 114 backend unit/integration tests passing (+ 1 skipped, 1 deselected live eval) + 16 frontend tests = 130 tests passing cleanly.
- Ruff clean on backend and supportdesk; lint clean on frontend.

## 5. Conventions in Use
- uv project inside `backend/` with `[tool.uv] package = false`.
- Settings loaded with `pydantic-settings` from `.env` in repo root. JWT_SECRET requires >= 32 chars.
- SQLAlchemy async engine configured with `NullPool` to prevent cross-event-loop connection pool leakage in pytest async test runner.
- Test database isolation via `backend/tests/conftest.py`: tests always run against `testpilot_test` with `NullPool`, schema created before session, tables truncated between tests, and `get_db` overridden. Tests never touch `testpilot`.
- Timezone-aware datetimes only: `datetime.now(timezone.utc)`. Never use `datetime.utcnow()`.
- Password hashing: `argon2-cffi` via `asyncio.to_thread` with startup dummy hash comparison for non-existent users (D-019).
- ORM model for user sessions is named `UserSession` (mapped to `sessions` table) to avoid colliding with SQLAlchemy's `Session`.
- JWT decoding requires explicit `algorithms=["HS256"]` and verifies `exp`, `sub`, and `jti`.
- Email handling: stripped and lowercased on registration and login.
- Redis health check uses scoped connection per check to prevent closed event loop errors across test runs.
- Redis Key Patterns & Cleanup (DB 0 runtime, DB 1 tests):
  - Duplicate-run lock: `project_run_lock:{project_id}` (TTL 900s). Cleanup: `redis-cli del "project_run_lock:<project_id>"`
  - Worker heartbeat: `worker_heartbeat:{run_id}` (TTL 60s, refreshed every 15s). Cleanup: `redis-cli del "worker_heartbeat:<run_id>"`
  - Live progress: `run_progress:{run_id}` (TTL 1800s, completed/total count). Cleanup: `redis-cli del "run_progress:<run_id>"`
  - Step events: `run_events:{run_id}` (TTL 1800s, Redis list). Cleanup: `redis-cli del "run_events:<run_id>"`
  - Run status cache: `run_status:{run_id}` (TTL 1800s, status/stage/failed_stage/error). Cleanup: `redis-cli del "run_status:<run_id>"`
  - User cancel flag: `run_cancel:{run_id}` (TTL 900s). Cleanup: `redis-cli del "run_cancel:<run_id>"`
- NPM commands on Windows PowerShell use `npm.cmd` / `npx.cmd` to bypass script execution policy restrictions.

## 6. Gotchas and Lessons
- Alembic `configparser` interprets `%` in URL-encoded database passwords as interpolation syntax; escape `%` to `%%` when setting `sqlalchemy.url`.
- Windows PowerShell blocks `npm.ps1` by default; invoke `npm.cmd` instead.
- WSL Redis must be explicitly started with `sudo service redis-server start` prior to running backend services.

## 7. Open Questions for the User
- Whether to keep the minimal professional design style (DESIGN.md)

## 8. Known Deferred Items
- Public hosting, re-run, flaky retry, SSE instead of polling, httpOnly cookie auth

## 9. Update Protocol
At the end of each session:
1. Update section 3 (phase, last task, next task, date).
2. Add new verified facts to section 4 and conventions to section 5.
3. Add any gotchas to section 6.
4. Move answered questions out of section 7.
5. Make sure TASKS.md checkboxes match reality.
