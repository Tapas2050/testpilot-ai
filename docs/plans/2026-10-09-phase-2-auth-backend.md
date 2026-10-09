# Phase 2: Authentication Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the complete authentication backend for TestPilot AI, including User and UserSession models, Alembic migration, argon2 password hashing with non-blocking async execution, JWT creation and revocation, and auth endpoints (`POST /auth/register`, `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`) with test database setup and comprehensive test suite covering T2.1–T2.10.

**Architecture:** Layered design following `IMPLEMENTATION.md`: routers (`app/api/auth.py`) -> dependency/services (`app/api/deps.py`, `app/core/security.py`, `app/services/auth_service.py`) -> models (`app/models/user.py`, `app/models/session.py`). Sessions are tracked in PostgreSQL (`sessions` table via `UserSession` ORM model) with `jti` and `revoked_at` so logout explicitly revokes tokens.

**Tech Stack:** FastAPI, async SQLAlchemy 2.0, asyncpg, Alembic, Pydantic v2, PyJWT (`pyjwt==2.10.1`), `argon2-cffi==23.1.0`, `email-validator==2.2.0`, pytest, httpx.

**Spec:** [docs/IMPLEMENTATION.md](file:///C:/dev/testpilot/docs/IMPLEMENTATION.md) (Phase 2 section and Sections D & E), [docs/RULES.md](file:///C:/dev/testpilot/docs/RULES.md), [docs/DECISIONS.md](file:///C:/dev/testpilot/docs/DECISIONS.md) (D-010, D-019), [docs/TEST_PLAN.md](file:///C:/dev/testpilot/docs/TEST_PLAN.md) (Phase 2, T2.1–T2.10).

---

## Global Constraints

- Python 3.12 pinned via uv; run commands using `uv run`.
- Async SQLAlchemy and FastAPI async endpoints throughout.
- All request and response validation via Pydantic v2 schemas (`app/schemas/auth.py`).
- No plaintext passwords stored, logged, or returned in responses (DECISIONS.md D-010, RULES.md section 3).
- Login failure and wrong-password failure return the exact same generic message: `"Invalid email or password"` (TEST_PLAN.md T2.3).
- JWT expiration is 60 minutes (`JWT_EXPIRE_MINUTES=60` in settings, D-010).
- Settings must refuse to start if `JWT_SECRET` is empty or shorter than 32 characters (ValidationError).
- Timezone-aware datetimes only: `datetime.now(timezone.utc)`. Never use `datetime.utcnow()`.
- Password hashing: `argon2-cffi` (pinned `23.1.0`), executed via `asyncio.to_thread` to keep the event loop non-blocking. Single dummy hash computed at startup for constant-time failure comparison when user email is not found.
- Passwords: 8 to 128 characters, enforced in Pydantic schemas.
- Emails: stripped and lowercased at register and login; stored normalized. `email-validator` pinned (`2.2.0`) for `EmailStr`.
- Database uniqueness race safety: Catch `IntegrityError` on duplicate email registration and return 400.
- ORM class named `UserSession` (mapped to `sessions` table) to avoid colliding with SQLAlchemy's `Session`.
- Token revocation is enforced via `UserSession` table lookups (`revoked_at is not None` -> 401).
- JWT decoding requires explicit `algorithms=["HS256"]` and validates `exp`, `sub`, and `jti`.
- Dedicated test database `testpilot_test` via `TEST_DATABASE_URL`; tests never touch `testpilot`.
- Database migrations exclusively through Alembic. Migration must be inspected to ensure only `users` and `sessions` tables are created, applied to `testpilot` only.

## Review Focus

1. **Test DB Isolation:** Ensure all test runs use `TEST_DATABASE_URL` against `testpilot_test` with truncated tables between tests and `get_db` dependency override.
2. **Case-insensitive email handling:** Registration and login normalize emails (strip + lowercase) so `User@Example.com` and `user@example.com` map to the same account; duplicate registration with different case returns 400.
3. **Timing attack mitigation:** Non-existent user logins run argon2 verification against a dummy hash via `asyncio.to_thread`.
4. **Token verification security:** JWT decode explicitly specifies `algorithms=["HS256"]`, requires `exp`, `sub`, `jti`, and checks tampered signature, unknown jti, non-existent user, and expired session rows.
5. **Leak prevention:** Response bodies never contain `password` or `password_hash`. Logs contain no passwords or tokens.

---

## Tasks

### Task 2.0: Test Database Setup and Pytest Fixtures

**Files:**
- Create: `backend/tests/conftest.py`
- Modify: `backend/tests/test_settings.py` (if needed for settings verification)

**Requirements:**
- Read `TEST_DATABASE_URL` from `.env` (pointing to `testpilot_test`).
- Configure async SQLAlchemy test engine with `NullPool`.
- Create tables before the test session (e.g. `Base.metadata.create_all`).
- Truncate tables (`users`, `sessions`) between tests.
- Override FastAPI `app.dependency_overrides[get_db]` with the test session.
- Ensure tests NEVER connect to `testpilot`.

- [ ] **Step 1: Implement `backend/tests/conftest.py`**
- [ ] **Step 2: Verify test engine setup and db isolation**

---

### Task 2.1: Add Dependencies, User & UserSession Models, and Alembic Migration

**Files:**
- Modify: `backend/pyproject.toml`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/session.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/migrations/env.py`
- Create: `backend/migrations/versions/<generated>_create_user_and_session_tables.py`
- Create: `backend/tests/test_auth_models.py`

**Interfaces:**
- Dependencies: `pyjwt==2.10.1`, `argon2-cffi==23.1.0`, `email-validator==2.2.0`.
- Produces:
  - `User`: `id` (UUID pk), `email` (str, unique, indexed), `password_hash` (str), `created_at` (datetime with timezone)
  - `UserSession`: table name `sessions`, `id` (UUID pk), `user_id` (UUID, FK to `users.id`), `token_id` (str, indexed), `expires_at` (datetime with timezone), `revoked_at` (datetime with timezone, nullable)

- [ ] **Step 1: Add dependencies via uv** (`pyjwt==2.10.1`, `argon2-cffi==23.1.0`, `email-validator==2.2.0`).
- [ ] **Step 2: Create User and UserSession declarative models**.
- [ ] **Step 3: Generate and inspect Alembic migration**. Verify only `users` and `sessions` tables are created. Apply to `testpilot` only.
- [ ] **Step 4: Write test verifying models and schema**.

---

### Task 2.2: Password Hashing, Dummy Hash, and JWT Security Helpers

**Files:**
- Create: `backend/app/core/security.py`
- Modify: `backend/app/core/config.py` (enforce `JWT_SECRET` min length 32)
- Modify: `docs/DECISIONS.md` (add D-019)
- Create: `backend/tests/test_security.py`

**Interfaces:**
- Produces:
  - `hash_password(password: str) -> Coroutine[str]`: runs argon2 hasher via `asyncio.to_thread`.
  - `verify_password(plain_password: str, hashed_password: str) -> Coroutine[bool]`: runs argon2 verify via `asyncio.to_thread`.
  - `verify_dummy_password(plain_password: str) -> Coroutine[bool]`: verifies against startup dummy hash via `asyncio.to_thread`.
  - `create_access_token(user_id: str | UUID, expires_delta: timedelta | None = None) -> tuple[str, str, datetime]`: returns `(access_token, jti, expires_at)`.
  - `decode_access_token(token: str) -> dict[str, Any]`: decodes JWT with explicit `algorithms=["HS256"]`, requiring `exp`, `sub`, and `jti`.
- Settings validation: `JWT_SECRET` empty or len < 32 raises `ValueError`/`ValidationError`.

- [ ] **Step 1: Write tests for argon2 hashing, dummy hash verification, JWT encode/decode, and JWT_SECRET validation**.
- [ ] **Step 2: Run tests to verify failures**.
- [ ] **Step 3: Implement security helpers in `app/core/security.py` and settings validation in `app/core/config.py`**.
- [ ] **Step 4: Record decision D-019 in `docs/DECISIONS.md`**.
- [ ] **Step 5: Run tests to verify they pass**.

---

### Task 2.3: Pydantic Schemas and Register/Login Endpoints (T2.1, T2.2, T2.3, T2.6, T2.7, T2.8, T2.9, T2.10)

**Files:**
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/services/auth_service.py`
- Create: `backend/app/api/auth.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_auth_endpoints.py`

**Interfaces:**
- Produces:
  - Schemas:
    - `RegisterRequest`: `email` (EmailStr, normalized lowercase/strip), `password` (str, min_length=8, max_length=128)
    - `LoginRequest`: `email` (EmailStr, normalized lowercase/strip), `password` (str)
    - `UserResponse`: `id` (UUID), `email` (str), `created_at` (datetime)
    - `TokenResponse`: `access_token` (str), `token_type` (str = "bearer")
  - Endpoints:
    - `POST /auth/register` (201): registers user, catches `IntegrityError` on race condition and returns 400.
    - `POST /auth/login` (200): validates credentials (with dummy hash on missing user), creates `UserSession`, returns `TokenResponse`. Returns 401 `"Invalid email or password"` on invalid email or wrong password.

- [ ] **Step 1: Write failing tests for registration and login** (case-insensitivity, password length, duplicate email, dummy hash on nonexistent user, response body without password/hash, log cleanliness).
- [ ] **Step 2: Implement schemas, auth service, and endpoints**.
- [ ] **Step 3: Run tests to verify they pass**.

---

### Task 2.4: Current-User Dependency with Token Revocation and Claim Checks (T2.4, T2.8)

**Files:**
- Create: `backend/app/api/deps.py`
- Create: `backend/tests/test_auth_deps.py`

**Interfaces:**
- Produces:
  - `get_current_user_and_session`: FastAPI dependency returning `tuple[User, UserSession]`.
  - `get_current_user`: FastAPI dependency returning `User`.
  - Validates:
    - Bearer token header present and valid.
    - JWT signature valid, algorithm is HS256, `exp`, `sub`, `jti` claims present and valid.
    - `UserSession` exists matching `token_id == jti`.
    - `UserSession.revoked_at` is None.
    - `UserSession.expires_at > datetime.now(timezone.utc)`.
    - `User` exists matching `id == sub`.

- [ ] **Step 1: Write tests in `test_auth_deps.py`** (missing token, malformed token, tampered signature, expired token, unknown jti, user no longer exists, expired session row, revoked session).
- [ ] **Step 2: Implement dependencies in `app/api/deps.py`**.
- [ ] **Step 3: Run tests to verify they pass**.

---

### Task 2.5: Me and Logout Endpoints (T2.4, T2.5)

**Files:**
- Modify: `backend/app/api/auth.py`
- Modify: `backend/tests/test_auth_endpoints.py`

**Interfaces:**
- Produces:
  - `GET /auth/me` (200): returns `UserResponse`.
  - `POST /auth/logout` (200): marks `UserSession.revoked_at = datetime.now(timezone.utc)`, returns `{"message": "Logged out successfully"}`.

- [ ] **Step 1: Write tests for `/auth/me` and `/auth/logout`**.
- [ ] **Step 2: Implement `/auth/me` and `/auth/logout` in `app/api/auth.py`**.
- [ ] **Step 3: Run tests to verify they pass**.

---

### Task 2.6: Phase 2 Test Suite Verification and Code Quality Gate

**Files:**
- All backend test files and source files
- `docs/TASKS.md`, `docs/MEMORY.md`, `docs/TEST_PLAN.md`

- [ ] **Step 1: Run complete pytest suite** (`uv run pytest -v`).
- [ ] **Step 2: Run ruff check and format** (`uv run ruff check .` and `uv run ruff format --check .`).
- [ ] **Step 3: Update `docs/TASKS.md`, `docs/MEMORY.md`, `docs/TEST_PLAN.md`**.
- [ ] **Step 4: Create local git commit `"phase-2: authentication backend"`**.
