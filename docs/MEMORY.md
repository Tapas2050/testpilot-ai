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
- Current phase: Phase 13 complete (Hardening and Demo Readiness) - ALL PHASES 1-13 COMPLETE
- Last completed task: 13.8
- Next task: Review docs/FINAL_REPORT.md and human checklist
- Date of last update: 2026-10-10

## 4. Environment Facts (verified)
- Hardware: 8 GB RAM (about 83% used at idle), Intel Iris Xe integrated GPU, no dedicated GPU. Memory budget rules in D-018 respected throughout.
- Host OS: Windows 11. Postgres 18.6 installed locally; pgvector 0.8.5 installed and active in database `testpilot`. Alembic migrations applied to `testpilot`.
- Redis installed in WSL2 Ubuntu, reachable at `redis://localhost:6379/0`.
- Verified on host: uv 0.12.8, Python 3.12.14 pinned via `uv`, Node v24.19.0, npm 11.17.0, Git 2.55.0.
- Vite 8.3.4 + React in `frontend/`. Vitest jsdom tests: 11 passed (7 auth & project tests + 4 run and report tests). Build bundle cleanly generated.
- SupportDesk demo target in `supportdesk/`: FastAPI + SQLite, seeded demo credentials, toggleable planted defects via `SUPPORTDESK_DEFECTS`. All 3 tests (T7.1, T7.2, T7.3) pass cleanly.
- LangGraph agent foundation, Planner, Executor, Failure Analyst, and Report Generator verified.
- Complete frontend UI for all 6 screens per DESIGN.md: Login, Register, Dashboard, Project page, Test Run page, and Report page.
- Hardening & Security (Phase 13):
  - Redis fixed-window rate limiter: 10/min on `/auth/login`, 5/min on `POST /projects/{id}/runs` with 429 and Retry-After header.
  - Cross-user test suite (T13.2): 4/4 tests pass (projects, credentials, documents, runs/reports refuse cross-user access with 404).
  - Credential leak audit (T13.3): 2/2 tests pass (database, logs, API responses contain no plaintext secrets or credentials).
  - Error hardening (T13.4): 2/2 tests pass (missing/invalid LLM key & exhausted provider quota cleanly transition run to FAILED).
  - Structured logging with `run_id` contextvar and sensitive data masking.
  - Demo seed script (`backend/scripts/seed_demo.py`): seeds user, project, credentials, and 11 pgvector chunks.
- Test counts: 88 backend unit/integration tests + 3 SupportDesk tests + 11 frontend tests = 102 automated tests passing cleanly (plus 3 live evals).
- Ruff clean on backend and supportdesk; lint and build clean on frontend.

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
