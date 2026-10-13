"""Automated reproduction tests for Part 1: Live status progression."""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from app.core.database import get_async_session_factory
from app.models.test_run import TestRun
from app.services.run_service import update_run_stage_and_status


@pytest.mark.asyncio
async def test_live_status_stages_appear_in_order(client: AsyncClient, auth_headers):
    """A test run walking through stages must expose every stage in order to GET /runs/{id}."""
    headers, user_id, proj_id = auth_headers

    # 1. Create run (starts in QUEUED)
    create_resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert create_resp.status_code == 201
    run_id = uuid.UUID(create_resp.json()["id"])

    stages_sequence = [
        "QUEUED",
        "PREFLIGHT",
        "PLANNING",
        "EXECUTING",
        "ANALYZING",
        "REPORTING",
        "COMPLETED",
    ]

    observed_stages: list[str] = []
    observed_statuses: list[str] = []
    pipeline_finished = asyncio.Event()

    async def _mock_pipeline():
        try:
            for stg in ["PREFLIGHT", "PLANNING", "EXECUTING", "ANALYZING", "REPORTING"]:
                await asyncio.sleep(0.15)
                await update_run_stage_and_status(run_id, stage=stg, status=stg)

            # Completed
            await asyncio.sleep(0.15)
            now = datetime.now(timezone.utc)
            await update_run_stage_and_status(
                run_id, stage="COMPLETED", status="COMPLETED", completed_at=now
            )
        finally:
            pipeline_finished.set()

    pipeline_task = asyncio.create_task(_mock_pipeline())

    # Poll until pipeline completes and COMPLETED is observed
    for _ in range(80):
        resp = await client.get(f"/runs/{run_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        current_st = (
            data.get("stage")
            or data.get("current_stage")
            or data.get("agent_stage")
            or ""
        ).upper()
        current_status = (data.get("status") or "").upper()

        if not observed_stages or observed_stages[-1] != current_st:
            observed_stages.append(current_st)
        if not observed_statuses or observed_statuses[-1] != current_status:
            observed_statuses.append(current_status)

        if pipeline_finished.is_set() and current_st == "COMPLETED":
            break
        await asyncio.sleep(0.05)
    else:
        pytest.fail(f"Timed out polling pipeline. Observed stages: {observed_stages}")

    await pipeline_task

    # Verify that all stages were captured in order
    for expected_stage in stages_sequence:
        assert expected_stage in observed_stages, (
            f"Expected {expected_stage} in observed stages sequence: {observed_stages}"
        )

    # Verify chronological order
    indices = [observed_stages.index(s) for s in stages_sequence]
    assert indices == sorted(indices), (
        f"Stages did not appear in chronological order: {observed_stages}"
    )


@pytest.mark.asyncio
async def test_stage_change_always_updates_db_and_redis(client: AsyncClient, auth_headers):
    """Calling update_run_stage_and_status must update both PostgreSQL test_runs row and Redis."""
    from sqlalchemy import select

    from app.services.run_service import (
        get_cached_run_status,
        get_live_progress,
        update_run_stage_and_status,
    )

    headers, user_id, proj_id = auth_headers

    create_resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert create_resp.status_code == 201
    run_id = uuid.UUID(create_resp.json()["id"])

    # Update to PLANNING
    await update_run_stage_and_status(
        run_id=run_id,
        stage="PLANNING",
        status="PLANNING",
        tests_total=5,
        tests_done=1,
        current_test_key="TC-1",
    )

    # 1. Verify Database
    session_factory = get_async_session_factory()
    async with session_factory() as s:
        db_run = (
            await s.execute(select(TestRun).where(TestRun.id == run_id))
        ).scalar_one()
        assert db_run.status == "PLANNING"
        assert db_run.stage == "PLANNING"
        assert db_run.updated_at is not None

    # 2. Verify Redis status cache
    cached = await get_cached_run_status(run_id)
    assert cached is not None
    assert cached.get("status") == "PLANNING"
    assert cached.get("stage") == "PLANNING"

    # 3. Verify Redis live progress
    progress = await get_live_progress(run_id)
    assert progress is not None
    assert progress.get("stage") == "PLANNING"
    assert progress.get("total_tests") == 5
    assert progress.get("completed_tests") == 1


@pytest.mark.asyncio
async def test_get_run_endpoint_returns_no_store_and_server_fields(
    client: AsyncClient, auth_headers
):
    """GET /runs/{id} returns Cache-Control: no-store and authoritative server_time/updated_at."""
    headers, user_id, proj_id = auth_headers

    create_resp = await client.post(f"/projects/{proj_id}/runs", headers=headers)
    assert create_resp.status_code == 201
    run_id = create_resp.json()["id"]

    resp = await client.get(f"/runs/{run_id}", headers=headers)
    assert resp.status_code == 200
    assert "no-store" in resp.headers.get("Cache-Control", "")
    data = resp.json()
    assert "stage" in data
    assert "server_time" in data
    assert "updated_at" in data
    assert "tests_done" in data
    assert "tests_total" in data

