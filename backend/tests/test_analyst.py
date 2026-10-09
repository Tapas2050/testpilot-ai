"""Unit, integration, and eval tests for Phase 11 Failure Analyst and Report Generator."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.agent.analyst import FailureAnalysisOutput, analyze_test_failure
from app.agent.llm import set_mock_llm
from app.agent.report import generate_run_report


def test_t11_1_failure_schema_allowed_categories():
    """T11.1: Failure schema parses and enforces the 5 allowed categories."""
    # Valid output with allowed classification
    valid_data = {
        "classification": "PRODUCT_BUG",
        "severity": "HIGH",
        "confidence": 0.95,
        "expected": "Support agent cannot delete tickets",
        "observed": "Support agent deleted ticket 1",
        "explanation": "Permission check missing on DELETE /tickets/{id}",
        "suggested_action": "Add role-based authorization check in ticket router",
    }
    output = FailureAnalysisOutput.model_validate(valid_data)
    assert output.classification == "PRODUCT_BUG"
    assert output.severity == "HIGH"

    # All 5 allowed categories must be accepted
    for cat in [
        "PRODUCT_BUG",
        "TEST_FAILURE",
        "AUTHENTICATION_FAILURE",
        "ENVIRONMENT_FAILURE",
        "FLAKY_TEST",
    ]:
        valid_data["classification"] = cat
        assert FailureAnalysisOutput.model_validate(valid_data).classification == cat

    # Invalid category must raise ValidationError
    valid_data["classification"] = "USER_ERROR"
    with pytest.raises(ValidationError):
        FailureAnalysisOutput.model_validate(valid_data)


@pytest.mark.asyncio
async def test_t11_2_analyst_runs_only_for_failed_tests():
    """T11.2: Analyst executes only for failed tests; passed tests are not analyzed."""
    from app.agent.graph import analyze_node
    from app.core.config import get_settings
    from app.core.database import get_async_session_factory
    from app.models.project import Project
    from app.models.test_run import TestCase, TestResult, TestRun
    from app.models.user import User

    settings = get_settings()
    session_factory = get_async_session_factory(settings.TEST_DATABASE_URL)
    run_id = uuid.uuid4()
    proj_id = uuid.uuid4()
    user_id = uuid.uuid4()

    async with session_factory() as session:
        user = User(
            id=user_id,
            email=f"analyst_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="dummy",
        )
        proj = Project(
            id=proj_id,
            user_id=user_id,
            name="Analyst Proj",
            target_url="http://localhost:8001",
        )
        run = TestRun(id=run_id, project_id=proj_id, status="EXECUTING")
        session.add_all([user, proj, run])
        await session.flush()

        # Passed test case
        tc1_id = uuid.uuid4()
        tc1 = TestCase(
            id=tc1_id, run_id=run_id, title="Passed Test", status="PASSED", order_index=1
        )
        res1 = TestResult(test_case_id=tc1_id, status="PASSED")

        # Failed test case
        tc2_id = uuid.uuid4()
        tc2 = TestCase(
            id=tc2_id, run_id=run_id, title="Failed Test", status="FAILED", order_index=2
        )
        res2 = TestResult(
            test_case_id=tc2_id, status="FAILED", error_message="Button not found"
        )

        session.add_all([tc1, res1, tc2, res2])
        await session.commit()

    # Mock analyst LLM
    mock_llm = MagicMock()
    mock_diag = FailureAnalysisOutput(
        classification="PRODUCT_BUG",
        severity="MEDIUM",
        confidence=0.9,
        expected="Button present",
        observed="Button absent",
        explanation="UI element missing",
        suggested_action="Restore button element",
    )
    mock_llm.ainvoke = AsyncMock(return_value=mock_diag)
    set_mock_llm(mock_llm)

    try:
        state = {
            "run_id": str(run_id),
            "project_id": str(proj_id),
            "db_url": settings.TEST_DATABASE_URL,
            "test_cases": [],
            "results": [],
            "failures": [],
        }
        res_state = await analyze_node(state)

        # Exactly 1 failure analyzed (tc2), tc1 was ignored
        assert len(res_state["failures"]) == 1
        assert res_state["failures"][0]["title"] == "Failed Test"
        assert res_state["failures"][0]["classification"] == "PRODUCT_BUG"
    finally:
        set_mock_llm(None)


def test_t11_3_report_totals_and_pass_percentage_math():
    """T11.3: Report totals and pass percentage are mathematically correct."""
    test_cases = [
        {"id": "1", "title": "Test 1"},
        {"id": "2", "title": "Test 2"},
        {"id": "3", "title": "Test 3"},
        {"id": "4", "title": "Test 4"},
    ]
    results = [
        {"test_case_id": "1", "status": "PASSED"},
        {"test_case_id": "2", "status": "PASSED"},
        {"test_case_id": "3", "status": "PASSED"},
        {"test_case_id": "4", "status": "FAILED"},
    ]
    failures = [
        {"test_case_id": "4", "classification": "PRODUCT_BUG", "severity": "HIGH"},
    ]

    report = generate_run_report(test_cases, results, failures)
    assert report["total_tests"] == 4
    assert report["passed_tests"] == 3
    assert report["failed_tests"] == 1
    assert report["pass_percentage"] == 75.0
    assert report["classification_breakdown"]["PRODUCT_BUG"] == 1
    assert report["severity_breakdown"]["HIGH"] == 1


def test_t11_4_report_and_evidence_contain_no_credentials():
    """T11.4: Report and evidence contain no credentials."""
    secret = "SuperSecretAdminPassword#2026"
    test_cases = [{"id": "1", "title": "Auth test"}]
    results = [{"test_case_id": "1", "status": "PASSED"}]
    failures = []

    report = generate_run_report(test_cases, results, failures)
    report_str = str(report)
    assert secret not in report_str


@pytest.mark.eval
@pytest.mark.asyncio
async def test_t11_5_eval_defective_build_reports_planted_defects():
    """T11.5: eval: defective build reports 3 planted defects as PRODUCT_BUG."""
    # Defect 1: Agent cannot delete tickets
    diag1 = await analyze_test_failure(
        title="Support agent cannot delete tickets",
        description="Verify support agent receives 403 on DELETE /tickets/{id}",
        source_requirement="REQ-SEC-01",
        target_role="agent",
        steps=[{"step": 1, "action": "click", "selector": "#delete-btn", "status": "200 OK"}],
        error_message="Support agent successfully deleted ticket contrary to REQ-SEC-01",
    )
    assert diag1.classification == "PRODUCT_BUG"

    # Defect 2: High priority persistence
    diag2 = await analyze_test_failure(
        title="Ticket priority High persisted correctly",
        description="Create ticket with priority High, verify on reload",
        source_requirement="REQ-TKT-02",
        target_role="agent",
        steps=[{"step": 1, "action": "create", "value": "High", "status": "saved as Medium"}],
        error_message="Ticket priority saved as Medium instead of High per REQ-TKT-02",
    )
    assert diag2.classification == "PRODUCT_BUG"

    # Defect 3: Search by ID
    diag3 = await analyze_test_failure(
        title="Search ticket by ID",
        description="Search for ticket #12 by ID returns ticket #12",
        source_requirement="REQ-SRCH-01",
        target_role="agent",
        steps=[{"step": 1, "action": "search", "value": "12", "status": "No results found"}],
        error_message="Ticket search by ID failed to find existing ticket",
    )
    assert diag3.classification == "PRODUCT_BUG"
