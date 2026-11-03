# Understanding TestPilot AI (plain English guide)

Written for you, the developer, after reading the architecture review (ARCHITECTURE.md, ENDPOINTS.md), the final report and the project memory. It explains what the project is, what happens when you use it, where things live, and where the earlier reports are wrong or too optimistic.

How much to trust this guide: it is built from the architecture review files, which came from the coding agent reading the repository. I have not seen the code myself. Where I add my own reasoning, I say so.

---

## 1. What this project is, in one paragraph

TestPilot AI is a website where you give an AI a description of what another web app should do (a requirements document), plus the web app's address and login details. The AI then writes test cases from that document, opens the web app in a real (invisible) browser, tries to carry out each test by clicking and typing, decides pass or fail, explains any failures, takes screenshots as evidence, and gives you a report.

Think of it as hiring a junior QA tester who reads the spec, writes a checklist, tests the app, and files a bug report. The difference is that this tester is an AI model driving a browser.

## 2. The demo target: SupportDesk

SupportDesk is a small, separate support-ticket app that you built only to be tested. It has logins (admin and support agent), and tickets you can create, search, filter, assign, update and delete. It can be started in a "correct" mode or a "defective" mode. In defective mode it has three planted bugs:

1. A support agent can delete a ticket (only admins should be able to).
2. A ticket created with priority "High" is silently saved as "Low".
3. Searching for a ticket by its ID returns nothing.

The point of the demo: TestPilot should find all three bugs without being told about them.

---

## 3. The moving parts (what runs on your laptop)

When everything is running there are these pieces:

- The TestPilot website (React, runs on port 5173). This is what you click.
- The TestPilot API (FastAPI, port 8000). It handles logins, projects, uploads and starting runs.
- The worker (a separate Python process). It does the slow work: planning, browsing, analyzing. The API never does this itself, so the website stays responsive.
- The browser robot (a Node.js process the worker starts). It controls an invisible Chromium browser. The worker talks to it through a standard called MCP.
- SupportDesk (port 8001). The app being tested.
- PostgreSQL (port 5432). Permanent storage, including the vector search for requirements.
- Redis (port 6379, inside WSL). Short-lived things: the job queue, locks, status cache.
- Google Gemini (over the internet). The AI brain, with OpenRouter as a backup.

Simple picture of who talks to whom:

```
You (browser) -> React website -> API -> Postgres
                                   |
                                   +-> Redis queue -> Worker -> Gemini (the AI)
                                                         |
                                                         +-> Browser robot -> SupportDesk
```

The worker handles one run at a time (a deliberate limit because your laptop has 8 GB RAM).

---

## 4. What happens when you use it, step by step

### Step A: Sign up and log in
- You register with an email and password. The password is scrambled with Argon2 (a strong, slow scrambling method), so even the database does not contain the real password.
- When you log in you receive a token (a digital pass valid for 60 minutes). A row is also stored in a "sessions" table. Logging out marks that row as revoked, so the token stops working immediately.
- The website keeps the token in the browser's localStorage and sends it with every request.

