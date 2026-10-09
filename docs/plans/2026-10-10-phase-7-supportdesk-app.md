# Plan: Phase 7 - SupportDesk Demo Application

## 1. Goal
Build the target demo web application `SupportDesk` in `supportdesk/` as a self-contained FastAPI + SQLite application with server-rendered UI and REST endpoints. It supports user roles (admin, agent), ticket operations, and a defect toggle `SUPPORTDESK_DEFECTS` implementing the three planted defects.

## 2. Requirements & Constraints
- Location: `supportdesk/`
- Separate `pyproject.toml` (uv project)
- SQLite database (`supportdesk/supportdesk.db`)
- Seeded accounts:
  - Admin: `admin@supportdesk.local` / `AdminSecret123!`
  - Agent: `agent@supportdesk.local` / `AgentSecret123!`
- Core workflows:
  - Login with email & password, session cookie or token, and Logout.
  - Ticket Creation: title, description, priority (`Low`, `Medium`, `High`), customer email.
  - Ticket Viewing & Details: ticket list with pagination/filtering, detail view.
  - Ticket Status update (`OPEN`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`).
  - Ticket Assignee update (assign to admin or agent).
  - Search: search by title or search by numeric ID.
  - Ticket Deletion: restricted to `admin` role (403 Forbidden for `agent`).
- Defect toggle `SUPPORTDESK_DEFECTS` (`on` / `off`, default `off`):
  - Defect 1: Agent can delete tickets (authorization bypass).
  - Defect 2: High priority persisted incorrectly as Low.
  - Defect 3: ID search broken (fails to find ticket by ID).
- Requirements Document: `SUPPORTDESK_REQUIREMENTS.md` at root.
- Verification (TEST_PLAN.md):
  - T7.1 Correct build (`SUPPORTDESK_DEFECTS=off`): all requirements satisfied, admin-only delete enforced, High priority stored, ID search works.
  - T7.2 Defective build (`SUPPORTDESK_DEFECTS=on`): agent can delete, High priority stored as Low, ID search fails.
  - T7.3 Defect switch is off by default when unset.

## 3. Files to Create
- `supportdesk/pyproject.toml`
- `supportdesk/app/config.py` (reads `SUPPORTDESK_DEFECTS`, port, credentials)
- `supportdesk/app/database.py` (SQLite setup)
- `supportdesk/app/models.py` (User and Ticket models)
- `supportdesk/app/auth.py` (Simple cookie-based session auth)
- `supportdesk/app/main.py` (Routes, UI templates or server-rendered HTML, API endpoints)
- `supportdesk/tests/test_supportdesk.py` (T7.1, T7.2, T7.3)
- `SUPPORTDESK_REQUIREMENTS.md` (Formal requirement specification for TestPilot to test)
