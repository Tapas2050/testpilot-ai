# Backend Diagnostic & Evaluation Scripts

This directory contains standalone CLI scripts for diagnostics, verification, database seeding, and evaluation. All diagnostic and review scripts follow strict security boundaries: read-only database queries, zero secret exposure, and credential masking.

---

## Script Overview

| Script | Purpose | Usage |
|---|---|---|
| `review_run.py` | Standalone evaluation tool to inspect run statistics, test case outcomes, step counts, screenshots, and compare findings against SupportDesk ground-truth defects (`--expect-supportdesk-defects`). Supports text and `--markdown` formatting. | `uv run python scripts/review_run.py [run_id] [--markdown] [--expect-supportdesk-defects]` |
| `seed_demo.py` | Seeds the `testpilot` database with a demo user (`demo@testpilot.ai`), pre-configured SupportDesk project, encrypted credentials, and indexes `SUPPORTDESK_REQUIREMENTS.md` into `pgvector`. | `uv run python scripts/seed_demo.py` |
| `check_target_login.py` | Decrypts stored credentials for a project and performs a real HTTP login handshake against the target application to verify credentials ahead of test runs. | `uv run python scripts/check_target_login.py [project_id]` |
| `smoke_browser.py` | Live browser smoke test executing Chromium via Playwright MCP over stdio without invoking LLM APIs. Verifies MCP handshake, page navigation, and screenshot capture. | `uv run python scripts/smoke_browser.py` |
| `preflight_only.py` | Executes only the fast preflight phase for a test run under worker conditions (credential decryption, target reachability, MCP initialize handshake) and reports diagnostics. | `uv run python scripts/preflight_only.py [project_id]` |
| `diagnose_run.py` | Deep post-mortem diagnostic tool analyzing failed or cancelled test runs across database tables, checkpoints, action logs, and Redis error keys. | `uv run python scripts/diagnose_run.py [run_id]` |
| `inspect_completed_run.py` | Inspects completed run reports, failure reasons, and step event timelines. | `uv run python scripts/inspect_completed_run.py [run_id]` |

---

## Security Guarantees
- Scripts never echo decrypted passwords, JWT secrets, or encryption keys in terminal output.
- All evaluation tools (`review_run.py`, `diagnose_run.py`, `inspect_completed_run.py`) use read-only transactions.
- Ground truth evaluation rules in `review_run.py` are strictly quarantined from the runtime agent planner and executor.
