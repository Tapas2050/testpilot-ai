"""Run service for managing execution lifecycle, duplicate locks,
Redis caching, and cancellation.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.models.test_run import TestRun


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


async def cache_run_status(
    run_id: uuid.UUID, status: str, stage: str, error: Optional[str] = None
) -> None:
    """Cache the current status and stage in Redis."""
    redis = get_redis_client()
    data = {
        "run_id": str(run_id),
        "status": status,
        "stage": stage,
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


