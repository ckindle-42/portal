"""
SQLite Implementation of Repository Interfaces
===============================================

Production-ready SQLite implementations with:
- Async support via asyncio.to_thread (consistent with context_manager.py)
- Proper indexing for performance
- Transaction support
- Connection pooling
"""

import asyncio
import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .repositories import (
    Conversation,
    ConversationRepository,
    Document,
    KnowledgeRepository,
    Message,
)

logger = logging.getLogger(__name__)


class _ConnectionPool:
    """Thread-local SQLite connection cache."""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._local = threading.local()

    def get(self) -> sqlite3.Connection:
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return conn

    def close_all(self):
        conn = getattr(self._local, 'conn', None)
        if conn:
            conn.close()
            self._local.conn = None


class SQLiteConversationRepository(ConversationRepository):
    """
    SQLite implementation of ConversationRepository.
    Compatible with existing ContextManager schema.
    """

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or Path("data") / "conversations.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._pool = _ConnectionPool(self.db_path)
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        conn = self._pool.get()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                chat_id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                FOREIGN KEY (chat_id) REFERENCES conversations(chat_id) ON DELETE CASCADE
            )
        """)
        # Create indices for performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)")
        # Enable full-text search on message content
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                content=messages,
                content_rowid=id
            )
        """)
        # Triggers to keep FTS in sync
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_fts_insert AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_fts_delete AFTER DELETE ON messages BEGIN
                DELETE FROM messages_fts WHERE rowid = old.id;
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_fts_update AFTER UPDATE ON messages BEGIN
                UPDATE messages_fts SET content = new.content WHERE rowid = new.id;
            END
        """)
        conn.commit()

    # ------------------------------------------------------------------
    # Private sync helpers (called via asyncio.to_thread)
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> "Message":
        """Convert a sqlite3.Row to a Message dataclass."""
        return Message(
            role=row["role"],
            content=row["content"],
            timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else None,
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
        )

    def _sync_create_conversation(self, chat_id: str, metadata: dict[str, Any] | None) -> None:
        conn = self._pool.get()
        conn.execute(
            "INSERT OR IGNORE INTO conversations (chat_id, metadata) VALUES (?, ?)",
            (chat_id, json.dumps(metadata) if metadata else None)
        )
        conn.commit()

    def _sync_add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None,
    ) -> None:
        conn = self._pool.get()
        # Ensure conversation exists
        conn.execute(
            "INSERT OR IGNORE INTO conversations (chat_id, metadata) VALUES (?, ?)",
            (chat_id, None)
        )
        conn.execute(
            """
            INSERT INTO messages (chat_id, role, content, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, role, content, json.dumps(metadata) if metadata else None)
        )
        conn.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?",
            (chat_id,)
        )
        conn.commit()

    def _sync_get_messages(
        self,
        conn: sqlite3.Connection,
        chat_id: str,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Message]:
        """Retrieve messages using an existing connection."""
        conn.row_factory = sqlite3.Row

        query = """
            SELECT role, content, timestamp, metadata
            FROM messages
            WHERE chat_id = ?
            ORDER BY timestamp ASC
        """

        params: list[Any] = [chat_id]

        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_message(row) for row in rows]

    def _sync_get_messages_standalone(
        self,
        chat_id: str,
        limit: int | None,
        offset: int,
    ) -> list[Message]:
        conn = self._pool.get()
        return self._sync_get_messages(conn, chat_id, limit, offset)

    def _sync_get_conversation(self, chat_id: str) -> Conversation | None:
        conn = self._pool.get()
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT created_at, updated_at, metadata FROM conversations WHERE chat_id = ?",
            (chat_id,)
        ).fetchone()

        if not row:
            return None

        messages = self._sync_get_messages(conn, chat_id)

        return Conversation(
            chat_id=chat_id,
            messages=messages,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else None
        )

    def _sync_delete_conversation(self, chat_id: str) -> bool:
        conn = self._pool.get()
        cursor = conn.execute("DELETE FROM conversations WHERE chat_id = ?", (chat_id,))
        conn.commit()
        return cursor.rowcount > 0

    def _sync_list_conversations(
        self,
        limit: int | None,
        offset: int,
    ) -> list[Conversation]:
        conn = self._pool.get()
        conn.row_factory = sqlite3.Row

        # Single JOIN query eliminates N+1 per-conversation message fetches.
        query = """
            SELECT c.chat_id, c.created_at, c.updated_at, c.metadata,
                   m.role AS msg_role, m.content AS msg_content,
                   m.timestamp AS msg_timestamp, m.metadata AS msg_metadata
            FROM conversations c
            LEFT JOIN messages m ON m.chat_id = c.chat_id
            ORDER BY c.updated_at DESC, m.timestamp ASC
        """
        params: list[Any] = []

        if limit is not None:
            # Use a subquery so LIMIT applies to conversations, not joined rows.
            query = """
                SELECT c.chat_id, c.created_at, c.updated_at, c.metadata,
                       m.role AS msg_role, m.content AS msg_content,
                       m.timestamp AS msg_timestamp, m.metadata AS msg_metadata
                FROM (
                    SELECT chat_id, created_at, updated_at, metadata
                    FROM conversations
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                ) c
                LEFT JOIN messages m ON m.chat_id = c.chat_id
                ORDER BY c.updated_at DESC, m.timestamp ASC
            """
            params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()

        # Group rows by chat_id preserving order.
        conversations: dict[str, Conversation] = {}
        for row in rows:
            chat_id = row["chat_id"]
            if chat_id not in conversations:
                conversations[chat_id] = Conversation(
                    chat_id=chat_id,
                    messages=[],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    updated_at=datetime.fromisoformat(row["updated_at"]),
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                )
            if row["msg_role"] is not None:
                conversations[chat_id].messages.append(Message(
                    role=row["msg_role"],
                    content=row["msg_content"],
                    timestamp=(
                        datetime.fromisoformat(row["msg_timestamp"])
                        if row["msg_timestamp"] else None
                    ),
                    metadata=(
                        json.loads(row["msg_metadata"])
                        if row["msg_metadata"] else None
                    ),
                ))
        return list(conversations.values())

    def _sync_search_messages(
        self,
        query: str,
        chat_id: str | None,
        limit: int,
    ) -> list[Message]:
        conn = self._pool.get()
        conn.row_factory = sqlite3.Row

        sql = """
            SELECT m.role, m.content, m.timestamp, m.metadata
            FROM messages m
            JOIN messages_fts fts ON m.id = fts.rowid
            WHERE messages_fts MATCH ?
        """

        params: list[Any] = [query]

        if chat_id:
            sql += " AND m.chat_id = ?"
            params.append(chat_id)

        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)

        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_message(row) for row in rows]

    def _sync_get_stats(self) -> dict[str, Any]:
        conn = self._pool.get()
        stats: dict[str, Any] = {}

        stats["total_conversations"] = conn.execute(
            "SELECT COUNT(*) FROM conversations"
        ).fetchone()[0]

        stats["total_messages"] = conn.execute(
            "SELECT COUNT(*) FROM messages"
        ).fetchone()[0]

        if stats["total_conversations"] > 0:
            stats["avg_messages_per_conversation"] = round(
                stats["total_messages"] / stats["total_conversations"], 2
            )
        else:
            stats["avg_messages_per_conversation"] = 0

        stats["db_size_bytes"] = self.db_path.stat().st_size

        return stats

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def create_conversation(self, chat_id: str, metadata: dict[str, Any] | None = None) -> None:
        """Create a new conversation"""
        await asyncio.to_thread(self._sync_create_conversation, chat_id, metadata)

    async def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """Add a message to a conversation"""
        await asyncio.to_thread(self._sync_add_message, chat_id, role, content, metadata)

    async def get_messages(
        self,
        chat_id: str,
        limit: int | None = None,
        offset: int = 0
    ) -> list[Message]:
        """Retrieve messages from a conversation"""
        return await asyncio.to_thread(self._sync_get_messages_standalone, chat_id, limit, offset)

    async def get_conversation(self, chat_id: str) -> Conversation | None:
        """Get full conversation details"""
        return await asyncio.to_thread(self._sync_get_conversation, chat_id)

    async def delete_conversation(self, chat_id: str) -> bool:
        """Delete a conversation and all its messages"""
        return await asyncio.to_thread(self._sync_delete_conversation, chat_id)

    async def list_conversations(
        self,
        limit: int | None = None,
        offset: int = 0
    ) -> list[Conversation]:
        """List all conversations"""
        return await asyncio.to_thread(self._sync_list_conversations, limit, offset)

    async def search_messages(
        self,
        query: str,
        chat_id: str | None = None,
        limit: int = 10
    ) -> list[Message]:
        """Search messages by content using FTS5"""
        return await asyncio.to_thread(self._sync_search_messages, query, chat_id, limit)

    async def get_stats(self) -> dict[str, Any]:
        """Get repository statistics"""
        return await asyncio.to_thread(self._sync_get_stats)


