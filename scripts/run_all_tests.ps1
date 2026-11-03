# Run all TestPilot AI test suites on Windows PowerShell
# Verifies Backend (pytest), SupportDesk (pytest), Frontend (vitest), and linters

$ErrorActionPreference = "Stop"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host " Running TestPilot AI Complete Test Suite" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan

# 1. Backend Lint & Tests
Write-Host "`n[1/4] Running Backend Tests (pytest)..." -ForegroundColor Yellow
Set-Location "$PSScriptRoot\..\backend"
uv run ruff check .
uv run pytest -m "not eval"

# 2. SupportDesk Demo Tests
Write-Host "`n[2/4] Running SupportDesk Target Tests..." -ForegroundColor Yellow
Set-Location "$PSScriptRoot\..\supportdesk"
uv run pytest

# 3. Frontend Lint & Vitest Suite
Write-Host "`n[3/4] Running Frontend Tests (vitest & oxlint)..." -ForegroundColor Yellow
Set-Location "$PSScriptRoot\..\frontend"
npm.cmd run lint
npm.cmd test -- --run

# 4. Review Run Script Verification
Write-Host "`n[4/4] Verifying review_run CLI helper..." -ForegroundColor Yellow
Set-Location "$PSScriptRoot\..\backend"
uv run python scripts/review_run.py --help | Out-Null

Set-Location "$PSScriptRoot\.."
Write-Host "`n=========================================" -ForegroundColor Green
Write-Host " All TestPilot AI Test Suites Passed!" -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor Green
