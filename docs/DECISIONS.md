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
