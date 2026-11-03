# Security Policy: TestPilot AI

TestPilot AI drives a real browser in an automated loop and interacts with external LLM APIs. Security controls and defensive boundaries are enforced across all layers of the stack.

---

## Supported Versions

| Version | Supported |
|---|:---:|
| 1.0.x | ✅ |

---

## Defensive Security Controls

1. **Authentication & Session Isolation**:
   - Passwords hashed with `Argon2id` (RFC 9106 recommended parameters) with startup dummy hash comparisons to prevent timing side-channels.
   - JWT tokens signed with `HS256` (verifying `exp`, `sub`, and `jti` against active `UserSession` database entries).
   - Strict owner-scoped query isolation: cross-tenant requests return `404 Not Found`.

2. **Target URL Validation & SSRF Prevention**:
   - Target URLs strictly validated against scheme (`http`, `https`).
   - Private IP ranges and cloud metadata endpoints (`169.254.169.254`) blocked by default, with explicit overrides only for verified local development via `ALLOWED_PRIVATE_HOSTS`.

3. **Zero-Leak Credential Encryption**:
   - Target application credentials encrypted at rest using AES-256 Fernet.
   - Credentials systematically redacted and sanitized from action logs, LLM traces, step events, and frontend API payloads.

4. **Evidence & Screenshot Access Control**:
   - Screenshots stored outside web server docroots under `storage/screenshots/{run_id}/`.
   - Served exclusively via authenticated endpoint `GET /runs/{run_id}/screenshots/{filename}` with bearer token verification, ownership checks, regex filename restrictions, and directory traversal rejection.

5. **Subprocess Sandboxing & Execution Caps**:
   - Tool execution restricted strictly to browser actions (no filesystem, shell, or arbitrary network access).
   - Enforced per-step, per-test, and whole-run execution timeouts with clean process-tree termination.

---

## Reporting a Vulnerability

If you discover a security vulnerability in TestPilot AI, please **do not open a public issue**.  
Instead, report it responsibly to the maintainer:

- Maintainer: **Tapas** ([@Tapas2050](https://github.com/Tapas2050))
- Email: Contact via GitHub profile or private security advisory.

Please include:
- A description of the vulnerability and attack vector.
- Steps to reproduce or proof-of-concept script.
- Affected components (API, Worker, MCP client, or Frontend).

We take security issues seriously and will respond promptly to validate and remediate any confirmed vulnerabilities.
