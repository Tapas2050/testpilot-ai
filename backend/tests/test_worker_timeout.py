"""Tests for Part 1: arq worker job timeout and single try configuration."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.graph import execute_agent_run
from app.core.config import get_settings
from app.worker.tasks import WorkerSettings


def test_worker_settings_timeout_and_retry_configuration():
    """Verify WorkerSettings sets job_timeout to RUN_TIMEOUT_SECONDS + 300 and max_tries to 1."""
    settings = get_settings()
    assert WorkerSettings.job_timeout == settings.RUN_TIMEOUT_SECONDS + 300
    assert WorkerSettings.max_tries == 1
    assert WorkerSettings.retry_jobs is False


@pytest.mark.asyncio
async def test_execute_agent_run_graceful_timeout():
    """Verify execute_agent_run catches in-job TimeoutError and sets status to FAILED."""
    run_id = uuid.uuid4()
    project_id = uuid.uuid4()

    # Mock the settings and internal graph execution to simulate timeout
    with (
        patch("app.agent.graph.get_settings") as mock_settings,
        patch("app.agent.graph.update_run_in_db", new_callable=AsyncMock) as mock_update_db,
        patch("app.agent.graph.cache_run_status", new_callable=AsyncMock),
        patch("app.agent.graph.update_live_progress", new_callable=AsyncMock),
        patch("app.agent.graph.release_run_lock", new_callable=AsyncMock) as mock_release,
        patch("app.agent.graph.build_agent_graph") as mock_build_graph,
    ):
        mock_settings.return_value.RUN_TIMEOUT_SECONDS = 0.05

        # Create a graph that takes longer than 0.05 seconds
        async def slow_astream(*args, **kwargs):
            import asyncio

            await asyncio.sleep(0.5)
            yield {}

        mock_graph = AsyncMock()
        mock_graph.astream = slow_astream
        mock_build_graph.return_value = mock_graph

        await execute_agent_run(run_id=run_id, project_id=project_id)

        # Verify update_run_in_db was called with FAILED and the timeout error message
        assert mock_update_db.called
        calls = mock_update_db.call_args_list
        final_call = calls[-1]
        assert final_call.kwargs.get("status") == "FAILED"
        assert "Run exceeded the time limit of" in final_call.kwargs.get("error_message", "")

        # Verify lock was released
        mock_release.assert_awaited_once_with(project_id)
