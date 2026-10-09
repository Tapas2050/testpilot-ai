"""T13.4: Hardening tests for missing keys, unreachable targets, and quota exhaustion."""

import uuid
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.agent.graph import execute_agent_run
from app.core.config import get_settings


@pytest.mark.asyncio
async def test_t13_4_missing_or_invalid_llm_key_yields_clean_failed_run(
    client: AsyncClient, auth_headers
):
    """T13.4: When LLM key fails or errors during planner stage, run moves cleanly to FAILED."""
    headers, user_id, proj_id = auth_headers
    settings = get_settings()

    create_resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert create_resp.status_code == 201
    run_id = uuid.UUID(create_resp.json()["id"])

    # Simulate missing / invalid LLM configuration error
    with patch("app.agent.graph.plan_node") as mock_plan:
        mock_plan.side_effect = RuntimeError(
            "Invalid Google AI Studio API Key: authentication failed"
        )

        await execute_agent_run(
            run_id=run_id,
            project_id=proj_id,
            db_url=settings.TEST_DATABASE_URL,
        )

    get_resp = await client.get(f"/runs/{run_id}", headers=headers)
    assert get_resp.status_code == 200
    run_data = get_resp.json()
    assert run_data["status"] == "FAILED"
    assert "Invalid Google AI Studio API Key" in run_data["error_message"]


@pytest.mark.asyncio
async def test_t13_4_exhausted_provider_limits_yields_clean_failed_run(
    client: AsyncClient, auth_headers
):
    """T13.4: When all LLM providers return 429 quota exhaustion, run moves cleanly to FAILED."""
    headers, user_id, proj_id = auth_headers
    settings = get_settings()

    create_resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert create_resp.status_code == 201
    run_id = uuid.UUID(create_resp.json()["id"])

    with patch("app.agent.graph.plan_node") as mock_plan:
        mock_plan.side_effect = RuntimeError("All LLM providers exhausted: 429 ResourceExhausted")

        await execute_agent_run(
            run_id=run_id,
            project_id=proj_id,
            db_url=settings.TEST_DATABASE_URL,
        )

    get_resp = await client.get(f"/runs/{run_id}", headers=headers)
    assert get_resp.status_code == 200
    run_data = get_resp.json()
    assert run_data["status"] == "FAILED"
    assert "ResourceExhausted" in run_data["error_message"]
