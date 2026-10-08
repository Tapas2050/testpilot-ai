# DESIGN: TestPilot AI

Assumption: minimal, professional, developer-tool feel (no style preference was given). Change this file if that changes.

## 1. Direction
Clean, calm, information-dense. Status and evidence are the focus. Plain layout, generous whitespace, one accent color, color used mainly for pass / fail / running. Light theme only for the MVP.

## 2. Colour Palette
- Background: #FFFFFF
- Surface (cards): #F8FAFC
- Border: #E2E8F0
- Text primary: #0F172A
- Text secondary: #64748B
- Accent (primary actions): #4F46E5
- Pass: #16A34A
- Fail: #DC2626
- Blocked / warning: #D97706
- Running / info: #2563EB
Severity: Critical = fail red, High = orange, Medium = amber, Low = gray.
Never rely on color alone: every status also has a text label and an icon.

## 3. Typography
- UI: Inter (fallback system sans-serif)
- Code, IDs, action logs: JetBrains Mono (fallback monospace)
- Sizes: page title 24px semibold, section heading 18px semibold, body 14px, caption 12px

## 4. Main UI Components
Top nav bar, button (primary, secondary, danger), text input, textarea, select, card, status badge, severity badge, progress bar with stage label, stage stepper (Planning, Executing, Analyzing, Reporting), file dropzone with upload list, data list rows, expandable row (test details and action log), screenshot thumbnail with enlarge view, confirmation dialog, toast, stat tile.

## 5. Screens (6)
1. Login
2. Register
3. Dashboard
4. Project page
5. Test Run page
6. Report page
Create and edit project happen in a dialog, not a separate screen.

## 6. Purpose of Each Screen
- Login: authenticate (email, password).
- Register: create an account.
- Dashboard: project list with last run status, recent runs, New Project button.
- Project page: project details, test credentials by role, documents with dropzone, run history, Start Test Run button (disabled until at least one document exists).
- Test Run page: live status and stage, progress count, generated plan, per-test results, agent activity feed, Cancel while active.
- Report page: overall result, stat tiles, severity summary, failure list (classification, expected vs observed, explanation, suggested action), evidence screenshots. Passed tests collapsed by default.

## 7. Navigation
- Login <-> Register
- After login: Dashboard
- Dashboard -> Project page
- Project page -> Test Run page (Start Run or click a past run)
- Test Run page -> Report page (button appears when COMPLETED)
- Breadcrumbs on inner pages: Dashboard > Project > Run > Report
- Logout from user menu returns to Login
- Unauthenticated users redirect to Login

## 8. Main User Journey
Register or log in -> create project (SupportDesk, URL, credentials) -> upload requirements -> Start Test Run -> watch plan and execution -> open Report -> later reopen the run from history.

## 9. Empty States
- No projects: "No projects yet. Create one to start testing."
- No documents: "Upload your requirements so the agent knows what to test." Start Run disabled.
- No runs: "No runs yet. Start your first test run."
- Plan not ready: "Planning tests from your requirements..."
- No failures: "All tests passed. No failures to show."

## 10. Loading States
Skeleton rows for lists and cards; per-file upload progress then "Processing document..."; stage stepper with active stage animated (poll every 2 seconds); buttons show spinner and disable on submit; screenshot placeholder box.

## 11. Error States
- Login failure: inline "Incorrect email or password."
- Validation: inline under the field
- Upload rejected: reason plus allowed types and size
- Invalid target URL: inline message
- Network or server error: toast with Retry
- Run FAILED: red banner with failed stage and error, partial results shown
- Run CANCELLED: gray banner
- Rate limit from the LLM provider surfaced as a clear run message, not a crash
- Session expired: redirect to Login with message
- 404: "Not found" with link to Dashboard

## 12. Responsive Behaviour
Desktop first. Tablet: single column, stacking cards. Mobile: nav collapses to a menu, lists become stacked cards, stat tiles wrap two per row. Wide tables and logs scroll inside their own container; the page never scrolls sideways. Touch targets at least 44px.
