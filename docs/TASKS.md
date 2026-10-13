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
- [x] 13.1 Rate limiting on login and run creation
- [x] 13.2 Cross-user access test suite
- [x] 13.3 Credential-leak audit
- [x] 13.4 Structured logs with run ID
- [x] 13.5 Graceful LLM and rate-limit error handling
- [x] 13.6 README, seed scripts
- [x] 13.7 Demo rehearsal and backup recording
- [x] 13.8 Fresh-clone setup test

## Worker Timeout, Stuck-Run, and Cleanup Hardening
- [x] Part 1: arq worker timeout set to `RUN_TIMEOUT_SECONDS + 300` (2100s), single try `max_tries = 1`, `retry_jobs = False`, and in-job graceful timeout via `asyncio.wait_for` (D-026)
- [x] Part 2: Shielded run finalization `_finalize_run` on ANY exit setting status to FAILED/CANCELLED with descriptive error, marking unfinished tests BLOCKED, creating partial report, releasing Redis lock, clearing progress keys, closing MCP process (D-027)
- [x] Part 3: Per-tool non-blocking timeouts (45s nav, 30s actions/screenshots), Windows process tree termination via `taskkill /F /T /PID` (and POSIX SIGKILL), MCP restart on timeout, tests marked FAILED with ENVIRONMENT_FAILURE, clean teardown of child processes (D-028)
- [x] Part 4: Redis worker heartbeats (`worker_heartbeat:{run_id}`, TTL=60s, 15s refresh), dead worker detection (>90s without heartbeat marked FAILED with "Worker stopped responding") in GET /runs/{id} and startup sweep, frontend timer stopped on terminal states (D-029)
- [x] Part 5: Queue isolation with `TEST_REDIS_URL` in DB 1, `run_id` only payload, worker uses configured `DATABASE_URL` instead of job payload, missing run skipped cleanly with single short warning (D-030)
- [x] Part 6: LLM per-request timeout (`LLM_REQUEST_TIMEOUT_SECONDS=60.0`), fast daily-quota 429 fallback bypassing retry loops, test marked BLOCKED with ENVIRONMENT_FAILURE on provider failure, run aborted early on 2 consecutive provider failures (D-031)
- [x] Part 7: Embedding model singleton in `_process_model_cache` loaded once per worker process, preloaded on worker startup in `WorkerSettings.on_startup` (D-032)

## False 28s Timeout Bug, Preflight Checks, and Honest State Reporting
- [x] Part 1: Root cause analysis of real run `aced260c-f088-4589-85d0-ab96f6e01ddf` (cold launch Playwright MCP handshake timeout mislabeled as whole-run deadline), DB check, inner timeout reproduction
- [x] Part 2: Live browser smoke test `backend/scripts/smoke_browser.py` without LLM calls, MCP process cwd resolution and handshake timeout hardening (D-033)
- [x] Part 3: Monotonic whole-run deadline mechanism, inner timeout isolation with ENVIRONMENT_FAILURE, sanitized error message and traceback logging (D-035)
- [x] Part 4: Fast preflight checks before planning (target reachability, MCP initialize handshake, credential decryption) with fail-fast user guidance (D-034)
- [x] Part 5: Honest run state in backend and frontend (preserve real failed_stage, stepper red on failed stage, not-run test reasons, start-new-run button, separate summary tiles) (D-035)
- [x] Part 6: Consolidated single INFO line for worker startup stale job skipping, unified `project_run_lock:{project_id}` key name and documented manual cleanup commands (D-036)

## Playwright MCP Preflight Hardening, Loop Redesign, and Coverage Hardening
- [x] Part 1: Diagnose under worker conditions (`backend/scripts/preflight_only.py`, event loop verification, package pinning verification)
- [x] Part 2: Reliable MCP startup (cold-start budget 45s, automatic retry, single browser start handoff, RSS logging, local_files_only embedding load, D-037)
- [x] Part 3: Honest error messages (exception class name, elapsed time, budget, hints, sanitized secret values, test cases)
- [x] Part 4: Documentation and instructions cleanup (reconcile lock TTL, replace passwords with placeholders, update MEMORY.md, DECISIONS.md, TEST_PLAN.md, TASKS.md)
## Execution Details, Failure Fields, Trustworthy Verdicts, and Ground-Truth Verification
- [x] Part 1: Diagnose run 85109bf4-7983-405b-baa6-b7074bb717e9, trace data path, field name mismatches, reproduce with failing tests
- [x] Part 2: Show real execution details on TestRunPage and ReportPage (checks, timeline, observations, evidence quote, screenshot thumbnails, authenticated evidence endpoint)
- [x] Part 3: Deterministic expected & observed failure fields, analyst retry with fallback, distinction between PRODUCT_BUG and TEST_FAILURE (no "update test script")
- [x] Part 4: Planner single-role targeting, 1-4 checks per test, MAX_TESTS_PER_RUN=12 default based on measured 3.125 calls/test, quota math in D-039
- [x] Part 5: Action validation before execution (re-prompt once), per-check finish action evidence verification, negative check after-state attempt verification, trustworthy test verdicts (PASSED/FAILED/BLOCKED)
- [x] Part 6: Seed 5 realistic tickets in SupportDesk target, update requirements appendix, test seed and defect toggles
- [x] Part 7: Scripted real-browser ground-truth check against SupportDesk on port 8001 (defects on and off), verified all 7 scenarios match ground-truth
- [x] Part 8: Housekeeping (health check URL doc fix, Docker-free instructions, MEMORY/DECISIONS/TASKS/TEST_PLAN updates, total live LLM calls tracking in summary and UI)

## Screenshot Evidence Reliability & SupportDesk Unplanted Bug Investigation
- [x] Part 1: Diagnose run 5b6c8f3b-9d37-43ef-9e23-5ead94efe085 end-to-end (cwd-dependent STORAGE_DIR, MCP cwd mcp/node_modules, playwright-mcp-server timestamp appending, unverified DB paths, unauthenticated img tag, SupportDesk status parameter shadowing FastAPI status module causing 500)
- [x] Part 2: Make screenshot capture reliable (centralized screenshot_storage.py, absolute path from ROOT_DIR, viewport-sized captures, test-end and failure-moment captures, base64 and timestamp normalization, 8-byte PNG magic + size validation on disk, non-fatal screenshot errors, password field masking, D-040)
- [x] Part 3: Serve and show screenshots securely (GET /runs/{run_id}/screenshots/{filename} with ownership check returning 404, regex validation, directory traversal prevention, Cache-Control header, frontend authenticated blob fetch with object URL and unmount revoke, enlarged modal view, fallback message with reason, side-by-side failure and final screenshots)
- [x] Part 4: Automated tests (unit tests for CWD independence, base64 decoding, disk validation, non-fatal errors; API tests for owner 200, cross-user 404, traversal rejection; real Playwright MCP ground-truth browser test asserting all PNGs on disk >= 1000 bytes served with HTTP 200 with defects ON and OFF; frontend vitest suite for loading, success, 404, and no-path states)
- [x] Part 5: SupportDesk 500 investigation and fix (fixed status parameter shadowing in supportdesk/app/main.py with status_code=303, preserved 3 planted defects, added correct/defective build tests, reseeded supportdesk.db)
- [x] Part 6: Housekeeping (verified storage/ in .gitignore, README.md screenshot section, SCREENSHOT_RETENTION_DAYS=14 with startup cleanup, updated MEMORY.md, DECISIONS.md, TASKS.md, TEST_PLAN.md)

