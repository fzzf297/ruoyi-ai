"""Checkpointer lifecycle management for the agent graph.

The persistent saver is created lazily and cached for the process lifetime.
It must be closed on shutdown to release the aiosqlite connection.
"""

import asyncio
from pathlib import Path
from typing import Optional

import aiosqlite

from app.core.config import settings
from app.graphs.checkpoint_sqlite import AsyncSqliteCheckpoint

_checkpointer: Optional[AsyncSqliteCheckpoint] = None
_lock = asyncio.Lock()


def _db_path() -> str:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///") :]
    return url


async def get_checkpointer() -> AsyncSqliteCheckpoint:
    """Return the cached AsyncSqliteCheckpoint, creating it if necessary."""
    global _checkpointer
    if _checkpointer is None:
        async with _lock:
            if _checkpointer is None:
                path = _db_path()
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                conn = await aiosqlite.connect(path)
                _checkpointer = AsyncSqliteCheckpoint(conn)
                await _checkpointer.setup()
    return _checkpointer


async def close_checkpointer() -> None:
    """Close the cached checkpointer connection, if any."""
    global _checkpointer
    if _checkpointer is not None:
        await _checkpointer.conn.close()
        _checkpointer = None
