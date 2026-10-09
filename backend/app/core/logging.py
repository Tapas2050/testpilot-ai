"""Structured logging utilities with run_id context and sensitive data redaction."""

import contextvars
import logging
import re
from typing import Optional

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


def setup_structured_logging(level: int = logging.INFO) -> None:
    """Configure root logger with structured format and security filters."""
    log_format = "%(asctime)s [%(levelname)s] [run_id:%(run_id)s] [%(name)s] %(message)s"
    formatter = logging.Formatter(log_format)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(RunContextFilter())
    handler.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Clear existing handlers to avoid duplicates
    root_logger.handlers = [handler]
