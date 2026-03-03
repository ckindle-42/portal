"""Unified long-term memory manager for Portal."""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from portal.core.db import ConnectionPool

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MemorySnippet:
    """A memory item returned for context injection."""

    text: str
    score: float = 0.0
    source: str = "sqlite"


class MemoryManager:
    """User-scoped memory abstraction.

    Prefers Mem0 when available and enabled, and falls back to local SQLite retrieval.
    """

    # Pruning configuration
    _PRUNE_INTERVAL = 100  # prune check every N inserts

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or os.getenv("PORTAL_MEMORY_DB") or "data/memory.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.provider = os.getenv("PORTAL_MEMORY_PROVIDER", "auto").lower()
        self._max_age_days = int(os.getenv("PORTAL_MEMORY_RETENTION_DAYS", "90"))
        self._mem0 = None
        self._insert_count = 0
        self._pool = ConnectionPool(self.db_path, pragmas=("PRAGMA journal_mode=WAL",))
        self._init_db()
        self._init_provider()

    def _init_provider(self) -> None:
        if self.provider not in {"auto", "mem0", "sqlite"}:
            self.provider = "sqlite"

        if self.provider in {"auto", "mem0"}:
            try:
                from mem0 import MemoryClient  # type: ignore

                api_key = os.getenv("MEM0_API_KEY")
                if api_key:
                    self._mem0 = MemoryClient(api_key=api_key)
                    self.provider = "mem0"
                    logger.info("MemoryManager using Mem0 provider")
                    return
            except Exception as exc:  # pragma: no cover
                logger.info("Mem0 unavailable, falling back to sqlite: %s", exc)

        self.provider = "sqlite"
        logger.info("MemoryManager using sqlite provider")

    def _init_db(self) -> None:
        conn = self._pool.get()
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id, created_at DESC)"
        )
        conn.commit()

    async def add_message(self, user_id: str, content: str) -> None:
        if not content.strip():
            return
        if self.provider == "mem0" and self._mem0 is not None:
            await asyncio.to_thread(self._mem0.add, content, user_id=user_id)
            return
        await asyncio.to_thread(self._store_sqlite, user_id, content)
        # Periodic pruning: remove memories older than retention period
        self._insert_count += 1
        if self._insert_count % self._PRUNE_INTERVAL == 0:
            deleted = await asyncio.to_thread(self._prune_old_memories)
            if deleted:
                logger.info("Pruned %d old memories (>%d days)", deleted, self._max_age_days)

    def _store_sqlite(self, user_id: str, content: str) -> None:
        conn = self._pool.get()
        conn.execute("INSERT INTO memories (user_id, content) VALUES (?, ?)", (user_id, content))
        conn.commit()

    def _prune_old_memories(self) -> int:
        """Delete memories older than the retention period. Returns count deleted."""
        cutoff = (datetime.now(tz=UTC) - timedelta(days=self._max_age_days)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        conn = self._pool.get()
        cursor = conn.execute("DELETE FROM memories WHERE created_at < ?", (cutoff,))
        conn.commit()
        return cursor.rowcount

    async def retrieve(self, user_id: str, query: str, limit: int = 5) -> list[MemorySnippet]:
        if self.provider == "mem0" and self._mem0 is not None:
            try:
                result = await asyncio.to_thread(
                    self._mem0.search, query=query, user_id=user_id, limit=limit
                )
                return [
                    MemorySnippet(
                        text=item.get("memory", ""),
                        score=float(item.get("score", 0.0)),
                        source="mem0",
                    )
                    for item in result or []
                    if item.get("memory")
                ]
            except Exception as exc:  # pragma: no cover
                logger.warning("Mem0 retrieval failed: %s", exc)

        rows = await asyncio.to_thread(self._retrieve_sqlite, user_id, query, limit)
        return [MemorySnippet(text=row, source="sqlite") for row in rows]

    def _retrieve_sqlite(self, user_id: str, query: str, limit: int) -> Iterable[str]:
        like = f"%{query.strip()[:200]}%"
        conn = self._pool.get()
        cursor = conn.execute(
            """
            SELECT content
            FROM memories
            WHERE user_id = ?
            ORDER BY CASE WHEN content LIKE ? THEN 0 ELSE 1 END, created_at DESC
            LIMIT ?
            """,
            (user_id, like, limit),
        )
        return [r[0] for r in cursor.fetchall()]

    async def build_context_block(self, user_id: str, query: str) -> str:
        snippets = await self.retrieve(user_id=user_id, query=query)
        if not snippets:
            return ""
        lines = ["Relevant long-term memory:"]
        for idx, snippet in enumerate(snippets, start=1):
            lines.append(f"{idx}. {snippet.text}")
        return "\n".join(lines)

    def build_system_message(
        self,
        user_id: str,
        query: str,
        max_snippets: int = 5,
    ) -> dict[str, str] | None:
        """Build a dedicated system message for memory context.

        This method provides memory as a dedicated system message segment that can
        be injected into the conversation. Unlike build_context_block which returns
        plain text, this returns a properly formatted message dict for the LLM.

        Note: This is a synchronous wrapper. For async contexts, use build_system_message_async.

        Args:
            user_id: The user's identifier
            query: The current query to find relevant memories
            max_snippets: Maximum number of memory snippets to include

        Returns:
            A message dict with role="system" and content including memory context,
            or None if no relevant memories found.
        """
        # Use sync retrieval method
        rows = self._retrieve_sqlite(user_id, query, max_snippets)
        rows = list(rows)

        if not rows:
            return None

        lines = ["## Relevant Long-term Memory"]
        for idx, text in enumerate(rows, start=1):
            lines.append(f"{idx}. {text}")

        content = (
            "You have access to the user's long-term memory from previous conversations. "
            "Use this information to provide more personalized responses.\n\n" + "\n".join(lines)
        )

        return {"role": "system", "content": content, "name": "memory_context"}

    async def build_system_message_async(
        self,
        user_id: str,
        query: str,
        max_snippets: int = 5,
    ) -> dict[str, str] | None:
        """Async version of build_system_message.

        Args:
            user_id: The user's identifier
            query: The current query to find relevant memories
            max_snippets: Maximum number of memory snippets to include

        Returns:
            A message dict with role="system" and content including memory context,
            or None if no relevant memories found.
        """
        snippets = await self.retrieve(user_id=user_id, query=query, limit=max_snippets)

        if not snippets:
            return None

        lines = ["## Relevant Long-term Memory"]
        for idx, snippet in enumerate(snippets, start=1):
            relevance = f"(relevance: {snippet.score:.2f})" if snippet.score else ""
            lines.append(f"{idx}. {snippet.text} {relevance}")

        content = (
            "You have access to the user's long-term memory from previous conversations. "
            "Use this information to provide more personalized responses.\n\n" + "\n".join(lines)
        )

        return {"role": "system", "content": content, "name": "memory_context"}

    async def close(self) -> None:
        """Close the connection pool and release resources."""
        self._pool.close()
        logger.info("MemoryManager connection pool closed")
