# TestPilot Playwright MCP Subsystem

This package manages the **Model Context Protocol (MCP)** server for browser automation in TestPilot AI.

---

## Configuration & Architecture

- **Server Package**: `@executeautomation/playwright-mcp-server` pinned strictly to version `1.0.12`.
- **Communication Protocol**: JSON-RPC over `stdio` (standard input/output).
- **Process Orchestration**: The background worker (`app.agent.executor`) spawns the Node.js process directly using `mcp/node_modules/@executeautomation/playwright-mcp-server/dist/index.js` with explicit `cwd=mcp`.
- **Process Lifecycle & Cleanup**:
  - Cold-start budget: 45 seconds with automatic single-retry fallback to accommodate initial Node.js / Chromium cold launches.
  - Teardown: On run timeout, cancellation, or error, the process tree is cleanly terminated via `taskkill /F /T /PID` on Windows or POSIX `SIGKILL` on Linux.
- **Tool Allowlist**:
  - `playwright_navigate`: Navigate to target URLs within the project's allowed domain.
  - `playwright_click`: Click interactive elements by CSS selector or role.
  - `playwright_fill`: Input form fields with sanitization of secret values.
  - `playwright_select`: Select option values from dropdowns.
  - `playwright_press_key`: Send keyboard keystrokes (Enter, Tab, Escape).
  - `playwright_screenshot`: Capture full-page or viewport evidence PNGs.

---

## Installation

```bash
cd mcp
npm install
```
