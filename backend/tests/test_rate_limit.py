"""T13.1: Rate limiting tests for login attempts and test run creation."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_t13_1_login_rate_limiting_triggers_429(client: AsyncClient):
    """T13.1: Exceeding 10 login requests in 60 seconds returns 429 Too Many Requests."""
    with patch("app.core.rate_limit.get_redis_client") as mock_get_redis:
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        # Mock Redis incr returning 11 (exceeded 10 limit)
        mock_redis.incr.return_value = 11
        mock_redis.ttl.return_value = 45

        resp = await client.post(
            "/auth/login",
            json={"email": "attacker@example.com", "password": "wrongpassword123"},
        )
        assert resp.status_code == 429
        assert "Too many login attempts" in resp.json()["detail"]
        assert resp.headers.get("retry-after") == "45"


@pytest.mark.asyncio
async def test_t13_1_run_creation_rate_limiting_triggers_429(
    client: AsyncClient, auth_headers
):
    """T13.1: Exceeding 5 run creation requests in 60 seconds returns 429."""
    headers, user_id, proj_id = auth_headers

    with patch("app.core.rate_limit.get_redis_client") as mock_get_redis:
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis

        # Mock Redis incr returning 6 (exceeded 5 limit)
        mock_redis.incr.return_value = 6
        mock_redis.ttl.return_value = 30

        resp = await client.post(
            f"/projects/{proj_id}/runs",
            headers=headers,
        )
        assert resp.status_code == 429
        assert "Too many test runs created recently" in resp.json()["detail"]
        assert resp.headers.get("retry-after") == "30"
