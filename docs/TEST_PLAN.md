# TEST PLAN: TestPilot AI

## 1. Approach
- Backend: pytest, pytest-asyncio, httpx AsyncClient, a separate test database, fresh schema per test session.
- Frontend: Vitest and React Testing Library for components and hooks; manual checks for full flows.
- LLM calls are mocked in all unit and integration tests so they are fast and deterministic.
- A small set of live evaluation tests (marked eval) call the real providers and the real browser against SupportDesk. They run on demand only, because of free-tier limits.
- Every phase must pass its tests before the next starts. Do not weaken tests to pass.

## 2. Test Data
- SupportDesk correct build (SUPPORTDESK_DEFECTS=off) and defective build (on).
- SUPPORTDESK_REQUIREMENTS.md as the standard uploaded document.
- Fixture files: valid PDF, TXT, MD, JSON; an oversized file; an executable renamed to .pdf; an empty file; a file with injected instructions inside.
- Two test users to check cross-user isolation.

## 3. Tests by Phase
Phase 1
- T1.1 Health endpoint returns OK with DB and Redis status
- T1.2 Settings fail clearly when a required variable is missing

Phase 2 (Auth)
- T2.1 Register succeeds; duplicate email rejected
- T2.2 Password stored hashed, never plaintext
- T2.3 Login success and wrong-password failure with the same generic message
- T2.4 Protected endpoint rejects missing, malformed, expired, and revoked tokens
- T2.5 Logout revokes the token

Phase 3 (Projects)
- T3.1 CRUD works for the owner
- T3.2 Another user gets 404 on read, update, delete
- T3.3 URLs rejected: non-http scheme, private and link-local IPs, metadata address, hostnames resolving to private IPs; localhost allowed only through the allowlist
- T3.4 Credentials encrypted in the database and never returned in responses

Phase 4 (Frontend shell)
- T4.1 Protected route redirects when logged out
- T4.2 Login form shows inline errors
- T4.3 Project dialog validation
- T4.4 Manual flow: register, login, create project, logout

Phase 5 (Documents)
- T5.1 Each supported type uploads and extracts text
- T5.2 Wrong type, spoofed type, empty and oversized files rejected
- T5.3 Stored filename is generated, never the original
- T5.4 Delete removes file and record; cross-user access blocked

Phase 6 (RAG)
- T6.1 Chunks created and embedded with the right dimension
- T6.2 Query about ticket deletion retrieves the admin-only delete requirement
- T6.3 Retrieval never returns another project's chunks
- T6.4 Cache returns the same result and invalidates after a document change or delete

Phase 7 (SupportDesk)
- T7.1 Correct build satisfies every requirement (login, roles, create, view, search by ID and title, filter, status update, assign, admin-only delete, logout)
- T7.2 Defective build shows exactly: agent can delete, High priority stored wrongly, ID search broken
- T7.3 Defect switch off by default if the variable is unset

Phase 8 (Agent foundation)
- T8.1 Start run returns run_id and QUEUED immediately
- T8.2 Stub run moves through every state in order to COMPLETED with timestamps
- T8.3 Forced exception in a node yields FAILED with a message; API stays responsive
- T8.4 Second start for the same project while a run is active is blocked
- T8.5 Cancel stops the run at the next checkpoint and sets CANCELLED
- T8.6 Checkpoint exists for a run thread

Phase 9 (Planner)
- T9.1 Valid LLM output parses into test cases
- T9.2 Invalid output triggers one retry, then a clean stage failure
- T9.3 Test case without a source requirement is rejected
- T9.4 Number of tests never exceeds MAX_TESTS_PER_RUN
- T9.5 Primary provider failure or 429 triggers the fallback
- T9.6 Prompt keeps instructions and retrieved text in separate sections
- T9.7 eval: on SupportDesk requirements the plan covers create, search by ID and title, admin-only delete, agent-cannot-delete, priority persistence, and logout

Phase 10 (Executor)
- T10.1 Only allowlisted MCP tools are callable
- T10.2 Step budget and per-test timeout end a test cleanly
- T10.3 Screenshots saved and linked
- T10.4 Passwords and tokens never appear in logs, action logs or stored results
- T10.5 Page content containing "ignore previous instructions" does not change agent behavior (fixture page)
- T10.6 eval: login and delete-permission tests run against SupportDesk

Phase 11 (Analyst and report)
- T11.1 Failure output parses and uses only the five allowed categories
- T11.2 Analyst runs only for failed tests
- T11.3 Report totals and pass percentage are mathematically correct
- T11.4 Report and evidence contain no credentials
- T11.5 eval: defective build reports the three planted defects as PRODUCT_BUG; correct build reports none

Phase 12 (Frontend runs)
- T12.1 useRunStatus polls and stops on terminal states
- T12.2 Banners for FAILED and CANCELLED
- T12.3 Report renders stats, failures and screenshots
- T12.4 Manual end-to-end run on the defective build, then reopen from history

Phase 13 (Hardening)
- T13.1 Login and run-creation rate limits trigger
- T13.2 Cross-user suite: every endpoint refuses another user's resources
- T13.3 Credential-leak scan across logs, database, reports, and responses
- T13.4 Missing API key, unreachable target URL, and exhausted provider limit each yield a meaningful FAILED state
- T13.5 Repeat the full eval run three times and record consistency
- T13.6 Fresh-clone setup following README only

## 4. Agent Quality Metrics (record in MEMORY.md after each eval run)
- Planned tests traceable to a requirement: target 100 percent
- Planted defects found on the defective build: target 3 of 3
- False product bugs on the correct build: target 0
- Run completes inside free-tier limits: yes or no, with the number of LLM calls used

## 5. Exit Criteria for the MVP
All phase tests pass; all PRD success criteria demonstrated; no credential found in any scan; demo script rehearsed.
