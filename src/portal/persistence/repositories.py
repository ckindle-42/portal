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


# =============================================================================
# JOB QUEUE REPOSITORY - Phase 2: Async Job Queue
# =============================================================================


class JobStatus:
    """Job execution status constants"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class JobPriority:
    """Job priority levels"""
    LOW = 0
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class Job:
    """Represents an async job"""
    id: str
    job_type: str
    parameters: dict[str, Any]
    status: str = JobStatus.PENDING
    priority: int = JobPriority.NORMAL
    created_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: Any | None = None
    error: str | None = None
    retry_count: int = 0
    max_retries: int = 3
    metadata: dict[str, Any] | None = None
    chat_id: str | None = None  # For event bus notifications
    trace_id: str | None = None  # For distributed tracing


class JobRepository(ABC):
    """
    Abstract interface for job queue persistence.

    Implementations:
    - InMemoryJobRepository: Fast in-memory queue with asyncio.Queue
    - SQLiteJobRepository: Persistent job queue with SQLite
    - RedisJobRepository: Distributed job queue with Redis
    - PostgreSQLJobRepository: Enterprise job queue with PostgreSQL
    """

    @abstractmethod
    async def enqueue(self, job: Job) -> str:
        """
        Add a job to the queue.
        Returns job ID.
        """
        pass

    @abstractmethod
    async def dequeue(self, worker_id: str) -> Job | None:
        """
        Get the next job from queue (highest priority, oldest first).
        Marks job as RUNNING and assigns to worker.
        Returns None if queue is empty.
        """
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Job | None:
        """Get job by ID"""
        pass

    @abstractmethod
    async def update_status(
        self,
        job_id: str,
        status: str,
        result: Any | None = None,
        error: str | None = None
    ) -> bool:
        """Update job status and result"""
        pass

    @abstractmethod
    async def increment_retry(self, job_id: str) -> bool:
        """Increment retry count for a job"""
        pass

    @abstractmethod
    async def list_jobs(
        self,
        status: str | None = None,
        job_type: str | None = None,
        limit: int | None = None,
        offset: int = 0
    ) -> list[Job]:
        """List jobs with optional filtering"""
        pass

    @abstractmethod
    async def count_jobs(
        self,
        status: str | None = None,
        job_type: str | None = None
    ) -> int:
        """Count jobs with optional filtering"""
        pass

    @abstractmethod
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending or running job"""
        pass

    @abstractmethod
    async def delete_job(self, job_id: str) -> bool:
        """Delete a job from the queue"""
        pass

    @abstractmethod
    async def cleanup_completed(self, older_than_hours: int = 24) -> int:
        """
        Remove completed/failed jobs older than specified hours.
        Returns count of deleted jobs.
        """
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """Get queue statistics"""
        pass

    @abstractmethod
    async def get_worker_jobs(self, worker_id: str) -> list[Job]:
        """Get all jobs assigned to a specific worker"""
        pass

    @abstractmethod
    async def requeue_stale_jobs(self, timeout_minutes: int = 30) -> int:
        """
        Requeue jobs that have been RUNNING for longer than timeout.
        This handles worker crashes.
        Returns count of requeued jobs.
        """
        pass
