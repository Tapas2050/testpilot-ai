"""LLM provider interface with primary, fallback chain, rate limiting, and call tracking."""

import asyncio
import logging
import time
import warnings
from typing import Any, Optional, Type

from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import get_settings

# Filter temperature deprecation/unsupported warnings for models that ignore it
warnings.filterwarnings("ignore", message=".*temperature.*")

logger = logging.getLogger(__name__)

# Global call counter and rate limiter
_live_call_count = 0
_last_call_time = 0.0
_mock_llm: Optional[Any] = None


def set_mock_llm(mock_instance: Optional[Any]) -> None:
    """Set a mock LLM for testing. If set, get_llm returns this mock."""
    global _mock_llm
    _mock_llm = mock_instance


def get_live_call_count() -> int:
    """Return total number of live LLM calls made."""
    return _live_call_count


def reset_live_call_count() -> None:
    """Reset the live call counter."""
    global _live_call_count
    _live_call_count = 0


async def enforce_rate_limit() -> None:
    """Ensure we do not exceed LLM_REQUESTS_PER_MINUTE."""
    global _last_call_time, _live_call_count, _mock_llm
    if _mock_llm is not None:
        return

    settings = get_settings()
    rpm = max(1, settings.LLM_REQUESTS_PER_MINUTE)
    interval = 60.0 / rpm

    now = time.monotonic()
    elapsed = now - _last_call_time
    if elapsed < interval:
        sleep_needed = interval - elapsed
        logger.debug(f"Rate limiting: sleeping {sleep_needed:.2f}s to respect {rpm} RPM")
        await asyncio.sleep(sleep_needed)

    _last_call_time = time.monotonic()
    _live_call_count += 1


