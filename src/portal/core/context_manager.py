"""
Context Manager - Unified conversation history across interfaces
===============================================================

Ensures that users have consistent context whether they're using
Telegram, Web, Slack, or any other interface.
"""

import sqlite3
import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict

from .exceptions import ContextNotFoundError

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Represents a single message in conversation history"""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: str
    interface: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create from dictionary"""
        return cls(**data)


class ContextManager:
    """
    Manages conversation context with persistent storage

    Architecture:
    - Uses SQLite for reliable, concurrent access
    - Stores messages with timestamps and metadata
    - Supports context retrieval by chat_id
    - Handles context window limits
    """

    def __init__(self, db_path: Optional[Path] = None, max_context_messages: int = 50):
        """
        Initialize context manager

        Args:
            db_path: Path to SQLite database (default: data/context.db)
            max_context_messages: Maximum messages to keep in context window
        """
        self.db_path = db_path or Path("data") / "context.db"
        self.max_context_messages = max_context_messages

        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

        logger.info(f"ContextManager initialized: {self.db_path}")

    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
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

    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        interface: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add a message to conversation history

        Args:
            chat_id: Unique conversation identifier
            role: Message role ('user', 'assistant', 'system')
            content: Message content
            interface: Source interface (e.g., 'telegram', 'web')
            metadata: Additional metadata
        """
        timestamp = datetime.now().isoformat()
        metadata = metadata or {}

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO conversations (chat_id, role, content, timestamp, interface, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (chat_id, role, content, timestamp, interface, json.dumps(metadata)))
            conn.commit()

        logger.debug(f"Added {role} message to {chat_id} from {interface}")

    def get_history(
        self,
        chat_id: str,
        limit: Optional[int] = None,
        include_system: bool = True
    ) -> List[Message]:
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

        with sqlite3.connect(self.db_path) as conn:
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

        # Convert to Message objects and reverse to chronological order
        messages = []
        for row in reversed(rows):
            messages.append(Message(
                role=row['role'],
                content=row['content'],
                timestamp=row['timestamp'],
                interface=row['interface'],
                metadata=json.loads(row['metadata'])
            ))

        return messages

    def get_formatted_history(
        self,
        chat_id: str,
        limit: Optional[int] = None,
        format: str = 'openai'
    ) -> List[Dict[str, str]]:
        """
        Get history formatted for LLM APIs

        Args:
            chat_id: Conversation identifier
            limit: Maximum number of messages
            format: Format type ('openai', 'anthropic')

        Returns:
            Formatted message list
        """
        messages = self.get_history(chat_id, limit)

        if format == 'openai':
            return [{'role': msg.role, 'content': msg.content} for msg in messages]
        elif format == 'anthropic':
            # Anthropic uses different format
            formatted = []
            for msg in messages:
                formatted.append({
                    'role': 'user' if msg.role == 'user' else 'assistant',
                    'content': msg.content
                })
            return formatted
        else:
            raise ValueError(f"Unsupported format: {format}")

    def clear_history(self, chat_id: str):
        """Clear conversation history for a chat"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM conversations WHERE chat_id = ?", (chat_id,))
            conn.commit()

        logger.info(f"Cleared history for chat_id: {chat_id}")

    def get_conversation_summary(self, chat_id: str) -> Dict[str, Any]:
        """Get summary of a conversation"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            cursor = conn.execute("""
                SELECT
                    COUNT(*) as message_count,
                    MIN(timestamp) as first_message,
                    MAX(timestamp) as last_message,
                    interface
                FROM conversations
                WHERE chat_id = ?
                GROUP BY interface
            """, (chat_id,))

            rows = cursor.fetchall()

        if not rows:
            raise ContextNotFoundError(f"No conversation found for chat_id: {chat_id}")

        summary = {
            'chat_id': chat_id,
            'total_messages': sum(row['message_count'] for row in rows),
            'first_message': min(row['first_message'] for row in rows),
            'last_message': max(row['last_message'] for row in rows),
            'interfaces': [row['interface'] for row in rows]
        }

        return summary

    def cleanup_old_conversations(self, days_to_keep: int = 30):
        """Remove conversations older than specified days"""
        cutoff_date = datetime.now().timestamp() - (days_to_keep * 86400)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM conversations
                WHERE created_at < datetime(?, 'unixepoch')
            """, (cutoff_date,))

            deleted = cursor.rowcount
            conn.commit()

        logger.info(f"Cleaned up {deleted} old conversation messages")
        return deleted
