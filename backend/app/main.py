"""Main FastAPI application entrypoint for TestPilot AI."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.core.database import engine
from app.core.redis import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan managing startup and clean shutdown of connections."""
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

# Register health check router
app.include_router(health_router)
