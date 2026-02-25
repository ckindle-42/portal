"""
Persistence Layer - Data Access Objects (DAO) Pattern
======================================================

Abstract interfaces for all persistence operations.
Allows swapping backends (SQLite -> PostgreSQL, etc.) without changing core logic.
"""

from .repositories import (
    ConversationRepository,
    KnowledgeRepository,
)
from .sqlite_impl import (
    SQLiteConversationRepository,
    SQLiteKnowledgeRepository,
)

__all__ = [
    "ConversationRepository",
    "KnowledgeRepository",
    "SQLiteConversationRepository",
    "SQLiteKnowledgeRepository",
]
