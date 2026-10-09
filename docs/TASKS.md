# TASKS: TestPilot AI

Status key: [ ] not started, [~] in progress, [x] done, [!] blocked.
Update after every task. Only one phase is in progress at a time. Details for each phase are in IMPLEMENTATION.md; tests are in TEST_PLAN.md.

## Phase 1: Foundation
- [x] 1.1 Create repo structure and .gitignore
- [x] 1.2 Initialize backend uv project and add core dependencies
- [x] 1.3 Settings loader from .env and .env.example (all names from RULES.md section 6)
- [x] 1.4 FastAPI app with GET /health
- [x] 1.5 Async SQLAlchemy engine, Alembic init, pgvector extension migration
- [x] 1.6 Redis client and health check
- [x] 1.7 Vite React placeholder app
- [x] 1.8 README with local run commands
- [x] 1.9 Phase 1 tests pass

## Phase 2: Authentication Backend
- [x] 2.0 Test database setup (testpilot_test with NullPool, truncation, dependency override)
- [x] 2.1 User and UserSession models, migration
- [x] 2.2 Password hashing (argon2-cffi async) and JWT helpers (HS256, required claims)
- [x] 2.3 Register and login endpoints
- [x] 2.4 Current-user dependency with revocation check
- [x] 2.5 Me and logout endpoints
- [x] 2.6 Phase 2 tests pass (T2.1–T2.10)

## Phase 3: Project Management Backend
- [x] 3.1 Project and ProjectCredential models, migration
- [x] 3.2 Target URL validator (scheme, private-address blocking, allowlist)
- [x] 3.3 Credential encryption helper
- [x] 3.4 Project CRUD with owner scoping
- [x] 3.5 Credential endpoints
- [x] 3.6 Phase 3 tests pass

## Phase 4: Frontend Auth and Project Shell
- [x] 4.1 Router, protected routes, API client
- [x] 4.2 AuthContext
- [x] 4.3 Shared components and design tokens
- [x] 4.4 Login and Register screens
- [x] 4.5 Dashboard with project list and project dialog
- [x] 4.6 Project page shell
- [x] 4.7 Empty, loading and error states
- [x] 4.8 Phase 4 tests pass

## Phase 5: Document Upload and Extraction
- [x] 5.1 Document model, migration
- [x] 5.2 Storage module with interface
- [x] 5.3 Upload validation (type, size, safe names)
- [x] 5.4 Extractors (PDF, TXT, Markdown, JSON)
- [x] 5.5 List and delete endpoints
- [x] 5.6 Dropzone and document list in UI
- [x] 5.7 Phase 5 tests pass

## Phase 6: RAG Pipeline
- [x] 6.1 DocumentChunk model with vector(384), migration
- [x] 6.2 Chunking function
- [x] 6.3 Local embedder module (loaded once)
- [x] 6.4 Index on upload, delete on document delete
- [x] 6.5 Project-scoped retrieval
- [x] 6.6 Redis retrieval cache with invalidation
- [x] 6.7 Phase 6 tests pass

## Phase 7: SupportDesk Demo App (can run in parallel after Phase 1)
- [x] 7.1 Separate uv project and FastAPI app skeleton
- [x] 7.2 Login, roles, seeded users from env
- [x] 7.3 Ticket create, view, search, filter
- [x] 7.4 Status update, assign, delete (admin only), logout
- [x] 7.5 Defect switch SUPPORTDESK_DEFECTS with the three defects
- [x] 7.6 Write SUPPORTDESK_REQUIREMENTS.md
- [x] 7.7 Phase 7 tests pass (correct build and defective build)

## Phase 8: Agent Foundation
- [x] 8.1 TestRun, TestCase, TestResult, Failure models, migration
- [x] 8.2 Agent state model and LangGraph graph with stub nodes
- [x] 8.3 Postgres checkpointer
- [x] 8.4 arq worker and job
- [x] 8.5 Start-run endpoint with duplicate lock
- [x] 8.6 Status updates (Postgres and Redis), get, list endpoints
- [x] 8.7 Cancel flag and endpoint
- [x] 8.8 Failure handling to FAILED
- [x] 8.9 Phase 8 tests pass

## Phase 9: Planner Agent
- [x] 9.1 LLM provider module (primary, fallback, retry, rate limiting)
- [x] 9.2 Verify and record current free models and limits in DECISIONS.md
- [x] 9.3 Retrieval node
- [x] 9.4 Planner prompt and Pydantic test-case schema
- [x] 9.5 Validation with one retry
- [x] 9.6 Persist test cases, enforce MAX_TESTS_PER_RUN
- [x] 9.7 Phase 9 tests pass

## Phase 10: Executor with Playwright MCP
- [x] 10.1 Pinned Playwright MCP launch over stdio and client wrapper
- [x] 10.2 Tool allowlist
- [x] 10.3 Executor node (one test at a time, step budget, timeout)
- [x] 10.4 Role-based login from stored credentials
- [x] 10.5 Evidence capture (action log, observations, screenshots)
- [x] 10.6 Result schema and persistence
- [x] 10.7 Credential redaction in logs and action logs
- [x] 10.8 Phase 10 tests pass

## Phase 11: Failure Analyst and Report
- [x] 11.1 Analyst prompt and schema
- [x] 11.2 Analyst node (failed tests only), persist Failure
- [x] 11.3 Report node and report JSON
- [x] 11.4 Report endpoint and evidence endpoint
- [x] 11.5 Phase 11 tests pass (defective and correct builds)

## Phase 12: Run and Report Frontend
- [x] 12.1 useRunStatus hook
- [x] 12.2 Test Run page (stepper, progress, plan, results, activity feed, cancel)
- [x] 12.3 Report page (tiles, severity, failures, screenshots)
- [x] 12.4 Run history on Project page
- [x] 12.5 Banners and all states
- [x] 12.6 Phase 12 tests pass and manual end-to-end check

## Phase 13: Hardening and Demo Readiness
- [ ] 13.1 Rate limiting on login and run creation
- [ ] 13.2 Cross-user access test suite
- [ ] 13.3 Credential-leak audit
- [ ] 13.4 Structured logs with run ID
- [ ] 13.5 Graceful LLM and rate-limit error handling
- [ ] 13.6 README, seed scripts
- [ ] 13.7 Demo rehearsal and backup recording
- [ ] 13.8 Fresh-clone setup test

## Blocked / Deferred
(none yet)
