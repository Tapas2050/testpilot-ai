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
from app.models.test_run import TestRun
from app.models.user import User
from app.services.run_service import (
    acquire_run_lock,
    get_cached_run_status,
    release_run_lock,
    set_cancel_flag,
)
from app.worker import enqueue_agent_job

router = APIRouter(tags=["runs"])


# Pydantic schemas
class TestCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: Optional[str] = None
    source_requirement: Optional[str] = None
    target_role: Optional[str] = None
    status: str
    order_index: int


class RunDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    cancel_requested: bool
    report: Optional[dict[str, Any]] = None
    test_cases: list[TestCaseResponse] = []


class RunSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    cancel_requested: bool
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0


ACTIVE_STATUSES = {"QUEUED", "PLANNING", "EXECUTING", "ANALYZING", "REPORTING"}


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
    from app.core.config import get_settings

    settings = get_settings()
    target_db_url = (
        db.bind.url.render_as_string(hide_password=False)
        if db.bind
        else str(settings.DATABASE_URL)
    )
    await enqueue_agent_job(new_run.id, project_id, db_url=target_db_url)

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

    # Check if there is an active stage in Redis cache
    cached = await get_cached_run_status(run_id)
    if cached and run.status in ACTIVE_STATUSES:
        # Cache reflects active transition
        run.status = cached.get("status", run.status)

    return run


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
