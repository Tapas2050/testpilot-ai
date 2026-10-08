# IMPLEMENTATION: TestPilot AI

This file combines the technical requirements and the phased build plan. Read RULES.md first. Track progress in TASKS.md. Record deviations in DECISIONS.md.

No code is included here. Phases are ordered and sized so a coding agent can finish one without touching unrelated parts of the codebase.

## A. Technical Summary

Platform: web app, run locally (public access optional later, see D-007).
Python environment: uv (virtual environment and dependency management). No Docker for now.

Stack
- Backend: Python, FastAPI, Pydantic v2
- Database: PostgreSQL with pgvector, SQLAlchemy async, Alembic
- Cache and job broker: Redis
- Background jobs: arq worker
- Agent orchestration: LangGraph with Postgres checkpointer
- Browser automation: Playwright MCP server (Node, launched over stdio by the Python MCP client, version pinned)
- LLM: Google AI Studio (Gemini, primary) with OpenRouter free model (fallback), behind one provider interface
- Embeddings: local Hugging Face sentence-transformers model (all-MiniLM-L6-v2, 384 dimensions)
- PDF parsing: PyMuPDF
- Frontend: React with Vite, React Router, AuthContext
- Demo target: SupportDesk, a separate small FastAPI app with server-rendered templates and SQLite
- Tests: pytest, pytest-asyncio, httpx (backend); Vitest and React Testing Library (frontend)

Prerequisites on the machine
- Python 3.11 or newer, uv
- Node.js (LTS) for Vite and Playwright MCP
- PostgreSQL with pgvector (local install or a free hosted instance) and Redis (local install). See D-006.
- API keys: Google AI Studio key, OpenRouter key

## B. Backend Architecture
Layers: routers (thin) -> services -> models/repositories. Agent code lives in its own package and is never imported by route handlers except through AgentService / TestRunService.

Services: AuthenticationService, ProjectService, DocumentService, RAGService, TestRunService, AgentService, ReportService.

Run execution: the API creates a TestRun in QUEUED, enqueues an arq job, and returns run_id immediately. The worker runs the LangGraph graph. Each node updates status and stage in Postgres and the cached status in Redis. Any exception is caught, stored on the run, and moves it to FAILED.

Cancellation: a cancel flag in Redis, checked between nodes and between tests.

Guardrails (all configurable in .env): MAX_TESTS_PER_RUN, MAX_STEPS_PER_TEST, TEST_TIMEOUT_SECONDS, RUN_TIMEOUT_SECONDS, MAX_UPLOAD_MB.

## C. Frontend Architecture
Six screens per DESIGN.md. AuthContext holds user and token; all other state is local. API client module wraps fetch. Hooks: useAuth, useProjects, useRunStatus (polls every 2 seconds, stops on a terminal state). Protected routes redirect to Login.

## D. Database Schema (logical)
- User: id, email (unique), password_hash, created_at
- Session: id, user_id, token_id (jti), expires_at, revoked_at
- Project: id, user_id, name, description, target_url, created_at, updated_at
- ProjectCredential: id, project_id, role_label, username, password_encrypted
- Document: id, project_id, original_name, stored_name, file_type, size_bytes, extraction_status, extracted_text, created_at
- DocumentChunk: id, document_id, project_id, chunk_index, content, embedding (vector 384)
- TestRun: id, project_id, status, agent_stage, started_at, ended_at, error_message, summary (JSON), langgraph_thread_id, report (JSON)
- TestCase: id, run_id, test_key, title, description, preconditions, steps (JSON), expected_result, priority, source_requirement
- TestResult: id, test_case_id, status (PASSED, FAILED, BLOCKED), action_log (JSON), observations, error_info, evidence_paths (JSON), started_at, ended_at
- Failure: id, test_result_id, classification, severity, confidence, expected_behavior, observed_behavior, explanation, suggested_action

Relationships: User 1-N Project; Project 1-N Document; Project 1-N TestRun; TestRun 1-N TestCase; TestCase 1-1 TestResult; TestResult 0-1 Failure.

