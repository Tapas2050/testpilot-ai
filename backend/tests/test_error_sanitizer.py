"""Tests for Part 3: Error sanitizer, traceback logging, and deadline distinction."""

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.graph import execute_agent_run
from app.core.security import format_run_failure_message, sanitize_secret_values


def test_sanitize_secret_values_redacts_credentials():
    """Verify that sanitize_secret_values strips all passwords, tokens, and keys."""
    # 1. Database URL password
    raw_db_url = "postgresql://postgres:SecretPostgresPass123!@localhost:5432/testpilot"
    clean = sanitize_secret_values(raw_db_url)
    assert "SecretPostgresPass123!" not in clean
    assert "postgresql://postgres:[REDACTED]@localhost:5432/testpilot" in clean

    # 2. Bearer token
    raw_bearer = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secretpayload.sig"
    clean = sanitize_secret_values(raw_bearer)
    assert "secretpayload" not in clean
    assert "Bearer [REDACTED]" in clean

    # 3. Google AI Studio & OpenAI API keys
    raw_keys = "Keys: AIzaSyD1234567890abcdefghijklmnopqrstuv and sk-1234567890abcdef1234567890"
    clean = sanitize_secret_values(raw_keys)
    assert "AIzaSyD1234567890abcdefghijklmnopqrstuv" not in clean
    assert "sk-1234567890abcdef1234567890" not in clean
    assert "[REDACTED]" in clean

    # 4. Explicit project credential passwords
    project_passwords = ["AgentPass456!", "AdminPass789!"]
    raw_msg = "Login failed with password='AgentPass456!' for user agent@example.com"
    clean = sanitize_secret_values(raw_msg, secrets=project_passwords)
    assert "AgentPass456!" not in clean
    assert "[REDACTED]" in clean

    # 5. Generic password assignment pattern
    raw_assignment = 'connection failed: password="SuperSecret123" host=localhost'
    clean = sanitize_secret_values(raw_assignment)
    assert "SuperSecret123" not in clean
    assert 'password="[REDACTED]"' in clean or "password=[REDACTED]" in clean


def test_format_run_failure_message_structure():
    """Verify format_run_failure_message includes stage, test key, and clean message."""
    exc = RuntimeError("Database password postgres://user:pw123@host failed")
    msg = format_run_failure_message(
        stage="EXECUTING",
        exc=exc,
        test_key="tc_2",
        secrets=["pw123"],
    )
    assert "[EXECUTING:tc_2] RuntimeError:" in msg
    assert "pw123" not in msg
    assert "[REDACTED]" in msg


@pytest.mark.asyncio
async def test_real_deadline_exceeded_reported_correctly():
    """Verify that when run genuinely exceeds RUN_TIMEOUT_SECONDS, deadline message is set."""
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
        # 0.05 second limit
        mock_settings.return_value.RUN_TIMEOUT_SECONDS = 0.05

        async def slow_astream(*args, **kwargs):
            await asyncio.sleep(0.15)
            yield {}

        mock_graph = AsyncMock()
        mock_graph.astream = slow_astream
        mock_build_graph.return_value = mock_graph

        await execute_agent_run(run_id=run_id, project_id=project_id)

        assert mock_update_db.called
        final_call = mock_update_db.call_args_list[-1]
        err_msg = final_call.kwargs.get("error_message", "")
        assert "Run exceeded the time limit of 0.05 seconds" in err_msg
