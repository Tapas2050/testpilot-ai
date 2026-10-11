# DECISIONS: TestPilot AI

Format: ID, status, context, decision, consequences. Add a new entry for any change. Never silently edit an accepted decision; mark it Superseded and add a new one.

## D-001 Python tooling with uv
Status: Accepted
Context: User wants a virtual environment with uv and no Docker for now.
Decision: Use uv for backend and SupportDesk environments. No Docker files in the MVP.
Consequences: Postgres, Redis and Node must be installed or provided separately (see D-006). Setup steps go in README.

## D-002 Backend, database, queue
Status: Accepted
Decision: FastAPI, Pydantic v2, PostgreSQL with SQLAlchemy async and Alembic, Redis, arq for background jobs.
Consequences: Runs survive API restarts. arq is lighter than Celery and async-friendly. FastAPI BackgroundTasks rejected because a restart loses the job.

## D-003 LLM providers: Google AI Studio primary, OpenRouter fallback
Status: Accepted (model names to be verified at build time)
Context: User wants free providers, best one primary, both as fallbacks.
Decision: Primary is Google AI Studio with a Gemini Flash-class model. Fallback is an OpenRouter free model that supports tool calling. Both sit behind one interface in agent/llm.py using LangChain chat models with a fallback chain.
Reasoning: Gemini Flash-class models offer reliable tool calling, structured output and large context on a free tier, which suits an agent driving a browser. OpenRouter free models vary in quality and have tighter daily request caps, so they suit a fallback better than a primary.
Consequences:
- Free-tier limits and model names change often. Verify them in Phase 9 task 9.2 and record the result here. Do not rely on numbers from memory.
- Google's free tier may use submitted content to improve its products (verify current terms). Only use demo data (SupportDesk) and never send real customer data. See SECURITY.md.
- Model names live in .env, not in code.

## D-004 Free-tier rate limits are the main execution risk
Status: Accepted
Context: The executor makes many LLM calls per test (roughly one per browser step).
Decision: Default caps MAX_TESTS_PER_RUN=8, MAX_STEPS_PER_TEST=15. Client-side rate limiter below the provider limit, exponential backoff on 429, fallback to the second provider. Keep page-state payloads sent to the model small. Support a run finishing as FAILED with partial results rather than hanging.
Consequences: Runs may be slow. If limits still block the demo, options are fewer tests, a smaller plan, or adding billing credit to one provider. Record any change here.

## D-005 Local embeddings with sentence-transformers
Status: Accepted
Decision: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions), loaded once at worker/API startup.
Consequences: Free, no API calls, works on CPU. First run downloads the model. The torch dependency is large; use the CPU build to keep installs smaller. Vector column dimension is 384 and must change with the model.

## D-006 Postgres and Redis without Docker (Windows 11, local only)
Status: Accepted
Context: Host is Windows 11. Nothing is hosted; everything runs locally. PostgreSQL is already installed. Redis is NOT built into Windows and must be installed.
Decision:
- Postgres: existing local install. The pgvector extension is a separate add-on and is not bundled with the standard Windows installer. Check with: SELECT * FROM pg_available_extensions WHERE name = 'vector'; (empty result means it is not installed). If missing, either install a pgvector build matching the local Postgres major version, or use a free hosted Postgres with pgvector for the database only.
- Redis: run it inside WSL2 (Ubuntu) and connect from Windows at localhost:6379. Alternative: Memurai, a Windows-native Redis-compatible server. Verify current install steps and licensing at setup time.
Consequences: README must contain Windows setup steps. Phase 1 must verify pgvector and Redis connectivity before any other work. arq on Windows must be verified in Phase 8; if it misbehaves, run the worker inside WSL2 as well.

## D-007 Deployment: local first, public optional
Status: Accepted
Decision: Demo runs locally. If public access is needed, expose the local app through a tunnel rather than hosting it.
Reasoning: Playwright needs a real browser and memory, which free hosting tiers handle poorly; the demo is more reliable locally.
Consequences: Public hosting is deferred and needs its own decision entry.

## D-008 Playwright MCP launched over stdio
Status: Accepted
Decision: The Python MCP client starts the Playwright MCP server (Node) as a child process over stdio, pinned to a specific version.
Consequences: No separate server process to manage. Requires Node. The executor gets only an allowlist of browser tools.

## D-009 Vector store: pgvector
Status: Accepted
Decision: Store embeddings in Postgres with pgvector.
Consequences: One fewer service. Requires the extension on whatever Postgres is used.

