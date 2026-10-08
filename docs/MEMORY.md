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
- Current phase: Phase 1 complete (Foundation)
- Last completed task: 1.9
- Next task: 2.1 (Phase 2: Authentication Backend)
- Date of last update: 2026-10-09

## 4. Environment Facts (verified)
- Hardware: 8 GB RAM (about 83% used at idle), Intel Iris Xe integrated GPU, no dedicated GPU. Ollama installed with qwen3:1.7b only (not used by project, D-003). Memory budget rules in D-018.
- Host OS: Windows 11. Postgres 18.6 installed locally; pgvector 0.8.5 installed and active in database `testpilot`. Alembic migration `3ef571d8a202_enable_vector_extension` applied.
- Redis installed in WSL2 Ubuntu, reachable at `redis://localhost:6379/0` (verified live ping in Python). Requires `sudo service redis-server start` in WSL terminal.
- Verified on host: uv 0.12.8, Python 3.12.14 pinned via `uv` (system Python 3.14 bypassed), Node v24.19.0, npm 11.17.0, Git 2.55.0.
- Vite 8.3.4 + React in `frontend/`.
- All Phase 1 tests (T1.1, T1.2) pass with 6/6 test cases.

## 5. Conventions in Use
- uv project inside `backend/` with `[tool.uv] package = false`.
- Settings loaded with `pydantic-settings` from `.env` in repo root.
- SQLAlchemy async engine configured with `NullPool` to prevent cross-event-loop connection pool leakage in pytest async test runner.
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
