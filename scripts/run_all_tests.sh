#!/usr/bin/env bash
# Run all TestPilot AI test suites on Unix / Linux / macOS
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================="
echo " Running TestPilot AI Complete Test Suite"
echo "========================================="

# 1. Backend Lint & Tests
echo -e "\n[1/4] Running Backend Tests (pytest)..."
cd "$ROOT_DIR/backend"
uv run ruff check .
uv run pytest -m "not eval"

# 2. SupportDesk Demo Tests
echo -e "\n[2/4] Running SupportDesk Target Tests..."
cd "$ROOT_DIR/supportdesk"
uv run pytest

# 3. Frontend Lint & Vitest Suite
echo -e "\n[3/4] Running Frontend Tests (vitest & oxlint)..."
cd "$ROOT_DIR/frontend"
npm run lint
npm test -- --run

# 4. Review Run Script Verification
echo -e "\n[4/4] Verifying review_run CLI helper..."
cd "$ROOT_DIR/backend"
uv run python scripts/review_run.py --help > /dev/null

cd "$ROOT_DIR"
echo -e "\n========================================="
echo " All TestPilot AI Test Suites Passed!"
echo "========================================="
