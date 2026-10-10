"""Tests for Part 2: Always finish the run cleanly with shielded finalizer."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.graph import _active_mcp_clients, execute_agent_run
from app.models.project import Project
from app.models.test_run import TestCase, TestRun
from app.models.user import User


async def _create_test_project(session) -> uuid.UUID:
    user = User(
        id=uuid.uuid4(),
        email=f"cleanup.{uuid.uuid4().hex[:6]}@example.com",
        password_hash="fakehash",
    )
    project = Project(
        id=uuid.uuid4(),
        user_id=user.id,
        name="Cleanup Test Project",
        target_url="http://localhost:8001",
    )
    session.add_all([user, project])
    await session.commit()
    return project.id


@pytest.mark.asyncio
async def test_run_cleanup_on_timeout(db_session):
    """Verify that on timeout, the run is marked FAILED, lock released, and MCP client closed."""
    project_id = await _create_test_project(db_session)
    run_id = uuid.uuid4()

    # Create dummy TestRun and TestCase in DB
    run = TestRun(id=run_id, project_id=project_id, status="QUEUED")
    tc1 = TestCase(id=uuid.uuid4(), run_id=run_id, title="Test 1", order_index=0, status="PASSED")
    tc2 = TestCase(id=uuid.uuid4(), run_id=run_id, title="Test 2", order_index=1, status="RUNNING")
    db_session.add_all([run, tc1, tc2])
    await db_session.commit()

    # Mock MCP client
    mock_mcp = MagicMock()
    mock_mcp.close = AsyncMock()
    _active_mcp_clients[run_id] = mock_mcp

    # Mock graph to sleep longer than RUN_TIMEOUT_SECONDS
    async def slow_astream(*args, **kwargs):
        await asyncio.sleep(0.5)
        yield {}

    mock_graph = AsyncMock()
    mock_graph.astream = slow_astream

    with (
        patch("app.agent.graph.get_settings") as mock_settings,
        patch("app.agent.graph.build_agent_graph", return_value=mock_graph),
        patch("app.agent.graph.release_run_lock", new_callable=AsyncMock) as mock_release_lock,
        patch(
            "app.agent.graph.clear_live_progress_keys", new_callable=AsyncMock
        ) as mock_clear_prog,
    ):
        mock_settings.return_value.RUN_TIMEOUT_SECONDS = 0.05
        db_url = db_session.bind.url.render_as_string(hide_password=False)

        await execute_agent_run(run_id=run_id, project_id=project_id, db_url=db_url)

    # Refresh DB objects
    await db_session.refresh(run)
    await db_session.refresh(tc1)
    await db_session.refresh(tc2)

    # 1. Run ends FAILED with descriptive timeout message
    assert run.status == "FAILED"
    assert "Run exceeded the time limit of" in (run.error_message or "")
    assert run.completed_at is not None

    # 2. Unfinished test is marked BLOCKED; finished test remains PASSED
    assert tc1.status == "PASSED"
    assert tc2.status == "BLOCKED"

    # 3. Partial report is stored
    assert run.report is not None
    assert run.report.get("total_tests") == 2

    # 4. Lock is released
    mock_release_lock.assert_awaited_once_with(project_id)

    # 5. Live progress keys are cleared
    mock_clear_prog.assert_awaited_once_with(run_id)

    # 6. MCP client is closed
    mock_mcp.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_cleanup_on_cancellation(db_session):
    """Verify that on CancelledError, run ends FAILED, lock released, and MCP closed."""
    project_id = await _create_test_project(db_session)
    run_id = uuid.uuid4()

    run = TestRun(id=run_id, project_id=project_id, status="QUEUED")
    tc1 = TestCase(id=uuid.uuid4(), run_id=run_id, title="Test 1", order_index=0, status="RUNNING")
    db_session.add_all([run, tc1])
    await db_session.commit()

    mock_mcp = MagicMock()
    mock_mcp.close = AsyncMock()
    _active_mcp_clients[run_id] = mock_mcp

    # Simulate cancellation raised from graph execution
    async def cancelling_astream(*args, **kwargs):
        raise asyncio.CancelledError()
        yield {}

    mock_graph = AsyncMock()
    mock_graph.astream = cancelling_astream

    with (
        patch("app.agent.graph.build_agent_graph", return_value=mock_graph),
        patch("app.agent.graph.release_run_lock", new_callable=AsyncMock) as mock_release_lock,
        patch(
            "app.agent.graph.clear_live_progress_keys", new_callable=AsyncMock
        ) as mock_clear_prog,
    ):
        db_url = db_session.bind.url.render_as_string(hide_password=False)

        await execute_agent_run(run_id=run_id, project_id=project_id, db_url=db_url)

    await db_session.refresh(run)
    await db_session.refresh(tc1)

    # 1. Run ends FAILED with Worker was interrupted message
    assert run.status == "FAILED"
    assert run.error_message == "Worker was interrupted"
    assert run.completed_at is not None

    # 2. Running test is marked BLOCKED
    assert tc1.status == "BLOCKED"

    # 3. Partial report is stored
    assert run.report is not None

    # 4. Lock is released
    mock_release_lock.assert_awaited_once_with(project_id)

    # 5. Live progress keys are cleared
    mock_clear_prog.assert_awaited_once_with(run_id)

    # 6. MCP client is closed
    mock_mcp.close.assert_awaited_once()
