"""
Knowledge Management Tools
==========================

Tools for building and querying knowledge bases.

Tools:
- SQLite Knowledge Base - Persistent, searchable knowledge storage
- Local Knowledge - RAG-based document search
"""

from .knowledge_base_sqlite import EnhancedKnowledgeTool
from .local_knowledge import LocalKnowledgeTool

__all__ = [
    'EnhancedKnowledgeTool',
    'LocalKnowledgeTool',
]
