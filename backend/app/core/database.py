"""Database connectivity, async SQLAlchemy engine, session factory, and health check."""

import logging
from typing import Any, AsyncGenerator, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy declarative models."""

    pass


settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

_session_factories: dict[str, async_sessionmaker[AsyncSession]] = {}


def get_async_session_factory(db_url: Optional[str] = None) -> async_sessionmaker[AsyncSession]:
    """Get or create an async sessionmaker for the given database URL."""
    import os

    is_test = bool(os.getenv("PYTEST_CURRENT_TEST"))
    test_db = getattr(settings, "TEST_DATABASE_URL", None)
    if not db_url and is_test and test_db:
        target_url = str(test_db)
    else:
        target_url = str(db_url or settings.DATABASE_URL)
    if target_url not in _session_factories:
        eng = create_async_engine(target_url, poolclass=NullPool, echo=False)
        _session_factories[target_url] = async_sessionmaker(
            bind=eng, class_=AsyncSession, expire_on_commit=False
        )
    return _session_factories[target_url]


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async SQLAlchemy session."""
    async with async_session_factory() as session:
        yield session


async def check_db_health() -> Dict[str, Any]:
    """Check live connection to PostgreSQL and verify whether pgvector extension is enabled.

    Returns health status dictionary without raising exceptions.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            res = await conn.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            row = res.fetchone()
            vector_enabled = row is not None
            return {
                "status": "healthy",
                "pgvector_enabled": vector_enabled,
            }
    except Exception as exc:
        logger.warning(f"Database health check failed: {exc}")
        return {
            "status": "unhealthy",
            "pgvector_enabled": False,
            "error": "database connection failed",
        }


async def ensure_db_schema(target_engine: Optional[Any] = None) -> None:
    """Ensure database schema has required columns for non-Alembic setup."""
    eng = target_engine or engine
    try:
        async with eng.begin() as conn:
            await conn.execute(
                text("ALTER TABLE test_runs ADD COLUMN IF NOT EXISTS failed_stage VARCHAR(32);")
            )
            await conn.execute(
                text(
                    "ALTER TABLE test_results "
                    "ADD COLUMN IF NOT EXISTS failure_screenshot_path VARCHAR(512);"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE test_results "
                    "ADD COLUMN IF NOT EXISTS screenshot_error VARCHAR(512);"
                )
            )
    except Exception as exc:
        logger.warning("ensure_db_schema warning: %s", exc)
