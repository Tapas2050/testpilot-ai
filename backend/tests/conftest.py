"""Test configuration, fixtures, and database isolation for pytest."""

import asyncio
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.main import app

settings = get_settings()
test_db_url = settings.TEST_DATABASE_URL

if not test_db_url:
    raise RuntimeError("TEST_DATABASE_URL is not set in environment or .env!")

# STRICT SAFETY CHECK: Never run tests against production/development database
assert "testpilot_test" in test_db_url and not test_db_url.rstrip("/").endswith("/testpilot"), (
    f"DANGER: Tests must NEVER run against testpilot database! (Targeted: {test_db_url})"
)

test_engine = create_async_engine(
    test_db_url,
    poolclass=NullPool,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db_schema():
    """Create test schema and extensions before test session and drop after."""
    # Ensure all models are imported and registered on Base.metadata
    import app.models  # noqa: F401

    async def _setup():
        async with test_engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)

        from app.agent.checkpointer import get_checkpointer
        get_checkpointer(test_db_url).setup()

    asyncio.run(_setup())
    yield

    async def _teardown():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await test_engine.dispose()

    asyncio.run(_teardown())


@pytest.fixture(autouse=True)
async def truncate_tables():
    """Truncate all application tables between tests to ensure test isolation."""
    if Base.metadata.sorted_tables:
        async with test_engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
    yield
    if Base.metadata.sorted_tables:
        async with test_engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))


@pytest.fixture(autouse=True)
def override_db_dependency():
    """Override FastAPI get_db dependency to always use the test database."""

    async def _get_test_db() -> AsyncGenerator[AsyncSession, None]:
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a direct test database session for test setup or assertion."""
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client pointing to the FastAPI test application."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
