"""Health check router reporting API, database, pgvector, and Redis statuses."""

from typing import Any, Dict

from fastapi import APIRouter

from app.core.database import check_db_health
from app.core.redis import check_redis_health

router = APIRouter(tags=["Health"])


@router.get("/health")
async def get_health() -> Dict[str, Any]:
    """Check and return health status of API, database (with pgvector), and Redis."""
    db_health = await check_db_health()
    redis_health = await check_redis_health()

    is_db_ok = db_health.get("status") == "healthy"
    is_redis_ok = redis_health.get("status") == "healthy"

    overall_status = "ok" if (is_db_ok and is_redis_ok) else "degraded"

    return {
        "status": overall_status,
        "api": "ok",
        "database": db_health,
        "redis": redis_health,
    }
