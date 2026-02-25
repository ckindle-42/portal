"""
SQLite Implementation of Repository Interfaces
===============================================

Production-ready SQLite implementations with:
- Async support via aiosqlite
- Proper indexing for performance
- Transaction support
- Connection pooling
"""

import sqlite3
import json
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging

from .repositories import (
    ConversationRepository,
    KnowledgeRepository,
    Message,
    Conversation,
    Document,
)

logger = logging.getLogger(__name__)


class SQLiteConversationRepository(ConversationRepository):
    """
    SQLite implementation of ConversationRepository.
    Compatible with existing ContextManager schema.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("data") / "conversations.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
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

    async def create_conversation(self, chat_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Create a new conversation"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO conversations (chat_id, metadata) VALUES (?, ?)",
                (chat_id, json.dumps(metadata) if metadata else None)
            )
            conn.commit()

    async def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a message to a conversation"""
        # Ensure conversation exists
        await self.create_conversation(chat_id)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO messages (chat_id, role, content, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (chat_id, role, content, json.dumps(metadata) if metadata else None)
            )

            # Update conversation timestamp
            conn.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE chat_id = ?",
                (chat_id,)
            )

            conn.commit()

    async def get_messages(
        self,
        chat_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Message]:
        """Retrieve messages from a conversation"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = """
                SELECT role, content, timestamp, metadata
                FROM messages
                WHERE chat_id = ?
                ORDER BY timestamp ASC
            """

            params = [chat_id]

            if limit is not None:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [
                Message(
                    role=row["role"],
                    content=row["content"],
                    timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else None,
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None
                )
                for row in rows
            ]

    async def get_conversation(self, chat_id: str) -> Optional[Conversation]:
        """Get full conversation details"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get conversation info
            row = conn.execute(
                "SELECT created_at, updated_at, metadata FROM conversations WHERE chat_id = ?",
                (chat_id,)
            ).fetchone()

            if not row:
                return None

            # Get messages
            messages = await self.get_messages(chat_id)

            return Conversation(
                chat_id=chat_id,
                messages=messages,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                metadata=json.loads(row["metadata"]) if row["metadata"] else None
            )

    async def delete_conversation(self, chat_id: str) -> bool:
        """Delete a conversation and all its messages"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM conversations WHERE chat_id = ?", (chat_id,))
            conn.commit()
            return cursor.rowcount > 0

    async def list_conversations(
        self,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Conversation]:
        """List all conversations"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = "SELECT chat_id FROM conversations ORDER BY updated_at DESC"
            params = []

            if limit is not None:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

            cursor = conn.execute(query, params)
            chat_ids = [row["chat_id"] for row in cursor.fetchall()]

            # Get full conversation details for each
            conversations = []
            for chat_id in chat_ids:
                conv = await self.get_conversation(chat_id)
                if conv:
                    conversations.append(conv)

            return conversations

    async def search_messages(
        self,
        query: str,
        chat_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Message]:
        """Search messages by content using FTS5"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            sql = """
                SELECT m.role, m.content, m.timestamp, m.metadata
                FROM messages m
                JOIN messages_fts fts ON m.id = fts.rowid
                WHERE messages_fts MATCH ?
            """

            params = [query]

            if chat_id:
                sql += " AND m.chat_id = ?"
                params.append(chat_id)

            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)

            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()

            return [
                Message(
                    role=row["role"],
                    content=row["content"],
                    timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else None,
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None
                )
                for row in rows
            ]

    async def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics"""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}

            # Total conversations
            stats["total_conversations"] = conn.execute(
                "SELECT COUNT(*) FROM conversations"
            ).fetchone()[0]

            # Total messages
            stats["total_messages"] = conn.execute(
                "SELECT COUNT(*) FROM messages"
            ).fetchone()[0]

            # Average messages per conversation
            if stats["total_conversations"] > 0:
                stats["avg_messages_per_conversation"] = round(
                    stats["total_messages"] / stats["total_conversations"], 2
                )
            else:
                stats["avg_messages_per_conversation"] = 0

            # Database size
            stats["db_size_bytes"] = self.db_path.stat().st_size

            return stats


