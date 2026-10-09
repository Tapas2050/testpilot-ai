"""Redis-backed rate limiting utilities and FastAPI dependencies."""

from uuid import UUID

from fastapi import HTTPException, Request, status

from app.core.redis import get_redis_client


async def check_rate_limit(
    key: str,
    max_requests: int,
    window_seconds: int,
    error_message: str = "Rate limit exceeded. Please try again later.",
) -> None:
    """Enforce rate limit using Redis fixed window counter with TTL.

    Args:
        key: Unique Redis key for this limit (e.g., ip, email, project)
        max_requests: Maximum allowed calls within the window
        window_seconds: Window duration in seconds
        error_message: Detail message for HTTP 429 response
    """
    redis = get_redis_client()
    try:
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, window_seconds)
        if current > max_requests:
            ttl = await redis.ttl(key)
            headers = {"Retry-After": str(max(ttl, 1))}
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_message,
                headers=headers,
            )
    except HTTPException:
        raise
    except Exception:
        # If Redis is temporarily unavailable, fail open to avoid taking down endpoints
        pass


async def rate_limit_login(request: Request) -> None:
    """Rate limit login requests: 10 attempts per minute per client IP."""
    client_ip = request.client.host if request.client else "unknown_ip"
    key = f"rate_limit:login:{client_ip}"
    await check_rate_limit(
        key=key,
        max_requests=10,
        window_seconds=60,
        error_message="Too many login attempts. Please wait a minute and try again.",
    )


async def rate_limit_create_run(request: Request, project_id: UUID) -> None:
    """Rate limit test run creation: 5 runs per 60 seconds per project."""
    key = f"rate_limit:run_create:{project_id}"
    await check_rate_limit(
        key=key,
        max_requests=5,
        window_seconds=60,
        error_message=(
            "Too many test runs created recently for this project. "
            "Please wait before creating another."
        ),
    )