## D-010 Authentication and logout
Status: Accepted
Decision: JWT access token (60 minutes) with a jti, tracked in a Session table so logout truly revokes it. No refresh tokens in the MVP. Token kept in memory plus sessionStorage for the MVP; revisit httpOnly cookies later.
Consequences: Simple to build; known XSS tradeoff accepted for a local demo.

## D-011 Polling instead of websockets
Status: Accepted
Decision: Frontend polls run status every 2 seconds and stops on a terminal state.
Consequences: Simpler. Server-sent events can replace it later.

## D-012 Test credentials in env
Status: Accepted
Decision: Demo SupportDesk credentials are documented in RULES.md section 6 and moved to .env in Phase 1. User-entered project credentials are encrypted at rest with a Fernet key from .env.
Consequences: API keys are never documented or committed.

## D-013 SupportDesk implementation
Status: Accepted
Decision: Separate FastAPI app with server-rendered templates and SQLite, with a defect switch in env.
Consequences: No extra frontend build. Easy to flip between correct and defective builds for testing.

## D-014 Local file storage
Status: Accepted
Decision: Uploads and screenshots in ./storage, behind a storage interface, UUID filenames, served only through authenticated endpoints.
Consequences: Swappable for S3-compatible storage later.

## D-015 Out of scope: payments, analytics, notifications
Status: Accepted
Decision: None in the MVP. Observability comes from run records and structured logs.

## D-016 Pin Python 3.12 through uv (do not use system Python 3.14)
Status: Accepted
Context: The machine has system Python 3.14.7. Newer Python versions often lack prebuilt packages for heavy dependencies (torch, sentence-transformers, PyMuPDF, asyncpg, langchain stack), which causes slow source builds or install failures.
Decision: Backend and SupportDesk use Python 3.12, installed and managed by uv (uv python install 3.12, .python-version file, requires-python >=3.12,<3.13).
Consequences: Reproducible installs independent of the system Python. If a dependency later proves to support 3.13 or 3.14, change this with a new decision entry. Verify package compatibility at install time rather than assuming.

## D-017 Three-tier LLM fallback chain
Status: Accepted
Context: Free-tier daily quotas and rate limits are the primary execution risk for browser agent runs.
Decision: Primary provider is Google AI Studio with Gemini 3.5 Flash Lite (`gemini-3.5-flash-lite`), secondary fallback is Gemini 3.1 Flash Lite (`gemini-3.1-flash-lite`), tertiary fallback is an OpenRouter free model supporting tool calling.
Consequences: Resilience against transient provider outages and 429 rate limits without manual intervention.

## D-018 Memory budget and worker isolation (8 GB host)
Status: Accepted
Context: Local Windows 11 host with 8 GB RAM and integrated Intel Iris Xe GPU (~83% RAM utilized at idle). Heavy dependencies (PyTorch/sentence-transformers, Playwright Chromium, FastAPI, arq) must not exhaust RAM.
Decision: Run Playwright in headless mode only. Execute one test case at a time. Load sentence-transformers embeddings in the arq background worker process only, never in the API server web process.
Consequences: Peak RAM during testing stays within available physical memory limits without thrashing.

## D-019 Password hashing with argon2-cffi
Status: Accepted
Context: SECURITY.md 2.1 requires passwords hashed with argon2 or bcrypt. Python stdlib PBKDF2 lacks memory-hardness against GPU/ASIC attacks.
Decision: Use `argon2-cffi` (pinned) instead of PBKDF2. Run hashing and verification inside `asyncio.to_thread` so the async event loop is never blocked. Compute a single dummy hash at application startup and verify against it when a login email does not exist to mitigate timing attacks.
Consequences: Adds `argon2-cffi` dependency. Event loop stays responsive under high login traffic. Non-existent email lookups have indistinguishable response latency from wrong password checks.

## D-020 Postgres checkpointer on Windows using PostgresSaver and psycopg-binary
Status: Accepted
Context: On Windows, Python's default asyncio event loop is `ProactorEventLoop`. `psycopg` async does not support `ProactorEventLoop` (raises error asking for `SelectorEventLoop`).
Decision: Use synchronous `PostgresSaver` backed by a `psycopg_pool.ConnectionPool(kwargs={'autocommit': True})` wrapped with thread-safe execution or `asyncio.to_thread`.
Consequences: LangGraph graph persistence works reliably across Windows asyncio event loops without altering global event loop policies.

