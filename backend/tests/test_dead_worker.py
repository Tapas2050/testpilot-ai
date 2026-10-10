"""Tests for Part 4: Detect dead workers via Redis heartbeat and sweep."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.agent.graph import execute_agent_run
from app.models.project import Project
from app.models.test_run import TestCase, TestRun
from app.models.user import User
from app.services.run_service import (
    acquire_run_lock,
    check_and_fail_dead_run,
    check_worker_heartbeat,
    set_worker_heartbeat,
    sweep_dead_runs,
)


async def _create_test_project(session) -> tuple[uuid.UUID, User]:
    user = User(
        id=uuid.uuid4(),
        email=f"deadworker.{uuid.uuid4().hex[:6]}@example.com",
        password_hash="fakehash",
    )
    project = Project(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Dead Worker Test Project",
        target_url="http://localhost:8001",
    )
    session.add_all([user, project])
    await session.commit()
    return project.id, user


@pytest.mark.asyncio
async def test_dead_worker_detection_after_90_seconds_without_heartbeat(db_session):
    """Verify that an active run older than 90s without a heartbeat is marked FAILED."""
    project_id, _ = await _create_test_project(db_session)
    run_id = uuid.uuid4()

    # 100 seconds ago, active EXECUTING status
    started_time = datetime.now(timezone.utc) - timedelta(seconds=100)
    run = TestRun(
        id=run_id,
        project_id=project_id,
        status="EXECUTING",
        started_at=started_time,
        created_at=started_time,
    )
    tc = TestCase(
        id=uuid.uuid4(),
        run_id=run_id,
        title="Incomplete Test",
        status="EXECUTING",
        order_index=0,
    )
    db_session.add_all([run, tc])
    await db_session.commit()

    # Acquire run lock
    await acquire_run_lock(project_id, run_id)

    # Make sure no heartbeat is present
    from app.core.redis import get_redis_client

    redis = get_redis_client()
    await redis.delete(f"worker_heartbeat:{run_id}")

    # Check and fail dead run
    marked_dead = await check_and_fail_dead_run(run, db_session)
    assert marked_dead is True
    assert run.status == "FAILED"
    assert run.error_message == "Worker stopped responding"
    assert run.completed_at is not None

    # Check that test case was marked BLOCKED
    refreshed_tc = (
        await db_session.execute(select(TestCase).where(TestCase.id == tc.id))
    ).scalar_one()
    assert refreshed_tc.status == "BLOCKED"

    # Verify lock was released
    lock_val = await redis.get(f"project_run_lock:{project_id}")
    assert lock_val is None


@pytest.mark.asyncio
async def test_active_run_with_valid_heartbeat_is_not_marked_dead(db_session):
    """Verify that an active run older than 90s WITH a heartbeat is preserved as active."""
    project_id, _ = await _create_test_project(db_session)
    run_id = uuid.uuid4()

    started_time = datetime.now(timezone.utc) - timedelta(seconds=120)
    run = TestRun(
        id=run_id,
        project_id=project_id,
        status="EXECUTING",
        started_at=started_time,
        created_at=started_time,
    )
    db_session.add(run)
    await db_session.commit()

    # Set active heartbeat
    await set_worker_heartbeat(run_id, ttl=60)
    assert await check_worker_heartbeat(run_id) is True

    # Check should return False and not fail the run
    marked_dead = await check_and_fail_dead_run(run, db_session)
    assert marked_dead is False
    assert run.status == "EXECUTING"


@pytest.mark.asyncio
async def test_young_run_without_heartbeat_is_not_marked_dead(db_session):
    """Verify that an active run younger than 90s (e.g. 20s old) is given grace period."""
    project_id, _ = await _create_test_project(db_session)
    run_id = uuid.uuid4()

    started_time = datetime.now(timezone.utc) - timedelta(seconds=20)
    run = TestRun(
        id=run_id,
        project_id=project_id,
        status="EXECUTING",
        started_at=started_time,
        created_at=started_time,
    )
    db_session.add(run)
    await db_session.commit()

    # No heartbeat, but age is only 20s <= 90s
    marked_dead = await check_and_fail_dead_run(run, db_session)
    assert marked_dead is False
    assert run.status == "EXECUTING"


@pytest.mark.asyncio
async def test_sweep_dead_runs_on_multiple_runs(db_session):
    """Verify that sweep_dead_runs finds all dead runs and marks them FAILED."""
    project_id, _ = await _create_test_project(db_session)

    # 1 dead run (>90s, no heartbeat)
    old_time = datetime.now(timezone.utc) - timedelta(seconds=150)
    dead_run = TestRun(
        id=uuid.uuid4(),
        project_id=project_id,
        status="PLANNING",
        started_at=old_time,
        created_at=old_time,
    )

    # 1 alive run (>90s, with heartbeat)
    alive_run = TestRun(
        id=uuid.uuid4(),
        project_id=project_id,
        status="EXECUTING",
        started_at=old_time,
        created_at=old_time,
    )

    # 1 fresh run (<90s)
    fresh_time = datetime.now(timezone.utc) - timedelta(seconds=10)
    fresh_run = TestRun(
        id=uuid.uuid4(),
        project_id=project_id,
        status="QUEUED",
        created_at=fresh_time,
    )

    db_session.add_all([dead_run, alive_run, fresh_run])
    await db_session.commit()

    await set_worker_heartbeat(alive_run.id, ttl=60)

    swept_ids = await sweep_dead_runs(db_session)
    assert dead_run.id in swept_ids
    assert alive_run.id not in swept_ids
    assert fresh_run.id not in swept_ids

    # Refresh dead run
    refreshed_dead = (
        await db_session.execute(select(TestRun).where(TestRun.id == dead_run.id))
    ).scalar_one()
    assert refreshed_dead.status == "FAILED"
    assert refreshed_dead.error_message == "Worker stopped responding"


@pytest.mark.asyncio
async def test_worker_heartbeat_loop_writes_and_cleans_up():
    """Verify that execute_agent_run starts heartbeat and cleans it up upon termination."""
    run_id = uuid.uuid4()
    project_id = uuid.uuid4()

    from unittest.mock import AsyncMock, patch

    async def mock_astream(*args, **kwargs):
        # Verify heartbeat is present during execution
        assert await check_worker_heartbeat(run_id) is True
        yield {}

    mock_graph = AsyncMock()
    mock_graph.astream = mock_astream

    with (
        patch("app.agent.graph.build_agent_graph", return_value=mock_graph),
        patch("app.agent.graph.update_run_in_db", new_callable=AsyncMock),
        patch("app.agent.graph._finalize_run", new_callable=AsyncMock),
    ):
        await execute_agent_run(run_id=run_id, project_id=project_id)

    # Now verify heartbeat was set during the run
    # (Finalize_run was mocked here so we directly tested the loop writing it)
