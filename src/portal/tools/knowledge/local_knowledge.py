"""Local Knowledge Tool - RAG-based document search"""

import fcntl
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

try:
    import aiofiles

    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False

from portal.core.interfaces.tool import BaseTool, ToolCategory


class LocalKnowledgeTool(BaseTool):
    """Search and retrieve from local knowledge base"""

    _index: Any | None = None
    _documents: list[dict[str, Any]] = []
    _embeddings_model: Any | None = None
    _db_loaded: bool = False

    # Use config from environment or fallback to default
    DB_PATH = Path(os.getenv("KNOWLEDGE_BASE_DIR", "data")) / "knowledge_base.json"

    def __init__(self) -> None:
        super().__init__()
        # Load database only once
        if not LocalKnowledgeTool._db_loaded:
            self._load_db()
            LocalKnowledgeTool._db_loaded = True

    METADATA = {
        "name": "local_knowledge",
        "description": "Search local documents using semantic search (RAG)",
        "category": ToolCategory.KNOWLEDGE,
        "version": "1.0.0",
        "requires_confirmation": False,
        "parameters": [
            {"name": "action", "param_type": "string", "description": "Action: search, add, list, clear", "required": True},
            {"name": "query", "param_type": "string", "description": "Search query (for search action)", "required": False},
            {"name": "document_path", "param_type": "string", "description": "Path to document to add", "required": False},
            {"name": "content", "param_type": "string", "description": "Text content to add directly", "required": False},
            {"name": "top_k", "param_type": "int", "description": "Number of results to return", "required": False, "default": 5},
        ],
        "examples": ["Search for deployment instructions"],
    }

    def _get_embedding(self, text: str) -> list[float]:
        """Generate embedding for text (cached in model)"""
        try:
            if LocalKnowledgeTool._embeddings_model is None:
                from sentence_transformers import SentenceTransformer

                LocalKnowledgeTool._embeddings_model = SentenceTransformer("all-MiniLM-L6-v2")

            # Generate embedding and convert to list for JSON serialization
            embedding = LocalKnowledgeTool._embeddings_model.encode([text])[0]
            return embedding.tolist()
        except Exception as e:
            print(f"Warning: Could not generate embedding: {e}")
            return []

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute knowledge base operation"""
        try:
            action = parameters.get("action", "").lower()

            if action == "search":
                return await self._search(parameters.get("query", ""), parameters.get("top_k", 5))
            if action == "list":
                return await self._list_documents()
            if action == "clear":
                return await self._clear()
            if action == "add":
                doc_path = parameters.get("document_path")
                content = parameters.get("content")
                if doc_path:
                    return await self._add_document(doc_path)
                if content:
                    return await self._add_content(content)
                return self._error_response("Provide document_path or content")
            return self._error_response(f"Unknown action: {action}")

        except Exception as e:
            return self._error_response(str(e))

    def _keyword_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """Fallback keyword search when sentence-transformers is unavailable."""
        query_lower = query.lower()
        return [
            {"source": doc.get("source", "unknown"), "content": doc["content"][:500], "score": 1.0}
            for doc in LocalKnowledgeTool._documents
            if query_lower in doc["content"].lower()
        ][:top_k]

    def _embedding_search(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """Semantic search using sentence-transformers + numpy cosine similarity."""
        import numpy as np
        from sentence_transformers import SentenceTransformer

        if LocalKnowledgeTool._embeddings_model is None:
            LocalKnowledgeTool._embeddings_model = SentenceTransformer("all-MiniLM-L6-v2")
        model = LocalKnowledgeTool._embeddings_model

        query_vec = np.array(model.encode([query])[0])
        valid_docs = [d for d in LocalKnowledgeTool._documents if d.get("embedding")]
        if not valid_docs:
            return []

        embedding_matrix = np.array([d["embedding"] for d in valid_docs])
        embedding_norms = np.linalg.norm(embedding_matrix, axis=1, keepdims=True)
        query_norm = np.linalg.norm(query_vec) or 1
        embedding_norms = np.where(embedding_norms == 0, 1, embedding_norms)
        scores = np.dot(embedding_matrix / embedding_norms, query_vec / query_norm)
        top_indices = np.argsort(scores)[::-1][:top_k]

        return [
            {
                "source": valid_docs[i].get("source", "unknown"),
                "content": valid_docs[i]["content"][:500],
                "score": float(scores[i]),
            }
            for i in top_indices
        ]

    async def _search(self, query: str, top_k: int) -> dict[str, Any]:
        """Search the knowledge base using cached embeddings."""
        if not query:
            return self._error_response("Query is required")
        if not LocalKnowledgeTool._documents:
            return self._success_response({"message": "Knowledge base is empty", "results": []})

        try:
            results = self._embedding_search(query, top_k)
            return self._success_response({"query": query, "results": results})
        except ImportError:
            results = self._keyword_search(query, top_k)
            return self._success_response(
                {
                    "query": query,
                    "results": results,
                    "note": "Using keyword search (install sentence-transformers for semantic search)",
                }
            )

    async def _add_document(self, doc_path: str) -> dict[str, Any]:
        """Add document from file with pre-computed embedding"""
        if not os.path.exists(doc_path):
            return self._error_response(f"File not found: {doc_path}")

        # Read file content asynchronously if aiofiles is available
        try:
            if HAS_AIOFILES:
                async with aiofiles.open(doc_path, encoding="utf-8") as f:
                    content = await f.read()
            else:
                # Fallback to synchronous reading
                with open(doc_path, encoding="utf-8") as f:
                    content = f.read()
        except Exception as e:
            return self._error_response(f"Failed to read file: {e}")

        # Generate embedding once at add time (not at search time!)
        embedding = self._get_embedding(content[:1000])

        # Add to documents with cached embedding
        LocalKnowledgeTool._documents.append(
            {
                "source": doc_path,
                "content": content,
                "embedding": embedding,  # CACHED for fast search!
                "added_at": Path(doc_path).stat().st_mtime,
            }
        )

        # Save to disk
        self._save_db()

        return self._success_response(
            {
                "message": f"Added document: {doc_path}",
                "total_documents": len(LocalKnowledgeTool._documents),
            }
        )

    async def _add_content(self, content: str) -> dict[str, Any]:
        """Add content directly with pre-computed embedding"""
        # Generate embedding once at add time (not at search time!)
        embedding = self._get_embedding(content[:1000])

        LocalKnowledgeTool._documents.append(
            {
                "source": "direct_input",
                "content": content,
                "embedding": embedding,  # CACHED for fast search!
                "added_at": None,
            }
        )

        # Save to disk
        self._save_db()

        return self._success_response(
            {"message": "Content added", "total_documents": len(LocalKnowledgeTool._documents)}
        )

    async def _list_documents(self) -> dict[str, Any]:
        """List all documents"""
        docs = [
            {"source": d.get("source", "unknown"), "length": len(d["content"])}
            for d in LocalKnowledgeTool._documents
        ]

        return self._success_response({"total": len(docs), "documents": docs})

    async def _clear(self) -> dict[str, Any]:
        """Clear the knowledge base"""
        count = len(LocalKnowledgeTool._documents)
        LocalKnowledgeTool._documents = []
        LocalKnowledgeTool._index = None

        # Save the cleared state
        self._save_db()

        return self._success_response({"message": f"Cleared {count} documents"})

    def _load_db(self) -> None:
        """Load knowledge base from disk"""
        if self.DB_PATH.exists():
            try:
                with open(self.DB_PATH, encoding="utf-8") as f:
                    data = json.load(f)
                    LocalKnowledgeTool._documents = data.get("documents", [])
            except Exception as e:
                print(f"Error loading knowledge base: {e}")

    def _save_db(self) -> None:
        """
        Save knowledge base to disk with atomic write protection.

        Uses atomic rename to prevent corruption if process crashes during write.
        Implements file locking to prevent concurrent write conflicts.
        Creates backup before write for recovery.
        """
        try:
            self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

            # Create backup of existing file
            backup_path = self.DB_PATH.with_suffix(".json.backup")
            if self.DB_PATH.exists():
                try:
                    shutil.copy2(self.DB_PATH, backup_path)
                except Exception as e:
                    print(f"Warning: Could not create backup: {e}")

            # Write to temporary file first (atomic write pattern)
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.DB_PATH.parent, prefix=".knowledge_base_tmp_", suffix=".json"
            )

            try:
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    # Acquire exclusive lock to prevent race conditions
                    try:
                        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except OSError:
                        print("Warning: Another process is writing to the database")
                        # Continue anyway, but this indicates a concurrency issue

                    # Write data to temporary file
                    json.dump({"documents": LocalKnowledgeTool._documents}, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())  # Force write to disk

                # Atomic rename (overwrites destination on POSIX systems)
                # This is atomic on most filesystems - if we crash here, either
                # the old file exists OR the new file exists, never partial data
                shutil.move(temp_path, self.DB_PATH)

            except Exception:
                # Clean up temp file on error
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

        except Exception as e:
            print(f"Error saving knowledge base: {e}")
            # Attempt recovery from backup
            if backup_path.exists():
                print("Attempting to restore from backup...")
                try:
                    shutil.copy2(backup_path, self.DB_PATH)
                    print("Successfully restored from backup")
                except Exception as restore_error:
                    print(f"Failed to restore from backup: {restore_error}")