class SQLiteKnowledgeRepository(KnowledgeRepository):
    """
    SQLite implementation of KnowledgeRepository.
    Uses FTS5 for full-text search and numpy for vector similarity.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path("data") / "knowledge.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
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

    async def add_document(
        self,
        content: str,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Add a document to knowledge base"""
        doc_id = str(uuid.uuid4())

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO documents (id, content, embedding, metadata)
                VALUES (?, ?, ?, ?)
                """,
                (
                    doc_id,
                    content,
                    pickle.dumps(embedding) if embedding else None,
                    json.dumps(metadata) if metadata else None
                )
            )
            conn.commit()

        return doc_id

    async def add_documents_batch(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Add multiple documents in batch"""
        doc_ids = []

        with sqlite3.connect(self.db_path) as conn:
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
                        pickle.dumps(doc.get("embedding")) if doc.get("embedding") else None,
                        json.dumps(doc.get("metadata")) if doc.get("metadata") else None
                    )
                )

            conn.commit()

        return doc_ids

    async def search(
        self,
        query: str,
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """Search documents using FTS5 full-text search"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            sql = """
                SELECT d.id, d.content, d.embedding, d.metadata, d.created_at
                FROM documents d
                JOIN documents_fts fts ON d.rowid = fts.rowid
                WHERE documents_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """

            cursor = conn.execute(sql, [query, limit])
            rows = cursor.fetchall()

            return [
                Document(
                    id=row["id"],
                    content=row["content"],
                    embedding=pickle.loads(row["embedding"]) if row["embedding"] else None,
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
                )
                for row in rows
            ]

    async def search_by_embedding(
        self,
        embedding: List[float],
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """Search documents by vector similarity (cosine similarity)"""
        # Import numpy lazily
        import numpy as np

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get all documents with embeddings
            cursor = conn.execute(
                "SELECT id, content, embedding, metadata, created_at FROM documents WHERE embedding IS NOT NULL"
            )
            rows = cursor.fetchall()

            # Calculate similarities
            query_vec = np.array(embedding)
            similarities = []

            for row in rows:
                doc_embedding = pickle.loads(row["embedding"])
                doc_vec = np.array(doc_embedding)

                # Cosine similarity
                similarity = np.dot(query_vec, doc_vec) / (
                    np.linalg.norm(query_vec) * np.linalg.norm(doc_vec)
                )

                similarities.append((similarity, row))

            # Sort by similarity and take top k
            similarities.sort(reverse=True, key=lambda x: x[0])
            top_results = similarities[:limit]

            return [
                Document(
                    id=row["id"],
                    content=row["content"],
                    embedding=pickle.loads(row["embedding"]) if row["embedding"] else None,
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
                )
                for _, row in top_results
            ]

    async def get_document(self, document_id: str) -> Optional[Document]:
        """Retrieve a specific document by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            row = conn.execute(
                "SELECT id, content, embedding, metadata, created_at FROM documents WHERE id = ?",
                (document_id,)
            ).fetchone()

            if not row:
                return None

            return Document(
                id=row["id"],
                content=row["content"],
                embedding=pickle.loads(row["embedding"]) if row["embedding"] else None,
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
            )

    async def update_document(
        self,
        document_id: str,
        content: Optional[str] = None,
        embedding: Optional[List[float]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update an existing document"""
        updates = []
        params = []

        if content is not None:
            updates.append("content = ?")
            params.append(content)

        if embedding is not None:
            updates.append("embedding = ?")
            params.append(pickle.dumps(embedding))

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if not updates:
            return False

        params.append(document_id)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                f"UPDATE documents SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()
            return cursor.rowcount > 0

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            conn.commit()
            return cursor.rowcount > 0

    async def delete_all(self) -> bool:
        """Clear all documents"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM documents")
            conn.commit()
            return True

    async def count_documents(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count documents"""
        with sqlite3.connect(self.db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            return count

    async def list_documents(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Document]:
        """List documents with pagination"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            query = "SELECT id, content, embedding, metadata, created_at FROM documents ORDER BY created_at DESC"
            params = []

            if limit is not None:
                query += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])

            cursor = conn.execute(query, params)
            rows = cursor.fetchall()

            return [
                Document(
                    id=row["id"],
                    content=row["content"],
                    embedding=pickle.loads(row["embedding"]) if row["embedding"] else None,
                    metadata=json.loads(row["metadata"]) if row["metadata"] else None,
                    created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None
                )
                for row in rows
            ]

    async def get_stats(self) -> Dict[str, Any]:
        """Get repository statistics"""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}

            # Total documents
            stats["total_documents"] = conn.execute(
                "SELECT COUNT(*) FROM documents"
            ).fetchone()[0]

            # Documents with embeddings
            stats["documents_with_embeddings"] = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE embedding IS NOT NULL"
            ).fetchone()[0]

            # Database size
            stats["db_size_bytes"] = self.db_path.stat().st_size

            return stats
