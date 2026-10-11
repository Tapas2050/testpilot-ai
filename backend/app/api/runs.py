"""API endpoints for TestRuns: starting, polling, listing, and cancelling."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.rate_limit import rate_limit_create_run
from app.models.project import Project
from app.models.test_run import TestCase, TestRun
from app.models.user import User
from app.services.run_service import (
    ACTIVE_STATUSES,
    acquire_run_lock,
    check_and_fail_dead_run,
    get_cached_run_status,
    get_live_progress,
    get_live_step_events,
    release_run_lock,
    set_cancel_flag,
)
from app.worker import enqueue_agent_job

router = APIRouter(tags=["runs"])


# Pydantic schemas
class TestResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_case_id: uuid.UUID
    status: str
    error_message: Optional[str] = None
    steps: Optional[list[dict[str, Any]]] = None
    duration_seconds: Optional[float] = None
    screenshot_path: Optional[str] = None


class TestCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: Optional[str] = None
    source_requirement: Optional[str] = None
    target_role: Optional[str] = None
    status: str
    order_index: int
    error_message: Optional[str] = None


class RunDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    failed_stage: Optional[str] = None
    cancel_requested: bool
    report: Optional[dict[str, Any]] = None
    test_cases: list[TestCaseResponse] = []
    results: list[TestResultResponse] = []

    # Live progress fields
    agent_stage: Optional[str] = None
    current_stage: Optional[str] = None
    current_test: Optional[str] = None
    current_step: Optional[int] = None
    total_tests: Optional[int] = 0
    completed_tests: Optional[int] = 0
    passed_tests: Optional[int] = 0
    failed_tests: Optional[int] = 0
    blocked_tests: Optional[int] = 0
    not_run_tests: Optional[int] = 0
    recent_events: list[dict[str, Any]] = []


class RunSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    failed_stage: Optional[str] = None
    cancel_requested: bool
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    blocked_tests: int = 0
    not_run_tests: int = 0


@router.post(
    "/projects/{project_id}/runs",
    response_model=RunDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit_create_run)],
)
async def create_test_run(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a new test run for a project. Returns immediately with status QUEUED."""
    # Verify project exists and belongs to current user
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user.id)
    project = (await db.execute(stmt)).scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    # Check database for active run
    active_stmt = select(TestRun).where(
        TestRun.project_id == project_id,
        TestRun.status.in_(ACTIVE_STATUSES),
    )
    existing_active = (await db.execute(active_stmt)).scalars().first()
    if existing_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A test run is already active for this project",
        )

    # Create new run in QUEUED
    new_run = TestRun(
        project_id=project_id,
        status="QUEUED",
        created_at=datetime.now(timezone.utc),
    )
    db.add(new_run)
    await db.commit()
    await db.refresh(new_run)

    # Acquire Redis duplicate lock
    lock_acquired = await acquire_run_lock(project_id, new_run.id)
    if not lock_acquired:
        # Another process just started a run
        await db.delete(new_run)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A test run is already active for this project",
        )

    # Enqueue background job
    # We pass the db url if needed for test database execution
    await enqueue_agent_job(new_run.id)

    return new_run


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_test_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the status and details of a test run."""
    stmt = (
        select(TestRun)
        .options(selectinload(TestRun.test_cases).selectinload(TestCase.results))
        .join(Project, TestRun.project_id == Project.id)
        .where(TestRun.id == run_id, Project.user_id == user.id)
    )
    run = (await db.execute(stmt)).scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    # Check for dead worker if run is in active status
    if run.status in ACTIVE_STATUSES:
        await check_and_fail_dead_run(run, db)

    # Check if there is an active stage / progress in Redis cache
    cached = await get_cached_run_status(run_id)
    progress = await get_live_progress(run_id) or {}
    recent_events = await get_live_step_events(run_id)

    total_tests = len(run.test_cases)
    passed_tests = 0
    failed_tests = 0
    blocked_tests = 0
    not_run_tests = 0
    all_results = []
    tc_responses = []

    for tc in run.test_cases:
        res = tc.results[0] if tc.results else None
        if tc.results:
            all_results.extend(tc.results)

        st = res.status if res else tc.status
        err = (res.error_message if res else "") or ""

        if st == "PASSED":
            passed_tests += 1
        elif st == "FAILED":
            failed_tests += 1
        elif (
            st == "NOT_RUN"
            or err.startswith("Not executed: run stopped")
            or "did not finish before run terminated" in err
        ):
            not_run_tests += 1
        elif st == "BLOCKED":
            blocked_tests += 1
        elif st == "PENDING":
            if run.status in ("COMPLETED", "FAILED", "CANCELLED"):
                not_run_tests += 1

        tc_responses.append(
            TestCaseResponse(
                id=tc.id,
                title=tc.title,
                description=tc.description,
                source_requirement=tc.source_requirement,
                target_role=tc.target_role,
                status=st,
                order_index=tc.order_index,
                error_message=err if err else None,
            )
        )

    # Honest progress: count only tests that actually finished
    completed_tests = passed_tests + failed_tests + blocked_tests

    failed_stage = run.failed_stage or (cached.get("failed_stage") if cached else None)

    if run.status == "FAILED":
        current_stage = (
            failed_stage
            or (cached.get("stage") if cached else None)
            or progress.get("stage")
            or "QUEUED"
        )
    elif run.status == "COMPLETED":
        current_stage = "COMPLETED"
    elif run.status in ACTIVE_STATUSES:
        current_stage = (
            progress.get("stage") or (cached.get("stage") if cached else None) or run.status
        )
    else:
        current_stage = (
            (cached.get("stage") if cached else None) or progress.get("stage") or "QUEUED"
        )

    effective_status = run.status
    if cached and run.status in ACTIVE_STATUSES:
        effective_status = cached.get("status", run.status)

    return RunDetailResponse(
        id=run.id,
        project_id=run.project_id,
        status=effective_status,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
        failed_stage=failed_stage,
        cancel_requested=run.cancel_requested,
        report=run.report,
        test_cases=tc_responses,
        results=all_results,
        agent_stage=current_stage,
        current_stage=current_stage,
        current_test=progress.get("current_test"),
        current_step=progress.get("current_step"),
        total_tests=total_tests,
        completed_tests=completed_tests,
        passed_tests=passed_tests,
        failed_tests=failed_tests,
        blocked_tests=blocked_tests,
        not_run_tests=not_run_tests,
        recent_events=recent_events,
    )


@router.get("/projects/{project_id}/runs", response_model=list[RunSummaryResponse])
async def list_project_runs(
    project_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all test runs for a project."""
    # Verify project ownership
    stmt = select(Project).where(Project.id == project_id, Project.user_id == user.id)
    project = (await db.execute(stmt)).scalar_one_or_none()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    runs_stmt = (
        select(TestRun)
        .options(selectinload(TestRun.test_cases))
        .where(TestRun.project_id == project_id)
        .order_by(desc(TestRun.created_at))
    )
    runs = (await db.execute(runs_stmt)).scalars().all()

    summaries = []
    for r in runs:
        total = len(r.test_cases)
        passed = sum(1 for tc in r.test_cases if tc.status == "PASSED")
        failed = sum(1 for tc in r.test_cases if tc.status == "FAILED")
        summaries.append(
            RunSummaryResponse(
                id=r.id,
                project_id=r.project_id,
                status=r.status,
                created_at=r.created_at,
                started_at=r.started_at,
                completed_at=r.completed_at,
                error_message=r.error_message,
                cancel_requested=r.cancel_requested,
                total_tests=total,
                passed_tests=passed,
                failed_tests=failed,
            )
        )
    return summaries


