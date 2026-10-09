"""Phase 8 tests for Agent Foundation (T8.1 - T8.6)."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.checkpointer import get_checkpointer
from app.agent.graph import execute_agent_run
from app.core.config import get_settings
from app.models.user import User
from app.services.run_service import release_run_lock


@pytest.fixture
async def auth_headers(
    client: AsyncClient, db_session: AsyncSession
) -> tuple[dict[str, str], uuid.UUID, uuid.UUID]:
    """Register a user, create a project, and return headers, user_id, and project_id."""
    email = f"agent.foundation.{uuid.uuid4().hex[:8]}@example.com"
    pwd = "SecurePassword123!"
    reg_resp = await client.post(
        "/auth/register",
        json={"email": email, "password": pwd},
    )
    assert reg_resp.status_code == 201

    login_resp = await client.post(
        "/auth/login",
        json={"email": email, "password": pwd},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    proj_resp = await client.post(
        "/projects",
        json={"name": "Foundation Project", "target_url": "http://localhost:8001"},
        headers=headers,
    )
    assert proj_resp.status_code == 201
    proj_id = uuid.UUID(proj_resp.json()["id"])

    user_stmt = select(User).where(User.email == email)
    user = (await db_session.execute(user_stmt)).scalar_one()

    return headers, user.id, proj_id


@pytest.mark.asyncio
async def test_t8_1_start_run_returns_queued_immediately(client: AsyncClient, auth_headers):
    """T8.1: Start run returns run_id and QUEUED immediately."""
    headers, user_id, proj_id = auth_headers

    resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    assert "id" in data
    assert data["status"] == "QUEUED"
    assert data["project_id"] == str(proj_id)

    # Clean up lock
    await release_run_lock(proj_id)


@pytest.mark.asyncio
async def test_t8_2_stub_run_moves_through_states_to_completed(
    client: AsyncClient, auth_headers, db_session: AsyncSession
):
    """T8.2: Stub run moves through every state in order to COMPLETED with timestamps."""
    headers, user_id, proj_id = auth_headers
    settings = get_settings()

    # Create run directly or through endpoint
    create_resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert create_resp.status_code == 201
    run_id = uuid.UUID(create_resp.json()["id"])

    # Execute workflow synchronously against test database
    await execute_agent_run(
        run_id=run_id,
        project_id=proj_id,
        db_url=settings.TEST_DATABASE_URL,
    )

    # Verify run details via API
    get_resp = await client.get(f"/runs/{run_id}", headers=headers)
    assert get_resp.status_code == 200
    run_data = get_resp.json()

    assert run_data["status"] == "COMPLETED"
    assert run_data["started_at"] is not None
    assert run_data["completed_at"] is not None
    assert run_data["report"] is not None
    assert run_data["report"]["pass_rate"] == 100.0

    # Verify planned test cases were persisted
    assert len(run_data["test_cases"]) == 2
    for tc in run_data["test_cases"]:
        assert tc["status"] == "PASSED"


@pytest.mark.asyncio
async def test_t8_3_forced_exception_yields_failed_api_stays_responsive(
    client: AsyncClient, auth_headers
):
    """T8.3: Forced exception in a node yields FAILED with a message; API stays responsive."""
    headers, user_id, proj_id = auth_headers
    settings = get_settings()

    create_resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert create_resp.status_code == 201
    run_id = uuid.UUID(create_resp.json()["id"])

    # Execute with forced failure midway
    await execute_agent_run(
        run_id=run_id,
        project_id=proj_id,
        db_url=settings.TEST_DATABASE_URL,
        force_fail_at="midway",
    )

    # API is responsive and returns FAILED with error message
    get_resp = await client.get(f"/runs/{run_id}", headers=headers)
    assert get_resp.status_code == 200
    run_data = get_resp.json()

    assert run_data["status"] == "FAILED"
    assert run_data["error_message"] is not None
    assert "Forced node exception" in run_data["error_message"]

    # Health check is still 200 OK
    health_resp = await client.get("/health")
    assert health_resp.status_code == 200


@pytest.mark.asyncio
async def test_t8_4_second_start_while_active_is_blocked(client: AsyncClient, auth_headers):
    """T8.4: Second start for the same project while a run is active is blocked (HTTP 409)."""
    headers, user_id, proj_id = auth_headers

    # Start first run
    first_resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert first_resp.status_code == 201

    # Attempt second run while first is active
    second_resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert second_resp.status_code == 409
    assert "already active" in second_resp.json()["detail"].lower()

    # Clean up lock
    await release_run_lock(proj_id)


@pytest.mark.asyncio
async def test_t8_5_cancel_stops_run_and_sets_cancelled(client: AsyncClient, auth_headers):
    """T8.5: Cancel stops the run at the next checkpoint and sets CANCELLED."""
    headers, user_id, proj_id = auth_headers
    settings = get_settings()

    create_resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert create_resp.status_code == 201
    run_id = uuid.UUID(create_resp.json()["id"])

    # Request cancel
    cancel_resp = await client.post(f"/runs/{run_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["cancel_requested"] is True

    # Run execution after cancel requested
    await execute_agent_run(
        run_id=run_id,
        project_id=proj_id,
        db_url=settings.TEST_DATABASE_URL,
    )

    # Status should be CANCELLED
    get_resp = await client.get(f"/runs/{run_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["status"] == "CANCELLED"


@pytest.mark.asyncio
async def test_t8_6_checkpoint_exists_for_run_thread(client: AsyncClient, auth_headers):
    """T8.6: Checkpoint exists for a run thread in Postgres checkpointer."""
    headers, user_id, proj_id = auth_headers
    settings = get_settings()

    create_resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert create_resp.status_code == 201
    run_id = uuid.UUID(create_resp.json()["id"])

    # Execute run
    await execute_agent_run(
        run_id=run_id,
        project_id=proj_id,
        db_url=settings.TEST_DATABASE_URL,
    )

    # Checkpoint verification in PostgresSaver
    checkpointer = get_checkpointer(settings.TEST_DATABASE_URL)
    config = {"configurable": {"thread_id": str(run_id)}}
    checkpoint_tuple = checkpointer.get_tuple(config)

    assert checkpoint_tuple is not None
    assert checkpoint_tuple.checkpoint is not None
    # Thread ID matches
    assert checkpoint_tuple.config["configurable"]["thread_id"] == str(run_id)
