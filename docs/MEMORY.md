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
- Current phase: Phase 14: Showcase README, CI/CD Pipeline Matrix, and Public Repository Release (Completed)
- Status: Architecture-grounded showcase README created using `readme-creator` with ASCII execution state machines, tech stack matrix, and SupportDesk ground-truth benchmarks. Multi-job GitHub Actions CI/CD pipeline matrix configured for Backend (PostgreSQL 16 + pgvector, Redis), Frontend (Vitest, Oxlint), and SupportDesk CRM. Added automated multi-suite test runners, Docker Compose stack, GitHub community health files (bug report, feature request, PR template, MIT license, CONTRIBUTING, SECURITY), and markdown review CLI formatting. All 173 backend tests, 5 supportdesk tests, and 32 frontend vitest tests passing cleanly.
- Date of last update: 2026-11-03

## 4. Environment Facts (verified)
- Hardware: 8 GB RAM (about 83% used at idle), Intel Iris Xe integrated GPU, no dedicated GPU. Memory budget rules in D-018 respected throughout.
- Host OS: Windows 11. Postgres 18.6 installed locally; pgvector 0.8.5 installed and active in database `testpilot`. Alembic migrations applied to `testpilot`.
- Redis installed in WSL2 Ubuntu, configured to bind `0.0.0.0 ::1` with `protected-mode no`. Accessible at `localhost:6379`. WSL kept alive with background process to prevent idle suspension.
- Verified on host: uv 0.12.8, Python 3.12.14 pinned via `uv`, Node v24.19.0, npm 11.17.0, Git 2.55.0.
- Vite 8.3.4 + React in `frontend/`. Vitest jsdom tests: 32 passed across 8 test files.
- SupportDesk demo target in `supportdesk/`: FastAPI + SQLite, seeded with 5 tickets (IDs 1-5), toggleable planted defects via `SUPPORTDESK_DEFECTS`. Status/assignee update route fixed (`status_code=303`) and verified with 5 tests passing in both modes.
- SupportDesk ground-truth browser verification (`test_ground_truth_browser.py`): all 7 scenarios verified with real Playwright MCP against SupportDesk with defects ON (agent cannot delete correctly evaluated to FAILED, 3 defects caught) and defects OFF (all 7 passing).
- MCP Server Package: `@executeautomation/playwright-mcp-server` pinned to `1.0.12` in `mcp/package.json`. Launched directly with `node` and entrypoint `mcp/node_modules/@executeautomation/playwright-mcp-server/dist/index.js` with explicit `cwd=mcp`.
- Screenshot Storage: Located at `<repo_root>/storage/screenshots/{run_id}/`. Disk files: `{test_case_id}.png` (final state) and `{test_case_id}-failure.png` (moment of failure).
- Screenshot Retention: Default 14 days (`SCREENSHOT_RETENTION_DAYS=14`), cleaned automatically on worker startup.
- Test counts: 173 backend unit/integration tests passing (+ 1 skipped, 2 deselected live eval, 2 browser tests) + 5 supportdesk tests + 32 frontend tests.
- Ruff clean on backend, scripts, and supportdesk; lint clean on frontend.

