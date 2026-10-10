"""Main FastAPI application entrypoint for TestPilot AI."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.projects import router as projects_router
from app.api.runs import router as runs_router
from app.core.database import engine
from app.core.logging import setup_structured_logging
from app.core.redis import close_redis

# Initialize structured logging on module load
setup_structured_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan managing startup and clean shutdown of connections."""
    try:
        from app.core.database import async_session_factory, ensure_db_schema
        from app.services.run_service import sweep_dead_runs

        await ensure_db_schema()
        async with async_session_factory() as session:
            await sweep_dead_runs(session)
    except Exception as e:
        import logging

        logging.getLogger(__name__).warning("Startup initialization failed: %s", e)
    yield
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title="TestPilot AI API",
    description="Backend API for TestPilot AI automated testing platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(documents_router)
app.include_router(runs_router)
