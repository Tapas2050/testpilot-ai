"""arq background worker definitions for executing TestPilot agent runs."""

import asyncio
import uuid
from typing import Any, Optional
from urllib.parse import urlparse

from arq.connections import RedisSettings, create_pool

from app.agent.graph import execute_agent_run
from app.core.config import get_settings


async def run_agent_job(
    ctx: dict[str, Any],
    run_id_str: str,
    project_id_str: str,
    db_url: Optional[str] = None,
    force_fail_at: Optional[str] = None,
) -> None:
    """Worker task executed by arq."""
    run_id = uuid.UUID(run_id_str)
    project_id = uuid.UUID(project_id_str)
    await execute_agent_run(
        run_id=run_id,
        project_id=project_id,
        db_url=db_url,
        force_fail_at=force_fail_at,
    )


def get_redis_settings() -> RedisSettings:
    """Parse application REDIS_URL into arq RedisSettings."""
    settings = get_settings()
    parsed = urlparse(settings.REDIS_URL)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int(parsed.path.lstrip("/") or 0),
    )


class WorkerSettings:
    """Configuration for arq worker process."""

    functions = [run_agent_job]
    redis_settings = get_redis_settings()
    max_jobs = 1  # Respect D-018: execute 1 test run at a time to stay within memory limits


async def enqueue_agent_job(
    run_id: uuid.UUID,
    project_id: uuid.UUID,
    db_url: Optional[str] = None,
    force_fail_at: Optional[str] = None,
) -> None:
    """Enqueue a job to arq, or launch background task if worker is direct/testing."""
    try:
        redis_settings = get_redis_settings()
        pool = await create_pool(redis_settings)
        await pool.enqueue_job(
            "run_agent_job",
            str(run_id),
            str(project_id),
            db_url=db_url,
            force_fail_at=force_fail_at,
        )
        await pool.aclose()
    except Exception:
        # Fallback to in-process asyncio background task for tests or standalone mode
        asyncio.create_task(
            execute_agent_run(
                run_id=run_id,
                project_id=project_id,
                db_url=db_url,
                force_fail_at=force_fail_at,
            )
        )