class AllProvidersFailedError(RuntimeError):
    """Raised when primary LLM and all configured fallback providers fail."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
        super().__init__(message)
        self.original_error = original_error


def is_daily_quota_error(exc: Any) -> bool:
    """Return True if exception or response indicates daily quota exhaustion."""
    if exc is None:
        return False
    msg = str(exc).lower()
    daily_markers = (
        "per day",
        "per_day",
        "per-day",
        "daily",
        "daily_quota",
        "queries per day",
        "requests per day",
        "insufficient_quota",
        "free_tier_limit",
    )
    if any(m in msg for m in daily_markers):
        return True
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if (code == 429 or "429" in msg) and ("quota" in msg or "resource_exhausted" in msg):
        if not ("per minute" in msg or "rpm" in msg or "requests per minute" in msg):
            return True
    return False


# Patch google.genai retry handler to skip retrying on daily-quota exhaustion
try:
    from google.genai import _api_client

    _orig_retry_args = _api_client.retry_args

    def _patched_retry_args(options: Any) -> Any:
        res = _orig_retry_args(options)
        orig_retry = res.get("retry")
        if orig_retry is not None:

            def _should_retry_predicate(retry_state: Any) -> bool:
                if retry_state and retry_state.outcome:
                    exc = retry_state.outcome.exception()
                    if exc is not None and is_daily_quota_error(exc):
                        logger.warning(
                            "Daily quota exhausted for Gemini (%s); skipping retries immediately",
                            exc,
                        )
                        return False
                return orig_retry(retry_state)

            res["retry"] = _should_retry_predicate
        return res

    _api_client.retry_args = _patched_retry_args
except Exception as _patch_err:
    logger.debug("Could not patch google.genai retry args: %s", _patch_err)

# Patch openai retry handler to skip retrying on daily-quota / credit exhaustion
try:
    from openai._base_client import BaseClient

    _orig_should_retry = BaseClient._should_retry

    def _patched_should_retry(self: Any, response: Any) -> bool:
        if getattr(response, "status_code", None) == 429:
            try:
                body = response.text.lower()
                quota_markers = ("per day", "per-day", "per_day", "daily", "insufficient_quota")
                if any(m in body for m in quota_markers):
                    logger.warning(
                        "Daily quota exhausted for OpenRouter; skipping retries immediately"
                    )
                    return False
            except Exception:
                pass
        return _orig_should_retry(self, response)

    BaseClient._should_retry = _patched_should_retry
except Exception as _patch_err:
    logger.debug("Could not patch openai should_retry: %s", _patch_err)


def _model_supports_temperature(model_name: str) -> bool:
    """Return False if model is known to ignore temperature (e.g. gemini-3.5-flash-lite)."""
    m = model_name.lower()
    return not ("3.5" in m or "lite" in m or "thinking" in m)


def get_primary_llm(temperature: float = 0.0) -> BaseChatModel:
    """Build primary Gemini chat model."""
    settings = get_settings()
    model_name = settings.GOOGLE_MODEL or "gemini-3.5-flash-lite"
    kwargs: dict[str, Any] = {
        "model": model_name,
        "google_api_key": settings.GOOGLE_API_KEY,
        "max_retries": settings.LLM_MAX_RETRIES,
        "timeout": settings.LLM_REQUEST_TIMEOUT_SECONDS,
    }
    if _model_supports_temperature(model_name):
        kwargs["temperature"] = temperature
    return ChatGoogleGenerativeAI(**kwargs)


def get_fallback_google_llm(temperature: float = 0.0) -> Optional[BaseChatModel]:
    """Build secondary Gemini fallback chat model if configured."""
    settings = get_settings()
    if not settings.GOOGLE_FALLBACK_MODEL or not settings.GOOGLE_API_KEY:
        return None
    model_name = settings.GOOGLE_FALLBACK_MODEL
    kwargs: dict[str, Any] = {
        "model": model_name,
        "google_api_key": settings.GOOGLE_API_KEY,
        "max_retries": settings.LLM_MAX_RETRIES,
        "timeout": settings.LLM_REQUEST_TIMEOUT_SECONDS,
    }
    if _model_supports_temperature(model_name):
        kwargs["temperature"] = temperature
    return ChatGoogleGenerativeAI(**kwargs)


def get_openrouter_llm(temperature: float = 0.0) -> Optional[BaseChatModel]:
    """Build tertiary OpenRouter chat model if configured."""
    settings = get_settings()
    if not settings.OPENROUTER_API_KEY or not settings.OPENROUTER_MODEL:
        return None
    return ChatOpenAI(
        model=settings.OPENROUTER_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
        temperature=temperature,
        max_retries=settings.LLM_MAX_RETRIES,
        request_timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
    )


def get_llm(
    temperature: float = 0.0,
    structured_schema: Optional[Type[BaseModel]] = None,
    tools: Optional[list[Any]] = None,
) -> Any:
    """Get configured LLM with fallback chain or active mock.

    If structured_schema is provided, wraps with .with_structured_output().
    If tools are provided, binds tools with .bind_tools().
    """
    global _mock_llm
    if _mock_llm is not None:
        return _mock_llm

    primary = get_primary_llm(temperature=temperature)
    fallbacks = []

    fb_google = get_fallback_google_llm(temperature=temperature)
    if fb_google is not None:
        fallbacks.append(fb_google)

    fb_or = get_openrouter_llm(temperature=temperature)
    if fb_or is not None:
        fallbacks.append(fb_or)

    if structured_schema is not None:
        primary_structured = primary.with_structured_output(structured_schema)
        if fallbacks:
            fb_structured = [fb.with_structured_output(structured_schema) for fb in fallbacks]
            return primary_structured.with_fallbacks(fb_structured)
        return primary_structured

    if tools is not None:
        primary_tools = primary.bind_tools(tools)
        if fallbacks:
            fb_tools = [fb.bind_tools(tools) for fb in fallbacks]
            return primary_tools.with_fallbacks(fb_tools)
        return primary_tools

    if fallbacks:
        return primary.with_fallbacks(fallbacks)
    return primary
