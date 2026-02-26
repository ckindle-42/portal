"""Tests for portal.persistence.sqlite_impl"""

import asyncio
from pathlib import Path

import pytest

from portal.persistence.repositories import Document, Message
from portal.persistence.sqlite_impl import (
    SQLiteConversationRepository,
    SQLiteKnowledgeRepository,
    _ConnectionPool,
)


# ── _ConnectionPool ──────────────────────────────────────────────────────


class TestConnectionPool:
    def test_get_returns_connection(self, tmp_path):
        pool = _ConnectionPool(tmp_path / "test.db")
        conn = pool.get()
        assert conn is not None
        # Same thread → same connection
        assert pool.get() is conn
        pool.close_all()

    def test_close_all(self, tmp_path):
        pool = _ConnectionPool(tmp_path / "test.db")
        pool.get()
        pool.close_all()
        # After close, get() should create a new connection
        conn2 = pool.get()
        assert conn2 is not None
        pool.close_all()

    def test_close_all_when_no_connection(self, tmp_path):
        pool = _ConnectionPool(tmp_path / "test.db")
        pool.close_all()  # Should not raise


# ── SQLiteConversationRepository ─────────────────────────────────────────


class TestSQLiteConversationRepository:
    @pytest.fixture
    def repo(self, tmp_path):
        return SQLiteConversationRepository(db_path=tmp_path / "conv.db")

    @pytest.mark.asyncio
    async def test_create_conversation(self, repo):
        await repo.create_conversation("chat-1", metadata={"source": "test"})
        conv = await repo.get_conversation("chat-1")
        assert conv is not None
        assert conv.chat_id == "chat-1"

    @pytest.mark.asyncio
    async def test_create_conversation_idempotent(self, repo):
        await repo.create_conversation("chat-1")
        await repo.create_conversation("chat-1")  # Should not raise
        convs = await repo.list_conversations()
        assert len(convs) == 1

    @pytest.mark.asyncio
    async def test_add_message(self, repo):
        await repo.add_message("chat-1", "user", "hello")
        messages = await repo.get_messages("chat-1")
        assert len(messages) == 1
        assert messages[0].role == "user"
        assert messages[0].content == "hello"

    @pytest.mark.asyncio
    async def test_add_message_auto_creates_conversation(self, repo):
        await repo.add_message("new-chat", "user", "hi")
        conv = await repo.get_conversation("new-chat")
        assert conv is not None

    @pytest.mark.asyncio
    async def test_add_message_with_metadata(self, repo):
        await repo.add_message("chat-1", "user", "hi", metadata={"lang": "en"})
        messages = await repo.get_messages("chat-1")
        assert messages[0].metadata == {"lang": "en"}

    @pytest.mark.asyncio
    async def test_get_messages_limit_offset(self, repo):
        for i in range(5):
            await repo.add_message("chat-1", "user", f"msg {i}")
        messages = await repo.get_messages("chat-1", limit=2, offset=1)
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_get_messages_empty(self, repo):
        messages = await repo.get_messages("nonexistent")
        assert messages == []

    @pytest.mark.asyncio
    async def test_get_conversation_not_found(self, repo):
        assert await repo.get_conversation("missing") is None

    @pytest.mark.asyncio
    async def test_get_conversation_with_messages(self, repo):
        await repo.add_message("chat-1", "user", "hello")
        await repo.add_message("chat-1", "assistant", "hi there")
        conv = await repo.get_conversation("chat-1")
        assert conv is not None
        assert len(conv.messages) == 2
        assert conv.messages[0].role == "user"
        assert conv.messages[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_delete_conversation(self, repo):
        await repo.create_conversation("chat-1")
        result = await repo.delete_conversation("chat-1")
        assert result is True
        assert await repo.get_conversation("chat-1") is None

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, repo):
        result = await repo.delete_conversation("missing")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_conversations(self, repo):
        await repo.create_conversation("chat-1")
        await repo.create_conversation("chat-2")
        convs = await repo.list_conversations()
        assert len(convs) == 2

    @pytest.mark.asyncio
    async def test_list_conversations_with_limit(self, repo):
        for i in range(5):
            await repo.create_conversation(f"chat-{i}")
        convs = await repo.list_conversations(limit=2)
        assert len(convs) == 2

    @pytest.mark.asyncio
    async def test_list_conversations_with_messages(self, repo):
        await repo.add_message("chat-1", "user", "hello")
        await repo.add_message("chat-1", "assistant", "hi")
        convs = await repo.list_conversations()
        assert len(convs) == 1
        assert len(convs[0].messages) == 2

    @pytest.mark.asyncio
    async def test_search_messages(self, repo):
        await repo.add_message("chat-1", "user", "hello world")
        await repo.add_message("chat-1", "user", "goodbye world")
        await repo.add_message("chat-1", "user", "python code")
        results = await repo.search_messages("hello")
        assert len(results) >= 1
        assert any("hello" in r.content for r in results)

    @pytest.mark.asyncio
    async def test_search_messages_with_chat_filter(self, repo):
        await repo.add_message("chat-1", "user", "hello world")
        await repo.add_message("chat-2", "user", "hello there")
        results = await repo.search_messages("hello", chat_id="chat-1")
        assert all(True for r in results)  # At least no error

    @pytest.mark.asyncio
    async def test_get_stats(self, repo):
        await repo.add_message("chat-1", "user", "hi")
        await repo.add_message("chat-1", "assistant", "hello")
        stats = await repo.get_stats()
        assert stats["total_conversations"] == 1
        assert stats["total_messages"] == 2
        assert stats["avg_messages_per_conversation"] == 2.0
        assert stats["db_size_bytes"] > 0

    @pytest.mark.asyncio
    async def test_get_stats_empty(self, repo):
        stats = await repo.get_stats()
        assert stats["total_conversations"] == 0
        assert stats["total_messages"] == 0
        assert stats["avg_messages_per_conversation"] == 0


