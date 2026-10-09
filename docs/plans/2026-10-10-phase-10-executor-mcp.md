# Phase 10: Executor with Playwright MCP

Date: 2026-10-10
Status: In Progress
Phase: 10

## 1. Objectives
Execute generated test cases against real web targets using Playwright MCP over stdio with strictly enforced tool allowlists, step budgets, timeouts, role-based authentication, evidence capture (screenshots and action logs), and complete credential redaction.

## 2. Tasks & Plan
- **10.1 Playwright MCP stdio Client (`app/agent/mcp_client.py`)**:
  - Manage pinned MCP server child process over stdio.
  - Implement JSON-RPC 2.0 protocol (`initialize`, `notifications/initialized`, `tools/list`, `tools/call`).
  - Isolated browser context per run, graceful lifecycle management and cleanup.
- **10.2 Tool Allowlist & Redaction (`app/agent/mcp_client.py`)**:
  - Allowlist: `navigate`, `click`, `fill`, `screenshot`, `get_text`, `select_option`, `press_key`, `hover`.
  - Reject any unauthorized tool calls.
  - Redact sensitive credentials (passwords, tokens) before logging or saving steps.
- **10.3 Executor Engine & Node (`app/agent/executor.py` & `app/agent/graph.py`)**:
  - Step budget: `MAX_STEPS_PER_TEST = 15`.
  - Timeout: `TEST_TIMEOUT_SECONDS = 120`.
  - Process test cases one at a time.
  - Clean error handling if step budget or timeout exceeded.
- **10.4 Role-Based Authentication (`app/agent/executor.py`)**:
  - Lookup role credentials from database (`ProjectCredential`), decrypt using Fernet key.
  - Automated role login step before executing test actions.
- **10.5 Evidence Capture & Screenshots (`app/agent/executor.py`)**:
  - Capture step-by-step action log and observations.
  - Save full-page or viewport screenshots to `storage/screenshots/{run_id}/{test_case_id}.png`.
- **10.6 Result Schema and Persistence**:
  - Store `TestResult` in database with `status`, `steps`, `screenshot_path`, `duration_seconds`, `error_message`.
  - Update `TestCase.status` to match result.
- **10.7 Credential Redaction**:
  - Redact all password values, API keys, and auth tokens from action logs, DB records, and logs.
- **10.8 Tests (`backend/tests/test_executor.py`)**:
  - T10.1: Tool allowlist enforcement.
  - T10.2: Step budget and per-test timeout handling.
  - T10.3: Screenshot capture and linkage.
  - T10.4: Credential redaction in logs and action logs.
  - T10.5: Prompt injection defense on web page content.
  - T10.6: eval test against SupportDesk.
