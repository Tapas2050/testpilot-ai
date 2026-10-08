"""Redis client initialization and health check."""

import logging
from typing import Any, Dict, Optional

import redis.asyncio as aioredis

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: Optional[aioredis.Redis] = None


def get_redis_client() -> aioredis.Redis:
    """Return the shared async Redis client instance."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close the shared Redis client connection if open."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception:
            pass
        finally:
            _redis_client = None


async def check_redis_health() -> Dict[str, Any]:
    """Perform a live ping check against Redis for the active event loop.

    Returns health status dictionary without raising exceptions.
    """
    settings = get_settings()
    client: Optional[aioredis.Redis] = None
    try:
        client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        pong = await client.ping()
        if pong:
            return {"status": "healthy"}
        return {"status": "unhealthy", "error": "unexpected response to ping"}
    except Exception as exc:
        logger.warning(f"Redis health check failed: {exc}")
        return {
            "status": "unhealthy",
            "error": "redis connection failed",
        }
    finally:
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass
