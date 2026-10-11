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
- Current phase: Playwright MCP Worker Startup Hardening & Resilient Preflight (Parts 1-4 Complete)
- Status: Preflight cold-start tolerance (45s budget + retry), single browser launch handoff, honest error formatting, and test suites passing cleanly
- Date of last update: 2026-10-12

## 4. Environment Facts (verified)
- Hardware: 8 GB RAM (about 83% used at idle), Intel Iris Xe integrated GPU, no dedicated GPU. Memory budget rules in D-018 respected throughout.
- Host OS: Windows 11. Postgres 18.6 installed locally; pgvector 0.8.5 installed and active in database `testpilot`. Alembic migrations applied to `testpilot`.
- Redis installed in WSL2 Ubuntu, reachable at `redis://localhost:6379/0` (app) and `redis://localhost:6379/1` (tests).
- Verified on host: uv 0.12.8, Python 3.12.14 pinned via `uv`, Node v24.19.0, npm 11.17.0, Git 2.55.0.
- Vite 8.3.4 + React in `frontend/`. Vitest jsdom tests: 18 passed (7 auth & project tests + 9 run and report tests + 2 error boundary & not-found tests).
- SupportDesk demo target in `supportdesk/`: FastAPI + SQLite, seeded demo credentials, toggleable planted defects via `SUPPORTDESK_DEFECTS`. All 3 tests pass cleanly.
- MCP Server Package: `@executeautomation/playwright-mcp-server` pinned to `1.0.12` in `mcp/package.json`. Launched directly with `node` and entrypoint `mcp/node_modules/@executeautomation/playwright-mcp-server/dist/index.js` with explicit `cwd=mcp`. No npx, no cmd shell, no runtime downloads.
- Preflight Startup Timings Measured (via `backend/scripts/preflight_only.py`):
  - Embedding model preload: ~18.7s-20.6s (online HuggingFace check) -> reduced to ~0.44s-0.59s with `local_files_only=True`. Peak RSS: ~500-522 MB.
  - Credential decryption: 0.17s - 0.28s (budget 2.0s)
  - Target reachability: 0.39s - 0.47s (budget 5.0s)
  - MCP process start: ~0.015s
  - MCP initialize handshake: ~1.15s - 1.55s (warm) / 15-28s (cold under memory pressure).
  - Preflight budget: `MCP_STARTUP_TIMEOUT_SECONDS=45.0` (configurable), auto-retries once on first attempt timeout.
  - Single browser start: Preflight hands started MCP client to `execute_node` via `_active_mcp_clients[run_id]`, eliminating redundant second browser launch.
- Test counts: 129 backend unit/integration tests passing (+ 3 deselected live eval) + 18 frontend tests = 147 tests passing cleanly.
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
  - Duplicate-run lock: `project_run_lock:{project_id}` (TTL max(RUN_TIMEOUT_SECONDS + 300, 2100), default 2100s per D-025). Cleanup: `redis-cli del "project_run_lock:<project_id>"`
  - Worker heartbeat: `worker_heartbeat:{run_id}` (TTL 60s, refreshed every 15s). Cleanup: `redis-cli del "worker_heartbeat:<run_id>"`
  - Live progress: `run_progress:{run_id}` (TTL 1800s, completed/total count). Cleanup: `redis-cli del "run_progress:<run_id>"`
  - Step events: `run_events:{run_id}` (TTL 1800s, Redis list). Cleanup: `redis-cli del "run_events:<run_id>"`
  - Run status cache: `run_status:{run_id}` (TTL 1800s, status/stage/failed_stage/error). Cleanup: `redis-cli del "run_status:<run_id>"`
  - User cancel flag: `run_cancel:{run_id}` (TTL max(RUN_TIMEOUT_SECONDS + 300, 2100), default 2100s). Cleanup: `redis-cli del "run_cancel:<run_id>"`
- NPM commands on Windows PowerShell use `npm.cmd` / `npx.cmd` to bypass script execution policy restrictions.

## 6. Gotchas and Lessons
- Alembic `configparser` interprets `%` in URL-encoded database passwords as interpolation syntax; escape `%` to `%%` when setting `sqlalchemy.url`.
- Windows PowerShell blocks `npm.ps1` by default; invoke `npm.cmd` instead.
- WSL Redis must be explicitly started with `sudo service redis-server start` prior to running backend services.
- Cold MCP Startup: On Windows 11 with 8GB RAM, cold-launching Node/Playwright after loading heavy PyTorch embeddings takes 15-28s. A short 8.0s timeout caused false preflight failures. Setting budget to 45s with automatic single retry handles cold starts reliably.
- `asyncio.TimeoutError` string is empty: `str(TimeoutError())` is `""`. Formatting `f"({exc})"` outputs `()`. Always extract `type(exc).__name__`, elapsed time, budget, and print `no detail` when the exception message is empty.
- SentenceTransformer Network Overhead: `SentenceTransformer` contacts Hugging Face Hub on startup unless `local_files_only=True` is provided, introducing 18-20s network latency and unauthenticated rate-limit warnings.

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
