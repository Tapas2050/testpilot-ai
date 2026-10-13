"""API endpoints for TestRuns: starting, polling, listing, and cancelling."""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
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
    get_live_progress,
    get_live_step_events,
    release_run_lock,
    set_cancel_flag,
)
from app.worker import enqueue_agent_job

router = APIRouter(tags=["runs"])


def sanitize_step_timeline(steps: Optional[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Sanitize and truncate step timeline for lightweight API responses (Part 2)."""
    if not steps:
        return []
    clean_steps = []
    for s in steps:
        obs = s.get("observation")
        if obs and isinstance(obs, str) and len(obs) > 300:
            obs = obs[:297] + "..."
        thought = s.get("thought")
        if thought and isinstance(thought, str) and len(thought) > 300:
            thought = thought[:297] + "..."
        err = s.get("error")
        if err and isinstance(err, str) and len(err) > 300:
            err = err[:297] + "..."

        step_entry: dict[str, Any] = {
            "step": s.get("step"),
            "action": s.get("action", "action"),
            "status": s.get("status", "ok"),
        }
        if s.get("selector"):
            step_entry["selector"] = str(s["selector"])[:100]
        if s.get("url"):
            step_entry["url"] = str(s["url"])[:200]
        if s.get("value") is not None:
            step_entry["value"] = str(s["value"])[:100]
        if s.get("key"):
            step_entry["key"] = str(s["key"])[:50]
        if obs:
            step_entry["observation"] = obs
        if thought:
            step_entry["thought"] = thought
        if err:
            step_entry["error"] = err
        if s.get("evidence"):
            step_entry["evidence"] = str(s["evidence"])[:300]
        if s.get("check_results"):
            step_entry["check_results"] = s["check_results"]
        clean_steps.append(step_entry)
    return clean_steps


def extract_execution_details(res: Any) -> dict[str, Any]:
    """Extract and sanitize execution details (steps, duration, screenshot, evidence)."""
    if not res:
        return {
            "steps": [],
            "duration_seconds": None,
            "screenshot_path": None,
            "evidence": None,
            "final_observation": None,
            "check_results": [],
        }
    steps = getattr(res, "steps", None) or []
    sanitized = sanitize_step_timeline(steps)
    evidence = None
    final_obs = None
    check_results = []

    for s in reversed(steps):
        if s.get("check_results") and not check_results:
            check_results = s.get("check_results")
        if s.get("evidence") and not evidence:
            evidence = s.get("evidence")
        if s.get("action") == "finish" and s.get("observation") and not final_obs:
            final_obs = s.get("observation")
        elif s.get("action") == "loop_detected" and s.get("observation") and not final_obs:
            final_obs = s.get("observation")

    err = getattr(res, "error_message", None)
    if not final_obs and err:
        final_obs = err

    return {
        "steps": sanitized,
        "duration_seconds": getattr(res, "duration_seconds", None),
        "screenshot_path": getattr(res, "screenshot_path", None),
        "failure_screenshot_path": getattr(res, "failure_screenshot_path", None),
        "screenshot_error": getattr(res, "screenshot_error", None),
        "evidence": evidence,
        "final_observation": final_obs,
        "check_results": check_results,
    }


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
    failure_screenshot_path: Optional[str] = None
    screenshot_error: Optional[str] = None
    evidence: Optional[str] = None
    final_observation: Optional[str] = None
    check_results: Optional[list[dict[str, Any]]] = None


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
    test_key: Optional[str] = None
    checks: Optional[list[dict[str, Any]]] = None
    check_results: Optional[list[dict[str, Any]]] = None
    steps: Optional[list[dict[str, Any]]] = None
    duration_seconds: Optional[float] = None
    screenshot_path: Optional[str] = None
    failure_screenshot_path: Optional[str] = None
    screenshot_error: Optional[str] = None
    evidence: Optional[str] = None
    final_observation: Optional[str] = None


class RunDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: str
    stage: str = "QUEUED"
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
    server_time: Optional[datetime] = Field(default_factory=lambda: datetime.now(timezone.utc))
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
    current_test_key: Optional[str] = None
    current_step: Optional[int] = None
    total_tests: Optional[int] = 0
    completed_tests: Optional[int] = 0
    tests_done: Optional[int] = 0
    tests_total: Optional[int] = 0
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
    now = datetime.now(timezone.utc)
    new_run = TestRun(
        project_id=project_id,
        status="QUEUED",
        stage="QUEUED",
        created_at=now,
        updated_at=now,
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
    response: Response,
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

    # Live progress from Redis
    progress = await get_live_progress(run_id) or {}
    recent_events = await get_live_step_events(run_id)

    total_tests = len(run.test_cases)
    passed_tests = 0
    failed_tests = 0
    blocked_tests = 0
    not_run_tests = 0
    all_results = []
    tc_responses = []

    min_order = min((tc.order_index for tc in run.test_cases), default=0)
    for tc in run.test_cases:
        res = tc.results[0] if tc.results else None
        details = extract_execution_details(res)

        if tc.results:
            for r in tc.results:
                r_details = extract_execution_details(r)
                all_results.append(
                    TestResultResponse(
                        id=r.id,
                        test_case_id=r.test_case_id,
                        status=r.status,
                        error_message=r.error_message,
                        steps=r_details["steps"],
                        duration_seconds=r_details["duration_seconds"],
                        screenshot_path=r_details["screenshot_path"],
                        failure_screenshot_path=r_details["failure_screenshot_path"],
                        screenshot_error=r_details["screenshot_error"],
                        evidence=r_details["evidence"],
                        final_observation=r_details["final_observation"],
                        check_results=r_details["check_results"],
                    )
                )

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

        test_key = getattr(tc, "test_key", None)
        if not test_key:
            test_key = f"TC-{tc.order_index}" if min_order == 1 else f"TC-{tc.order_index + 1}"

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
                test_key=test_key,
                checks=getattr(tc, "checks", None) or [],
                check_results=details["check_results"],
                steps=details["steps"],
                duration_seconds=details["duration_seconds"],
                screenshot_path=details["screenshot_path"],
                failure_screenshot_path=details["failure_screenshot_path"],
                screenshot_error=details["screenshot_error"],
                evidence=details["evidence"],
                final_observation=details["final_observation"],
            )
        )

    # Honest progress: count only tests that actually finished
    completed_tests = passed_tests + failed_tests + blocked_tests

    failed_stage = run.failed_stage
    current_stage = (
        run.stage
        or (run.failed_stage if run.status == "FAILED" else None)
        or run.status
    )
    if run.status == "COMPLETED":
        current_stage = "COMPLETED"

    # Set no-store cache headers
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"

    now = datetime.now(timezone.utc)
    updated_at = run.updated_at or run.created_at or now

    tests_done = (
        progress.get("completed_tests")
        if progress.get("completed_tests") is not None
        else completed_tests
    )
    tests_total = (
        progress.get("total_tests")
        if progress.get("total_tests") is not None
        else total_tests
    )

    return RunDetailResponse(
        id=run.id,
        project_id=run.project_id,
        status=run.status,
        stage=current_stage,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        updated_at=updated_at,
        server_time=now,
        error_message=run.error_message,
        failed_stage=failed_stage,
        cancel_requested=run.cancel_requested,
        report=run.report,
        test_cases=tc_responses,
        results=all_results,
        agent_stage=current_stage,
        current_stage=current_stage,
        current_test=progress.get("current_test"),
        current_test_key=progress.get("current_test_key") or progress.get("current_test"),
        current_step=progress.get("current_step"),
        total_tests=total_tests,
        completed_tests=completed_tests,
        tests_done=tests_done,
        tests_total=tests_total,
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

    if not run.report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not yet generated for this run",
        )

    rep = dict(run.report)

    # Normalize failures expected / observed keys
    if "failures" in rep and isinstance(rep["failures"], list):
        for f in rep["failures"]:
            if "expected" not in f and "expected_behavior" in f:
                f["expected"] = f["expected_behavior"]
            if "expected_behavior" not in f and "expected" in f:
                f["expected_behavior"] = f["expected"]
            if "observed" not in f and "observed_behavior" in f:
                f["observed"] = f["observed_behavior"]
            if "observed_behavior" not in f and "observed" in f:
                f["observed_behavior"] = f["observed"]

    # Ensure test_cases and results are populated
    missing_tcs = "test_cases" not in rep or not rep["test_cases"]
    missing_res = "results" not in rep or not rep["results"]
    if missing_tcs or missing_res:
        tc_list = []
        res_list = []
        for tc in run.test_cases:
            res = tc.results[0] if tc.results else None
            details = extract_execution_details(res)
            test_key = getattr(tc, "test_key", None) or f"TC-{tc.order_index + 1}"
            tc_list.append({
                "id": str(tc.id),
                "title": tc.title,
                "description": tc.description,
                "source_requirement": tc.source_requirement,
                "target_role": tc.target_role,
                "status": res.status if res else tc.status,
                "order_index": tc.order_index,
                "test_key": test_key,
                "checks": getattr(tc, "checks", None) or [],
                "check_results": details["check_results"],
                "steps": details["steps"],
                "duration_seconds": details["duration_seconds"],
                "screenshot_path": details["screenshot_path"],
                "failure_screenshot_path": details["failure_screenshot_path"],
                "screenshot_error": details["screenshot_error"],
                "evidence": details["evidence"],
                "final_observation": details["final_observation"],
            })
            if res:
                res_list.append({
                    "id": str(res.id),
                    "test_case_id": str(res.test_case_id),
                    "status": res.status,
                    "error_message": res.error_message,
                    "steps": details["steps"],
                    "duration_seconds": details["duration_seconds"],
                    "screenshot_path": details["screenshot_path"],
                    "failure_screenshot_path": details["failure_screenshot_path"],
                    "screenshot_error": details["screenshot_error"],
                    "evidence": details["evidence"],
                    "final_observation": details["final_observation"],
                    "check_results": details["check_results"],
                })
        rep["test_cases"] = tc_list
        rep["results"] = res_list

    return rep


@router.get("/runs/{run_id}/screenshots/{filename}")
async def get_run_screenshot(
    run_id: uuid.UUID,
    filename: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Serve authenticated test screenshot evidence."""
    from fastapi.responses import FileResponse

    from app.services.screenshot_storage import (
        FILENAME_PATTERN,
        resolve_screenshot_file,
    )

    # Verify run ownership - cross-user access returns 404
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

    # Validate filename pattern and strictly reject directory traversal
    if (
        not filename
        or not FILENAME_PATTERN.match(filename)
        or "/" in filename
        or "\\" in filename
        or ".." in filename
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid screenshot filename format",
        )

    target_file = resolve_screenshot_file(run_id, filename)
    if not target_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screenshot evidence not found",
        )

    return FileResponse(
        target_file,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=300"},
    )