## E. API
Auth: POST /auth/register, POST /auth/login, GET /auth/me, POST /auth/logout
Projects: POST /projects, GET /projects, GET /projects/{id}, PATCH /projects/{id}, DELETE /projects/{id}
Credentials: POST/GET/DELETE /projects/{id}/credentials
Documents: POST /projects/{id}/documents, GET /projects/{id}/documents, DELETE /documents/{id}
Runs: POST /projects/{id}/runs, GET /runs/{id}, GET /projects/{id}/runs, POST /runs/{id}/cancel
Reports: GET /runs/{id}/report
Evidence: GET /runs/{id}/evidence/{file} (authenticated)
Health: GET /health

## F. Suggested Folder Structure
```
testpilot/
  README.md
  .env.example
  .gitignore
  backend/
    pyproject.toml            (uv project)
    app/
      main.py
      core/                   (config, security, database, redis)
      models/
      schemas/
      api/                    (auth, projects, documents, runs, reports)
      services/
      agent/
        graph.py
        state.py
        llm.py                (provider interface, primary + fallback)
        mcp_client.py
        nodes/                (retrieve, planner, executor, analyst, reporter)
        prompts/
        schemas/
      worker/
    migrations/
    tests/
  frontend/
    src/ (api, context, hooks, components, pages, routes)
  supportdesk/
    pyproject.toml
    app/ (templates, routes, db, defect flags)
  storage/                    (git-ignored: uploads, screenshots)
  docs/                       (these planning files)
```

## G. Build Phases

### Phase 1: Foundation
Objective: running skeleton, config, database connectivity.
Features: none user-facing.
Tasks: repo and folders; uv project for backend; settings loader reading .env; .env.example with all variables from RULES.md section 6; .gitignore; FastAPI app with GET /health; async SQLAlchemy engine; Alembic initialized; Redis client; enable pgvector extension via migration; Vite React app showing a placeholder; README with run commands.
Dependencies: Postgres, Redis, Node, uv installed.
Testing: health test; DB and Redis connectivity check.
Completion: backend starts with uv run; health returns OK and reports DB and Redis status; frontend dev server loads.

### Phase 2: Authentication Backend
Objective: secure registration, login, protected endpoints.
Tasks: User and Session models and migration; password hashing; register, login, me, logout; JWT with jti; current-user dependency with revocation check.
Dependencies: Phase 1.
Testing: success and failure paths, duplicate email, expired and revoked tokens, no token.
Completion: all auth tests pass; no plaintext passwords stored; logout revokes the token.

### Phase 3: Project Management Backend
Objective: users manage their own projects.
Tasks: Project and ProjectCredential models and migration; CRUD; owner scoping on every query; target URL validation with private-address blocking and configurable allowlist; credential encryption using a key from .env.
Dependencies: Phase 2.
Testing: CRUD; cross-user access returns 404; invalid and private URLs rejected; credentials unreadable in the database.
Completion: all project endpoints tested with ownership enforced.

### Phase 4: Frontend Auth and Project Shell
Objective: usable login, register, dashboard and project dialogs.
Tasks: routing and protected routes; AuthContext; API client; shared components (button, input, card, toast, dialog, badge); Login, Register, Dashboard, Project page shell; empty, loading, error states; design tokens from DESIGN.md.
Dependencies: Phases 2 and 3.
Testing: component tests for auth form and protected route; manual register, login, create project, logout.
Completion: a user can register, log in, create, edit and delete a project in the browser.

### Phase 5: Document Upload and Extraction
Objective: validated uploads with extracted text.
Tasks: Document model and migration; upload endpoint with type and size validation and UUID filenames; storage module behind an interface; extractors for PDF, TXT, Markdown, JSON; list and delete endpoints; dropzone and document list in the UI.
Dependencies: Phases 3 and 4.
Testing: each type extracts; wrong type and oversize rejected; deletion removes file and record; cross-user access blocked.
Completion: uploaded requirements appear in the UI with extraction status.

### Phase 6: RAG Pipeline
Objective: retrieve relevant requirement chunks.
Tasks: DocumentChunk model with vector(384); chunking; local sentence-transformers embedder behind an interface (model loaded once, not per request); index on upload, remove on delete; project-scoped retrieval; Redis cache with expiry and invalidation on document change.
Dependencies: Phase 5.
Testing: a deletion-permission query returns the delete requirement from the SupportDesk requirements; no cross-project results; cache invalidates.
Completion: retrieval is reliable on the SupportDesk requirements.