class SQLiteKnowledgeRepository(KnowledgeRepository):
    """
    SQLite implementation of KnowledgeRepository.
    Uses FTS5 for full-text search and numpy for vector similarity.
    """

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or Path("data") / "knowledge.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._pool = _ConnectionPool(self.db_path)
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        conn = self._pool.get()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                embedding BLOB,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # FTS5 for full-text search
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                content,
                content=documents,
                content_rowid=rowid,
                tokenize='porter unicode61'
            )
        """)
        # Triggers to keep FTS in sync
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_fts_insert AFTER INSERT ON documents BEGIN
                INSERT INTO documents_fts(rowid, content) VALUES (new.rowid, new.content);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_fts_delete AFTER DELETE ON documents BEGIN
                DELETE FROM documents_fts WHERE rowid = old.rowid;
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_fts_update AFTER UPDATE ON documents BEGIN
                UPDATE documents_fts SET content = new.content WHERE rowid = new.rowid;
            END
        """)
        # Index for metadata filtering
        conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at)")
        conn.commit()

    # ------------------------------------------------------------------
    # Private sync helpers (called via asyncio.to_thread)
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_document(row: sqlite3.Row) -> "Document":
        """Convert a sqlite3.Row to a Document dataclass."""
        return Document(
            id=row["id"],
            content=row["content"],
            embedding=json.loads(row["embedding"]) if row["embedding"] else None,
            metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )

    def _sync_add_document(
        self,
        doc_id: str,
        content: str,
        embedding: list[float] | None,
        metadata: dict[str, Any] | None,
    ) -> None:
        conn = self._pool.get()
        conn.execute(
            """
            INSERT INTO documents (id, content, embedding, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (
                doc_id,
                content,
                json.dumps(embedding) if embedding is not None else None,
                json.dumps(metadata) if metadata else None
            )
        )
        conn.commit()

    def _sync_add_documents_batch(self, documents: list[dict[str, Any]]) -> list[str]:
        doc_ids = []
        conn = self._pool.get()
        for doc in documents:
            doc_id = str(uuid.uuid4())
            doc_ids.append(doc_id)
            conn.execute(
                """
                INSERT INTO documents (id, content, embedding, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (
                    doc_id,
                    doc["content"],
                    json.dumps(doc["embedding"]) if doc.get("embedding") is not None else None,
                    json.dumps(doc["metadata"]) if doc.get("metadata") else None
                )
            )
        conn.commit()
        return doc_ids

    def _sync_search(self, query: str, limit: int) -> list[Document]:
        conn = self._pool.get()
        conn.row_factory = sqlite3.Row

        sql = """
            SELECT d.id, d.content, d.embedding, d.metadata, d.created_at
            FROM documents d
            JOIN documents_fts fts ON d.rowid = fts.rowid
            WHERE documents_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """

        rows = conn.execute(sql, [query, limit]).fetchall()
        return [self._row_to_document(row) for row in rows]

    def _sync_search_by_embedding(self, embedding: list[float], limit: int) -> list[Document]:
        import numpy as np

        conn = self._pool.get()
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            "SELECT id, content, embedding, metadata, created_at FROM documents WHERE embedding IS NOT NULL"
        )
        rows = cursor.fetchall()

        query_vec = np.array(embedding)
        similarities = []

        for row in rows:
            doc_embedding = json.loads(row["embedding"])
            doc_vec = np.array(doc_embedding)

            similarity = np.dot(query_vec, doc_vec) / (
                np.linalg.norm(query_vec) * np.linalg.norm(doc_vec)
            )

            similarities.append((similarity, row))

        similarities.sort(reverse=True, key=lambda x: x[0])
        return [self._row_to_document(row) for _, row in similarities[:limit]]

    def _sync_get_document(self, document_id: str) -> Document | None:
        conn = self._pool.get()
        conn.row_factory = sqlite3.Row

        row = conn.execute(
            "SELECT id, content, embedding, metadata, created_at FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()

        return self._row_to_document(row) if row else None

    def _sync_update_document(
        self,
        document_id: str,
        content: str | None,
        embedding: list[float] | None,
        metadata: dict[str, Any] | None,
    ) -> bool:
        updates = []
        params: list[Any] = []

        if content is not None:
            updates.append("content = ?")
            params.append(content)

        if embedding is not None:
            updates.append("embedding = ?")
            params.append(json.dumps(embedding))

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if not updates:
            return False

        params.append(document_id)

        conn = self._pool.get()
        cursor = conn.execute(
            f"UPDATE documents SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()
        return cursor.rowcount > 0

    def _sync_delete_document(self, document_id: str) -> bool:
        conn = self._pool.get()
        cursor = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        conn.commit()
        return cursor.rowcount > 0

    def _sync_delete_all(self) -> bool:
        conn = self._pool.get()
        conn.execute("DELETE FROM documents")
        conn.commit()
        return True

    def _sync_count_documents(self) -> int:
        conn = self._pool.get()
        return conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]

    def _sync_list_documents(self, limit: int | None, offset: int) -> list[Document]:
        conn = self._pool.get()
        conn.row_factory = sqlite3.Row

        query = "SELECT id, content, embedding, metadata, created_at FROM documents ORDER BY created_at DESC"
        params: list[Any] = []

        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_document(row) for row in rows]

    def _sync_get_stats(self) -> dict[str, Any]:
        conn = self._pool.get()
        stats: dict[str, Any] = {}

        stats["total_documents"] = conn.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]

        stats["documents_with_embeddings"] = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL"
        ).fetchone()[0]

        stats["db_size_bytes"] = self.db_path.stat().st_size

        return stats

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def add_document(
        self,
        content: str,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None
    ) -> str:
        """Add a document to knowledge base"""
        doc_id = str(uuid.uuid4())
        await asyncio.to_thread(self._sync_add_document, doc_id, content, embedding, metadata)
        return doc_id

    async def add_documents_batch(self, documents: list[dict[str, Any]]) -> list[str]:
        """Add multiple documents in batch"""
        return await asyncio.to_thread(self._sync_add_documents_batch, documents)

    async def search(
        self,
        query: str,
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[Document]:
        """Search documents using FTS5 full-text search"""
        return await asyncio.to_thread(self._sync_search, query, limit)

    async def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[Document]:
        """Search documents by vector similarity (cosine similarity)"""
        return await asyncio.to_thread(self._sync_search_by_embedding, embedding, limit)

    async def get_document(self, document_id: str) -> Document | None:
        """Retrieve a specific document by ID"""
        return await asyncio.to_thread(self._sync_get_document, document_id)

    async def update_document(
        self,
        document_id: str,
        content: str | None = None,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Update an existing document"""
        return await asyncio.to_thread(
            self._sync_update_document, document_id, content, embedding, metadata
        )

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document"""
        return await asyncio.to_thread(self._sync_delete_document, document_id)

    async def delete_all(self) -> bool:
        """Clear all documents"""
        return await asyncio.to_thread(self._sync_delete_all)

    async def count_documents(self, filters: dict[str, Any] | None = None) -> int:
        """Count documents"""
        return await asyncio.to_thread(self._sync_count_documents)

    async def list_documents(
        self,
        limit: int | None = None,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[Document]:
        """List documents with pagination"""
        return await asyncio.to_thread(self._sync_list_documents, limit, offset)

    async def get_stats(self) -> dict[str, Any]:
        """Get repository statistics"""
        return await asyncio.to_thread(self._sync_get_stats)
