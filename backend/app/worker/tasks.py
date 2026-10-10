"""arq background worker definitions for executing TestPilot agent runs."""

import asyncio
import logging
import os
import uuid
from typing import Any, Optional
from urllib.parse import urlparse

from arq.connections import RedisSettings, create_pool
from sqlalchemy import select

from app.agent.graph import execute_agent_run
from app.agent.llm import get_live_call_count
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def parse_redis_settings(url: str) -> RedisSettings:
    """Parse a Redis URL into arq RedisSettings."""
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int(parsed.path.lstrip("/") or 0),
    )


def get_redis_settings(is_test: bool = False) -> RedisSettings:
    """Parse application REDIS_URL or TEST_REDIS_URL into arq RedisSettings."""
    settings = get_settings()
    url = settings.TEST_REDIS_URL if is_test else settings.REDIS_URL
    return parse_redis_settings(url)


async def run_agent_job(
    ctx: dict[str, Any],
    run_id_str: str,
    *args: Any,
    **kwargs: Any,
) -> None:
    """Worker task executed by arq.

    Carries run_id only and always uses configured DATABASE_URL.
    Safely skips missing runs with one short warning and no stack trace.
    """
    try:
        run_id = uuid.UUID(str(run_id_str))
    except Exception:
        logger.warning("Worker received invalid run_id: %s. Skipping job.", run_id_str)
        return

    settings = get_settings()
    configured_db_url = str(
        settings.TEST_DATABASE_URL
        if (os.getenv("PYTEST_CURRENT_TEST") and settings.TEST_DATABASE_URL)
        else settings.DATABASE_URL
    )

    # Verify run exists in configured database (Requirement 5b)
    from app.core.database import get_async_session_factory
    from app.models.test_run import TestRun

    session_factory = get_async_session_factory(configured_db_url)
    try:
        async with session_factory() as session:
            stmt = select(TestRun).where(TestRun.id == run_id)
            run = (await session.execute(stmt)).scalar_one_or_none()
            if run is None:
                logger.warning("TestRun %s not found in database. Skipping job.", run_id)
                return
            project_id = run.project_id
    except Exception as exc:
        logger.warning(
            "Database error checking TestRun %s: %s. Skipping job.", run_id, exc
        )
        return

    logger.info("[run_id=%s] Worker started job for project %s", run_id, project_id)

    import time

    start_mono = time.monotonic()
    job_deadline = start_mono + float(settings.RUN_TIMEOUT_SECONDS)

    try:
        await asyncio.wait_for(
            execute_agent_run(
                run_id=run_id,
                project_id=project_id,
                db_url=configured_db_url,
            ),
            timeout=float(settings.RUN_TIMEOUT_SECONDS) + 30.0,
        )
    except (asyncio.TimeoutError, TimeoutError):
        if time.monotonic() >= (job_deadline - 0.1):
            logger.error(
                "[run_id=%s] Run exceeded the time limit of %d seconds",
                run_id,
                settings.RUN_TIMEOUT_SECONDS,
            )
        else:
            logger.error(
                "[run_id=%s] Worker job caught unexpected inner timeout",
                run_id,
                exc_info=True,
            )
    finally:
        logger.info(
            "[run_id=%s] Worker completed job. Total live LLM calls: %d",
            run_id,
            get_live_call_count(),
        )


async def worker_startup(ctx: dict[str, Any]) -> None:
    """Preload process-level singleton embedding model during worker process initialization."""
    from app.services.embedder import get_embedding_model

    logger.info("Worker process starting up; preloading embedding model singleton...")
    try:
        get_embedding_model()
    except Exception as exc:
        logger.warning("Could not preload embedding model on worker startup: %s", exc)


class WorkerSettings:
    """Configuration for arq worker process."""

    functions = [run_agent_job]
    redis_settings = get_redis_settings()
    max_jobs = 1  # Respect D-018: execute 1 test run at a time to stay within memory limits
    job_timeout = get_settings().RUN_TIMEOUT_SECONDS + 300
    max_tries = 1
    retry_jobs = False
    on_startup = worker_startup


async def enqueue_agent_job(
    run_id: uuid.UUID,
    project_id: Optional[uuid.UUID] = None,
    db_url: Optional[str] = None,
    force_fail_at: Optional[str] = None,
) -> None:
    """Enqueue a job carrying run_id only to arq Redis queue."""
    is_test = bool(os.getenv("PYTEST_CURRENT_TEST"))
    # In test mode, use TEST_REDIS_URL (DB 1) and never touch DB 0
    redis_settings = get_redis_settings(is_test=is_test)

    try:
        pool = await create_pool(redis_settings)
        await pool.enqueue_job("run_agent_job", str(run_id))
        await pool.aclose()
    except Exception as exc:
        logger.debug("[run_id=%s] Could not enqueue to arq: %s", run_id, exc)
