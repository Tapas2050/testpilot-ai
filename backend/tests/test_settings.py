"""Tests for Phase 1: T1.2 Settings validation."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_settings_loads_successfully():
    """T1.2: Settings load successfully from active environment configuration."""
    settings = get_settings()
    assert settings.DATABASE_URL
    assert settings.REDIS_URL
    assert settings.ALLOWED_PRIVATE_HOSTS == ["localhost", "127.0.0.1"]


def test_settings_fails_when_required_variable_missing(monkeypatch):
    """T1.2: Settings fail with ValidationError when DATABASE_URL is missing."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    errors = exc_info.value.errors()
    missing_fields = [err["loc"][0] for err in errors]
    assert "DATABASE_URL" in missing_fields


def test_settings_allowed_private_hosts_parsing():
    """T1.2: Custom comma-separated allowed private hosts string parses to list."""
    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/test",
        JWT_SECRET="a" * 32,
        ALLOWED_PRIVATE_HOSTS="app.local, api.local",
        _env_file=None,
    )
    assert settings.ALLOWED_PRIVATE_HOSTS == ["app.local", "api.local"]


def test_settings_refuses_empty_jwt_secret():
    """T2.9: Settings must refuse to start when JWT_SECRET is empty."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/test",
            JWT_SECRET="",
            _env_file=None,
        )
    assert any("JWT_SECRET" in str(err) for err in exc_info.value.errors())


def test_settings_refuses_short_jwt_secret():
    """T2.9: Settings must refuse to start when JWT_SECRET is shorter than 32 characters."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/test",
            JWT_SECRET="short-secret-under-32-chars",
            _env_file=None,
        )
    assert any("JWT_SECRET" in str(err) for err in exc_info.value.errors())


def test_part5_settings_defaults_and_lock_ttl():
    """Part 5: Verify default model is gemini-3.5-flash-lite, RPM is 12,
    timeout is 1800, and lock TTL exceeds timeout.
    """
    from app.services.run_service import get_lock_ttl_seconds

    settings = Settings(
        DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/test",
        JWT_SECRET="a" * 32,
        _env_file=None,
    )
    assert settings.GOOGLE_MODEL == "gemini-3.5-flash-lite"
    assert settings.LLM_REQUESTS_PER_MINUTE == 12
    assert settings.RUN_TIMEOUT_SECONDS == 1800

    lock_ttl = get_lock_ttl_seconds()
    assert lock_ttl > settings.RUN_TIMEOUT_SECONDS
