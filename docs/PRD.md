# PRD: TestPilot AI

Version: 0.2 (MVP)
Status: Approved for build
Type: AI-powered QA / test automation web platform

## 1. Product Overview
TestPilot AI is a web platform. A user supplies a web app's URL and its requirements documents. An AI agent plans test scenarios grounded in those requirements, executes them in a real browser, analyzes failures, and produces an evidence-backed report.

Core flow: Requirements -> RAG -> Test Planning -> Agent Orchestration -> Browser Execution -> Failure Analysis -> Report

## 2. Problem Statement
Manual testing means reading requirements, writing test cases, running workflows, investigating failures and documenting results. Scripted automation reduces execution effort but needs maintenance whenever the app changes. TestPilot AI lets an agent interpret requirements and run a bounded set of tests on its own.

## 3. Target Users
- Primary: QA engineer or developer validating a release candidate without hand-writing every end-to-end test.
- Secondary: developer wanting a quick AI-generated validation report for a feature or release.

## 4. Core Features
1. Registration, login, logout (JWT)
2. Projects: name, target URL, per-role test credentials
3. Document upload: PDF, TXT, Markdown, JSON
4. RAG over uploaded requirements
5. AI test planning producing structured test cases
6. Browser execution through Playwright MCP
7. Failure analysis and classification
8. Final report with evidence (screenshots)
9. Run history
10. Asynchronous runs with live status

## 5. User Stories
Account
- As a user, I can register and log in so my projects stay private.
- As a user, I can log out so my session ends.

Projects
- As a user, I can create a project with a target URL so the agent knows what to test.
- As a user, I can edit or delete a project.
- As a user, I can save test credentials per role so the agent can log in to the app under test.

Documents
- As a user, I can upload requirements so tests are based on my real requirements.
- As a user, I see a clear error for wrong file types or oversized files.
- As a user, I can delete a document so outdated requirements stop influencing tests.

Runs
- As a user, I can start a run and get an immediate response.
- As a user, I can watch run status, stage and progress.
- As a user, I can see the generated test plan.
- As a user, I can cancel a run.

Results
- As a user, I can see pass/fail per test with evidence.
- As a user, I can see why a test failed and whether it is a product bug or a test problem.
- As a user, I can open a final report with totals, severity summary and screenshots.
- As a user, I can reopen past runs and reports.

## 6. MVP Scope
In scope:
- Everything in section 4
- Five-stage agent pipeline (Context Retrieval, Planner, Executor, Failure Analyst, Report Generator) orchestrated by LangGraph with checkpointing
- Run states: QUEUED, PLANNING, EXECUTING, ANALYZING, REPORTING, COMPLETED, FAILED, CANCELLED
- Failure categories: PRODUCT_BUG, TEST_FAILURE, AUTHENTICATION_FAILURE, ENVIRONMENT_FAILURE, FLAKY_TEST
- SupportDesk demo app with 3 planted defects
- Six frontend views: Login, Register, Dashboard, Project, Test Run, Report
- Free LLM providers (primary plus fallback) and free local embeddings
- Local run with uv, no Docker

## 7. Not in Version 1
Mobile testing, load or performance testing, penetration testing, CI/CD integration, distributed browser execution, Kubernetes, enterprise SSO, autonomous code modification, self-healing automation, test scheduling, re-run, automatic flaky retry, GitHub integration, regression selection, coverage analytics, human approval checkpoints, long-term project memory, payments, email notifications, teams or sharing, Docker packaging.

## 8. Success Criteria
The MVP succeeds if a user can:
1. Register and log in.
2. Create a SupportDesk project with credentials.
3. Upload the requirements.
4. Start a run and see live progress.
5. See generated test cases, each traceable to a requirement.
6. Watch the browser execute them.
7. Detect the planted defects (at least one required, all three targeted).
8. See each failure classified with an explanation.
9. View a final report with screenshots.
10. Reopen the run later.

Quality measures:
- The planner invents no requirements beyond the uploaded documents.
- Every LLM output passes schema validation or is handled gracefully.
- A failed agent step never crashes the API server.
- A full run completes within free-tier rate limits (see DECISIONS.md D-004).

## 9. Demo Scenario
Controlled SupportDesk release with these defects:
- Defect 1: a support agent can delete a ticket.
- Defect 2: ticket priority "High" is persisted incorrectly.
- Defect 3: ticket ID search does not work.

Flow: Login -> open SupportDesk project -> show requirements -> Start AI Test -> show generated plan -> show browser execution -> show MCP interaction -> show failure analysis -> show final report.

## 10. Open Items
- Exact free-tier model and limits must be verified at build time (D-004).
- Host operating system not yet confirmed (affects Redis and Postgres setup, D-006).
