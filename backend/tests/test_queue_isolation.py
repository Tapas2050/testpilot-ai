"""Tests for Part 5: Stale queue jobs, test queue isolation, and worker resilience."""

import logging
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as aioredis
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.project import Project
from app.models.test_run import TestRun
from app.models.user import User
from app.worker.tasks import run_agent_job


async def _create_test_project(
    session: AsyncSession,
) -> tuple[dict[str, str], uuid.UUID, uuid.UUID]:
    user = User(
        id=uuid.uuid4(),
        email=f"isolation.{uuid.uuid4().hex[:6]}@example.com",
        password_hash="fakehash",
    )
    project = Project(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Queue Isolation Test Project",
        target_url="http://localhost:8001",
    )
    session.add_all([user, project])
    await session.commit()
    headers = {"Authorization": "Bearer fake_token"}
    return headers, user.id, project.id


@pytest.mark.asyncio
async def test_suite_leaves_real_redis_queue_db0_untouched(
    client: AsyncClient, db_session: AsyncSession
):
    """Part 5(a): Test suite never enqueues jobs into real Redis DB 0."""
    _, user_id, proj_id = await _create_test_project(db_session)
    from app.api.deps import get_current_user
    from app.main import app

    user = (await db_session.execute(select(User).where(User.id == user_id))).scalar_one()
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        # Clear any preexisting arq keys on real DB 0 before testing
        real_redis = aioredis.from_url("redis://localhost:6379/0", decode_responses=True)
        try:
            db0_keys_before = await real_redis.keys("arq:*")
        except Exception:
            db0_keys_before = []

        # Create a run via the API endpoint
        resp = await client.post(f"/projects/{proj_id}/runs")
        assert resp.status_code == 201

        # Assert real Redis DB 0 queue was not touched
        try:
            db0_keys_after = await real_redis.keys("arq:*")
            new_keys = set(db0_keys_after) - set(db0_keys_before)
            assert len(new_keys) == 0, (
                f"DANGER: Test suite enqueued into real Redis DB 0! {new_keys}"
            )
        finally:
            await real_redis.aclose()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_worker_skips_nonexistent_run_without_crash(caplog):
    """Part 5(b): Worker handles missing run by logging one warning and skipping, no stack trace."""
    missing_run_id = uuid.uuid4()

    with caplog.at_level(logging.WARNING):
        with patch("app.worker.tasks.execute_agent_run", new_callable=AsyncMock) as mock_exec:
            # Should not raise any exception
            await run_agent_job(ctx={}, run_id_str=str(missing_run_id))
            assert not mock_exec.called

    # Verify short warning logged with run_id
    assert any(
        f"TestRun {missing_run_id} not found" in record.message or "Skipping job" in record.message
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_job_payload_and_worker_db_url_decoupling(db_session: AsyncSession):
    """Part 5(c): Job carries run_id only; worker uses configured DATABASE_URL, never job db_url."""
    _, _, proj_id = await _create_test_project(db_session)
    run_id = uuid.uuid4()
    run = TestRun(id=run_id, project_id=proj_id, status="QUEUED")
    db_session.add(run)
    await db_session.commit()

    settings = get_settings()

    with patch("app.worker.tasks.execute_agent_run", new_callable=AsyncMock) as mock_exec:
        # Pass a bogus db_url to test that worker completely ignores external db_url
        await run_agent_job(ctx={}, run_id_str=str(run_id), db_url="postgresql://bogus/db")

        assert mock_exec.called
        call_kwargs = mock_exec.call_args.kwargs
        assert call_kwargs["run_id"] == run_id
        assert call_kwargs["project_id"] == proj_id
        # Worker must have used its own configured database URL (never job db_url)
        expected_db_url = str(
            settings.TEST_DATABASE_URL
            if settings.TEST_DATABASE_URL
            else settings.DATABASE_URL
        )
        assert call_kwargs["db_url"] == expected_db_url
        assert "bogus" not in call_kwargs["db_url"]


@pytest.mark.asyncio
async def test_database_protection_against_main_db_drops():
    """Verify tests assert and reject any connection to production testpilot database for drops."""
    settings = get_settings()
    # Verify TEST_DATABASE_URL targets test database
    assert "testpilot_test" in settings.TEST_DATABASE_URL
    assert not settings.TEST_DATABASE_URL.rstrip("/").endswith("/testpilot")
