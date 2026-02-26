"""
Abstract Repository Interfaces
================================

Defines contracts for all persistence operations.
Implementations can use any backend (SQLite, PostgreSQL, Redis, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class Message:
    """Represents a conversation message"""
    role: str
    content: str
    timestamp: datetime | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class Conversation:
    """Represents a conversation thread"""
    chat_id: str
    messages: list[Message]
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] | None = None


@dataclass
class Document:
    """Represents a knowledge base document"""
    id: str
    content: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime | None = None


class ConversationRepository(ABC):
    """
    Abstract interface for conversation persistence.

    Implementations:
    - SQLiteConversationRepository: Local SQLite database
    - PostgreSQLConversationRepository: Scalable PostgreSQL
    - RedisConversationRepository: Fast in-memory cache
    """

    @abstractmethod
    async def create_conversation(self, chat_id: str, metadata: dict[str, Any] | None = None) -> None:
        """Create a new conversation"""
        pass

    @abstractmethod
    async def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """Add a message to a conversation"""
        pass

    @abstractmethod
    async def get_messages(
        self,
        chat_id: str,
        limit: int | None = None,
        offset: int = 0
    ) -> list[Message]:
        """Retrieve messages from a conversation"""
        pass

    @abstractmethod
    async def get_conversation(self, chat_id: str) -> Conversation | None:
        """Get full conversation details"""
        pass

    @abstractmethod
    async def delete_conversation(self, chat_id: str) -> bool:
        """Delete a conversation and all its messages"""
        pass

    @abstractmethod
    async def list_conversations(
        self,
        limit: int | None = None,
        offset: int = 0
    ) -> list[Conversation]:
        """List all conversations"""
        pass

    @abstractmethod
    async def search_messages(
        self,
        query: str,
        chat_id: str | None = None,
        limit: int = 10
    ) -> list[Message]:
        """Search messages by content"""
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Get repository statistics"""
        pass


class KnowledgeRepository(ABC):
    """
    Abstract interface for knowledge/vector storage.

    Implementations:
    - SQLiteKnowledgeRepository: Local SQLite with FTS5
    - PostgreSQLKnowledgeRepository: PostgreSQL with pgvector
    - PineconeKnowledgeRepository: Cloud vector database
    - WeaviateKnowledgeRepository: Semantic search engine
    """

    @abstractmethod
    async def add_document(
        self,
        content: str,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None
    ) -> str:
        """
        Add a document to knowledge base.
        Returns document ID.
        """
        pass

    @abstractmethod
    async def add_documents_batch(
        self,
        documents: list[dict[str, Any]],
    ) -> list[str]:
        """
        Add multiple documents in batch.
        Returns list of document IDs.
        """
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[Document]:
        """
        Search documents by semantic similarity and/or full-text search.
        """
        pass

    @abstractmethod
    async def search_by_embedding(
        self,
        embedding: list[float],
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[Document]:
        """
        Search documents by vector similarity.
        """
        pass

    @abstractmethod
    async def get_document(self, document_id: str) -> Document | None:
        """Retrieve a specific document by ID"""
        pass

    @abstractmethod
    async def update_document(
        self,
        document_id: str,
        content: str | None = None,
        embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Update an existing document"""
        pass

    @abstractmethod
    async def delete_document(self, document_id: str) -> bool:
        """Delete a document"""
        pass

    @abstractmethod
    async def delete_all(self) -> bool:
        """Clear all documents"""
        pass

    @abstractmethod
    async def count_documents(self, filters: dict[str, Any] | None = None) -> int:
        """Count documents, optionally filtered"""
        pass

    @abstractmethod
    async def list_documents(
        self,
        limit: int | None = None,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[Document]:
        """List documents with pagination"""
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Get repository statistics"""
        pass

