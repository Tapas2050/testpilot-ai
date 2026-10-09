# Phase 3: Project Management Backend Implementation Plan

> **For agentic workers:** Required sub-skills: subagent-driven-development / executing-plans. Follow task-by-task execution.

**Goal:** Implement the complete project management backend for TestPilot AI, including Project and ProjectCredential models, Alembic migration, target URL SSRF validation with private-address blocking and allowlist, Fernet credential encryption, and project/credential CRUD endpoints with strict owner scoping.

**Architecture:** Layered design following `IMPLEMENTATION.md`: routers (`app/api/projects.py`) -> dependency/services (`app/services/project_service.py`, `app/core/url_validator.py`, `app/core/security.py`) -> models (`app/models/project.py`, `app/models/credential.py`).

**Tech Stack:** FastAPI, async SQLAlchemy 2.0, asyncpg, Alembic, Pydantic v2, cryptography (Fernet), pytest, httpx.

**Spec:** [docs/IMPLEMENTATION.md](file:///c:/dev/testpilot/docs/IMPLEMENTATION.md) (Phase 3 section and Sections B, D, E), [docs/RULES.md](file:///c:/dev/testpilot/docs/RULES.md), [docs/DECISIONS.md](file:///c:/dev/testpilot/docs/DECISIONS.md), [docs/TEST_PLAN.md](file:///c:/dev/testpilot/docs/TEST_PLAN.md) (T3.1–T3.4), [docs/SECURITY.md](file:///c:/dev/testpilot/docs/SECURITY.md) (2.2, 2.4).

---

## Global Constraints

- Python 3.12 pinned via uv.
- Async SQLAlchemy and FastAPI async endpoints throughout.
- All request and response validation via Pydantic v2 schemas (`app/schemas/project.py`).
- Owner scoping on every database query: another user querying, updating, or deleting a project gets 404 Not Found (T3.2, SECURITY.md 2.1).
- Target URL validator blocks non-http/https schemes, private/loopback/link-local/metadata IP addresses, and hostnames resolving to private IPs, with allowlist exception for `ALLOWED_PRIVATE_HOSTS` (T3.3, SECURITY.md 2.2).
- Test credentials encrypted at rest using Fernet with `CREDENTIAL_ENCRYPTION_KEY` from `.env`. Plaintext or encrypted passwords NEVER returned in API responses (T3.4, SECURITY.md 2.4).
- Database migrations exclusively through Alembic. Migration creates only `projects` and `project_credentials` tables.
- All tests run against `testpilot_test` with `NullPool` and table truncation.

---

## Tasks

### Task 3.1: Project and ProjectCredential Models and Alembic Migration
- Create `backend/app/models/project.py` with `Project` model (id, user_id, name, description, target_url, created_at, updated_at).
- Create `backend/app/models/credential.py` with `ProjectCredential` model (id, project_id, role_label, username, password_encrypted).
- Update `backend/app/models/user.py` and `backend/app/models/__init__.py`.
- Generate Alembic revision, verify it creates only `projects` and `project_credentials` tables, and apply to `testpilot`.

### Task 3.2: Target URL Validation (SSRF Protection)
- Create `backend/app/core/url_validator.py`.
- Validate URL scheme is http or https.
- Resolve hostnames and block loopback, private, link-local, and cloud metadata (169.254.169.254) addresses.
- Permit hosts in `settings.ALLOWED_PRIVATE_HOSTS` (e.g. `localhost`, `127.0.0.1`).
- Write unit tests in `backend/tests/test_url_validator.py` covering T3.3.

### Task 3.3: Credential Encryption Utilities
- Implement `encrypt_credential` and `decrypt_credential` using Fernet in `backend/app/core/security.py`.
- Ensure encrypted values are non-empty and decrypt accurately.
- Write tests in `backend/tests/test_credential_encryption.py`.

### Task 3.4: Pydantic Schemas, Project Service, and Endpoints (T3.1, T3.2, T3.4)
- Create `backend/app/schemas/project.py`.
- Create `backend/app/services/project_service.py` with owner-scoped queries and password encryption.
- Create `backend/app/api/projects.py` and mount router in `backend/app/main.py`.
- Implement endpoints:
  - `POST /projects`
  - `GET /projects`
  - `GET /projects/{id}`
  - `PATCH /projects/{id}`
  - `DELETE /projects/{id}`
  - `POST /projects/{id}/credentials`
  - `GET /projects/{id}/credentials`
  - `DELETE /projects/{id}/credentials/{credential_id}`

### Task 3.5: Comprehensive Phase 3 Test Suite and Verification
- Create `backend/tests/test_projects.py` covering T3.1, T3.2, T3.4.
- Run full pytest test suite (Phase 1, 2, 3).
- Run ruff check and ruff format.
- Update tracking docs and make git commit `"phase-3: project management backend"`.
