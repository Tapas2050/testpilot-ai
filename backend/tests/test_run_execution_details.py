"""Tests for Part 2: Execution details response shape for runs and reports."""

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.test_run import TestCase, TestResult, TestRun


@pytest.mark.asyncio
async def test_get_run_detail_response_shape(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: tuple[dict[str, str], any, any],
):
    """Verify GET /runs/{id} returns rich execution details, steps, screenshot, and duration."""
    headers, user_id, project_id = auth_headers

    run = TestRun(
        project_id=project_id,
        status="COMPLETED",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(run)
    await db_session.flush()

    tc = TestCase(
        run_id=run.id,
        title="Create Ticket Test",
        description="Verify ticket creation",
        source_requirement="REQ-TC-01",
        target_role="agent",
        status="PASSED",
        order_index=0,
    )
    db_session.add(tc)
    await db_session.flush()

    res = TestResult(
        test_case_id=tc.id,
        status="PASSED",
        duration_seconds=5.4,
        screenshot_path=f"screenshots/{run.id}/{tc.id}.png",
        error_message=None,
        steps=[
            {
                "step": 1,
                "action": "navigate",
                "url": "http://localhost:8001/tickets/new",
                "observation": "Navigated to new ticket page " + ("x" * 400),
            },
            {
                "step": 2,
                "action": "finish",
                "status": "PASSED",
                "observation": "Ticket created successfully with ID 42",
                "evidence": "Ticket #42 confirmed",
                "check_results": [
                    {"check_id": "chk-1", "result": "PASSED", "evidence": "Ticket #42 confirmed"}
                ],
            },
        ],
    )
    db_session.add(res)
    await db_session.commit()

    resp = await client.get(f"/runs/{run.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["id"] == str(run.id)
    assert len(data["test_cases"]) == 1
    assert len(data["results"]) == 1

    tc_data = data["test_cases"][0]
    assert tc_data["test_key"] == "TC-1"
    assert tc_data["duration_seconds"] == 5.4
    assert tc_data["screenshot_path"] == f"screenshots/{run.id}/{tc.id}.png"
    assert tc_data["evidence"] == "Ticket #42 confirmed"
    assert tc_data["final_observation"] == "Ticket created successfully with ID 42"
    assert len(tc_data["steps"]) == 2
    # Check that observation was truncated to <= 300 characters
    assert len(tc_data["steps"][0]["observation"]) <= 300
    assert tc_data["steps"][0]["observation"].endswith("...")

    res_data = data["results"][0]
    assert res_data["duration_seconds"] == 5.4
    assert res_data["screenshot_path"] == f"screenshots/{run.id}/{tc.id}.png"
    assert res_data["final_observation"] == "Ticket created successfully with ID 42"
    assert res_data["evidence"] == "Ticket #42 confirmed"
    assert len(res_data["steps"]) == 2


@pytest.mark.asyncio
async def test_get_run_report_response_shape(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: tuple[dict[str, str], any, any],
):
    """Verify GET /runs/{id}/report includes test_cases, results, and normalized failure fields."""
    headers, user_id, project_id = auth_headers

    run = TestRun(
        project_id=project_id,
        status="COMPLETED",
        created_at=datetime.now(timezone.utc),
        report={
            "total_tests": 1,
            "passed_tests": 0,
            "failed_tests": 1,
            "pass_percentage": 0.0,
            "summary": "1 test failed",
            "failures": [
                {
                    "title": "Agent Deletion Test",
                    "expected_behavior": "403 Forbidden received",
                    "observed_behavior": "Ticket was deleted",
                    "classification": "PRODUCT_BUG",
                    "severity": "HIGH",
                    "confidence": 0.95,
                    "explanation": "Permission check missing",
                    "suggested_action": "Add role guard",
                }
            ],
        },
    )
    db_session.add(run)
    await db_session.flush()

    tc = TestCase(
        run_id=run.id,
        title="Agent Deletion Test",
        description="Verify agent deletion",
        source_requirement="REQ-SEC-02",
        target_role="agent",
        status="FAILED",
        order_index=0,
    )
    db_session.add(tc)
    await db_session.flush()

    res = TestResult(
        test_case_id=tc.id,
        status="FAILED",
        duration_seconds=2.8,
        screenshot_path=f"screenshots/{run.id}/{tc.id}.png",
        error_message="Observed deletion succeeded",
        steps=[
            {
                "step": 1,
                "action": "click",
                "selector": ".delete-btn",
                "observation": "Clicked delete button",
            }
        ],
    )
    db_session.add(res)
    await db_session.commit()

    resp = await client.get(f"/runs/{run.id}/report", headers=headers)
    assert resp.status_code == 200
    report = resp.json()

    assert "test_cases" in report
    assert "results" in report
    assert len(report["test_cases"]) == 1
    assert len(report["results"]) == 1

    failure = report["failures"][0]
    # Check normalized expected and observed fields
    assert failure["expected"] == "403 Forbidden received"
    assert failure["observed"] == "Ticket was deleted"
    assert failure["expected_behavior"] == "403 Forbidden received"
    assert failure["observed_behavior"] == "Ticket was deleted"