## D-021 Verified LLM model names and limits for Phase 9
Status: Accepted
Context: Task 9.2 requires verifying and recording active free models, structured output reliability, tool-calling capability, and rate limits.
Decision: Primary model is Google AI Studio `gemini-3.5-flash-lite`, verified via live smoke test with 100% success for structured JSON output and tool-calling. Secondary fallback is `gemini-3.1-flash-lite`. Tertiary fallback is OpenRouter `nvidia/nemotron-3-ultra-550b-a55b:free`. Configured client-side rate limit `LLM_REQUESTS_PER_MINUTE=15` with exponential backoff on transient 429 errors.
Consequences: Complies with PRD and D-003 while staying strictly within free-tier quotas.

## D-022 Pinned Playwright MCP Server via mcp/package.json
Status: Accepted
Context: D-008 and Task 10.1 require launching the pinned Playwright MCP server over stdio from Python. On Windows, executing npx.cmd dynamically inside async subprocess pipes can lead to interactive prompt deadlocks or network download overhead during test executions.
Decision: Pin `@executeautomation/playwright-mcp-server@1.0.12` in `mcp/package.json` and execute its entrypoint directly with Node over stdio via `PlaywrightMCPClient`. Default to fast mock MCP client during automated Pytest runs unless marked for live evaluation.
Consequences: Deterministic, offline-capable execution of Playwright MCP over stdio with zero download latency and no batch-script subprocess deadlocks.

## D-023 Live Execution Events and Progress in Redis
Status: Accepted
Context: During a test run, the frontend needs to display real-time stage progress, current executing test, step count, and a live activity feed without overwhelming the primary PostgreSQL database with high-frequency writes for every browser action step.
Decision: Store live step events and execution progress transiently in Redis (`run_events:{run_id}` and `run_progress:{run_id}`). Events are pushed via `rpush`, capped with `ltrim` to the last 100 events, and set with an automatic 24-hour expiration (`expire 86400`). Credentials are redacted in memory prior to pushing. Polling `GET /runs/{id}` returns the aggregated live progress and recent events from Redis during active execution, while persistent final test results and screenshots continue to be committed to PostgreSQL upon step/test conclusion.
Consequences: Zero database migration required; near-zero latency for live activity polling; automatic cleanup via Redis TTL; complete isolation from historical report storage.

## D-024 Fail-Fast on Target Authentication Failures and Executor Loop Detection
Status: Accepted
Context: If target credentials are wrong or missing, previous runs attempted to execute all planned tests, repeatedly submitting login credentials and hanging in loops until timeout.
Decision:
- If a scripted role login fails, immediately mark the test case as BLOCKED with classification AUTHENTICATION_FAILURE without making any LLM calls.
- If two consecutive test cases encounter authentication failure, stop the entire run early as FAILED with a clear notification naming the role and advising the user to verify project credentials in Project Settings. Mark remaining tests as BLOCKED, release the Redis lock, and store the generated report.
- If all executed tests are BLOCKED due to authentication, mark the final run status as FAILED rather than COMPLETED.
- In the executor, detect stuck loops: if the same action, selector, and value repeat 3 times in a row, or the visible page text remains unchanged across 4 consecutive steps, immediately terminate the test as FAILED with 0 further LLM calls.
Consequences: Massive token and time savings; eliminates runaway LLM calls and execution loops; gives instantaneous feedback to the user on incorrect credential configuration.

## D-025 Synchronized Target App Credentials, Lock Expiry Alignment, and Logging
Status: Accepted
Context: Demo target credentials must strictly match the target app without hardcoded secrets, and the worker process needs complete lifecycle logging and aligned timeouts.
Decision:
- Both SupportDesk CRM and TestPilot's demo seeder (`backend/scripts/seed_demo.py`) load credentials and URLs directly from the root `.env` (`SUPPORTDESK_ADMIN_EMAIL`, `SUPPORTDESK_ADMIN_PASSWORD`, `SUPPORTDESK_AGENT_EMAIL`, `SUPPORTDESK_AGENT_PASSWORD`, `SUPPORTDESK_URL`). If passwords are empty, both fail loudly naming the missing variable.
- SupportDesk database reset is provided as a single command `supportdesk/reseed.py`.
- Target login verification script `backend/scripts/check_target_login.py` decrypts in memory and prints ONLY role names and OK/FAIL without leaking any credentials or email addresses.
- Primary model code default is set to `gemini-3.5-flash-lite`, rate limit default to 12 RPM, and `RUN_TIMEOUT_SECONDS` to 1800.
- Redis run lock TTL dynamically scales to `max(RUN_TIMEOUT_SECONDS + 300, 2100)` to ensure locks never prematurely expire during long runs.
- Worker emits structured INFO logs with `[run_id=...]` for every stage change, test start/end, and sanitized executor step, plus total live LLM calls at run completion.
Consequences: Zero credential discrepancies; complete visibility into agent runs; safe lock lifecycles.

