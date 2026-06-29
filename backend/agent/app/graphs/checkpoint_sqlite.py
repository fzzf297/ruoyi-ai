"""Persistent SQLite checkpointer for LangGraph.

Subclasses AsyncSqliteSaver to work around aiosqlite 0.22.1 missing
``is_alive()``, which causes the upstream ``setup()`` method to fail.
"""

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver


class AsyncSqliteCheckpoint(AsyncSqliteSaver):
    """Async SQLite checkpoint saver compatible with current aiosqlite."""

    async def setup(self) -> None:
        """Create checkpoints/writes tables without calling ``is_alive()``."""
        if self.is_setup:
            return
        async with self.lock:
            if self.is_setup:
                return
            async with self.conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS checkpoints (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL DEFAULT '',
                    checkpoint_id TEXT NOT NULL,
                    parent_checkpoint_id TEXT,
                    type TEXT,
                    checkpoint BLOB,
                    metadata BLOB,
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
                );
                CREATE TABLE IF NOT EXISTS writes (
                    thread_id TEXT NOT NULL,
                    checkpoint_ns TEXT NOT NULL DEFAULT '',
                    checkpoint_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    idx INTEGER NOT NULL,
                    channel TEXT NOT NULL,
                    type TEXT,
                    value BLOB,
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
                );
                """
            ):
                await self.conn.commit()
            self.is_setup = True
