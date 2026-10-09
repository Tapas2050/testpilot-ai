"""Run service for managing execution lifecycle, duplicate locks,
Redis caching, and cancellation.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.test_run import TestRun

LOCK_TTL_SECONDS = 1800  # 30 minutes


async def acquire_run_lock(project_id: uuid.UUID, run_id: uuid.UUID) -> bool:
    """Acquire a per-project run lock in Redis. Returns True if acquired, False if locked."""
    redis = get_redis_client()
    lock_key = f"project_run_lock:{project_id}"
    acquired = await redis.set(lock_key, str(run_id), nx=True, ex=LOCK_TTL_SECONDS)
    return bool(acquired)


async def release_run_lock(project_id: uuid.UUID) -> None:
    """Release the per-project run lock in Redis."""
    redis = get_redis_client()
    lock_key = f"project_run_lock:{project_id}"
    await redis.delete(lock_key)


async def set_cancel_flag(run_id: uuid.UUID) -> None:
    """Set cancellation flag in Redis for fast polling by running agent nodes."""
    redis = get_redis_client()
    await redis.set(f"run_cancel:{run_id}", "1", ex=LOCK_TTL_SECONDS)


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
