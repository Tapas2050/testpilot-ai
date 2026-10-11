"""Run service for managing execution lifecycle, duplicate locks,
Redis caching, and cancellation.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.models.test_run import TestCase, TestResult, TestRun

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"QUEUED", "PLANNING", "EXECUTING", "ANALYZING", "REPORTING"}


def get_lock_ttl_seconds() -> int:
    """Return Redis lock and cache TTL that is strictly longer than RUN_TIMEOUT_SECONDS."""
    settings = get_settings()
    return max(settings.RUN_TIMEOUT_SECONDS + 300, 2100)


async def acquire_run_lock(project_id: uuid.UUID, run_id: uuid.UUID) -> bool:
    """Acquire a per-project run lock in Redis. Returns True if acquired, False if locked."""
    redis = get_redis_client()
    lock_key = f"project_run_lock:{project_id}"
    ttl = get_lock_ttl_seconds()
    acquired = await redis.set(lock_key, str(run_id), nx=True, ex=ttl)
    return bool(acquired)


async def release_run_lock(project_id: uuid.UUID) -> None:
    """Release the per-project run lock in Redis."""
    redis = get_redis_client()
    lock_key = f"project_run_lock:{project_id}"
    await redis.delete(lock_key)


async def set_cancel_flag(run_id: uuid.UUID) -> None:
    """Set cancellation flag in Redis for fast polling by running agent nodes."""
    redis = get_redis_client()
    ttl = get_lock_ttl_seconds()
    await redis.set(f"run_cancel:{run_id}", "1", ex=ttl)


async def is_cancel_flag_set(run_id: uuid.UUID) -> bool:
    """Check if cancellation was requested for this run."""
    redis = get_redis_client()
    val = await redis.get(f"run_cancel:{run_id}")
    return bool(val)


async def set_worker_heartbeat(run_id: uuid.UUID, ttl: int = 60) -> None:
    """Set or refresh worker heartbeat in Redis with a TTL (default 60s)."""
    try:
        redis = get_redis_client()
        await redis.set(f"worker_heartbeat:{run_id}", "alive", ex=ttl)
    except Exception as e:
        logger.debug("[run_id=%s] Failed to set worker heartbeat: %s", run_id, e)


async def check_worker_heartbeat(run_id: uuid.UUID) -> bool:
    """Check if worker heartbeat key exists in Redis."""
    try:
        redis = get_redis_client()
        val = await redis.get(f"worker_heartbeat:{run_id}")
        return val is not None
    except Exception as e:
        logger.warning("[run_id=%s] Failed to check worker heartbeat: %s", run_id, e)
        return False


async def cache_run_status(
    run_id: uuid.UUID,
    status: str,
    stage: str,
    error: Optional[str] = None,
    failed_stage: Optional[str] = None,
) -> None:
    """Cache the current status and stage in Redis."""
    redis = get_redis_client()
    data = {
        "run_id": str(run_id),
        "status": status,
        "stage": stage,
        "failed_stage": failed_stage,
        "error": error,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await redis.set(f"run_status:{run_id}", json.dumps(data), ex=86400)


async def get_cached_run_status(run_id: uuid.UUID) -> Optional[dict[str, Any]]:
    """Retrieve run status from Redis cache if available."""
    redis = get_redis_client()
    val = await redis.get(f"run_status:{run_id}")
    if val:
        try:
            return json.loads(val)
        except Exception:
            return None
    return None


async def update_run_in_db(
    run_id: uuid.UUID,
    status: Optional[str] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
    error_message: Optional[str] = None,
    failed_stage: Optional[str] = None,
    report: Optional[dict[str, Any]] = None,
    cancel_requested: Optional[bool] = None,
    session: Optional[AsyncSession] = None,
    db_url: Optional[str] = None,
) -> None:
    """Update fields of a TestRun record in PostgreSQL."""
    values: dict[str, Any] = {}
    if status is not None:
        values["status"] = status
    if started_at is not None:
        values["started_at"] = started_at
    if completed_at is not None:
        values["completed_at"] = completed_at
    if error_message is not None:
        values["error_message"] = error_message
    if failed_stage is not None:
        values["failed_stage"] = failed_stage
    if report is not None:
        values["report"] = report
    if cancel_requested is not None:
        values["cancel_requested"] = cancel_requested

    if not values:
        return

    if session is not None:
        await session.execute(update(TestRun).where(TestRun.id == run_id).values(**values))
        await session.commit()
    else:
        from app.core.database import get_async_session_factory

        factory = get_async_session_factory(db_url)
        async with factory() as s:
            await s.execute(update(TestRun).where(TestRun.id == run_id).values(**values))
            await s.commit()


async def append_live_step_event(
    run_id: uuid.UUID, event: dict[str, Any], max_events: int = 100
) -> None:
    """Store live step events in Redis as a capped list with an expiry."""
    redis = get_redis_client()
    key = f"run_events:{run_id}"
    try:
        await redis.rpush(key, json.dumps(event))
        await redis.ltrim(key, -max_events, -1)
        await redis.expire(key, 86400)
    except Exception:
        pass


async def get_live_step_events(run_id: uuid.UUID, limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve the recent live step events from Redis."""
    redis = get_redis_client()
    key = f"run_events:{run_id}"
    try:
        raw_events = await redis.lrange(key, -limit, -1)
        events = []
        for raw in raw_events:
            try:
                events.append(json.loads(raw))
            except Exception:
                continue
        return events
    except Exception:
        return []