## 5. Conventions in Use
- uv project inside `backend/` with `[tool.uv] package = false`.
- Absolute Storage Path Rule: `STORAGE_DIR` is strictly resolved against repository root (`ROOT_DIR`), never relative to CWD. All processes (API, worker, MCP child) use centralized `app.services.screenshot_storage`.
- Screenshot Security: Evidence endpoint `GET /runs/{run_id}/screenshots/{filename}` enforces project ownership (cross-user gets 404), regex filename validation (`^[a-zA-Z0-9_\-\.]+\.png$`), rejects directory traversal attempts, and sets `Cache-Control: private, max-age=300`.
- Frontend Screenshot Fetching: Fetched using bearer token via `api.runs.fetchScreenshotBlob`, converted to blob object URL and revoked on unmount.
- Settings loaded with `pydantic-settings` from `.env` in repo root. JWT_SECRET requires >= 32 chars.
- SQLAlchemy async engine configured with `NullPool` to prevent cross-event-loop connection pool leakage in pytest async test runner.
- Test database isolation via `backend/tests/conftest.py`: tests always run against `testpilot_test` with `NullPool`, schema created before session, tables truncated between tests, and `get_db` overridden. Tests never touch `testpilot`.
- Timezone-aware datetimes only: `datetime.now(timezone.utc)`. Never use `datetime.utcnow()`.
- Password hashing: `argon2-cffi` via `asyncio.to_thread` with startup dummy hash comparison for non-existent users (D-019).
- ORM model for user sessions is named `UserSession` (mapped to `sessions` table) to avoid colliding with SQLAlchemy's `Session`.
- JWT decoding requires explicit `algorithms=["HS256"]` and verifies `exp`, `sub`, and `jti`.
- Email handling: stripped and lowercased on registration and login.
- Health check route: `GET /health` on port 8000 (verifies API, DB with pgvector, and Redis).
- Single-role test cases: each test case targets exactly ONE role and 1 to 4 checks (`TestCase.checks` JSONB column).
- Action validation: navigate requires url, click requires selector, fill/select require selector + value, press_key requires key. Missing required fields trigger a single re-prompt and do not count toward step limit.
- Per-check evidence verification: finish action returns `check_results` mapping each planned check to PASSED/FAILED/INCONCLUSIVE, evidence quote, and >= 20-char observation. PASSED checks must have evidence verified against DOM text or URL.
- Negative-check rule: An absent button or link is NOT proof of a protected action (if unattempted, check is INCONCLUSIVE / test BLOCKED). Executor attempts the action and cites the step in `attempted_step`. Code verification `evaluate_check_result` deterministically verifies tool success and after-state DOM text: if the action succeeded without rejection keywords (`forbidden`, `403`, `denied`), verdict is forced to FAILED (prohibited action permitted). Only marks PASSED if explicit rejection is proven in evidence.
- Single Authoritative Status Helper: `update_run_stage_and_status` writes DB row first and then Redis (`run_status` and `run_progress`). All transitions (PREFLIGHT, PLANNING, EXECUTING, ANALYZING, REPORTING, COMPLETED, FAILED, CANCELLED) use this helper.
- Run Status API: `GET /runs/{id}` returns database row merged with Redis live progress, sends `Cache-Control: no-store`, and includes `server_time`, `updated_at`, `stage`, `current_test_key`, `current_step`, `tests_done`, `tests_total`.
- Test Key Numbering: Test cases use 0-indexed `order_index` (0..N-1), formatted as `TC-{order_index + 1}`. Legacy runs with 1-indexed `order_index` are detected via `min_order == 1` and formatted as `TC-{order_index}`, guaranteeing every run starts at `TC-1` and is sequential across API, run page, and report.
- Run Review Script: `backend/scripts/review_run.py` evaluates run stats, test cases, screenshots, and ground truth defect matches (`--expect-supportdesk-defects`). Read-only, no secrets printed or copied.
- Verdict rule: PASSED only if every check is PASSED with verified evidence. Any FAILED check makes test FAILED. Any INCONCLUSIVE check makes test BLOCKED.
- Deterministic Expected & Observed failure details: expected from `expected_result`, observed from final observation, quote, and last page state.
- Live LLM calls tracking: live calls tracked via `get_live_call_count()`, persisted in run report JSON and displayed in UI.
- Redis Key Patterns & Cleanup (DB 0 runtime, DB 1 tests):
  - Duplicate-run lock: `project_run_lock:{project_id}` (TTL max(RUN_TIMEOUT_SECONDS + 300, 2100), default 2100s per D-025). Cleanup: `redis-cli del "project_run_lock:<project_id>"`
  - Worker heartbeat: `worker_heartbeat:{run_id}` (TTL 60s, refreshed every 15s). Cleanup: `redis-cli del "worker_heartbeat:<run_id>"`
  - Live progress: `run_progress:{run_id}` (TTL 1800s, completed/total count). Cleanup: `redis-cli del "run_progress:<run_id>"`
  - Step events: `run_events:{run_id}` (TTL 1800s, Redis list). Cleanup: `redis-cli del "run_events:<run_id>"`
  - Run status cache: `run_status:{run_id}` (TTL 1800s, status/stage/failed_stage/error). Cleanup: `redis-cli del "run_status:<run_id>"`
  - User cancel flag: `run_cancel:{run_id}` (TTL max(RUN_TIMEOUT_SECONDS + 300, 2100), default 2100s). Cleanup: `redis-cli del "run_cancel:<run_id>"`
