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
    norm_url = url.replace("://localhost:", "://127.0.0.1:").replace("@localhost:", "@127.0.0.1:")
    parsed = urlparse(norm_url)
    host = parsed.hostname or "127.0.0.1"
    if host == "localhost":
        host = "127.0.0.1"
    return RedisSettings(
        host=host,
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

    from app.core.logging import current_run_id

    run_token = current_run_id.set(str(run_id))
    try:
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
            logger.warning("Database error checking TestRun %s: %s. Skipping job.", run_id, exc)
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
    finally:
        current_run_id.reset(run_token)


async def worker_startup(ctx: dict[str, Any]) -> None:
    """Preload process-level singleton embedding model and skip stale jobs at worker startup."""
    from app.core.logging import setup_structured_logging
    from app.core.process_memory import get_process_rss_mb
    from app.services.embedder import get_embedding_model

    setup_structured_logging()
    logger.info("Worker process starting up; memory RSS = %.1f MB", get_process_rss_mb())
    logger.info("Preloading embedding model singleton...")
    try:
        get_embedding_model()
    except Exception as exc:
        logger.warning("Could not preload embedding model on worker startup: %s", exc)
    logger.info(
        "Worker startup embedding model preloaded; memory RSS = %.1f MB",
        get_process_rss_mb(),
    )

    # Cleanup expired screenshots older than SCREENSHOT_RETENTION_DAYS (Requirement Part 2 & 6)
    try:
        from app.services.screenshot_storage import cleanup_old_screenshots

        removed_dirs = cleanup_old_screenshots()
        if removed_dirs > 0:
            logger.info("Worker startup: Cleaned up %d expired screenshot folder(s)", removed_dirs)
    except Exception as exc:
        logger.warning("Worker startup: Failed cleaning up old screenshots: %s", exc)

    stale_jobs_count = 0
    redis = ctx.get("redis")
    if redis:
        try:
            from arq.constants import default_queue_name, job_key_prefix
            from arq.jobs import Job

            from app.core.database import get_async_session_factory
            from app.models.test_run import TestRun

            settings = get_settings()
            configured_db_url = str(
                settings.TEST_DATABASE_URL
                if (os.getenv("PYTEST_CURRENT_TEST") and settings.TEST_DATABASE_URL)
                else settings.DATABASE_URL
            )
            session_factory = get_async_session_factory(configured_db_url)
            queue_name = ctx.get("queue_name") or default_queue_name
            job_ids = await redis.zrange(queue_name, 0, -1)

            async with session_factory() as session:
                for j_id in job_ids:
                    str_jid = j_id if isinstance(j_id, str) else j_id.decode()
                    job = Job(str_jid, redis, _queue_name=queue_name)
                    info = await job.info()
                    if not info or not info.args:
                        await redis.zrem(queue_name, j_id)
                        await redis.delete(job_key_prefix + str_jid)
                        stale_jobs_count += 1
                        continue

                    raw_run_id = info.args[0]
                    try:
                        run_uuid = uuid.UUID(str(raw_run_id))
                    except Exception:
                        await redis.zrem(queue_name, j_id)
                        await redis.delete(job_key_prefix + str_jid)
                        stale_jobs_count += 1
                        continue

                    stmt = select(TestRun).where(TestRun.id == run_uuid)
                    run = (await session.execute(stmt)).scalar_one_or_none()
                    if run is None or run.status in ("COMPLETED", "FAILED", "CANCELLED"):
                        await redis.zrem(queue_name, j_id)
                        await redis.delete(job_key_prefix + str_jid)
                        stale_jobs_count += 1
        except Exception as exc:
            logger.warning("Error inspecting stale jobs on worker startup: %s", exc)

    logger.info("Worker startup: %d stale job(s) skipped", stale_jobs_count)


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