## D-026 Worker Job Timeout Alignment, Single-Try Semantics, and Graceful In-Job Timeout
Status: Accepted
Context: An empirical agent run timed out at exactly 300.34s during test 8 of 8 because arq defaults to `job_timeout = 300` seconds (5 minutes) and `max_tries = 5` with `retry_jobs = True`. Furthermore, failed/cancelled runs were subject to automatic arq retries from scratch, repeating browser interactions, LLM token consumption, and target mutations.
Decision:
- Configure `WorkerSettings.job_timeout = settings.RUN_TIMEOUT_SECONDS + 300` (default 2100s).
- Configure `WorkerSettings.max_tries = 1` and `WorkerSettings.retry_jobs = False`. An AI agent test run has non-idempotent side effects across browser sessions, target databases, and user reports; runs must never be silently re-executed from scratch on failure or cancellation.
- Enforce `RUN_TIMEOUT_SECONDS` (default 1800s) gracefully inside the job (`execute_agent_run` and `run_agent_job`) using `asyncio.wait_for`. When the in-job limit is reached, an in-job `asyncio.TimeoutError` triggers graceful cleanup: updating the run to FAILED with error message `"Run exceeded the time limit of N seconds"`, marking remaining tests BLOCKED, releasing Redis locks, and closing MCP processes.
- The 300-second delta (`job_timeout` minus `RUN_TIMEOUT_SECONDS`) guarantees that arq's hard process-level kill is strictly a last resort if graceful finalization hangs.

## D-027 Guaranteed Shielded Run Finalization on Any Exit
Status: Accepted
Context: If a worker was cancelled, encountered an unhandled exception, or timed out, the run remained stuck in EXECUTING, test results were lost, the Redis duplicate-run lock remained forever, and headless Chromium/node MCP subprocesses were orphaned.
Decision: Wrap agent run execution in `_finalize_run(run_id, project_id, ...)` protected by `asyncio.shield` so finalization cannot be aborted by cancellation. On any non-completed exit, finalization:
- Updates run status to FAILED (or CANCELLED if user-initiated) with an explicit, human-readable error message.
- Marks any unfinished/running test cases as BLOCKED.
- Assembles and persists a partial mathematical report based on tests completed so far.
- Releases the project Redis run lock (`lock:run:{project_id}`).
- Clears live progress keys (`run_events:{run_id}` and `run_progress:{run_id}`).
- Gracefully terminates and closes any active Playwright MCP client and browser process.
Consequences: Runs never remain stuck in EXECUTING; orphaned locks are eliminated; partial test evidence is preserved.

## D-028 Per-Tool MCP Timeouts and Windows Process Tree Termination
Status: Accepted
Context: Blocking MCP tool calls executed via `asyncio.to_thread` could hang indefinitely when the target application lagged or deadlocked, because thread blocking cannot be stopped by asyncio cancellation.
Decision:
- Enforce per-tool non-blocking timeouts: navigation 45s, screenshots 30s, other browser actions 30s (all configurable).
- On timeout, immediately terminate the entire MCP child process tree using `taskkill /F /T /PID` on Windows and `SIGKILL` process-group termination on POSIX.
- Automatically restart the MCP client for the next test.
- Classify timed-out tests as FAILED with `ENVIRONMENT_FAILURE` and proceed to subsequent tests.
- Close and terminate all MCP processes on worker teardown.
Consequences: Stuck browser interactions cannot hang tests or runs; zero orphaned node/Chromium processes left behind.