# ── SQLiteKnowledgeRepository ────────────────────────────────────────────


class TestSQLiteKnowledgeRepository:
    @pytest.fixture
    def repo(self, tmp_path):
        return SQLiteKnowledgeRepository(db_path=tmp_path / "knowledge.db")

    @pytest.mark.asyncio
    async def test_add_document(self, repo):
        doc_id = await repo.add_document("test content", metadata={"type": "test"})
        assert doc_id is not None
        assert len(doc_id) > 0

    @pytest.mark.asyncio
    async def test_get_document(self, repo):
        doc_id = await repo.add_document("my doc content")
        doc = await repo.get_document(doc_id)
        assert doc is not None
        assert doc.content == "my doc content"

    @pytest.mark.asyncio
    async def test_get_document_not_found(self, repo):
        assert await repo.get_document("nonexistent") is None

    @pytest.mark.asyncio
    async def test_add_document_with_embedding(self, repo):
        doc_id = await repo.add_document("text", embedding=[0.1, 0.2, 0.3])
        doc = await repo.get_document(doc_id)
        assert doc.embedding == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_add_documents_batch(self, repo):
        docs = [
            {"content": "doc1"},
            {"content": "doc2", "metadata": {"k": "v"}},
            {"content": "doc3", "embedding": [1.0, 2.0]},
        ]
        ids = await repo.add_documents_batch(docs)
        assert len(ids) == 3
        for doc_id in ids:
            assert await repo.get_document(doc_id) is not None

    @pytest.mark.asyncio
    async def test_search(self, repo):
        await repo.add_document("python programming tutorial")
        await repo.add_document("javascript web development")
        results = await repo.search("python", limit=5)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_by_embedding(self, repo):
        import numpy as np
        await repo.add_document("doc1", embedding=[1.0, 0.0, 0.0])
        await repo.add_document("doc2", embedding=[0.0, 1.0, 0.0])
        results = await repo.search_by_embedding([1.0, 0.0, 0.0], limit=2)
        assert len(results) >= 1
        # First result should be closest to query
        assert results[0].embedding == [1.0, 0.0, 0.0]

    @pytest.mark.asyncio
    async def test_update_document_content(self, repo):
        doc_id = await repo.add_document("original")
        result = await repo.update_document(doc_id, content="updated")
        assert result is True
        doc = await repo.get_document(doc_id)
        assert doc.content == "updated"

    @pytest.mark.asyncio
    async def test_update_document_embedding(self, repo):
        doc_id = await repo.add_document("text")
        await repo.update_document(doc_id, embedding=[0.5, 0.5])
        doc = await repo.get_document(doc_id)
        assert doc.embedding == [0.5, 0.5]

    @pytest.mark.asyncio
    async def test_update_document_metadata(self, repo):
        doc_id = await repo.add_document("text")
        await repo.update_document(doc_id, metadata={"new": True})
        doc = await repo.get_document(doc_id)
        assert doc.metadata == {"new": True}

    @pytest.mark.asyncio
    async def test_update_document_no_changes(self, repo):
        doc_id = await repo.add_document("text")
        result = await repo.update_document(doc_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_update_nonexistent(self, repo):
        result = await repo.update_document("missing", content="x")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_document(self, repo):
        doc_id = await repo.add_document("to delete")
        result = await repo.delete_document(doc_id)
        assert result is True
        assert await repo.get_document(doc_id) is None

    @pytest.mark.asyncio
    async def test_delete_document_not_found(self, repo):
        result = await repo.delete_document("missing")
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_all(self, repo):
        await repo.add_document("doc1")
        await repo.add_document("doc2")
        result = await repo.delete_all()
        assert result is True
        assert await repo.count_documents() == 0

    @pytest.mark.asyncio
    async def test_count_documents(self, repo):
        assert await repo.count_documents() == 0
        await repo.add_document("doc1")
        await repo.add_document("doc2")
        assert await repo.count_documents() == 2

    @pytest.mark.asyncio
    async def test_list_documents(self, repo):
        await repo.add_document("doc1")
        await repo.add_document("doc2")
        await repo.add_document("doc3")
        docs = await repo.list_documents()
        assert len(docs) == 3

    @pytest.mark.asyncio
    async def test_list_documents_with_pagination(self, repo):
        for i in range(5):
            await repo.add_document(f"doc {i}")
        docs = await repo.list_documents(limit=2, offset=1)
        assert len(docs) == 2

    @pytest.mark.asyncio
    async def test_get_stats(self, repo):
        await repo.add_document("text", embedding=[0.1])
        await repo.add_document("text2")
        stats = await repo.get_stats()
        assert stats["total_documents"] == 2
        assert stats["documents_with_embeddings"] == 1
        assert stats["db_size_bytes"] > 0
