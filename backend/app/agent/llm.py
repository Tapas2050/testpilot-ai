"""LLM provider interface with primary, fallback chain, rate limiting, and call tracking."""

import asyncio
import logging
import time
from typing import Any, Optional, Type

from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.core.config import get_settings

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


def get_primary_llm(temperature: float = 0.0) -> BaseChatModel:
    """Build primary Gemini chat model."""
    settings = get_settings()
    return ChatGoogleGenerativeAI(
        model=settings.GOOGLE_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=temperature,
        max_retries=settings.LLM_MAX_RETRIES,
    )


def get_fallback_google_llm(temperature: float = 0.0) -> Optional[BaseChatModel]:
    """Build secondary Gemini fallback chat model if configured."""
    settings = get_settings()
    if not settings.GOOGLE_FALLBACK_MODEL or not settings.GOOGLE_API_KEY:
        return None
    return ChatGoogleGenerativeAI(
        model=settings.GOOGLE_FALLBACK_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=temperature,
        max_retries=settings.LLM_MAX_RETRIES,
    )


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
