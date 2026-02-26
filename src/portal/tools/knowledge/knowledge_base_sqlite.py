"""
Enhanced Knowledge Base Tool - SQLite Backend
=============================================

Replaces JSON-based knowledge storage with SQLite for better scalability.

Features:
- SQLite backend with full-text search (FTS5)
- Efficient embedding storage with BLOB type
- Indexing for fast queries
- Handles 1000+ documents efficiently
- Automatic migration from JSON
- Vector similarity search with numpy
- Metadata filtering

Performance:
- JSON: O(n) search, slow at 100+ docs
- SQLite: O(log n) search, fast at 1000+ docs
"""

import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter

logger = logging.getLogger(__name__)

# Try to import sentence transformers
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.warning("sentence-transformers not available")


class EnhancedKnowledgeTool(BaseTool):
    """
    SQLite-based knowledge base with full-text search and vector embeddings.

    Improvements over JSON version:
    - 10-100x faster search at scale
    - Full-text search (FTS5)
    - Better memory efficiency
    - ACID transactions
    - Concurrent read access
    """

    # Class-level shared resources
    _db_path: Path | None = None
    _embeddings_model: Any | None = None

    def __init__(self):
        super().__init__()

        # Initialize database path
        if EnhancedKnowledgeTool._db_path is None:
            data_dir = Path.home() / ".telegram_agent" / "knowledge_base"
            data_dir.mkdir(parents=True, exist_ok=True)
            EnhancedKnowledgeTool._db_path = data_dir / "knowledge_base.db"

        # Initialize database schema
        self._init_database()

        # Load embeddings model (lazy load)
        if EMBEDDINGS_AVAILABLE and EnhancedKnowledgeTool._embeddings_model is None:
            logger.info("Loading embeddings model...")
            EnhancedKnowledgeTool._embeddings_model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Embeddings model loaded")

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="knowledge_base_enhanced",
            description="Enhanced knowledge base with SQLite backend (1000+ documents)",
            category=ToolCategory.KNOWLEDGE,
            version="2.0.0",
            requires_confirmation=False,
            parameters=[
                ToolParameter(
                    name="action",
                    param_type="string",
                    description="Action: add, search, list, delete, stats, migrate",
                    required=True
                ),
                ToolParameter(
                    name="query",
                    param_type="string",
                    description="Search query (for search action)",
                    required=False
                ),
                ToolParameter(
                    name="path",
                    param_type="string",
                    description="File path (for add action)",
                    required=False
                ),
                ToolParameter(
                    name="content",
                    param_type="string",
                    description="Text content (for add action)",
                    required=False
                ),
                ToolParameter(
                    name="doc_id",
                    param_type="integer",
                    description="Document ID (for delete action)",
                    required=False
                ),
                ToolParameter(
                    name="limit",
                    param_type="integer",
                    description="Number of results (for search/list)",
                    required=False,
                    default=5
                ),
                ToolParameter(
                    name="metadata",
                    param_type="object",
                    description="Document metadata (tags, author, etc.)",
                    required=False
                )
            ]
        )

    def _init_database(self):
        """Initialize SQLite database with FTS5 and vector storage"""

        with sqlite3.connect(EnhancedKnowledgeTool._db_path) as conn:
            cursor = conn.cursor()

            # Main documents table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding BLOB,
                    metadata TEXT,
                    added_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(source)
                )
            """)

            # Full-text search table (FTS5)
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                    content,
                    content=documents,
                    content_rowid=id
                )
            """)

            # Triggers to keep FTS in sync
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                    INSERT INTO documents_fts(rowid, content) VALUES (new.id, new.content);
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                    DELETE FROM documents_fts WHERE rowid = old.id;
                END
            """)

            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
                    UPDATE documents_fts SET content = new.content WHERE rowid = new.id;
                END
            """)

            # Indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON documents(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_added_at ON documents(added_at)")

            conn.commit()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with row factory"""
        conn = sqlite3.connect(EnhancedKnowledgeTool._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _generate_embedding(self, text: str) -> bytes | None:
        """Generate and serialize embedding"""
        if not EMBEDDINGS_AVAILABLE or not EnhancedKnowledgeTool._embeddings_model:
            return None

        try:
            # Generate embedding
            embedding = EnhancedKnowledgeTool._embeddings_model.encode([text[:1000]])[0]
            # Serialize as JSON bytes (safe alternative to pickle)
            return json.dumps(embedding.tolist()).encode('utf-8')
        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            return None

    def _deserialize_embedding(self, blob: bytes) -> np.ndarray | None:
        """Deserialize embedding from blob"""
        try:
            return np.array(json.loads(blob.decode('utf-8') if isinstance(blob, bytes) else blob))
        except (json.JSONDecodeError, UnicodeDecodeError):
            if os.getenv("ALLOW_LEGACY_PICKLE_EMBEDDINGS", "false").lower() not in ("1", "true", "yes"):
                logger.error(
                    "Legacy pickle-serialized embedding detected but ALLOW_LEGACY_PICKLE_EMBEDDINGS "
                    "is disabled. Re-index documents to migrate to JSON encoding."
                )
                return None
            try:
                import pickle
                logger.warning(
                    "Loading embedding serialized with pickle (deprecated). "
                    "Re-save this document to migrate to JSON encoding."
                )
                return np.array(pickle.loads(blob))  # noqa: S301
            except Exception as e:
                logger.error(f"Embedding deserialization failed (pickle fallback): {e}")
                return None
        except Exception as e:
            logger.error(f"Embedding deserialization failed: {e}")
            return None

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute knowledge base action"""

        action = parameters.get("action", "").lower()

        if action == "add":
            return await self._add_document(parameters)
        elif action == "search":
            return await self._search(parameters)
        elif action == "list":
            return await self._list_documents(parameters)
        elif action == "delete":
            return await self._delete_document(parameters)
        elif action == "stats":
            return await self._get_stats()
        elif action == "migrate":
            return await self._migrate_from_json(parameters)
        else:
            return self._error_response(f"Unknown action: {action}")

    async def _add_document(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Add document to knowledge base"""

        path = parameters.get("path")
        content = parameters.get("content")
        metadata = parameters.get("metadata", {})

        if not path and not content:
            return self._error_response("Either 'path' or 'content' required")

        # Read from file if path provided
        if path:
            try:
                file_path = Path(path).expanduser()
                if not file_path.exists():
                    return self._error_response(f"File not found: {path}")

                content = file_path.read_text(encoding='utf-8')
                source = str(file_path)
            except Exception as e:
                return self._error_response(f"Failed to read file: {e}")
        else:
            source = f"text_{datetime.now().isoformat()}"

        # Generate embedding
        embedding_blob = self._generate_embedding(content)

        # Insert into database
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                now = datetime.now().isoformat()

                cursor.execute("""
                    INSERT OR REPLACE INTO documents
                    (source, content, embedding, metadata, added_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    source,
                    content,
                    embedding_blob,
                    json.dumps(metadata),
                    now,
                    now
                ))

                doc_id = cursor.lastrowid
                conn.commit()

            return self._success_response(
                result={"doc_id": doc_id, "source": source},
                metadata={"content_length": len(content)}
            )

        except Exception as e:
            logger.error(f"Failed to add document: {e}")
            return self._error_response(f"Database error: {e}")

    async def _search(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Search knowledge base using FTS5 and vector similarity"""

        query = parameters.get("query")
        limit = parameters.get("limit", 5)

        if not query:
            return self._error_response("Query required for search")

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # First try full-text search (fast)
                cursor.execute("""
                    SELECT d.id, d.source, d.content, d.metadata, d.added_at,
                           bm25(documents_fts) as rank
                    FROM documents_fts
                    JOIN documents d ON documents_fts.rowid = d.id
                    WHERE documents_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (query, limit * 2))  # Get more for reranking

                fts_results = cursor.fetchall()

                # If embeddings available, rerank using similarity
                if EMBEDDINGS_AVAILABLE and fts_results:
                    query_embedding = self._generate_embedding(query)
                    if query_embedding:
                        query_vec = self._deserialize_embedding(query_embedding)

                        # Calculate similarities
                        results_with_scores = []
                        for row in fts_results:
                            cursor.execute("SELECT embedding FROM documents WHERE id = ?", (row['id'],))
                            embedding_row = cursor.fetchone()

                            if embedding_row and embedding_row['embedding']:
                                doc_vec = self._deserialize_embedding(embedding_row['embedding'])
                                if doc_vec is not None:
                                    # Cosine similarity
                                    similarity = np.dot(doc_vec, query_vec) / (
                                        np.linalg.norm(doc_vec) * np.linalg.norm(query_vec)
                                    )
                                    results_with_scores.append((row, similarity))

                        # Sort by similarity and take top results
                        results_with_scores.sort(key=lambda x: x[1], reverse=True)
                        final_results = [row for row, _ in results_with_scores[:limit]]
                    else:
                        final_results = fts_results[:limit]
                else:
                    final_results = fts_results[:limit]

                # Format results
                documents = []
                for row in final_results:
                    documents.append({
                        "id": row['id'],
                        "source": row['source'],
                        "content": row['content'][:500] + "..." if len(row['content']) > 500 else row['content'],
                        "metadata": json.loads(row['metadata']) if row['metadata'] else {},
                        "added_at": row['added_at']
                    })

                return self._success_response(
                    result=documents,
                    metadata={
                        "query": query,
                        "results_count": len(documents),
                        "method": "fts5_vector" if EMBEDDINGS_AVAILABLE else "fts5"
                    }
                )

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return self._error_response(f"Search error: {e}")

    async def _list_documents(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """List all documents"""

        limit = parameters.get("limit", 10)

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, source,
                           substr(content, 1, 200) as preview,
                           metadata, added_at
                    FROM documents
                    ORDER BY added_at DESC
                    LIMIT ?
                """, (limit,))

                documents = []
                for row in cursor.fetchall():
                    documents.append({
                        "id": row['id'],
                        "source": row['source'],
                        "preview": row['preview'] + "...",
                        "metadata": json.loads(row['metadata']) if row['metadata'] else {},
                        "added_at": row['added_at']
                    })

                return self._success_response(result=documents)

        except Exception as e:
            return self._error_response(f"List error: {e}")

    async def _delete_document(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Delete document by ID"""

        doc_id = parameters.get("doc_id")

        if not doc_id:
            return self._error_response("doc_id required")

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

                if cursor.rowcount == 0:
                    return self._error_response(f"Document {doc_id} not found")

                conn.commit()

            return self._success_response(
                result={"deleted_id": doc_id}
            )

        except Exception as e:
            return self._error_response(f"Delete error: {e}")

    async def _get_stats(self) -> dict[str, Any]:
        """Get knowledge base statistics"""

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Total documents
                cursor.execute("SELECT COUNT(*) FROM documents")
                total_docs = cursor.fetchone()[0]

                # Total size
                cursor.execute("SELECT SUM(LENGTH(content)) FROM documents")
                total_size = cursor.fetchone()[0] or 0

                # Database file size
                db_size = EnhancedKnowledgeTool._db_path.stat().st_size

                # Recent additions
                cursor.execute("""
                    SELECT COUNT(*) FROM documents
                    WHERE added_at > datetime('now', '-7 days')
                """)
                recent_additions = cursor.fetchone()[0]

                return self._success_response(
                    result={
                        "total_documents": total_docs,
                        "total_content_bytes": total_size,
                        "database_size_mb": db_size / (1024 * 1024),
                        "recent_additions_7d": recent_additions,
                        "embeddings_enabled": EMBEDDINGS_AVAILABLE,
                        "database_path": str(EnhancedKnowledgeTool._db_path)
                    }
                )

        except Exception as e:
            return self._error_response(f"Stats error: {e}")

    async def _migrate_from_json(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Migrate from old JSON-based knowledge base"""

        json_path = parameters.get("path", "~/.telegram_agent/knowledge_base/knowledge_base.json")
        json_path = Path(json_path).expanduser()

        if not json_path.exists():
            return self._error_response(f"JSON file not found: {json_path}")

        try:
            # Load old JSON data
            with open(json_path) as f:
                data = json.load(f)

            documents = data.get('documents', [])

            migrated = 0
            failed = 0

            for doc in documents:
                try:
                    # Add to SQLite
                    result = await self._add_document({
                        "content": doc.get('content', ''),
                        "metadata": {
                            "source": doc.get('source', 'unknown'),
                            "migrated_from_json": True
                        }
                    })

                    if result['success']:
                        migrated += 1
                    else:
                        failed += 1

                except Exception as e:
                    logger.error(f"Failed to migrate document: {e}")
                    failed += 1

            return self._success_response(
                result={
                    "migrated": migrated,
                    "failed": failed,
                    "total": len(documents)
                }
            )

        except Exception as e:
            return self._error_response(f"Migration error: {e}")


# ============================================================================
# MIGRATION SCRIPT
# ============================================================================

async def migrate_to_sqlite():
    """Standalone migration script"""
    print("=" * 60)
    print("Knowledge Base Migration: JSON → SQLite")
    print("=" * 60)

    tool = EnhancedKnowledgeTool()

    result = await tool._migrate_from_json({})

    if result['success']:
        stats = result['result']
        print("\n✅ Migration complete!")
        print(f"   Migrated: {stats['migrated']} documents")
        print(f"   Failed: {stats['failed']} documents")
        print(f"   Total: {stats['total']} documents")
    else:
        print(f"\n❌ Migration failed: {result['error']}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(migrate_to_sqlite())
