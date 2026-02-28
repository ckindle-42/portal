"""
Context Manager - Unified conversation history across interfaces
===============================================================

Ensures that users have consistent context whether they're using
Telegram, Web, Slack, or any other interface.
"""

import asyncio
import json
import logging
import os
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from portal.core.db import ConnectionPool

logger = logging.getLogger(__name__)


@dataclass
class ContextMessage:
    """Represents a single message in conversation history"""

    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: str
    interface: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class ContextManager:
    """
    Manages conversation context with persistent storage

    Architecture:
    - Uses SQLite for reliable, concurrent access
    - Stores messages with timestamps and metadata
    - Supports context retrieval by chat_id
    - Handles context window limits
    """

    # Pruning configuration
    _PRUNE_INTERVAL = 100  # prune check every N inserts
    _MAX_AGE_DAYS = int(os.getenv("PORTAL_CONTEXT_RETENTION_DAYS", "30"))

    def __init__(self, db_path: Path | None = None, max_context_messages: int = 50) -> None:
        """
        Initialize context manager

        Args:
            db_path: Path to SQLite database (default: data/context.db)
            max_context_messages: Maximum messages to keep in context window
        """
        self.db_path = db_path or Path("data") / "context.db"
        self.max_context_messages = max_context_messages
        self._insert_count = 0

        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Thread-local connection pool (E4)
        self._pool = ConnectionPool(self.db_path)

        # Initialize database (synchronous; called from __init__)
        self._init_db()

        logger.info("ContextManager initialized: %s", self.db_path)

    def _init_db(self) -> None:
        """Initialize database schema"""
        conn = self._pool.get()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                interface TEXT NOT NULL,
                metadata TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_id
            ON conversations(chat_id, timestamp DESC)
        """)
        conn.commit()

    # ------------------------------------------------------------------
    # Private sync helpers (called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _sync_add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        interface: str,
        metadata: dict[str, Any],
    ) -> None:
        timestamp = datetime.now(tz=UTC).isoformat()
        conn = self._pool.get()
        conn.execute(
            """
            INSERT INTO conversations (chat_id, role, content, timestamp, interface, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (chat_id, role, content, timestamp, interface, json.dumps(metadata)),
        )
        conn.commit()

    def _sync_get_history(
        self,
        chat_id: str,
        limit: int,
        include_system: bool,
    ) -> list[ContextMessage]:
        conn = self._pool.get()
        conn.row_factory = sqlite3.Row

        query = """
            SELECT role, content, timestamp, interface, metadata
            FROM conversations
            WHERE chat_id = ?
        """

        if not include_system:
            query += " AND role != 'system'"

        query += " ORDER BY timestamp DESC LIMIT ?"

        cursor = conn.execute(query, (chat_id, limit))
        rows = cursor.fetchall()

        messages = []
        for row in reversed(rows):
            messages.append(
                ContextMessage(
                    role=row["role"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                    interface=row["interface"],
                    metadata=json.loads(row["metadata"]),
                )
            )
        # Reset row_factory to avoid leaking into subsequent queries
        conn.row_factory = None
        return messages

    def _sync_clear_history(self, chat_id: str) -> None:
        conn = self._pool.get()
        conn.execute("DELETE FROM conversations WHERE chat_id = ?", (chat_id,))
        conn.commit()

    def _sync_prune_old_messages(self) -> int:
        """Delete messages older than the retention period. Returns count deleted."""
        cutoff = (datetime.now(tz=UTC) - timedelta(days=self._MAX_AGE_DAYS)).isoformat()
        conn = self._pool.get()
        cursor = conn.execute("DELETE FROM conversations WHERE timestamp < ?", (cutoff,))
        conn.commit()
        return cursor.rowcount

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        interface: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add a message to conversation history

        Args:
            chat_id: Unique conversation identifier
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            interface: Source interface (e.g., 'telegram', 'web')
            metadata: Additional metadata
        """
        metadata = metadata or {}
        await asyncio.to_thread(self._sync_add_message, chat_id, role, content, interface, metadata)
        logger.debug("Added %s message to %s from %s", role, chat_id, interface)
        # Periodic pruning: remove messages older than retention period
        self._insert_count += 1
        if self._insert_count % self._PRUNE_INTERVAL == 0:
            deleted = await asyncio.to_thread(self._sync_prune_old_messages)
            if deleted:
                logger.info(
                    "Pruned %d old context messages (>%d days)", deleted, self._MAX_AGE_DAYS
                )

    async def get_history(
        self, chat_id: str, limit: int | None = None, include_system: bool = True
    ) -> list[ContextMessage]:
        """
        Retrieve conversation history

        Args:
            chat_id: Conversation identifier
            limit: Maximum number of messages (default: max_context_messages)
            include_system: Include system messages

        Returns:
            List of messages in chronological order
        """
        limit = limit or self.max_context_messages
        return await asyncio.to_thread(self._sync_get_history, chat_id, limit, include_system)

    async def get_formatted_history(
        self, chat_id: str, limit: int | None = None, format: str = "openai"
    ) -> list[dict[str, str]]:
        """
        Get history formatted for LLM APIs

        Args:
            chat_id: Conversation identifier
            limit: Maximum number of messages
            format: Format type ('openai', 'anthropic')

        Returns:
            Formatted message list
        """
        messages = await self.get_history(chat_id, limit)

        if format == "openai":
            return [{"role": msg.role, "content": msg.content} for msg in messages]
        elif format == "anthropic":
            # Anthropic handles system prompts separately; skip system messages here
            formatted = []
            for msg in messages:
                if msg.role == "system":
                    continue
                formatted.append(
                    {
                        "role": msg.role,  # preserve 'user' and 'assistant' as-is
                        "content": msg.content,
                    }
                )
            return formatted
        else:
            raise ValueError(f"Unsupported format: {format}")

    async def clear_history(self, chat_id: str) -> None:
        """Clear conversation history for a chat"""
        await asyncio.to_thread(self._sync_clear_history, chat_id)
        logger.info("Cleared history for chat_id: %s", chat_id)
