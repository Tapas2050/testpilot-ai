# TestPilot AI API Reference (`ENDPOINTS.md`)

This document provides a comprehensive, code-verified reference for every REST API endpoint exposed by the TestPilot AI FastAPI backend server ([backend/app/main.py](file:///c:/dev/testpilot/backend/app/main.py)).

All routes are prefixed with `/api` unless otherwise specified by the router prefix. The FastAPI application is mounted with CORS middleware allowing origins from `http://localhost:5173` and `http://127.0.0.1:5173` with credentials enabled.

---

## Table of Contents

1. [Health & Diagnostics Router](#1-health--diagnostics-router)
2. [Authentication Router (`/auth`)](#2-authentication-router-auth)
3. [Projects & Credentials Router (`/projects`)](#3-projects--credentials-router-projects)
4. [Documents & Knowledge Router](#4-documents--knowledge-router)
5. [Test Runs & Evidence Router](#5-test-runs--evidence-router)

---

## 1. Health & Diagnostics Router

Defined in [backend/app/api/health.py](file:///c:/dev/testpilot/backend/app/api/health.py). Tag: `Health`.

### `GET /health`
- **Method & Path**: `GET /health`
- **Description**: Verifies operational readiness of the FastAPI application, the PostgreSQL database (including `pgvector` extension availability), and the Redis server.
- **Authentication**: None (Public health check probe).
- **Ownership Check**: None.
- **Rate Limit**: None.
- **Request Schema**: None.
- **Response Schema**:
  ```json
  {
    "status": "ok | degraded",
    "api": "ok",
    "database": {
      "status": "healthy | unhealthy",
      "pgvector_enabled": true
    },
    "redis": {
      "status": "healthy | unhealthy"
    }
  }
  ```
- **Status Codes & Errors**:
  - `200 OK`: Successful probe (status field will indicate `"ok"` if all dependencies are healthy, `"degraded"` otherwise).
- **Handling Function**: `get_health()` in [app/api/health.py](file:///c:/dev/testpilot/backend/app/api/health.py#L13-L30).
- **Database / Redis Actions**:
  - Runs `SELECT 1` and `SELECT extname FROM pg_extension WHERE extname = 'vector'` via [app/core/database.py:check_db_health](file:///c:/dev/testpilot/backend/app/core/database.py#L60).
  - Runs `PING` on Redis via [app/core/redis.py:check_redis_health](file:///c:/dev/testpilot/backend/app/core/redis.py#L42).

---

## 2. Authentication Router (`/auth`)

Defined in [backend/app/api/auth.py](file:///c:/dev/testpilot/backend/app/api/auth.py). Tag: `auth`.

### `POST /auth/register`
- **Method & Path**: `POST /auth/register`
- **Description**: Creates a new user account with an email address and Argon2-hashed password.
- **Authentication**: None (Public).
- **Ownership Check**: None.
- **Rate Limit**: None.
- **Request Schema**: `RegisterRequest` in [app/schemas/auth.py](file:///c:/dev/testpilot/backend/app/schemas/auth.py#L8-L12):
  - `email`: `EmailStr` (required)
  - `password`: `str`, min length 8 (required)
- **Response Schema**: `UserResponse` in [app/schemas/auth.py](file:///c:/dev/testpilot/backend/app/schemas/auth.py#L25-L31):
  - `id`: `UUID`
  - `email`: `str`
  - `created_at`: `datetime`
- **Status Codes & Errors**:
  - `201 CREATED`: User created successfully.
  - `400 BAD REQUEST`: `"Email already registered"`.
  - `422 UNPROCESSABLE ENTITY`: Malformed email or password less than 8 characters.
- **Handling Function**: `AuthService.register_user()` in [app/services/auth_service.py](file:///c:/dev/testpilot/backend/app/services/auth_service.py#L20-L40).
- **Database Actions**:
  - `SELECT` on `users` where `email = lower(data.email)`.
  - `INSERT` into `users` (`id`, `email`, `password_hash`, `created_at`).

### `POST /auth/login`
- **Method & Path**: `POST /auth/login`
- **Description**: Authenticates user credentials using Argon2 with timing-attack mitigation and creates a persisted JWT session record.
- **Authentication**: None (Public).
- **Ownership Check**: None.
- **Rate Limit**: **10 requests per 60 seconds per client IP** via `rate_limit_login` in [app/core/rate_limit.py](file:///c:/dev/testpilot/backend/app/core/rate_limit.py#L44).
- **Request Schema**: `LoginRequest` in [app/schemas/auth.py](file:///c:/dev/testpilot/backend/app/schemas/auth.py#L15-L18):
  - `email`: `EmailStr` (required)
  - `password`: `str` (required)
- **Response Schema**: `TokenResponse` in [app/schemas/auth.py](file:///c:/dev/testpilot/backend/app/schemas/auth.py#L34-L37):
  - `access_token`: `str`
  - `token_type`: `"bearer"`
- **Status Codes & Errors**:
  - `200 OK`: Authentication successful, token generated.
  - `401 UNAUTHORIZED`: `"Invalid email or password"`.
  - `429 TOO MANY REQUESTS`: `"Too many login attempts. Please wait a minute and try again."`
  - `422 UNPROCESSABLE ENTITY`: Invalid request payload.
- **Handling Function**: `AuthService.authenticate_user()` in [app/services/auth_service.py](file:///c:/dev/testpilot/backend/app/services/auth_service.py#L42-L73).
- **Database & Redis Actions**:
  - Redis: Increments key `rate_limit:login:{client_ip}` with 60s TTL.
  - PostgreSQL `SELECT` on `users` where `email = lower(data.email)`.
  - Argon2 verification via `verify_password()` or `verify_dummy_password()` in [app/core/security.py](file:///c:/dev/testpilot/backend/app/core/security.py#L38).
  - PostgreSQL `INSERT` into `sessions` (`id`, `user_id`, `token_id`, `expires_at`, `revoked_at=NULL`).

### `GET /auth/me`
- **Method & Path**: `GET /auth/me`
- **Description**: Returns the profile of the currently authenticated user.
- **Authentication**: Bearer Token required via `get_current_user` in [app/api/deps.py](file:///c:/dev/testpilot/backend/app/api/deps.py#L90).
- **Ownership Check**: Inherent to validated session token.
- **Rate Limit**: None.
- **Request Schema**: None.
- **Response Schema**: `UserResponse` (`id`, `email`, `created_at`).
- **Status Codes & Errors**:
  - `200 OK`: Profile returned.
  - `401 UNAUTHORIZED`: Missing, expired, malformed, or revoked token.
- **Handling Function**: `get_me()` in [app/api/auth.py](file:///c:/dev/testpilot/backend/app/api/auth.py#L59-L63).
- **Database Actions**:
  - PostgreSQL `SELECT` on `sessions` where `token_id = jti` and `revoked_at IS NULL` and `expires_at > now()`.
  - PostgreSQL `SELECT` on `users` where `id = sub`.

### `POST /auth/logout`
- **Method & Path**: `POST /auth/logout`
- **Description**: Revokes the active session token in the database, invalidating future requests immediately.
- **Authentication**: Bearer Token required via `get_current_user_and_session` in [app/api/deps.py](file:///c:/dev/testpilot/backend/app/api/deps.py#L24).
- **Ownership Check**: Revokes session bound to incoming JWT `jti`.
- **Rate Limit**: None.
- **Request Schema**: None.
- **Response Schema**: `{"message": "Logged out successfully"}`
- **Status Codes & Errors**:
  - `200 OK`: Session revoked successfully.
  - `401 UNAUTHORIZED`: Invalid or already revoked token.
- **Handling Function**: `logout()` in [app/api/auth.py](file:///c:/dev/testpilot/backend/app/api/auth.py#L71-L80).
- **Database Actions**:
  - PostgreSQL `UPDATE sessions SET revoked_at = now() WHERE id = user_session.id`.

---

## 3. Projects & Credentials Router (`/projects`)

Defined in [backend/app/api/projects.py](file:///c:/dev/testpilot/backend/app/api/projects.py). Tag: `projects`.

### `POST /projects`
- **Method & Path**: `POST /projects`
- **Description**: Creates a new testing project for the authenticated user, enforcing SSRF validation on the target URL.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Sets `user_id = current_user.id`.
- **Rate Limit**: None.
- **Request Schema**: `ProjectCreate` in [app/schemas/project.py](file:///c:/dev/testpilot/backend/app/schemas/project.py#L12-L22):
  - `name`: `str` (1..255 chars, required)
  - `target_url`: `str` (validated via `validate_target_url`, required)
  - `description`: `Optional[str]` = `None`
- **Response Schema**: `ProjectResponse` in [app/schemas/project.py](file:///c:/dev/testpilot/backend/app/schemas/project.py#L32-L42):
  - `id`: `UUID`, `user_id`: `UUID`, `name`: `str`, `description`: `Optional[str]`, `target_url`: `str`, `created_at`: `datetime`, `updated_at`: `datetime`
- **Status Codes & Errors**:
  - `201 CREATED`: Project created.
  - `400 BAD REQUEST / 422`: SSRF violation, unresolvable hostname, or invalid URL format.
  - `401 UNAUTHORIZED`: Authentication failure.
- **Handling Function**: `ProjectService.create_project()` in [app/services/project_service.py](file:///c:/dev/testpilot/backend/app/services/project_service.py#L18-L34).
- **Database Actions**:
  - PostgreSQL `INSERT` into `projects` (`id`, `user_id`, `name`, `description`, `target_url`, `created_at`, `updated_at`).

### `GET /projects`
- **Method & Path**: `GET /projects`
- **Description**: Lists all projects owned by the currently authenticated user.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Strictly filtered by `projects.user_id == current_user.id`.
- **Rate Limit**: None.
- **Request Schema**: None.
- **Response Schema**: `List[ProjectResponse]`.
- **Status Codes & Errors**:
  - `200 OK`: Projects list returned.
  - `401 UNAUTHORIZED`: Authentication failure.
- **Handling Function**: `ProjectService.get_projects_for_user()` in [app/services/project_service.py](file:///c:/dev/testpilot/backend/app/services/project_service.py#L36-L45).
- **Database Actions**:
  - PostgreSQL `SELECT` on `projects` where `user_id = current_user.id` ordered by `created_at DESC`.

### `GET /projects/{project_id}`
- **Method & Path**: `GET /projects/{project_id}`
- **Description**: Retrieves detailed information for a single project owned by the user.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Checks `Project.id == project_id AND Project.user_id == current_user.id`.
- **Rate Limit**: None.
- **Request Schema**: None.
- **Response Schema**: `ProjectResponse`.
- **Status Codes & Errors**:
  - `200 OK`: Project found and returned.
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: `"Project not found"` (returned if non-existent or owned by another tenant).
- **Handling Function**: `ProjectService.get_project()` in [app/services/project_service.py](file:///c:/dev/testpilot/backend/app/services/project_service.py#L47-L61).
- **Database Actions**:
  - PostgreSQL `SELECT` on `projects` where `id = project_id AND user_id = current_user.id`.

### `PATCH /projects/{project_id}`
- **Method & Path**: `PATCH /projects/{project_id}`
- **Description**: Updates name, description, or target URL of a project.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Enforced via `get_project` ownership query; raises 404 if not owned.
- **Rate Limit**: None.
- **Request Schema**: `ProjectUpdate` in [app/schemas/project.py](file:///c:/dev/testpilot/backend/app/schemas/project.py#L25-L29):
  - `name`: `Optional[str]`
  - `description`: `Optional[str]`
  - `target_url`: `Optional[str]` (validated for SSRF)
- **Response Schema**: `ProjectResponse`.
- **Status Codes & Errors**:
  - `200 OK`: Project updated.
  - `400 BAD REQUEST`: SSRF violation on updated target URL.
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: Project not found or unauthorized.
- **Handling Function**: `ProjectService.update_project()` in [app/services/project_service.py](file:///c:/dev/testpilot/backend/app/services/project_service.py#L63-L84).
- **Database Actions**:
  - PostgreSQL `UPDATE projects SET ... WHERE id = project_id`.

### `DELETE /projects/{project_id}`
- **Method & Path**: `DELETE /projects/{project_id}`
- **Description**: Deletes a project and cascades deletion to credentials, documents, vector chunks, and test runs.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Validates user owns the project; raises 404 if not owned.
- **Rate Limit**: None.
- **Request Schema**: None.
- **Response Schema**: None (`204 No Content`).
- **Status Codes & Errors**:
  - `204 NO CONTENT`: Project deleted.
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: Project not found.
- **Handling Function**: `ProjectService.delete_project()` in [app/services/project_service.py](file:///c:/dev/testpilot/backend/app/services/project_service.py#L86-L94).
- **Database Actions**:
  - PostgreSQL `DELETE FROM projects WHERE id = project_id AND user_id = current_user.id`. (Foreign key cascades remove related rows in `project_credentials`, `documents`, `document_chunks`, `test_runs`).

### `POST /projects/{project_id}/credentials`
- **Method & Path**: `POST /projects/{project_id}/credentials`
- **Description**: Stores an encrypted target application credential (e.g. admin or agent credentials) scoped to a project.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Validates project is owned by `current_user.id`.
- **Rate Limit**: None.
- **Request Schema**: `CredentialCreate` in [app/schemas/project.py](file:///c:/dev/testpilot/backend/app/schemas/project.py#L45-L48):
  - `role_label`: `str` (e.g. `"admin"`, `"agent"`, required)
  - `username`: `str` (required)
  - `password`: `str` (required)
- **Response Schema**: `CredentialResponse` in [app/schemas/project.py](file:///c:/dev/testpilot/backend/app/schemas/project.py#L51-L57):
  - `id`: `UUID`, `project_id`: `UUID`, `role_label`: `str`, `username`: `str` (password is strictly omitted).
- **Status Codes & Errors**:
  - `201 CREATED`: Credential encrypted and saved.
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: Project not found.
- **Handling Function**: `ProjectService.add_credential()` in [app/services/project_service.py](file:///c:/dev/testpilot/backend/app/services/project_service.py#L96-L113).
- **Database Actions**:
  - Encrypts password using Fernet symmetric encryption via [app/core/security.py:encrypt_credential](file:///c:/dev/testpilot/backend/app/core/security.py#L103).
  - PostgreSQL `INSERT` into `project_credentials` (`id`, `project_id`, `role_label`, `username`, `password_encrypted`).

### `GET /projects/{project_id}/credentials`
- **Method & Path**: `GET /projects/{project_id}/credentials`
- **Description**: Lists all stored test credentials for a project. Passwords are never returned.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Validates project ownership.
- **Rate Limit**: None.
- **Request Schema**: None.
- **Response Schema**: `List[CredentialResponse]`.
- **Status Codes & Errors**:
  - `200 OK`: Credentials returned.
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: Project not found.
- **Handling Function**: `ProjectService.get_credentials()` in [app/services/project_service.py](file:///c:/dev/testpilot/backend/app/services/project_service.py#L115-L127).
- **Database Actions**:
  - PostgreSQL `SELECT` on `project_credentials` where `project_id = project_id`.

### `DELETE /projects/{project_id}/credentials/{credential_id}`
- **Method & Path**: `DELETE /projects/{project_id}/credentials/{credential_id}`
- **Description**: Deletes a specific credential from a project.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Validates user owns the parent project.
- **Rate Limit**: None.
- **Request Schema**: None.
- **Response Schema**: None (`204 No Content`).
- **Status Codes & Errors**:
  - `204 NO CONTENT`: Credential deleted.
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: Credential or project not found.
- **Handling Function**: `ProjectService.delete_credential()` in [app/services/project_service.py](file:///c:/dev/testpilot/backend/app/services/project_service.py#L129-L147).
- **Database Actions**:
  - PostgreSQL `DELETE FROM project_credentials WHERE id = credential_id AND project_id = project_id`.

---

## 4. Documents & Knowledge Router

Defined in [backend/app/api/documents.py](file:///c:/dev/testpilot/backend/app/api/documents.py). Tag: `documents`.

### `POST /projects/{project_id}/documents`
- **Method & Path**: `POST /projects/{project_id}/documents`
- **Description**: Uploads a requirements specification document, extracts text, generates 384-dim dense embeddings using sentence-transformers, persists vector chunks in pgvector, and flushes the Redis RAG cache.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Verifies project is owned by current user.
- **Rate Limit**: None.
- **Request Schema**: `multipart/form-data` with `file: UploadFile` (enforces max size 10MB; allowed extensions: `.txt`, `.md`, `.pdf`, `.docx`, `.json`).
- **Response Schema**: `DocumentResponse` in [app/schemas/document.py](file:///c:/dev/testpilot/backend/app/schemas/document.py#L6-L16):
  - `id`: `UUID`, `project_id`: `UUID`, `original_name`: `str`, `file_type`: `str`, `size_bytes`: `int`, `extraction_status`: `str`, `chunk_count`: `int`, `created_at`: `datetime`
- **Status Codes & Errors**:
  - `201 CREATED`: Document uploaded, parsed, and indexed.
  - `400 BAD REQUEST`: Empty file, exceeds 10MB limit, or unsupported file extension.
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: Project not found.
- **Handling Function**: `document_service.upload_document()` in [app/services/document_service.py](file:///c:/dev/testpilot/backend/app/services/document_service.py#L29-L97).
- **Storage, Database, and Redis Actions**:
  - Writes physical file to disk at `storage/documents/{uuid}.{ext}` via [app/services/storage.py](file:///c:/dev/testpilot/backend/app/services/storage.py).
  - PostgreSQL `INSERT` into `documents` table (`extraction_status='SUCCESS'`, `extracted_text=...`).
  - Chunks text into ~500-char segments via [app/services/chunker.py](file:///c:/dev/testpilot/backend/app/services/chunker.py).
  - Runs embedding model (`sentence-transformers/all-MiniLM-L6-v2`) via [app/services/embedder.py](file:///c:/dev/testpilot/backend/app/services/embedder.py).
  - PostgreSQL `INSERT` into `document_chunks` table with `embedding = Vector(384)`.
  - Redis: Scans and deletes all keys matching pattern `rag:{project_id}:*` to invalidate RAG cache.

### `GET /projects/{project_id}/documents`
- **Method & Path**: `GET /projects/{project_id}/documents`
- **Description**: Lists all specification documents attached to a project.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Verifies project ownership.
- **Rate Limit**: None.
- **Request Schema**: None.
- **Response Schema**: `List[DocumentResponse]`.
- **Status Codes & Errors**:
  - `200 OK`: Document list returned.
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: Project not found.
- **Handling Function**: `document_service.list_documents()` in [app/services/document_service.py](file:///c:/dev/testpilot/backend/app/services/document_service.py#L99-L127).
- **Database Actions**:
  - PostgreSQL `SELECT` on `documents` with subquery count of `document_chunks`.

### `DELETE /documents/{document_id}`
- **Method & Path**: `DELETE /documents/{document_id}`
- **Description**: Deletes a specification document, its physical disk artifact, and all vector chunks in pgvector.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Validates document's project is owned by current user.
- **Rate Limit**: None.
- **Request Schema**: None.
- **Response Schema**: None (`204 No Content`).
- **Status Codes & Errors**:
  - `204 NO CONTENT`: Document and chunks deleted.
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: Document not found.
- **Handling Function**: `document_service.delete_document()` in [app/services/document_service.py](file:///c:/dev/testpilot/backend/app/services/document_service.py#L129-L157).
- **Storage, Database, and Redis Actions**:
  - Deletes physical file from `storage/documents/`.
  - PostgreSQL `DELETE FROM documents WHERE id = document_id` (cascades to `document_chunks`).
  - Redis: Flushes `rag:{project_id}:*` cache.

---

## 5. Test Runs & Evidence Router

Defined in [backend/app/api/runs.py](file:///c:/dev/testpilot/backend/app/api/runs.py). Tag: `runs`.

### `POST /projects/{project_id}/runs`
- **Method & Path**: `POST /projects/{project_id}/runs`
- **Description**: Initiates a new autonomous agent test run. Acquires a Redis duplicate-run lock, creates a `TestRun` row in `QUEUED`, enqueues a background job to `arq`, and returns immediately.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Verifies project is owned by `current_user.id`.
- **Rate Limit**: **5 runs per 60 seconds per project** via `rate_limit_create_run` in [app/core/rate_limit.py](file:///c:/dev/testpilot/backend/app/core/rate_limit.py#L56).
- **Request Schema**: None.
- **Response Schema**: `RunDetailResponse` in [app/api/runs.py](file:///c:/dev/testpilot/backend/app/api/runs.py#L43-L56):
  - `id`: `UUID`, `project_id`: `UUID`, `status`: `"QUEUED"`, `created_at`: `datetime`, `test_cases`: `[]`
- **Status Codes & Errors**:
  - `201 CREATED`: Run accepted and queued.
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: Project not found.
  - `409 CONFLICT`: `"A test run is already active for this project"` (enforced via database query and Redis `SET NX` lock).
  - `429 TOO MANY REQUESTS`: Rate limit exceeded.
- **Handling Function**: `create_test_run()` in [app/api/runs.py](file:///c:/dev/testpilot/backend/app/api/runs.py#L83-L141).
- **Database & Queue Actions**:
  - PostgreSQL `SELECT` verifying no active runs (`QUEUED`, `PLANNING`, `EXECUTING`, `ANALYZING`, `REPORTING`) exist for this project.
  - PostgreSQL `INSERT` into `test_runs` (`id`, `project_id`, `status='QUEUED'`, `created_at=now()`).
  - Redis `SET project_run_lock:{project_id} {run_id} NX EX 900` via [app/services/run_service.py:acquire_run_lock](file:///c:/dev/testpilot/backend/app/services/run_service.py#L32).
  - Redis `arq:queue` push: calls `enqueue_agent_job(new_run.id, project_id, db_url=target_db_url)` via [app/worker/tasks.py](file:///c:/dev/testpilot/backend/app/worker/tasks.py#L52).

### `GET /runs/{run_id}`
- **Method & Path**: `GET /runs/{run_id}`
- **Description**: Polls status and details of an active or completed test run. Overlays active in-flight stage from Redis cache over database status.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Joins with `projects` table verifying `Project.user_id == current_user.id`.
- **Rate Limit**: None.
- **Request Schema**: None.
- **Response Schema**: `RunDetailResponse` (including planned `test_cases` list and `report` JSON if complete).
- **Status Codes & Errors**:
  - `200 OK`: Run details returned.
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: Test run not found or unauthorized.
- **Handling Function**: `get_test_run()` in [app/api/runs.py](file:///c:/dev/testpilot/backend/app/api/runs.py#L144-L171).
- **Database & Redis Actions**:
  - PostgreSQL `SELECT` on `test_runs` joined with `test_cases` (using `selectinload`).
  - Redis `GET run_status:{run_id}`: If active, overrides DB status with transient cache stage.

### `GET /projects/{project_id}/runs`
- **Method & Path**: `GET /projects/{project_id}/runs`
- **Description**: Returns all historical and active test runs for a given project, sorted by newest first.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Verifies project is owned by current user.
- **Rate Limit**: None.
- **Request Schema**: None.
- **Response Schema**: `List[RunSummaryResponse]` in [app/api/runs.py](file:///c:/dev/testpilot/backend/app/api/runs.py#L58-L72):
  - `id`: `UUID`, `project_id`: `UUID`, `status`: `str`, `created_at`: `datetime`, `started_at`: `Optional[datetime]`, `completed_at`: `Optional[datetime]`, `error_message`: `Optional[str]`, `cancel_requested`: `bool`, `total_tests`: `int`, `passed_tests`: `int`, `failed_tests`: `int`
- **Status Codes & Errors**:
  - `200 OK`: List of run summaries returned.
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: Project not found.
- **Handling Function**: `list_project_runs()` in [app/api/runs.py](file:///c:/dev/testpilot/backend/app/api/runs.py#L173-L218).
- **Database Actions**:
  - PostgreSQL `SELECT` on `test_runs` where `project_id = project_id` ordered by `created_at DESC`.

### `POST /runs/{run_id}/cancel`
- **Method & Path**: `POST /runs/{run_id}/cancel`
- **Description**: Requests immediate graceful cancellation of an active test run. Sets cancel flag in database and Redis, and releases the project run lock.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Validates run belongs to a project owned by user.
- **Rate Limit**: None.
- **Request Schema**: None.
- **Response Schema**: `RunDetailResponse` (with `cancel_requested=true`).
- **Status Codes & Errors**:
  - `200 OK`: Cancellation flag set.
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: Run not found.
- **Handling Function**: `cancel_test_run()` in [app/api/runs.py](file:///c:/dev/testpilot/backend/app/api/runs.py#L220-L252).
- **Database & Redis Actions**:
  - PostgreSQL `UPDATE test_runs SET cancel_requested = true WHERE id = run_id`.
  - Redis `SET run_cancel:{run_id} 1 EX 900` via [app/services/run_service.py:set_cancel_flag](file:///c:/dev/testpilot/backend/app/services/run_service.py#L65).
  - Redis `DEL project_run_lock:{project_id}` via [app/services/run_service.py:release_run_lock](file:///c:/dev/testpilot/backend/app/services/run_service.py#L46).

### `GET /runs/{run_id}/report`
- **Method & Path**: `GET /runs/{run_id}/report`
- **Description**: Retrieves the finalized JSON report object containing pass percentages, failure categorizations, and executive summary.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Validates user owns the run.
- **Rate Limit**: None.
- **Request Schema**: None.
- **Response Schema**: `dict` (stored report JSON object matching [app/agent/report.py](file:///c:/dev/testpilot/backend/app/agent/report.py)).
- **Status Codes & Errors**:
  - `200 OK`: Report JSON returned.
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: Run not found OR report not yet generated (`"Report not yet generated for this run"`).
- **Handling Function**: `get_test_run_report()` in [app/api/runs.py](file:///c:/dev/testpilot/backend/app/api/runs.py#L254-L280).
- **Database Actions**:
  - PostgreSQL `SELECT report FROM test_runs WHERE id = run_id`.

### `GET /runs/{run_id}/screenshots/{filename}`
- **Method & Path**: `GET /runs/{run_id}/screenshots/{filename}`
- **Description**: Serves authenticated screenshot evidence captured during browser test execution. Protects against directory traversal.
- **Authentication**: Bearer Token required (`get_current_user`).
- **Ownership Check**: Validates user owns the run.
- **Rate Limit**: None.
- **Request Schema**: `filename: str` path parameter.
- **Response Schema**: Binary `image/png` file stream (`FileResponse`).
- **Status Codes & Errors**:
  - `200 OK`: Image binary returned.
  - `400 BAD REQUEST`: `"Invalid screenshot file format"` (if not ending in `.png` or attempting directory traversal).
  - `401 UNAUTHORIZED`: Authentication failure.
  - `404 NOT FOUND`: Run not found OR physical screenshot file missing from disk.
- **Handling Function**: `get_run_screenshot()` in [app/api/runs.py](file:///c:/dev/testpilot/backend/app/api/runs.py#L282-L326).
- **Storage & Database Actions**:
  - PostgreSQL `SELECT` on `test_runs` verifying ownership.
  - Reads image from local filesystem at `storage/screenshots/{run_id}/{clean_name}`.
