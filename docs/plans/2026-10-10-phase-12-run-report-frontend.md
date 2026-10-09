# Phase 12 Plan: Run and Report Frontend

Date: 2026-10-10
Phase: 12 (Run and Report Frontend)

## Objective
Build and integrate the frontend interfaces for initiating test runs, live tracking with stage stepper and activity logs, and reviewing detailed test reports with failure classifications and screenshot evidence, adhering to `DESIGN.md` (Screens 5 & 6) and `PRD.md`.

## Key Deliverables & Files

1. **API Client Extension (`frontend/src/api/client.js`)**:
   - `api.runs.create(projectId)` -> `POST /projects/{projectId}/runs`
   - `api.runs.list(projectId)` -> `GET /projects/{projectId}/runs`
   - `api.runs.get(runId)` -> `GET /runs/{runId}`
   - `api.runs.cancel(runId)` -> `POST /runs/{runId}/cancel`
   - `api.runs.report(runId)` -> `GET /runs/{runId}/report`

2. **Hook: `useRunStatus` (`frontend/src/hooks/useRunStatus.js`)**:
   - Polls `GET /runs/{runId}` every 2 seconds.
   - Automatically ceases polling upon reaching terminal states: `COMPLETED`, `FAILED`, `CANCELLED`.
   - Exposes `{ run, testCases, results, loading, error, cancelRun, refetch }`.

3. **Stage Stepper & UI Components (`frontend/src/components/`)**:
   - `StageStepper.jsx`: Renders the 4 stages (`PLANNING`, `EXECUTING`, `ANALYZING`, `REPORTING`) with visual active, completed, or failed state indicator.
   - `Banner.jsx`: Clean alerts for `FAILED` (red banner with failure stage and error message) and `CANCELLED` (neutral/gray banner).
   - `ScreenshotModal.jsx`: Modal for displaying enlarged full-resolution screenshots with authenticated token loading.

4. **Test Run Page (`frontend/src/pages/TestRunPage.jsx`)**:
   - Screen 5 per `DESIGN.md`.
   - Header with status badge, stage stepper, progress metrics.
   - Cancel button (active when not in terminal state).
   - Test Plan & Execution section: expandable test case rows displaying step details, status (PASSED / FAILED / BLOCKED), action logs, and observations.
   - View Report button when status is `COMPLETED`.
   - Activity feed or log overview.

5. **Report Page (`frontend/src/pages/ReportPage.jsx`)**:
   - Screen 6 per `DESIGN.md`.
   - Stat tiles: Total Tests, Passed, Failed, Pass Percentage.
   - Severity breakdown counters (Critical, High, Medium, Low).
   - AI Analysis summary card.
   - Failure list cards: classification badge, expected behavior vs observed behavior, explanation, suggested remediation.
   - Screenshot gallery / thumbnails with click-to-enlarge modal.
   - Expandable passed test cases section (collapsed by default).

6. **Project Page Run History (`frontend/src/pages/ProjectPage.jsx`)**:
   - "Start Test Run" button (disabled with helpful tooltip if no documents are uploaded).
   - Recent Runs list/table with status badge, timestamp, pass rate, and link to Run / Report.

7. **Routes in `App.jsx`**:
   - `/projects/:projectId/runs/:runId` -> `TestRunPage`
   - `/runs/:runId/report` -> `ReportPage`

8. **Tests (`frontend/src/__tests__/runs_and_reports.test.jsx`)**:
   - T12.1: `useRunStatus` polls every 2 seconds and ceases polling when status is COMPLETED, FAILED, or CANCELLED.
   - T12.2: TestRunPage renders FAILED banner with stage/error and CANCELLED banner.
   - T12.3: ReportPage renders stat tiles, severity counters, failure explanation, and screenshot thumbnail.
