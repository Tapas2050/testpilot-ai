"""Tests for Phase 1: T1.1 Health endpoint."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok_with_db_and_redis():
    """T1.1: Health endpoint returns OK with live DB, pgvector, and Redis status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["api"] == "ok"
    assert data["database"]["status"] == "healthy"
    assert data["database"]["pgvector_enabled"] is True
    assert data["redis"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_endpoint_reports_db_failure_without_crashing():
    """T1.1 resilience: If Postgres is down, report it and do not crash."""
    with patch(
        "app.api.health.check_db_health",
        return_value={"status": "unhealthy", "pgvector_enabled": False, "error": "db down"},
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["api"] == "ok"
        assert data["database"]["status"] == "unhealthy"
        assert data["database"]["pgvector_enabled"] is False
        assert data["redis"]["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_endpoint_reports_redis_failure_without_crashing():
    """T1.1 resilience: If Redis is down, report it and do not crash."""
    with patch(
        "app.api.health.check_redis_health",
        return_value={"status": "unhealthy", "error": "redis down"},
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["api"] == "ok"
        assert data["database"]["status"] == "healthy"
        assert data["redis"]["status"] == "unhealthy"