@router.post("/runs/{run_id}/cancel", response_model=RunDetailResponse)
async def cancel_test_run(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Request cancellation of an active test run."""
    stmt = (
        select(TestRun)
        .options(selectinload(TestRun.test_cases))
        .join(Project, TestRun.project_id == Project.id)
        .where(TestRun.id == run_id, Project.user_id == user.id)
    )
    run = (await db.execute(stmt)).scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    if run.status in {"COMPLETED", "FAILED", "CANCELLED"}:
        return run

    # Set cancel flag in DB and Redis
    run.cancel_requested = True
    await db.commit()
    await set_cancel_flag(run_id)

    # Release project lock
    await release_run_lock(run.project_id)

    return run


@router.get("/runs/{run_id}/report")
async def get_test_run_report(
    run_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the generated test run report JSON."""
    stmt = (
        select(TestRun)
        .join(Project, TestRun.project_id == Project.id)
        .where(TestRun.id == run_id, Project.user_id == user.id)
    )
    run = (await db.execute(stmt)).scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    if not run.report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not yet generated for this run",
        )

    return run.report


@router.get("/runs/{run_id}/screenshots/{filename}")
async def get_run_screenshot(
    run_id: uuid.UUID,
    filename: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Serve authenticated test screenshot evidence."""
    from pathlib import Path

    from fastapi.responses import FileResponse

    from app.core.config import get_settings

    # Verify run ownership
    stmt = (
        select(TestRun)
        .join(Project, TestRun.project_id == Project.id)
        .where(TestRun.id == run_id, Project.user_id == user.id)
    )
    run = (await db.execute(stmt)).scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test run not found",
        )

    # Sanitize filename against directory traversal
    clean_name = Path(filename).name
    if not clean_name.endswith(".png"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid screenshot file format",
        )

    settings = get_settings()
    file_path = Path(settings.STORAGE_DIR) / "screenshots" / str(run_id) / clean_name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screenshot evidence not found",
        )

    return FileResponse(file_path, media_type="image/png")
