"""
Portal Routing System

Two-layer routing:
1. FastAPI proxy router (router.py) — sits at :8000, handles Ollama proxying,
   VRAM management, workspace virtual models, regex keyword rules.
2. Intelligent router (intelligent_router.py) — task classification and
   model selection used by Portal's own AgentCore.

Both layers use router_rules.json as the single source of routing truth.
"""

from portal.routing.execution_engine import ExecutionEngine
from portal.routing.intelligent_router import IntelligentRouter, RoutingStrategy
from portal.routing.model_backends import BaseHTTPBackend
from portal.routing.model_registry import ModelRegistry
from portal.routing.task_classifier import TaskClassifier

__all__ = [
    "BaseHTTPBackend",
    "ExecutionEngine",
    "IntelligentRouter",
    "ModelRegistry",
    "RoutingStrategy",
    "TaskClassifier",
]
