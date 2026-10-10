"""Tests for Part 3: Browser tool timeouts, process tree termination, and ENVIRONMENT_FAILURE."""

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.graph import execute_node
from app.agent.mcp_client import (
    PlaywrightMCPClient,
    ToolTimeoutError,
    kill_process_tree,
)
from app.models.project import Project
from app.models.test_run import Failure, TestCase, TestRun
from app.models.user import User


def test_tool_timeout_defaults_and_configurability():
    """Verify tool timeout defaults (nav 45s, screenshot 30s, actions 30s) and custom overrides."""
    client = PlaywrightMCPClient(is_mock=True)
    assert client.get_tool_timeout("playwright_navigate") == 45.0
    assert client.get_tool_timeout("playwright_screenshot") == 30.0
    assert client.get_tool_timeout("playwright_click") == 30.0

    custom_client = PlaywrightMCPClient(
        is_mock=True,
        tool_timeouts={"playwright_navigate": 60.0},
        default_timeout=20.0,
    )
    assert custom_client.get_tool_timeout("playwright_navigate") == 60.0
    assert custom_client.get_tool_timeout("playwright_click") == 20.0


@pytest.mark.asyncio
async def test_mcp_call_tool_times_out_and_restarts():
    """Verify that hanging tool call triggers timeout, kills tree, and restarts MCP server."""
    client = PlaywrightMCPClient(is_mock=False, default_timeout=0.05)

    mock_proc = AsyncMock()
    mock_proc.pid = 99999
    mock_proc.returncode = None

    async def hanging_readline():
        await asyncio.sleep(1.0)
        return b""

    mock_proc.stdout = AsyncMock()
    mock_proc.stdout.readline = hanging_readline
    mock_proc.stdin = MagicMock()
    mock_proc.stdin.write = MagicMock()
    mock_proc.stdin.drain = AsyncMock()
    client._process = mock_proc

    client.restart = AsyncMock()

    with pytest.raises(ToolTimeoutError) as exc_info:
        await client.call_tool("playwright_click", {"selector": "button"})

    assert "timed out after 0.05s" in str(exc_info.value)
    client.restart.assert_awaited_once()


@pytest.mark.asyncio
async def test_test_timeout_stops_hanging_tool_and_continues(db_session):
    """Verify that test timeout stops a hanging test, marks ENVIRONMENT_FAILURE, and continues."""
    user = User(
        id=uuid.uuid4(),
        email=f"mcp.timeout.{uuid.uuid4().hex[:6]}@example.com",
        password_hash="fakehash",
    )
    project = Project(
        id=uuid.uuid4(),
        user_id=user.id,
        name="MCP Timeout Test Project",
        target_url="http://localhost:8001",
    )
    run_id = uuid.uuid4()
    run = TestRun(id=run_id, project_id=project.id, status="QUEUED")
    tc1 = TestCase(
        id=uuid.uuid4(), run_id=run_id, title="Hanging Test 1", order_index=0, status="PENDING"
    )
    tc2 = TestCase(
        id=uuid.uuid4(), run_id=run_id, title="Normal Test 2", order_index=1, status="PENDING"
    )
    db_session.add_all([user, project, run, tc1, tc2])
    await db_session.commit()

    db_url = db_session.bind.url.render_as_string(hide_password=False)
    state = {
        "run_id": str(run_id),
        "project_id": str(project.id),
        "db_url": db_url,
        "is_mock_mcp": True,
        "cancel_requested": False,
    }

    # Simulate executor where test 1 hangs on a tool, test 2 passes
    async def mock_execute_single(test_case, *args, **kwargs):
        if test_case.id == tc1.id:
            raise ToolTimeoutError("Browser tool 'playwright_click' timed out after 30.0s")
        from app.models.test_run import TestResult
        return TestResult(test_case_id=test_case.id, status="PASSED")

    with (
        patch("app.agent.graph.executor.execute_single_test_case", side_effect=mock_execute_single),
        patch("app.agent.graph.get_settings") as mock_settings,
    ):
        mock_settings.return_value.TEST_TIMEOUT_SECONDS = 0.5
        mock_settings.return_value.STORAGE_DIR = "./storage"

        await execute_node(state)

    await db_session.refresh(tc1)
    await db_session.refresh(tc2)

    # Test 1 marked FAILED
    assert tc1.status == "FAILED"
    # Test 2 continued and PASSED
    assert tc2.status == "PASSED"

    # Verify ENVIRONMENT_FAILURE record was created for test 1
    from sqlalchemy import select
    stmt = select(Failure).where(Failure.test_case_id == tc1.id)
    failure = (await db_session.execute(stmt)).scalar_one_or_none()
    assert failure is not None
    assert failure.classification == "ENVIRONMENT_FAILURE"


def test_kill_process_tree_handles_invalid_pid():
    """Verify kill_process_tree does not crash on 0 or invalid PID."""
    kill_process_tree(0)
    kill_process_tree(-1)
