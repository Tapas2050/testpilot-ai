# TestPilot AI — Frontend SPA

The frontend for **TestPilot AI** is a responsive Single Page Application built with **React 19**, **Vite 6**, and **Tailwind CSS**. It provides real-time test run monitoring, interactive stepper visualizations, evidence inspection, and failure analytics.

---

## Key Pages & Routing

| Route | Page Component | Purpose |
|---|---|---|
| `/login` | `LoginPage` | User authentication via email/password |
| `/register` | `RegisterPage` | New user account registration |
| `/` | `Dashboard` | Project overview, project creation modal, recent runs |
| `/projects/:id` | `ProjectPage` | Project detail, stored target credentials, requirements upload dropzone, run history |
| `/projects/:id/runs/:runId` | `TestRunPage` | Live execution view with 4-stage stepper, progress bar, active test row details, and step activity feed |
| `/runs/:runId/report` | `ReportPage` | Comprehensive executive report, defect classification cards, and side-by-side screenshot evidence |

---

## State & Polling Architecture

- **`useRunStatus` Hook**: Implements high-frequency polling (1.5s interval) against `/runs/{run_id}`.
  - Enforces monotonic updates using `updated_at` timestamps to reject out-of-order network responses.
  - Aligns elapsed execution timer using server-provided `server_time`.
  - Automatically ceases polling upon reaching terminal states (`COMPLETED`, `FAILED`, `CANCELLED`).
  - Displays a stall alert if no progress updates arrive for >60 seconds.
- **`ScreenshotViewer` Component**: Authenticated image display that fetches binary blobs via bearer token, transforms them into object URLs, and revokes URLs cleanly on component unmount to prevent browser memory leaks.

---

## Development & Testing

```bash
# Install dependencies
npm.cmd install

# Start Vite development server on port 5173
npm.cmd run dev

# Run Vitest test suite (32 tests across 8 files)
npm.cmd test -- --run

# Run Oxlint linter
npm.cmd run lint

# Build production bundle
npm.cmd run build
```