## D-029 Redis Worker Heartbeats and Dead Run Auto-Detection
Status: Accepted
Context: If a worker process crashed, was SIGKILL'ed, or lost power, the database maintained active status (EXECUTING/PLANNING) indefinitely, while the frontend timer ran indefinitely.
Decision:
- Workers refresh a Redis heartbeat key `worker_heartbeat:{run_id}` with TTL=60s every 15 seconds during active execution.
- `GET /runs/{id}` and an application startup sweep check active runs: if older than 90s and missing a heartbeat key, the run is immediately marked FAILED with `"Worker stopped responding"`, the lock is released, and keys cleared.
- The frontend `TestRunPage.jsx` stops the elapsed timer at any terminal state (COMPLETED, FAILED, CANCELLED) and displays a clear failure banner.
Consequences: UI never displays dead workers as active; stale runs self-heal immediately on access or restart.

## D-030 Test Redis Isolation and Worker Database Independence
Status: Accepted
Context: Automated test runs previously enqueued jobs into the production Redis DB 0 carrying the test database URL (`testpilot_test`). After pytest finished and truncated test tables, external workers picked up the job and crashed with `relation "test_runs" does not exist` or masked password errors.
Decision:
- Added `TEST_REDIS_URL` in `.env.example` and `config.py` pointing to Redis DB 1 (`redis://localhost:6379/1`).
- Enforced assertions in `conftest.py` ensuring the test suite connects only to Redis DB 1 and never touches DB 0.
- Jobs carry `run_id` only; workers always use their own configured `DATABASE_URL`, never accepting a DB URL from job payloads.
- If a worker dequeues a run ID that does not exist in the database, it logs a single short warning and skips the job without a crash or stack trace.
Consequences: Total queue isolation between test runs and live workers; eliminates cross-database pollution and table-missing crashes.

## D-031 LLM Per-Request Timeout, Fast Daily-Quota Fallback, and Environment Failure Handling
Status: Accepted
Context: LLM providers could hang without per-request timeouts, and daily quota exhaustion (HTTP 429 `RESOURCE_EXHAUSTED` / `Queries per day`) triggered slow exponential backoff retry loops (3 attempts over tens of seconds) before failing over to the fallback chain. Furthermore, provider outages did not cleanly abort the run.
Decision:
- Added `LLM_REQUEST_TIMEOUT_SECONDS = 60.0` in `config.py` and `.env.example`, applied to `ChatGoogleGenerativeAI(timeout=...)` and `ChatOpenAI(request_timeout=...)`.
- Intercepted retry predicates in Google GenAI and OpenAI clients: daily-quota errors immediately bypass retries and fall back to the next model without delay.
- If all providers fail on a test step, mark the test BLOCKED with `ENVIRONMENT_FAILURE`.
- If two consecutive tests fail due to LLM provider failure, abort the run early as FAILED with a clear notification naming the likely cause (quota or provider outage).
Consequences: Fast fallback on quota exhaustion; runs fail-fast cleanly when LLM services are unavailable.

## D-032 Process-Level Singleton Embedding Model in Worker
Status: Accepted
Context: The worker re-instantiated `LocalEmbedder` on every job, reloading PyTorch model weights from disk and logging "Loading weights" repeatedly.
Decision:
- Made `get_embedding_model` cache model instances in a module-level dictionary `_process_model_cache` keyed by model name.
- Configured arq `WorkerSettings.on_startup = worker_startup` to preload the embedding model once when the worker process boots.
Consequences: PyTorch weights loaded exactly once per worker process; eliminates redundant disk I/O and job startup latency.

## D-033 MCP Subprocess CWD and Handshake Resiliency on Windows
Status: Accepted
Context: On Windows 11, cold startup of `@modelcontextprotocol/server-playwright` via npx took up to ~15-20 seconds. The client process lacked an explicit `cwd` parameter causing path resolution delays, and the handshake timeout was set to 15.0s, causing the cold start to time out after ~15-28s.
Decision:
- Added explicit `cwd=str(mcp_cwd)` pointing to repo root `node_modules` during subprocess creation.
- Increased handshake timeout from 15.0s to 25.0s with clean stdin pipe closure to prevent `BrokenPipeError` on Windows.
- Created standalone live smoke test `backend/scripts/smoke_browser.py` verifying MCP launch, SupportDesk `/login` navigation, screenshot capture, and clean zero-orphan process termination in ~10 seconds.
Consequences: Playwright MCP starts cleanly on Windows 11 with 0 child process leaks.