### Phase 7: SupportDesk Demo App
Objective: controlled target with planted defects.
Tasks: separate uv project; login with admin and support agent roles; create, view, search, filter, update status, assign, delete (admin only), logout; SQLite; seed two users from env; env switch SUPPORTDESK_DEFECTS (off = correct build, on = three defects); write SUPPORTDESK_REQUIREMENTS.md as the document to upload.
Dependencies: Phase 1 only (can be built in parallel).
Testing: correct build satisfies every requirement; defective build shows exactly the three defects.
Completion: both builds behave as specified; requirements file ready.

### Phase 8: Agent Foundation (stub nodes)
Objective: async run through all states without AI.
Tasks: TestRun, TestCase, TestResult, Failure models and migration; agent state model; LangGraph graph with five stub nodes; Postgres checkpointer; arq worker; start-run endpoint with instant return and duplicate-run lock; status in Postgres and Redis; get, list, cancel endpoints; failure handling to FAILED.
Dependencies: Phases 3 and 6.
Testing: instant return; full state progression; forced exception gives FAILED and the API stays up; duplicate blocked; cancel works.
Completion: stubbed run visible through the API with correct statuses and timestamps.

### Phase 9: Planner Agent
Objective: grounded, structured test plans.
Tasks: LLM provider module with primary (Google AI Studio) and fallback (OpenRouter), retry and backoff on rate limits; retrieval node; planner prompt separating instructions from retrieved context, no-invention rule, required source requirement per test; Pydantic test-case schema; validation with one retry; persist test cases; enforce MAX_TESTS_PER_RUN.
Dependencies: Phase 8.
Testing: schema tests with good and bad output; mocked LLM for determinism; plan on SupportDesk includes the agent-cannot-delete test; tests without a source requirement rejected; fallback triggers when primary fails.
Completion: a run produces a valid, grounded plan saved to the database.

### Phase 10: Executor with Playwright MCP
Objective: execute tests in a real browser.
Tasks: MCP client launching the pinned Playwright MCP over stdio; tool allowlist; executor node, one test at a time, with step budget and timeout; role-based login using stored credentials; capture action log, observations, status, error, screenshots; isolated browser context per run; untrusted-page-content handling; result schema; persist TestResult; keep page-state payloads small to protect free-tier token limits.
Dependencies: Phases 7, 8, 9.
Testing: login test; delete-permission test; screenshots saved; credentials absent from logs and stored action logs; timeout yields a clean status.
Completion: all planned tests execute with recorded evidence.

### Phase 11: Failure Analyst and Report
Objective: classified failures and a final report.
Tasks: analyst node for failed tests only; classification criteria in the prompt; schema (classification, severity, confidence, expected, observed, explanation, suggested action); persist Failure; report node (totals, pass percentage, failure and severity summaries, evidence links, AI analysis); store report JSON; report endpoint; final COMPLETED.
Dependencies: Phase 10.
Testing: defective build yields the planted defects as PRODUCT_BUG; correct build yields none; report math correct; no credentials in report.
Completion: a full run on the defective build yields a correct report with evidence.

### Phase 12: Run and Report Frontend
Objective: start, watch and review runs in the UI.
Tasks: useRunStatus hook; stage stepper and progress; plan display; per-test rows with expandable action logs; activity feed; cancel; failed and cancelled banners; report view with stat tiles, severity summary, failure cards, screenshot viewer; run history on the Project page; all states from DESIGN.md.
Dependencies: Phases 4 and 11.
Testing: manual end-to-end on the defective build; polling stops on terminal states; reopened run matches.
Completion: full demo flow works in the browser.

### Phase 13: Hardening and Demo Readiness
Objective: reliable, safe, demonstrable.
Tasks: rate limiting on login and run creation; cross-user test suite; credential-leak audit of logs and reports; structured logs with run ID; graceful LLM and rate-limit errors; README with setup; seed scripts; rehearsal of the demo; backup screen recording.
Dependencies: Phase 12.
Testing: repeated full runs; bad URL and missing-key cases give meaningful FAILED states; fresh-clone setup test.
Completion: demo runs from a clean setup following README only; PRD success criteria met.

## H. Build Order Note
Phases 1 to 5 and 7 form a working non-AI product. Phases 6, 8 to 11 are the AI core. Phase 12 makes it presentable.
