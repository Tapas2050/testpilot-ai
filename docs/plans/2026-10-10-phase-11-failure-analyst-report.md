# Phase 11: Failure Analyst and Report

Date: 2026-10-10
Status: In Progress
Phase: 11

## 1. Objectives
Implement the Failure Analyst agent that classifies failed tests into the 5 allowed categories, generates actionable diagnosis, calculates mathematically sound report metrics, and serves authenticated report and evidence endpoints.

## 2. Tasks & Plan
- **11.1 Analyst Prompt and Schema (`app/agent/analyst.py`)**:
  - Classifications: `PRODUCT_BUG`, `TEST_FAILURE`, `AUTHENTICATION_FAILURE`, `ENVIRONMENT_FAILURE`, `FLAKY_TEST`.
  - Severities: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
  - Confidence (float 0..1), Expected, Observed, Explanation, Suggested Action.
- **11.2 Analyst Node (`app/agent/graph.py` & `app/agent/analyst.py`)**:
  - Filter for failed tests only; skip passed tests.
  - Analyze failure context (requirement, scenario, error, action log).
  - Persist `Failure` entity in database linked to `test_case_id`.
- **11.3 Report Node & Report JSON (`app/agent/graph.py` & `app/agent/report.py`)**:
  - Calculate totals, passed, failed, pass percentage.
  - Compile classification and severity breakdowns.
  - Attach evidence links (screenshots) and generate executive summary.
  - Persist report JSON in `TestRun.report`.
- **11.4 Report & Evidence Endpoints (`app/api/runs.py`)**:
  - `GET /runs/{run_id}/report`: Returns full report JSON with ownership verification.
  - `GET /runs/{run_id}/screenshots/{filename}`: Authenticated screenshot file download.
- **11.5 Tests (`backend/tests/test_analyst.py`)**:
  - T11.1: Failure schema parses and enforces 5 categories.
  - T11.2: Analyst executes only for failed tests.
  - T11.3: Report mathematical correctness.
  - T11.4: Report and evidence contain no credentials.
  - T11.5: eval: SupportDesk defective build yields 3 planted defects as PRODUCT_BUG; correct build yields 0 false product bugs.
