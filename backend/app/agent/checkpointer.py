"""Postgres checkpointer management for LangGraph."""

import asyncio
from typing import Any, Optional, Sequence

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

from app.core.config import get_settings


class AsyncThreadPostgresSaver(PostgresSaver):
    """PostgresSaver with thread-safe async adapters for Windows event loops."""

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return await asyncio.to_thread(self.get_tuple, config)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return await asyncio.to_thread(self.put, config, checkpoint, metadata, new_versions)

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        return await asyncio.to_thread(self.put_writes, config, writes, task_id, task_path)


_pools: dict[str, ConnectionPool] = {}


def get_connection_pool(db_url: Optional[str] = None) -> ConnectionPool:
    """Get or create a thread-safe psycopg connection pool for checkpointing."""
    settings = get_settings()
    target_url = db_url or str(settings.DATABASE_URL)
    conn_info = target_url.replace("+asyncpg", "")

    if conn_info not in _pools:
        _pools[conn_info] = ConnectionPool(
            conninfo=conn_info,
            min_size=1,
            max_size=5,
            kwargs={"autocommit": True},
        )
    return _pools[conn_info]


def get_checkpointer(db_url: Optional[str] = None) -> AsyncThreadPostgresSaver:
    """Get a LangGraph AsyncThreadPostgresSaver backed by the connection pool."""
    pool = get_connection_pool(db_url)
    return AsyncThreadPostgresSaver(pool)
