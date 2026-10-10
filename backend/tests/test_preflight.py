import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import execute_agent_run
from app.agent.llm import get_live_call_count, reset_live_call_count, set_mock_llm
from app.agent.preflight import run_preflight_checks
from app.core.config import get_settings
from app.models.credential import ProjectCredential


@pytest.fixture(autouse=True)
def prevent_live_llm():
    """Ensure zero live LLM calls happen under any circumstances in preflight tests."""
    mock = MagicMock()
    mock.ainvoke = AsyncMock()
    mock.with_structured_output.return_value = mock
    set_mock_llm(mock)
    yield
    set_mock_llm(None)


@pytest.mark.asyncio
async def test_preflight_target_unreachable_fails_early_without_llm_or_blocked_tests(
    client: AsyncClient, auth_headers, db_session: AsyncSession
):
    """Preflight Check 1: When target URL does not respond, run ends in preflight stage."""
    headers, user_id, proj_id = auth_headers
    settings = get_settings()
    reset_live_call_count()

    # Create run
    create_resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert create_resp.status_code == 201
    run_id = uuid.UUID(create_resp.json()["id"])

    # Simulate HTTP connection failure on target URL
    with patch(
        "app.agent.preflight.check_target_url_reachable",
        side_effect=Exception("Connection refused"),
    ):
        await execute_agent_run(
            run_id=run_id,
            project_id=proj_id,
            db_url=settings.TEST_DATABASE_URL,
        )

    get_resp = await client.get(f"/runs/{run_id}", headers=headers)
    assert get_resp.status_code == 200
    run_data = get_resp.json()

    assert run_data["status"] == "FAILED"
    assert "did not respond" in run_data["error_message"]
    assert "Is it running?" in run_data["error_message"]
    assert "[preflight]" in run_data["error_message"]

    # Verify zero planned test cases and zero misleading BLOCKED tests
    assert len(run_data.get("test_cases", [])) == 0
    # Zero live LLM calls were made
    assert get_live_call_count() == 0


@pytest.mark.asyncio
async def test_preflight_mcp_startup_failure_fails_early(
    client: AsyncClient, auth_headers, db_session: AsyncSession
):
    """Preflight Check 2: When Playwright MCP fails handshake, run ends with clear user action."""
    headers, user_id, proj_id = auth_headers
    settings = get_settings()
    reset_live_call_count()

    create_resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert create_resp.status_code == 201
    run_id = uuid.UUID(create_resp.json()["id"])

    # Simulate MCP server startup failure
    with patch(
        "app.agent.preflight.PlaywrightMCPClient.start",
        side_effect=RuntimeError("Node process exited"),
    ):
        await execute_agent_run(
            run_id=run_id,
            project_id=proj_id,
            db_url=settings.TEST_DATABASE_URL,
        )

    get_resp = await client.get(f"/runs/{run_id}", headers=headers)
    assert get_resp.status_code == 200
    run_data = get_resp.json()

    assert run_data["status"] == "FAILED"
    assert "Playwright MCP server could not start" in run_data["error_message"]
    assert "Check Node.js and Playwright installation" in run_data["error_message"]
    assert "[preflight]" in run_data["error_message"]
    assert len(run_data.get("test_cases", [])) == 0
    assert get_live_call_count() == 0


@pytest.mark.asyncio
async def test_preflight_undecryptable_credential_fails_early(
    client: AsyncClient, auth_headers, db_session: AsyncSession
):
    """Preflight Check 3: When stored credential cannot be decrypted, run ends with key guidance."""
    headers, user_id, proj_id = auth_headers
    settings = get_settings()
    reset_live_call_count()

    # Add a corrupt credential to the project
    corrupt_cred = ProjectCredential(
        id=uuid.uuid4(),
        project_id=proj_id,
        role_label="admin",
        username="admin@example.com",
        password_encrypted="corrupted_not_fernet_ciphertext",
    )
    db_session.add(corrupt_cred)
    await db_session.commit()

    create_resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert create_resp.status_code == 201
    run_id = uuid.UUID(create_resp.json()["id"])

    await execute_agent_run(
        run_id=run_id,
        project_id=proj_id,
        db_url=settings.TEST_DATABASE_URL,
    )

    get_resp = await client.get(f"/runs/{run_id}", headers=headers)
    assert get_resp.status_code == 200
    run_data = get_resp.json()

    assert run_data["status"] == "FAILED"
    assert "Stored credential for role 'admin' could not be decrypted" in run_data["error_message"]
    assert "Check CREDENTIAL_ENCRYPTION_KEY" in run_data["error_message"]
    assert "[preflight]" in run_data["error_message"]
    assert len(run_data.get("test_cases", [])) == 0
    assert get_live_call_count() == 0


@pytest.mark.asyncio
async def test_preflight_checks_pass_when_target_and_creds_valid(
    auth_headers, db_session: AsyncSession
):
    """Verify run_preflight_checks returns OK when all checks succeed."""
    headers, user_id, proj_id = auth_headers
    settings = get_settings()

    res = await run_preflight_checks(
        project_id=proj_id,
        db_url=settings.TEST_DATABASE_URL,
        is_mock_mcp=True,
    )
    assert res["status"] == "ok"
