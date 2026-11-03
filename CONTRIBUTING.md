# Contributing to TestPilot AI

Thank you for your interest in contributing to **TestPilot AI**!  
We welcome contributions ranging from bug reports and documentation improvements to new agent capabilities and Playwright MCP tooling.

---

## Code of Conduct
We are committed to providing a welcoming, inclusive, and harassment-free environment for everyone. Please be respectful and constructive in all issues and pull requests.

---

## Development Setup

1. **Prerequisites**:
   - Python 3.12 pinned via [Astral uv](https://docs.astral.sh/uv/)
   - Node.js v20+ / v24+ with `npm`
   - PostgreSQL 18 with `pgvector`
   - Redis 7+

2. **Clone & Install**:
   ```bash
   git clone https://github.com/Tapas2050/testpilot-ai.git
   cd testpilot-ai
   cp .env.example .env
   ```

3. **Backend Setup**:
   ```bash
   cd backend
   uv sync
   uv run alembic upgrade head
   uv run python scripts/seed_demo.py
   ```

4. **Frontend Setup**:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

---

## Architectural Principles & Rules

When contributing code, please adhere to the project conventions:
- **Zero-Leak Credentials**: Never print, log, or commit passwords, API keys, or raw JWT tokens. Use the sanitization utilities in `app.core.sanitizer`.
- **Absolute Paths**: Storage directories must resolve against the repository root (`ROOT_DIR`), never relative to the current working directory.
- **Deterministic Evidence**: Tests and checks must never rely on subjective LLM assumptions. Evidence must cite concrete DOM text quotes or URL state transitions.
- **Async Database Sessions**: Use `async with session_factory() as session:` for all database interactions. Pytest tests must run with `NullPool` against `testpilot_test`.

---

## Testing & PR Verification

Before submitting a Pull Request, verify that all test suites pass:

```bash
# Backend unit & integration tests
cd backend && uv run pytest -m "not eval"

# Demo target tests
cd ../supportdesk && uv run pytest

# Frontend unit & component tests
cd ../frontend && npm test -- --run

# Linters
cd ../backend && uv run ruff check .
cd ../frontend && npm run lint
```
