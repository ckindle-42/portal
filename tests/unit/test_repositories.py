"""Tests for portal.persistence.repositories — abstract interfaces and dataclasses"""

from datetime import datetime

import pytest

from portal.persistence.repositories import (
    Conversation,
    ConversationRepository,
    Document,
    KnowledgeRepository,
    Message,
)


class TestMessage:
    def test_defaults(self):
        msg = Message(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.timestamp is None
        assert msg.metadata is None

    def test_with_all_fields(self):
        now = datetime.now()
        msg = Message(role="assistant", content="hi", timestamp=now, metadata={"k": "v"})
        assert msg.timestamp == now
        assert msg.metadata == {"k": "v"}


class TestConversation:
    def test_fields(self):
        now = datetime.now()
        conv = Conversation(
            chat_id="c1",
            messages=[Message(role="user", content="hi")],
            created_at=now,
            updated_at=now,
        )
        assert conv.chat_id == "c1"
        assert len(conv.messages) == 1
        assert conv.metadata is None


class TestDocument:
    def test_defaults(self):
        doc = Document(id="d1", content="text")
        assert doc.id == "d1"
        assert doc.embedding is None
        assert doc.metadata is None
        assert doc.created_at is None

    def test_with_embedding(self):
        doc = Document(id="d2", content="text", embedding=[0.1, 0.2, 0.3])
        assert len(doc.embedding) == 3


class TestConversationRepositoryABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            ConversationRepository()

    @pytest.mark.asyncio
    async def test_concrete_impl(self):
        class FakeConvRepo(ConversationRepository):
            async def create_conversation(self, chat_id, metadata=None):
                pass

            async def add_message(self, chat_id, role, content, metadata=None):
                pass

            async def get_messages(self, chat_id, limit=None, offset=0):
                return []

            async def get_conversation(self, chat_id):
                return None

            async def delete_conversation(self, chat_id):
                return True

            async def list_conversations(self, limit=None, offset=0):
                return []

            async def search_messages(self, query, chat_id=None, limit=10):
                return []

            async def get_stats(self):
                return {}

        repo = FakeConvRepo()
        await repo.create_conversation("test")
        result = await repo.get_messages("test")
        assert result == []


class TestKnowledgeRepositoryABC:
    def test_cannot_instantiate(self):
        with pytest.raises(TypeError):
            KnowledgeRepository()
