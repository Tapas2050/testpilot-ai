"""Unit tests for review_run.py evaluation script (Part 6).

Verifies that review_run fetches and formats run statistics, test case details,
and correctly compares verdicts against ground truth when --expect-supportdesk-defects is passed.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.test_run import TestCase, TestResult, TestRun
from app.models.user import User
from scripts.review_run import fetch_review_data, format_review_text


@pytest.fixture
async def sample_run_fixtures(db_session: AsyncSession):
    """Create fixture test run with test cases and results."""
    user = User(
        email=f"reviewer_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hashed",
    )
    db_session.add(user)
    await db_session.flush()

    project = Project(
        name="Review Test Project",
        target_url="http://localhost:8001",
        user_id=user.id,
    )
    db_session.add(project)
    await db_session.flush()

    started = datetime.now(timezone.utc) - timedelta(minutes=2, seconds=15)
    completed = datetime.now(timezone.utc)

    # 1. Defective run (2 defects found, 1 missed)
    run_defective = TestRun(
        project_id=project.id,
        status="COMPLETED",
        started_at=started,
        completed_at=completed,
        created_at=started,
        report={"live_llm_calls": 35},
    )
    db_session.add(run_defective)
    await db_session.flush()

    # TC-1: REQ-AUTH-01 (PASSED)
    tc1 = TestCase(
        run_id=run_defective.id,
        title="Admin Login",
        source_requirement="REQ-AUTH-01",
        target_role="admin",
        status="PASSED",
        order_index=0,
    )
    db_session.add(tc1)
    await db_session.flush()

    res1 = TestResult(
        test_case_id=tc1.id,
        status="PASSED",
        screenshot_path="screenshots/tc1.png",
        steps=[{"step": 1, "action": "login", "observation": "Logged in successfully"}],
    )
    db_session.add(res1)

    # TC-2: REQ-SEC-02 (Agent deletion - MISSED defect, ended PASSED)
    tc2 = TestCase(
        run_id=run_defective.id,
        title="Agent Deletion Prohibition",
        source_requirement="REQ-SEC-02",
        target_role="agent",
        status="PASSED",
        order_index=1,
    )
    db_session.add(tc2)
    await db_session.flush()

    res2 = TestResult(
        test_case_id=tc2.id,
        status="PASSED",
        screenshot_path=None,
        steps=[{"step": 1, "action": "click", "observation": "Button missing"}],
    )
    db_session.add(res2)

    # TC-3: REQ-TKT-02 (High priority - FOUND defect, ended FAILED)
    tc3 = TestCase(
        run_id=run_defective.id,
        title="High Priority Persistence",
        source_requirement="REQ-TKT-02",
        target_role="agent",
        status="FAILED",
        order_index=2,
    )
    db_session.add(tc3)
    await db_session.flush()

    res3 = TestResult(
        test_case_id=tc3.id,
        status="FAILED",
        failure_screenshot_path="screenshots/tc3_fail.png",
        steps=[
            {
                "step": 1,
                "action": "finish",
                "observation": (
                    "Priority saved as Low instead of High: " + ("detailed explanation " * 15)
                ),
            }
        ],
    )
    db_session.add(res3)

    # TC-4: REQ-SRCH-01 (ID Search - FOUND defect, ended FAILED)
    tc4 = TestCase(
        run_id=run_defective.id,
        title="Ticket ID Search",
        source_requirement="REQ-SRCH-01",
        target_role="agent",
        status="FAILED",
        order_index=3,
    )
    db_session.add(tc4)
    await db_session.flush()

    res4 = TestResult(
        test_case_id=tc4.id,
        status="FAILED",
        screenshot_path="screenshots/tc4.png",
        steps=[{"step": 1, "action": "search", "observation": "Zero results for ticket #1"}],
    )
    db_session.add(res4)

    await db_session.commit()

    return {
        "run_id": run_defective.id,
        "user_id": user.id,
        "project_id": project.id,
    }


@pytest.mark.asyncio
async def test_fetch_review_data_extracts_correct_fields(
    db_session: AsyncSession,
    sample_run_fixtures: dict[str, Any],
):
    """Test fetch_review_data retrieves run stats and test metadata cleanly."""
    run_id = sample_run_fixtures["run_id"]

    data = await fetch_review_data(db_session, run_id=run_id)
    assert data is not None
    assert data["run_id"] == str(run_id)
    assert data["status"] == "COMPLETED"
    assert data["duration"] == "2m 15s"
    assert data["live_llm_calls"] == 35
    assert data["tests_planned"] == 4

    tests = data["tests"]
    assert len(tests) == 4

    # TC-1
    assert tests[0]["test_key"] == "TC-1"
    assert tests[0]["target_role"] == "admin"
    assert tests[0]["source_requirement"] == "REQ-AUTH-01"
    assert tests[0]["final_status"] == "PASSED"
    assert tests[0]["step_count"] == 1
    assert tests[0]["screenshot_present"] == "yes"

    # TC-2
    assert tests[1]["test_key"] == "TC-2"
    assert tests[1]["source_requirement"] == "REQ-SEC-02"
    assert tests[1]["screenshot_present"] == "no"

    # TC-3: observation truncation check (<= 160 characters)
    assert tests[2]["test_key"] == "TC-3"
    assert tests[2]["final_status"] == "FAILED"
    assert len(tests[2]["final_observation"]) <= 160
    assert tests[2]["final_observation"].endswith("...")
    assert tests[2]["screenshot_present"] == "yes"


def test_format_review_text_without_ground_truth():
    """Test format_review_text produces standard table."""
    mock_data = {
        "run_id": "test-uuid-1234",
        "status": "COMPLETED",
        "duration": "1m 30s",
        "live_llm_calls": 12,
        "tests_planned": 2,
        "tests": [
            {
                "test_key": "TC-1",
                "title": "Login",
                "target_role": "admin",
                "source_requirement": "REQ-AUTH-01",
                "final_status": "PASSED",
                "step_count": 3,
                "final_observation": "Admin login succeeded",
                "screenshot_present": "yes",
            },
            {
                "test_key": "TC-2",
                "title": "Search",
                "target_role": "agent",
                "source_requirement": "REQ-SRCH-01",
                "final_status": "FAILED",
                "step_count": 4,
                "final_observation": "Search failed",
                "screenshot_present": "yes",
            },
        ],
    }

    out = format_review_text(mock_data, expect_defects=False)
    assert "TESTPILOT RUN REVIEW" in out
    assert "Run ID:             test-uuid-1234" in out
    assert "Live LLM Calls:     12" in out
    assert "TC-1   admin    REQ-AUTH-01    PASSED" in out
    assert "SUPPORTDESK GROUND TRUTH EVALUATION" not in out


def test_format_review_text_with_ground_truth_defects():
    """Test format_review_text with --expect-supportdesk-defects flag."""
    mock_data = {
        "run_id": "test-uuid-5678",
        "status": "COMPLETED",
        "duration": "3m 00s",
        "live_llm_calls": 25,
        "tests_planned": 3,
        "tests": [
            {
                "test_key": "TC-1",
                "title": "Login",
                "target_role": "admin",
                "source_requirement": "REQ-AUTH-01",
                "final_status": "PASSED",
                "step_count": 2,
                "final_observation": "Passed",
                "screenshot_present": "yes",
            },
            {
                "test_key": "TC-2",
                "title": "Agent Deletion",
                "target_role": "agent",
                "source_requirement": "REQ-SEC-02",
                "final_status": "FAILED",  # Planted defect found!
                "step_count": 3,
                "final_observation": "Action permitted",
                "screenshot_present": "yes",
            },
            {
                "test_key": "TC-3",
                "title": "Priority",
                "target_role": "agent",
                "source_requirement": "REQ-TKT-02",
                "final_status": "PASSED",  # Planted defect missed!
                "step_count": 3,
                "final_observation": "Saved as High",
                "screenshot_present": "yes",
            },
        ],
    }

    out = format_review_text(mock_data, expect_defects=True)
    assert "SUPPORTDESK GROUND TRUTH EVALUATION (SUPPORTDESK_DEFECTS=on)" in out
    assert "TC-1   REQ-AUTH-01    PASSED     PASSED     MATCH" in out
    assert "TC-2   REQ-SEC-02     FAILED     FAILED     MATCH" in out
    assert "TC-3   REQ-TKT-02     FAILED     PASSED     MISMATCH" in out
    assert "Defects found: 1 of 3" in out
    assert "Total requirements matched: 2 of 3" in out