async def update_live_progress(
    run_id: uuid.UUID,
    stage: Optional[str] = None,
    current_test: Optional[str] = None,
    current_step: Optional[int] = None,
    total_tests: Optional[int] = None,
    completed_tests: Optional[int] = None,
) -> None:
    """Update live execution progress in Redis."""
    redis = get_redis_client()
    key = f"run_progress:{run_id}"
    try:
        raw = await redis.get(key)
        data = json.loads(raw) if raw else {}
        if stage is not None:
            data["stage"] = stage
        if current_test is not None:
            data["current_test"] = current_test
        if current_step is not None:
            data["current_step"] = current_step
        if total_tests is not None:
            data["total_tests"] = total_tests
        if completed_tests is not None:
            data["completed_tests"] = completed_tests
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await redis.set(key, json.dumps(data), ex=86400)
    except Exception:
        pass


async def get_live_progress(run_id: uuid.UUID) -> Optional[dict[str, Any]]:
    """Retrieve live execution progress from Redis."""
    redis = get_redis_client()
    key = f"run_progress:{run_id}"
    try:
        raw = await redis.get(key)
        if raw:
            return json.loads(raw)
    except Exception:
        return None
    return None


async def clear_live_progress_keys(run_id: uuid.UUID) -> None:
    """Clear transient live progress, step events, and worker heartbeat keys from Redis."""
    try:
        redis = get_redis_client()
        await redis.delete(
            f"run_progress:{run_id}",
            f"run_events:{run_id}",
            f"worker_heartbeat:{run_id}",
        )
    except Exception:
        pass


async def check_and_fail_dead_run(run: TestRun, session: AsyncSession) -> bool:
    """
    Check if an active-status run has lost its worker heartbeat and is older than 90 seconds.
    If dead, mark it FAILED with 'Worker stopped responding', release lock, clear keys,
    and update run in DB and cache.
    Returns True if the run was marked dead, False otherwise.
    """
    if run.status not in ACTIVE_STATUSES:
        return False

    now = datetime.now(timezone.utc)
    ref_time = run.started_at or run.created_at
    if ref_time.tzinfo is None:
        ref_time = ref_time.replace(tzinfo=timezone.utc)
    age_seconds = (now - ref_time).total_seconds()
    if age_seconds <= 90:
        return False

    has_heartbeat = await check_worker_heartbeat(run.id)
    if has_heartbeat:
        return False

    # Run is active, >90s old, and missing heartbeat -> dead worker!
    logger.warning(
        "[run_id=%s] Detected dead worker run (age=%.1fs, no heartbeat). Marking FAILED.",
        run.id,
        age_seconds,
    )
    run.failed_stage = run.status if run.status != "FAILED" else "QUEUED"
    run.status = "FAILED"
    run.error_message = "Worker stopped responding"
    run.completed_at = now

    # Mark unfinished test cases as BLOCKED and ensure TestResult exists
    try:
        tc_stmt = select(TestCase).where(TestCase.run_id == run.id).order_by(TestCase.order_index)
        tcs = (await session.execute(tc_stmt)).scalars().all()
        for tc in tcs:
            if tc.status not in ("PASSED", "FAILED", "BLOCKED"):
                tc.status = "BLOCKED"
                session.add(tc)

        res_stmt = (
            select(TestResult)
            .join(TestCase, TestResult.test_case_id == TestCase.id)
            .where(TestCase.run_id == run.id)
        )
        existing_results = (await session.execute(res_stmt)).scalars().all()
        existing_tc_ids = {r.test_case_id for r in existing_results}
        for tc in tcs:
            if tc.id not in existing_tc_ids:
                blocked_res = TestResult(
                    test_case_id=tc.id,
                    status="BLOCKED",
                    error_message="Not executed: run stopped (Worker stopped responding)",
                )
                session.add(blocked_res)
                existing_results.append(blocked_res)

        if not run.report:
            from app.agent.report import generate_run_report

            tcs_data = [{"id": str(tc.id), "status": tc.status, "title": tc.title} for tc in tcs]
            results_data = [
                {"status": r.status, "test_case_id": str(r.test_case_id)} for r in existing_results
            ]
            run.report = generate_run_report(test_cases=tcs_data, results=results_data, failures=[])
    except Exception as e:
        logger.error("[run_id=%s] Error finalizing dead run test cases: %s", run.id, e)

    session.add(run)
    await session.commit()
    await session.refresh(run)

    # Update cache, release run lock, clear progress keys
    await cache_run_status(
        run.id,
        status="FAILED",
        stage=run.failed_stage or "QUEUED",
        failed_stage=run.failed_stage or "QUEUED",
        error="Worker stopped responding",
    )
    await release_run_lock(run.project_id)
    await clear_live_progress_keys(run.id)
    return True


async def sweep_dead_runs(session: AsyncSession) -> list[uuid.UUID]:
    """Find all active runs older than 90 seconds without heartbeat and fail them."""
    stmt = (
        select(TestRun)
        .options(selectinload(TestRun.test_cases))
        .where(TestRun.status.in_(ACTIVE_STATUSES))
    )
    active_runs = (await session.execute(stmt)).scalars().all()
    failed_run_ids = []
    for run in active_runs:
        if await check_and_fail_dead_run(run, session):
            failed_run_ids.append(run.id)
    return failed_run_ids
