"""Automated reproduction tests for Part 1: Live status progression."""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import update

from app.core.database import get_async_session_factory
from app.models.test_run import TestRun
from app.services.run_service import cache_run_status, update_live_progress


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
        session_factory = get_async_session_factory()

        for stg in ["PREFLIGHT", "PLANNING", "EXECUTING", "ANALYZING", "REPORTING"]:
            await asyncio.sleep(0.15)
            async with session_factory() as s:
                await s.execute(
                    update(TestRun)
                    .where(TestRun.id == run_id)
                    .values(status=stg)
                )
                await s.commit()
            await cache_run_status(run_id, status=stg, stage=stg)
            await update_live_progress(run_id, stage=stg)

        # Completed
        await asyncio.sleep(0.15)
        now = datetime.now(timezone.utc)
        async with session_factory() as s:
            await s.execute(
                update(TestRun)
                .where(TestRun.id == run_id)
                .values(status="COMPLETED", completed_at=now)
            )
            await s.commit()
        await cache_run_status(run_id, status="COMPLETED", stage="COMPLETED")
        await update_live_progress(run_id, stage="COMPLETED")
        pipeline_finished.set()

    pipeline_task = asyncio.create_task(_mock_pipeline())

    # Poll until pipeline completes and COMPLETED is observed
    while True:
        resp = await client.get(f"/runs/{run_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()

        # The stage could come from stage or current_stage or agent_stage
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