## D-034 Fast Preflight Checks Before Planning Stage
Status: Accepted
Context: When target URLs were down, MCP servers misconfigured, or credential encryption keys mismatched, runs consumed LLM tokens generating test plans before failing in execution with misleading BLOCKED test states.
Decision:
- Worker executes `run_preflight_checks()` within ~1-3s (max 10s) prior to the planning node.
- Validates: (1) target URL reachability via SSRF-safe HTTP request, (2) Playwright MCP launch and handshake, (3) project credential decryption.
- If preflight fails, terminates immediately as FAILED with stage `"preflight"`, action-oriented guidance for the user, and zero LLM calls or misleading BLOCKED tests.
Consequences: Saves LLM tokens; provides immediate diagnostic feedback when dependencies or targets are offline.

## D-035 Honest Terminal Run States and Failure Attribution
Status: Accepted
Context: Failed runs previously had their stage overwritten with the string "FAILED", stepper marked Queued as failed, and tests that never ran were shown as finished or BLOCKED with no explanation. Inner timeouts were misattributed as run deadline timeouts.
Decision:
- Preserved real active stage on failure in `test_runs.failed_stage` column and Redis cache.
- Stepper marks the true failed stage in red while keeping earlier stages ticked; failed banner displays real cause and actionable hint.
- Added monotonic deadline check (`time.monotonic() >= deadline - 0.1`) so run timeout message is raised ONLY when total duration genuinely exceeded `RUN_TIMEOUT_SECONDS`.
- Tests that never ran due to early run failure are marked `BLOCKED` with reason `"Not executed: run stopped (<cause>)"`.
- Progress counts only tests that actually completed execution. Added "Start a new run" button to failed run banner.
Consequences: UI reflects exact failure stage and reason; test results clearly delineate executed vs skipped tests.

## D-036 Unified Redis Operational Key Patterns and Stale Job Startup Draining
Status: Accepted
Context: Inconsistent lock key names (`run_lock` vs `project_run_lock`) existed across documentation, and worker startup logged individual warnings for every stale queued job.
Decision:
- Standardized all lock operations and documentation to `project_run_lock:{project_id}`.
- Documented exact key patterns and manual `redis-cli del` commands for lock, heartbeat, progress, status, and event keys in `docs/MEMORY.md`, `docs/RULES.md`, and `README.md`.
- `worker_startup` inspects the arq queue and logs a single consolidated INFO message listing the number of stale jobs skipped.
Consequences: Accurate operator documentation and clean, uncluttered worker startup logs.

## D-037 Playwright MCP Startup Hardening, Cold-Start Preflight Budget, and Single Browser Launch
Status: Accepted
Context: Run 4cef9022-ed1e-417e-9053-552be3eb165f failed in preflight after ~12s with `PreflightCheckError: Playwright MCP server could not start or complete handshake (). Check Node.js and Playwright installation.` The previous preflight had a hardcoded 8.0s timeout, which failed on Windows 11 with 8GB RAM where cold MCP startup takes 15-28s under memory pressure after preloading embeddings (~520MB RSS). The underlying exception was `asyncio.TimeoutError`, whose string representation is empty, causing empty parentheses `()`. In addition, the run was starting the browser twice (once in preflight, then again in execute_node).
Decision:
- Package verification: `@executeautomation/playwright-mcp-server` pinned to `1.0.12` in `mcp/package.json` is installed and launched directly using `node` and entrypoint `mcp/node_modules/@executeautomation/playwright-mcp-server/dist/index.js` with `cwd=mcp`. No npx, no cmd shell, no runtime downloads.
- Introduced configurable `MCP_STARTUP_TIMEOUT_SECONDS = 45.0` in `config.py` separate from quick checks (target reachability ~5s, credential decryption ~2s). Overall preflight limit is the sum of these checks.
- Added automatic single retry if the initial MCP startup attempt times out or fails.
- Reused preflight MCP client: preflight returns the started MCP client which is registered in `_active_mcp_clients[run_id]`. `execute_node` reuses the live client without starting a second browser instance. Cleanup is guaranteed on every exit path by `_finalize_run` and `execute_node` finally block.
- Fast local embedding load: `get_embedding_model` uses `local_files_only=True` to skip Hugging Face Hub online checks, dropping preload time from ~19s to ~0.5s.
- Log process memory (RSS) at worker startup and during preflight checks.
- Honest error reporting: `format_exception_summary` formats exceptions with class name, elapsed time, budget, and replaces empty messages with 'no detail', guaranteeing zero empty parentheses `()`.
Consequences: High reliability during cold start on memory-constrained systems; eliminates redundant browser starts; produces crystal-clear diagnostic failure messages.