- NPM commands on Windows PowerShell use `npm.cmd` / `npx.cmd` to bypass script execution policy restrictions.

## 6. Gotchas and Lessons
- Stuck "Planning" Screen Root Cause: The frontend stepper derived from `run.stage`. The worker was updating stage transitions only in Redis `run_progress` while `test_runs` row in Postgres remained with `stage="PLANNING"`. `GET /runs/{id}` only read the DB row and had no `Cache-Control: no-store`, so the frontend polled and stayed stuck on Planning until completion. Solved with single authoritative `update_run_stage_and_status` writing DB first, then Redis, merged in `GET /runs/{id}`, and Cache-Control: no-store.
- Missed Agent Deletion Defect Root Cause: SupportDesk renders `#delete-ticket-btn` unconditionally for all users on `/tickets/{id}`. When `SUPPORTDESK_DEFECTS=on`, deletion succeeded and redirected 303 to `/tickets`. The LLM executor landed on `/tickets`, saw "Support Tickets" header, and misjudged the absence of a delete button on the list page as prohibition: claiming PASSED. Solved with deterministic code-level verification in `evaluate_check_result`: requiring explicit rejection keywords in after-state evidence and forcing FAILED if the prohibited action succeeded without rejection.
- Missing TC-1 Numbering Root Cause: Planner was indexing test cases with `enumerate(..., start=1)`, storing `order_index = 1..11`. The API was generating `test_key` as `f"TC-{tc.order_index + 1}"`, turning index 1 into `TC-2` and omitting `TC-1`. Solved by setting planner `start=0` and adding `min_order` normalization across `graph.py` and `runs.py`.
- Missing Screenshots Root Cause: Relative `STORAGE_DIR` resolved to different locations for worker (`backend/storage`) vs API (`storage`), and MCP client ran with cwd `mcp/node_modules` creating `mcp/node_modules/storage/screenshots/...`. Furthermore, `@executeautomation/playwright-mcp-server` appends `-${timestamp}.png`, causing filename mismatches with database-stored paths. Centralized `screenshot_storage.py` resolves one absolute path against `ROOT_DIR`, renames timestamped output to canonical target, and validates 8-byte PNG magic + size boundaries.
- SupportDesk 500 Root Cause: In `supportdesk/app/main.py:467`, parameter `status: str = Form(...)` shadowed FastAPI's `from fastapi import status` module. Line 478 `status.HTTP_303_SEE_OTHER` crashed with `AttributeError: 'str' object has no attribute 'HTTP_303_SEE_OTHER'`. Fixed by specifying `status_code=303` directly.
- WSL2 Idle Suspension: In Windows 11, WSL2 instances automatically stop background systemd services when all foreground sessions close. Keeping a background daemon (`wsl sleep infinity`) prevents Redis disconnections. Additionally, Redis must bind `0.0.0.0 ::1` with `protected-mode no` so connections from Windows `localhost` (which resolve to IPv6 `::1` first) succeed reliably.
- Alembic `configparser` interprets `%` in URL-encoded database passwords as interpolation syntax; escape `%` to `%%` when setting `sqlalchemy.url`.
- Windows PowerShell blocks `npm.ps1` by default; invoke `npm.cmd` instead.
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
