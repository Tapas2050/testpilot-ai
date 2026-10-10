"""Unit tests for LLM resilience, per-request timeout, daily-quota fast fallback."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.executor import execute_single_test_case
from app.agent.llm import (
    AllProvidersFailedError,
    get_openrouter_llm,
    get_primary_llm,
    is_daily_quota_error,
    set_mock_llm,
)
from app.core.config import get_settings
from app.models.project import Project
from app.models.test_run import Failure, TestCase, TestResult, TestRun
from app.models.user import User


def test_is_daily_quota_error():
    """Verify daily quota error detection distinguishes daily quota vs per-minute rate limits."""
    # Daily quota strings
    quota_str = (
        "Quota exceeded for quota metric 'Queries' and limit 'Queries per day' of PROJECT"
    )
    assert is_daily_quota_error(ValueError(quota_str))
    assert is_daily_quota_error(Exception("429 RESOURCE_EXHAUSTED: daily quota limit reached"))
    assert is_daily_quota_error(RuntimeError("429: insufficient_quota for current model"))
    assert is_daily_quota_error(
        Exception("429 Resource has been exhausted (e.g. check quota per day)")
    )

    # Per-minute rate limit strings (should return False)
    assert not is_daily_quota_error(
        ValueError("429: Rate limit exceeded: 12 requests per minute")
    )
    assert not is_daily_quota_error(ValueError("429: rate limit rpm exceeded"))

    # Non-quota errors
    assert not is_daily_quota_error(ValueError("500 Internal Server Error"))
    assert not is_daily_quota_error(None)


def test_llm_request_timeout_configuration():
    """Verify that per-request timeout is configured on primary, fallback, and OpenRouter LLMs."""
    settings = get_settings()
    assert hasattr(settings, "LLM_REQUEST_TIMEOUT_SECONDS")
    assert settings.LLM_REQUEST_TIMEOUT_SECONDS == 60.0

    primary = get_primary_llm()
    assert hasattr(primary, "timeout")
    assert primary.timeout == settings.LLM_REQUEST_TIMEOUT_SECONDS

    # Mock openrouter key and model to inspect timeout
    with patch.object(settings, "OPENROUTER_API_KEY", "test_key"), \
         patch.object(settings, "OPENROUTER_MODEL", "test_model"):
        or_llm = get_openrouter_llm()
        assert or_llm is not None
        assert or_llm.request_timeout == settings.LLM_REQUEST_TIMEOUT_SECONDS


@pytest.mark.asyncio
async def test_single_test_llm_failure_marks_blocked_environment_failure(db_session, tmp_path):
    """When all LLM providers fail on a test, mark the test BLOCKED with ENVIRONMENT_FAILURE."""
    run_id = uuid.uuid4()
    tc = TestCase(
        id=uuid.uuid4(),
        run_id=run_id,
        title="Test Login Page",
        description="Verify user can log in",
        source_requirement="REQ-AUTH-01",
        target_role="anonymous",
        status="PENDING",
        order_index=0,
    )

    # Mock MCP client
    mock_mcp = AsyncMock()
    mock_mcp.call_tool = AsyncMock(return_value={"text": "<html>Login</html>"})

    # Mock LLM to simulate all providers failing
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(
        side_effect=AllProvidersFailedError(
            "Resource exhausted across all configured LLM providers"
        )
    )
    set_mock_llm(mock_llm)

    try:
        result = await execute_single_test_case(
            test_case=tc,
            target_url="http://localhost:8001",
            credentials={},
            mcp_client=mock_mcp,
            run_id=run_id,
            storage_dir=tmp_path,
        )

        assert result.status == "BLOCKED"
        assert "All LLM providers failed" in (result.error_message or "")
    finally:
        set_mock_llm(None)


@pytest.mark.asyncio
async def test_two_consecutive_llm_failures_terminates_run_failed(db_session, tmp_path):
    """When 2 consecutive tests fail due to LLM provider failure, the run ends as FAILED."""
    project_id = uuid.uuid4()
    run_id = uuid.uuid4()

    user = User(
        id=uuid.uuid4(),
        email=f"resilience.{uuid.uuid4().hex[:6]}@example.com",
        password_hash="fakehash",
    )
    project = Project(
        id=project_id,
        user_id=user.id,
        name="Test LLM Resilience Project",
        target_url="http://localhost:8001",
    )
    test_run = TestRun(
        id=run_id,
        project_id=project_id,
        status="PLANNING",
    )
    tc1 = TestCase(
        id=uuid.uuid4(),
        run_id=run_id,
        title="Test Case 1",
        description="Verify test 1",
        source_requirement="REQ-01",
        target_role="anonymous",
        status="PENDING",
        order_index=0,
    )
    tc2 = TestCase(
        id=uuid.uuid4(),
        run_id=run_id,
        title="Test Case 2",
        description="Verify test 2",
        source_requirement="REQ-02",
        target_role="anonymous",
        status="PENDING",
        order_index=1,
    )
    tc3 = TestCase(
        id=uuid.uuid4(),
        run_id=run_id,
        title="Test Case 3",
        description="Verify test 3",
        source_requirement="REQ-03",
        target_role="anonymous",
        status="PENDING",
        order_index=2,
    )

    db_session.add_all([user, project, test_run, tc1, tc2, tc3])
    await db_session.commit()

    # Mock execute_single_test_case to simulate LLM failure on all tests
    call_count = 0

    async def mock_execute_test(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        tc_arg = kwargs.get("test_case")
        return TestResult(
            test_case_id=tc_arg.id,
            status="BLOCKED",
            error_message="All LLM providers failed: Quota exceeded for model per day",
        )

    # Mock MCP client start/close
    with patch(
        "app.agent.graph.executor.execute_single_test_case",
        side_effect=mock_execute_test,
    ), patch("app.agent.graph.PlaywrightMCPClient") as mock_mcp_cls:
        instance = AsyncMock()
        mock_mcp_cls.return_value = instance

        db_url = db_session.bind.url.render_as_string(hide_password=False)

        initial_state = {
            "run_id": str(run_id),
            "project_id": str(project_id),
            "current_stage": "EXECUTING",
            "db_url": db_url,
            "is_mock_mcp": True,
        }

        # Fast-forward execute node directly
        from app.agent.graph import complete_node, execute_node, report_node
        res_exec = await execute_node(initial_state)

        # After 2 failures, loop should have broken and tc3 never executed!
        assert call_count == 2
        assert res_exec.get("llm_aborted") is True
        assert "All LLM providers failed on consecutive tests" in res_exec.get(
            "abort_message", ""
        )

        state_after_exec = {**initial_state, **res_exec}
        res_report = await report_node(state_after_exec)
        state_after_report = {**state_after_exec, **res_report}
        res_complete = await complete_node(state_after_report)

        assert res_complete["status"] == "FAILED"
        assert "All LLM providers failed" in res_complete["error_message"]

        # Verify DB records
        await db_session.refresh(tc1)
        await db_session.refresh(tc2)
        await db_session.refresh(tc3)
        await db_session.refresh(test_run)

        assert tc1.status == "BLOCKED"
        assert tc2.status == "BLOCKED"
        assert tc3.status == "BLOCKED"
        assert test_run.status == "FAILED"

        # Verify failures classified as ENVIRONMENT_FAILURE
        from sqlalchemy import select
        failures = (
            await db_session.execute(
                select(Failure).where(Failure.test_case_id.in_([tc1.id, tc2.id]))
            )
        ).scalars().all()
        assert len(failures) == 2
        for f in failures:
            assert f.classification == "ENVIRONMENT_FAILURE"
