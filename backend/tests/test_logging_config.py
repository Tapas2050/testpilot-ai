"""Tests for explicit logging configuration and run_id context injection."""

import logging

from app.core.logging import (
    RunContextFilter,
    SensitiveDataFilter,
    current_run_id,
    setup_structured_logging,
)


def test_setup_structured_logging_levels(monkeypatch) -> None:
    """Test setup_structured_logging with various level specifications."""
    # Test with string level
    setup_structured_logging(level="DEBUG")
    assert logging.getLogger().level == logging.DEBUG
    assert logging.getLogger("app").level == logging.DEBUG
    assert logging.getLogger("arq").level == logging.DEBUG

    # Test with int level
    setup_structured_logging(level=logging.WARNING)
    assert logging.getLogger().level == logging.WARNING
    assert logging.getLogger("app").level == logging.WARNING
    assert logging.getLogger("arq").level == logging.WARNING

    # Test default fallback via settings/env
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    setup_structured_logging(level=None)
    assert logging.getLogger().level == logging.INFO


def test_run_context_filter() -> None:
    """Test that RunContextFilter injects current run_id or default '-'."""
    f = RunContextFilter()
    rec = logging.LogRecord("test", logging.INFO, "path", 1, "test message", (), None)

    # When no run_id set
    assert f.filter(rec) is True
    assert rec.run_id == "-"

    # When run_id is set
    token = current_run_id.set("run-abc-123")
    try:
        assert f.filter(rec) is True
        assert rec.run_id == "run-abc-123"
    finally:
        current_run_id.reset(token)


def test_sensitive_data_filter() -> None:
    """Test that SensitiveDataFilter redacts secrets and credentials."""
    f = SensitiveDataFilter()
    rec = logging.LogRecord(
        "test",
        logging.INFO,
        "path",
        1,
        "Connecting with Bearer mysecrettoken and password='supersecret'",
        (),
        None,
    )
    assert f.filter(rec) is True
    assert "Bearer [REDACTED]" in rec.msg
    assert "password='[REDACTED]'" in rec.msg
    assert "supersecret" not in rec.msg
    assert "mysecrettoken" not in rec.msg
