# SupportDesk CRM — TestPilot AI Demo Target

SupportDesk is a realistic, standalone support ticketing web application built with **FastAPI**, **Jinja2 templates**, and **SQLite**. It serves as the primary verification target for TestPilot AI.

---

## Seed Accounts & Roles

| Role | Username | Password | Permissions |
|---|---|---|---|
| **Admin** | `admin@supportdesk.local` | `AdminSecret123!` | View, create, assign, update status, and **delete** tickets |
| **Agent** | `agent@supportdesk.local` | `AgentSecret123!` | View, create, update tickets (ticket deletion is strictly prohibited) |
| **Customer** | `customer@supportdesk.local` | `CustomerSecret123!` | Create and view own tickets |

---

## Planted Defect Switches

SupportDesk features toggleable planted defects controlled via the `SUPPORTDESK_DEFECTS` environment variable:

- `SUPPORTDESK_DEFECTS=on` (Default in demo mode): Activates 3 deliberate defects:
  1. **DEF-01 / REQ-SEC-02 (Agent Deletion Vulnerability)**: The `#delete-ticket-btn` is rendered for agents, and deleting a ticket succeeds with a 303 redirect instead of returning 403 Forbidden.
  2. **DEF-02 / REQ-TICK-03 (Priority Persistence Defect)**: Tickets created with "High" priority are silently downgraded and saved as "Low".
  3. **DEF-03 / REQ-TICK-04 (Search by ID Broken)**: Searching for tickets using exact numeric ID yields zero results.

- `SUPPORTDESK_DEFECTS=off` (Clean mode): All features behave strictly according to specification.

---

## Local Execution & Database Reset

```bash
# 1. Reset database to 5 clean seeded tickets
cd supportdesk
uv run python reseed.py

# 2. Launch SupportDesk on port 8001
uv run uvicorn app.main:app --port 8001
```
