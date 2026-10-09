# Phase 13 Plan: Hardening and Demo Readiness

Date: 2026-10-10
Phase: 13 (Hardening and Demo Readiness)

## Objective
Finalize system robustness, security verification, rate limiting, structured logging, automated credential audits, complete cross-user isolation test suites, demo seeding scripts, and production-quality documentation.

## Key Tasks & Files

1. **Rate Limiting in Backend (`backend/app/core/rate_limit.py`)**:
   - Redis-backed rate limiter dependency.
   - Login rate limiting: 10 attempts per minute per IP / email.
   - Run creation rate limiting: 5 runs per minute per project, alongside existing single active run lock.
   - Return HTTP 429 Too Many Requests with descriptive message.

2. **Structured Logging (`backend/app/core/logging.py`)**:
   - Configure Python standard library logging with contextual `run_id` (using `contextvars`).
   - Clean formatting that redacts sensitive keys or tokens.

3. **Cross-User Access Test Suite (`backend/tests/test_cross_user_isolation.py`)**:
   - T13.2: Verify every endpoint returns 404 or refuses access when User B attempts to access User A's resources (projects, credentials, documents, runs, cancel, reports, screenshots).

4. **Credential Leak Scan Suite (`backend/tests/test_credential_leak_audit.py`)**:
   - T13.3: Automated scanner that verifies:
     - Password hashes are argon2 format, never plaintext.
     - Stored credentials in database are Fernet ciphertext, never plaintext.
     - API responses for credentials, test runs, test results, and reports never leak passwords, secrets, or keys.
     - Git tracked files contain no `.env` values or private keys.

5. **Graceful Error Handling Test (`backend/tests/test_error_hardening.py`)**:
   - T13.4: Verify missing LLM key, unreachable target URL, or provider rate exhaustion moves the test run cleanly to FAILED without API crash.

6. **Seed Script & Demo Setup (`backend/scripts/seed_demo.py`)**:
   - Script to populate demo user (`demo@testpilot.ai`), SupportDesk project (`http://localhost:8001`), credentials for `admin` and `agent`, and upload `SUPPORTDESK_REQUIREMENTS.md`.

7. **Root `README.md`**:
   - Step-by-step setup guide for Windows 11 host (uv, Python 3.12, Node LTS, Postgres with pgvector, Redis).
   - Commands to start backend, worker, frontend, and SupportDesk target.
   - Demo walkthrough script.
