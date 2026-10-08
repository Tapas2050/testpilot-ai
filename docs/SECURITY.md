# SECURITY: TestPilot AI

Scope: local MVP with optional tunnel exposure. The product drives a real browser and sends content to third-party LLMs, so the main risks are SSRF, prompt injection, credential leakage and unsafe uploads.

## 1. Assets
User accounts and tokens; stored test credentials; uploaded requirements; screenshots and reports; API keys (.env); the host machine and network.

## 2. Threats and Controls

### 2.1 Authentication and Sessions
- Passwords hashed with argon2 or bcrypt; never logged.
- JWT secret from .env; tokens expire in 60 minutes; Session table with jti enables real logout.
- Generic login error message; rate limit login attempts in Redis.
- Every query is scoped to the owner; other users' resources return 404.

### 2.2 SSRF through the target URL
Risk: a user could point the agent at internal services or cloud metadata.
- Allow only http and https.
- Resolve the hostname and block loopback, private, link-local and metadata addresses by default; re-check after redirects.
- Exception: hosts in ALLOWED_PRIVATE_HOSTS (localhost for the demo).
- Restrict the browser to the project's target domain where the tool allows it, and block navigation to other domains and file URLs.

### 2.3 Prompt Injection
Risk: requirements documents and web page content can contain instructions aimed at the model.
- Instructions and untrusted data go in separate, labeled sections; the model is told to treat data as data.
- Executor has no filesystem, shell or network tools beyond the allowlisted browser tools.
- The browser is limited to the target domain.
- Structured outputs are validated with Pydantic; unknown actions are rejected.
- Step budget and timeout cap the damage of a hijacked run.
- Never place secrets in prompts beyond the minimum needed to log in, and never echo credentials back in model output or reports.

### 2.4 Credentials
- Project credentials encrypted at rest with a Fernet key from .env; never returned by the API.
- Redact credential values from logs, action logs, errors, screenshots metadata, and reports. Take no screenshot of a page that displays a password field's contents.
- .env is git-ignored; .env.example holds names only. Demo SupportDesk credentials are throwaway local values.
- API keys must not appear in code, logs, test fixtures, or chat messages.

### 2.5 File Uploads
- Allowed types PDF, TXT, Markdown, JSON; validated by extension and by content, not only by the declared type.
- Size limit MAX_UPLOAD_MB; empty files rejected.
- Generated UUID filenames; no user-controlled paths; files stored outside any publicly served directory.
- PDF parsing in a size-limited, time-limited step; extraction failures produce a clear status, not a crash.

### 2.6 Third-Party LLM Data Exposure
- Free tiers may use submitted content for product improvement (verify current provider terms; see D-003).
- Only send demo or non-sensitive data. Show a notice in the README and UI that uploaded requirements are sent to external LLM providers.
- Send only the retrieved chunks and the minimum page state needed, not whole documents or full pages unless required.

### 2.7 Resource Abuse and Cost
- Limits: MAX_TESTS_PER_RUN, MAX_STEPS_PER_TEST, TEST_TIMEOUT_SECONDS, RUN_TIMEOUT_SECONDS.
- One active run per project (Redis lock); rate limit run creation.
- Client-side LLM rate limiter below provider limits with backoff.

### 2.8 Evidence and Report Access
- Screenshots served only through an authenticated endpoint that checks ownership.
- Reports exclude credentials and raw secrets.

### 2.9 Dependencies and Supply Chain
- Pin versions and commit lock files (uv.lock, package-lock).
- Pin the Playwright MCP version; do not run it as "latest".
- Avoid releases published in the last 14 days unless needed; prefer maintained, well-known packages.
- Run a dependency audit (for example pip-audit and npm audit) before the demo.

### 2.10 Logging and Errors
- Structured logs with run ID and timestamps; no secrets, tokens, or full prompts containing credentials.
- API errors never expose stack traces.
- A failed agent step records its error on the run and never takes down the API.

### 2.11 Network Exposure
- Bind services to 127.0.0.1 by default.
- If a tunnel is used for public access, enable it only for the demo, keep registration rate-limited, and shut it down afterward. The SupportDesk defective build must never be exposed publicly.
- CORS restricted to the frontend origin.

## 3. Explicitly Out of Scope
Penetration testing of third-party sites, enterprise SSO, formal compliance, multi-tenant isolation beyond per-user ownership.

## 4. Pre-Demo Security Checklist
- [ ] .env not committed; no secrets in git history
- [ ] Cross-user suite passes (T13.2)
- [ ] Credential-leak scan clean (T13.3)
- [ ] SSRF tests pass (T3.3)
- [ ] Injection fixture test passes (T10.5)
- [ ] Dependency audit reviewed
- [ ] Services bound to localhost; tunnel off unless needed
- [ ] Demo uses only demo data
