"""Structured logging utilities with run_id context and sensitive data redaction."""

import contextvars
import logging
import os
import re
from typing import Optional, Union

# Context variable tracking current test run ID across async execution
current_run_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_run_id", default=None
)

# Common sensitive patterns to redact
REDACTION_PATTERNS = [
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]+", re.IGNORECASE),
    re.compile(r"(password[\"']?\s*[:=]\s*[\"'])([^\"']+)([\"'])", re.IGNORECASE),
    re.compile(r"(token[\"']?\s*[:=]\s*[\"'])([^\"']+)([\"'])", re.IGNORECASE),
    re.compile(r"(secret[\"']?\s*[:=]\s*[\"'])([^\"']+)([\"'])", re.IGNORECASE),
]


class RunContextFilter(logging.Filter):
    """Injects current run_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.run_id = current_run_id.get() or "-"
        return True


class SensitiveDataFilter(logging.Filter):
    """Redacts secrets, passwords, and bearer tokens from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            for pattern in REDACTION_PATTERNS:
                if "Bearer" in pattern.pattern:
                    msg = pattern.sub(r"\1[REDACTED]", msg)
                else:
                    msg = pattern.sub(r"\1[REDACTED]\3", msg)
            record.msg = msg
        return True


def setup_structured_logging(level: Optional[Union[int, str]] = None) -> None:
    """Configure root logger with structured format and security filters."""
    resolved_level: int = logging.INFO
    if level is None:
        try:
            from app.core.config import get_settings

            level_str = get_settings().LOG_LEVEL
            resolved_level = getattr(logging, str(level_str).upper(), logging.INFO)
        except Exception:
            resolved_level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    elif isinstance(level, str):
        resolved_level = getattr(logging, level.upper(), logging.INFO)
    elif isinstance(level, int):
        resolved_level = level

    log_format = "%(asctime)s [%(levelname)s] [run_id:%(run_id)s] [%(name)s] %(message)s"
    formatter = logging.Formatter(log_format)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(resolved_level)
    handler.addFilter(RunContextFilter())
    handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)
    # Clear existing handlers to avoid duplicates,
    # but preserve test/capture handlers (e.g. pytest caplog)
    capture_handlers = [
        h
        for h in root_logger.handlers
        if "Capture" in type(h).__name__ or getattr(h, "name", "") == "log-capture"
    ]
    root_logger.handlers = [handler] + capture_handlers

    # Explicitly set level on app and arq loggers
    logging.getLogger("app").setLevel(resolved_level)
    logging.getLogger("arq").setLevel(resolved_level)
