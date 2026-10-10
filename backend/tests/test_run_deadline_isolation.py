"""Tests verifying that inner TimeoutError is not misreported as whole-run timeout."""

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.graph import execute_agent_run


@pytest.mark.asyncio
async def test_inner_timeout_not_misreported_as_run_deadline_exceeded():
    """Prove that an inner TimeoutError is currently mislabeled as a run timeout.

    When an inner call (e.g., MCP handshake or HTTP request) raises TimeoutError
    well before the 1800s run deadline, the error message should reflect the inner
    failure, NOT 'Run exceeded the time limit of 1800 seconds'.
    """
    run_id = uuid.uuid4()
    project_id = uuid.uuid4()

    with (
        patch("app.agent.graph.get_settings") as mock_settings,
        patch("app.agent.graph.update_run_in_db", new_callable=AsyncMock) as mock_update_db,
        patch("app.agent.graph.cache_run_status", new_callable=AsyncMock),
        patch("app.agent.graph.update_live_progress", new_callable=AsyncMock),
        patch("app.agent.graph.release_run_lock", new_callable=AsyncMock),
        patch("app.agent.graph.build_agent_graph") as mock_build_graph,
    ):
        mock_settings.return_value.RUN_TIMEOUT_SECONDS = 1800

        # An inner component raises TimeoutError after just 0.01 seconds
        async def failing_astream(*args, **kwargs):
            await asyncio.sleep(0.01)
            raise asyncio.TimeoutError("MCP startup handshake timed out after 15.0s")
            yield {}

        mock_graph = AsyncMock()
        mock_graph.astream = failing_astream
        mock_build_graph.return_value = mock_graph

        await execute_agent_run(run_id=run_id, project_id=project_id)

        assert mock_update_db.called
        final_call = mock_update_db.call_args_list[-1]
        err_msg = final_call.kwargs.get("error_message", "")
        # This assertion MUST fail on current code because current code sets:
        # "Run exceeded the time limit of 1800 seconds"
        assert "Run exceeded the time limit of 1800 seconds" not in err_msg
        assert "MCP startup handshake" in err_msg
