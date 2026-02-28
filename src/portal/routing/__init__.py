"""
Portal Routing System

Two independent routing layers:
1. Proxy router (router.py) — FastAPI app at :8000 that proxies Ollama.
   Uses router_rules.json for workspace virtual models and regex keyword rules.
   Serves Open WebUI / LibreChat directly.
2. Intelligent router (intelligent_router.py) — task classification and
   model selection used by Portal's AgentCore (:8081).
   Uses TaskClassifier heuristics and configurable model preferences.

Both route to the same Ollama backend but use different selection logic.
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