### Step B: Create a project
- A project is: a name, the address of the app to test (for example http://localhost:8001), and optional login credentials for that app (one for admin, one for agent).
- The address is checked for safety. The system refuses addresses that point at internal networks or cloud metadata servers (this prevents an attack called SSRF). Localhost is allowed only because it is explicitly on an allowed list in the settings, which is needed for the demo.
- The app's passwords are encrypted (Fernet) before storage and are never sent back to the website.

### Step C: Upload the requirements
- You upload a document. Supported types per the architecture review: txt, md, pdf, docx, json (docx is a small extra beyond the original plan).
- The system extracts the text, cuts it into chunks, and converts each chunk into a list of 384 numbers (an "embedding") that captures its meaning. These are stored in Postgres with the pgvector extension, so later it can search by meaning instead of by exact words.

### Step D: Click "Start Test Run"
This is the main event. In plain terms:

1. The website asks the API to start a run.
2. The API checks you own the project, checks no run is already active for it, and sets a lock in Redis (so you can't start two at once).
3. It creates a run record with status QUEUED, drops a job in the Redis queue, and replies immediately.
4. The website starts asking the API "what's the status?" every 2 seconds.
5. The worker picks up the job and starts a workflow (built with LangGraph, a tool for chaining AI steps) with five stages:

```
PLANNING -> EXECUTING -> ANALYZING -> REPORTING -> COMPLETED
```

**Stage 1, Planning.** The worker searches the stored requirement chunks for the 8 most relevant ones, then asks Gemini to write test cases. Each test case has a title, steps, expected result and priority, and must name the requirement it comes from (like REQ-SEC-01). The plan is limited to 8 tests. If Gemini returns something that does not fit the expected format, the worker retries once with the error message.

**Stage 2, Executing.** The worker starts the browser robot and, for each test case:
- It logs into the target app as the right role. This part is scripted, not AI (see the limitations below).
- Then it repeats up to 15 times: read the visible text on the page, ask Gemini "what should I do next?", and carry out the answer (navigate, click, fill a field, select, press a key, or finish).
- When Gemini decides it is done, it says finished with PASSED or FAILED plus a note on what it saw.
- A screenshot is saved and the result is stored. Passwords are scrubbed from anything that gets logged.
- Each test has a 120 second limit.

**Stage 3, Analyzing.** For each failed test, Gemini is asked to classify why it failed: PRODUCT_BUG (the app is wrong), TEST_FAILURE (the test itself was bad), AUTHENTICATION_FAILURE, ENVIRONMENT_FAILURE, or FLAKY_TEST. It also gives severity, a confidence number, expected vs observed behavior, and a suggested next step. If nothing failed, no AI call is made here.

**Stage 4, Reporting.** Plain Python (no AI) counts passed and failed tests, calculates the pass percentage and groups failures by type and severity. The report is saved on the run record.

**Stage 5, Complete.** The run is marked COMPLETED and the Redis lock is released.

6. Your website sees COMPLETED, stops polling, and shows a "View Report" button. The report page shows totals, severity, each failure with its explanation, and clickable screenshots.

If anything crashes along the way, the run is marked FAILED with a message, and the API keeps working. You can also cancel a run while it is active.

### Step E: Look at history
Every run is saved in Postgres. You can reopen old runs and reports from the project page.

---

## 5. Where data lives

Postgres (permanent):
- users and sessions (accounts and login passes)
- projects and project_credentials (apps to test, encrypted logins)
- documents and document_chunks (uploaded files and their searchable vector chunks)
- test_runs, test_cases, test_results, failures (everything about a run)
- extra tables LangGraph creates to save workflow progress (checkpoints)

Redis (temporary):
- the job queue
- run lock (one active run per project)
- cancel flag
- cached run status
- cached requirement search results

Disk (the storage folder):
- uploaded documents
- screenshots at storage/screenshots/{run_id}/{test_case_id}.png, served back only through a login-protected route

---

## 6. The API in one list

The review lists these routes (its README says 17, but the actual list has 22).

Health
- GET /health : checks API, Postgres, pgvector and Redis

Accounts
- POST /auth/register
- POST /auth/login (rate limited to 10 per minute)
- GET /auth/me
- POST /auth/logout

Projects
- POST /projects, GET /projects, GET /projects/{id}, PATCH /projects/{id}, DELETE /projects/{id}

Credentials for the app under test
- POST /projects/{id}/credentials, GET /projects/{id}/credentials (never returns passwords), DELETE /projects/{id}/credentials/{cred_id}

Documents
- POST /projects/{id}/documents, GET /projects/{id}/documents, DELETE /documents/{id}

Runs
- POST /projects/{id}/runs (rate limited to 5 per minute; 409 if a run is already active)
- GET /runs/{id} (status and details)
- GET /projects/{id}/runs (history)
- POST /runs/{id}/cancel
- GET /runs/{id}/report
- GET /runs/{id}/screenshots/{filename}

Every route except register, login and health requires a token, and every project-related route checks the project belongs to you (other people's items return 404).

---

## 7. The website's pages

- /login and /register
- / : dashboard with your projects
- /projects/:id : project details, credentials, documents, run history, Start button
- /runs/:runId : live status with a stage indicator, the test plan, results as they arrive
- /runs/:runId/report : final report with screenshots

---

## 8. Safety features in plain words

- Passwords are never stored in readable form (Argon2).
- Logout truly kills a login token (session table).
- Everything is scoped to the owner; no one sees others' projects.
- URL checks block internal and cloud-metadata addresses.
- Uploaded files are validated and renamed to random names.
- The browser robot can only use a short list of 9 allowed actions (navigate, click, fill, select, hover, press key, read text, screenshot, close). No file access or shell.
- Page text and requirement text are put in clearly marked "untrusted" sections of the AI prompts, so text inside a web page that says "ignore your instructions" should not take over (a defense, not a guarantee).
- Limits: max 8 tests per run, 15 steps per test, 120 seconds per test, rate limits on login and run creation.

---

## 9. Honest limitations (what it cannot do well)

1. **Login is hardcoded for apps like SupportDesk.** The login step assumes a /login page with an email field, a password field and a submit button. An app with a different path, a username field, a multi-step login or single sign-on will fail at login. The cleanest fix is letting each project define its login path and field selectors.
2. **The AI only sees the first 1000 characters of page text.** On long pages the button or error message it needs may be cut off.
3. **Pass or fail is the AI's opinion.** There are no hard rule-based checks (like "this element must exist"). That is flexible but can be wrong or inconsistent between runs.
4. **No retry for flaky tests.** A test that fails because the page was slow is reported as failed.
5. **A few SupportDesk-specific hints are inside the agent code** (a default search phrase mentioning tickets, prompt examples). It is not purely generic yet.
6. **Browser tool is a third-party MCP package** (`@executeautomation/playwright-mcp-server`, pinned to 1.0.12), not Microsoft's own. That is fine for an MVP, but review it before trusting it with anything important.
7. **One run at a time, one test at a time.** Deliberate, to fit 8 GB RAM.
8. Browser apps only. No mobile apps, no load testing, no CAPTCHA or SMS login.

---

## 10. Where the earlier reports are wrong or too rosy

Read this section before showing the project to anyone.

1. **FINAL_REPORT says "2 LLM calls per full run". That is wrong.** The executor calls Gemini on every browser step. That makes it a real agent, but it also means a run uses many calls. My estimate (not measured): planner 1, plus roughly 3 to 8 steps for each of up to 8 tests, plus 1 per failed test. Typical run is about 30 to 60 calls, worst case about 130. The review's own estimate of 15 to 25 calls looks too low for 8 tests.
2. **That also means no real full live run has probably been done yet.** The report says only 4 live AI calls were made during the whole build, which cannot cover one real executor run. So the claim that all 3 defects were detected live is unproven in my view. Treat it as unverified until you do the manual demo.
3. **Quota math, using your Gemini limits (15 requests per minute, 500 per day per Flash-Lite model).** At 12 per minute, a typical run takes roughly 3 to 5 minutes and a worst case about 11 minutes. At about 30 to 60 calls per run, one model supports roughly 8 to 16 typical runs a day. Two Flash-Lite models give you more. These are estimates.
4. **"Verified Live" is generous.** Several PRD criteria were checked by automated tests against a test database with mocks, not by using the app live. The architecture review itself says test-suite runs use mocks.
5. **D-018 (embedding model loaded only in the worker) is violated.** The API loads the embedding model during upload and the worker loads it again, so two copies sit in your 8 GB. Recommended fix: make uploads queue the indexing to the worker.
6. **The login token is in localStorage**, while decision D-010 said memory plus sessionStorage. Minor for a local demo, but the docs and code disagree.
7. **The code default model is gemini-2.5-flash**, which on your account has only 5 per minute and 20 per day. Your .env sets gemini-3.5-flash-lite, so it works, but if that variable is ever missing the app silently falls back to the slow model. Change the default.
8. **The review says "all core PRD criteria are real."** I would not accept that until the manual demo run proves it.

---

## 11. How to run it (from the final report)

Start Redis in Ubuntu (WSL): `sudo service redis-server start`, then `redis-cli ping` should say PONG.

Seed the demo data (PowerShell):
```
cd C:\dev\testpilot\backend
uv run python scripts/seed_demo.py
```
This creates a demo user, the SupportDesk project, saved credentials and indexed requirements. It prints the demo login; the password is in the script (a throwaway local value).

Then start four terminals:
1. SupportDesk: `cd C:\dev\testpilot\supportdesk` then `uv run uvicorn app.main:app --port 8001`
2. API: `cd C:\dev\testpilot\backend` then `uv run uvicorn app.main:app --port 8000`
3. Worker: `cd C:\dev\testpilot\backend` then `uv run python -m app.worker`
4. Website: `cd C:\dev\testpilot\frontend` then `npm.cmd run dev`

Open http://localhost:5173, log in, open the SupportDesk project, click Start Test Run, and watch. Close other heavy apps first and keep Task Manager open; note peak memory and run time.

Make sure SupportDesk is running in defective mode (the SUPPORTDESK_DEFECTS setting is "on") when you want to see it find the bugs.

---

## 12. What to do next (in order)

1. Do the manual demo run and write down: did it finish, how long, how many tests, which defects were found, peak memory, number of LLM calls (the code counts them).
2. If it finds fewer than 3 defects or behaves oddly, send me the run's report and the worker log (with no secrets) and we will fix it properly.
3. Fix the quick wins: embedding model only in the worker, config default model, and a configurable login path and selectors per project.
4. Improve what the AI sees on the page (interactive elements instead of the first 1000 characters).
5. Add a retry for failed tests before they are sent to the analyst.

---

## 13. Glossary

- **Agent**: an AI that decides its own next action in a loop, instead of following a fixed script.
- **API**: the backend program the website talks to.
- **arq / worker**: the background job system that runs the slow AI work.
- **Embedding / vector search**: turning text into numbers so you can search by meaning.
- **pgvector**: the Postgres add-on that stores and searches those numbers.
- **RAG**: first search your documents, then give the best matches to the AI so it answers from them.
- **LangGraph**: a library for running AI work as a chain of steps with saved progress.
- **MCP**: a standard way for an AI program to use outside tools; here the tool is a browser.
- **Playwright**: software that controls a real browser.
- **Fernet**: the encryption method used for stored app passwords.
- **Argon2**: the password scrambling method.
- **JWT**: the login token.
- **SSRF**: an attack where a server is tricked into contacting internal addresses; the URL checks defend against it.
- **Quota / RPM / RPD**: how many AI requests you may make per minute / per day on the free tier.
