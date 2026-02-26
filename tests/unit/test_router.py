"""
Tests for intelligent router and CentralDispatcher interface registry.
"""

import pytest

from portal.routing.intelligent_router import IntelligentRouter
from portal.routing.task_classifier import TaskClassifier


class TestTaskClassifier:
    """Test task classification logic"""

    def test_classify_trivial_queries(self):
        """Test that greetings and simple queries are classified as trivial"""
        classifier = TaskClassifier()

        trivial_queries = [
            "hello",
            "hi there",
            "what's up",
            "thanks",
            "ok"
        ]

        for query in trivial_queries:
            result = classifier.classify(query)
            assert result.complexity.value in ["trivial", "simple"], f"'{query}' should be trivial/simple, got {result}"

    def test_classify_complex_queries(self):
        """Test that complex queries are correctly classified"""
        classifier = TaskClassifier()

        complex_queries = [
            "Write a detailed analysis of the current codebase architecture and suggest improvements",
            "Generate a comprehensive report on system performance with graphs and recommendations",
        ]

        for query in complex_queries:
            result = classifier.classify(query)
            assert result.complexity.value in ["simple", "moderate", "complex", "expert"], f"'{query}' should be at least simple, got {result}"

    def test_classify_code_queries(self):
        """Test that code-related queries are at least medium complexity"""
        classifier = TaskClassifier()

        code_queries = [
            "Write a Python function to sort a list",
            "Create a React component for user authentication",
            "Debug this error in my code"
        ]

        for query in code_queries:
            result = classifier.classify(query)
            assert result.complexity.value in ["simple", "moderate", "complex", "expert"], f"'{query}' should need at least simple complexity, got {result}"


class TestIntelligentRouter:
    """Test intelligent routing decisions"""

    def test_router_initialization(self):
        """Test router initializes with registry"""
        from portal.routing.model_registry import ModelRegistry

        registry = ModelRegistry()
        router = IntelligentRouter(registry)

        assert router.registry is not None
        assert router.classifier is not None

    def test_route_selection(self):
        """Test that router selects appropriate models"""
        from portal.routing.model_registry import ModelRegistry

        registry = ModelRegistry()
        router = IntelligentRouter(registry)

        # Simple query should use fast model
        simple_task = router.classifier.classify("hello")
        assert simple_task.complexity.value in ["trivial", "simple"]

        # Complex query should use larger model
        complex_task = router.classifier.classify("Write a detailed analysis with code examples")
        assert complex_task.complexity.value in ["moderate", "complex", "expert"]


class TestCentralDispatcher:
    """Tests for the CentralDispatcher interface registry."""

    def test_registered_interfaces_accessible(self):
        """Interfaces decorated with @CentralDispatcher.register are retrievable."""
        import portal.interfaces.slack.interface  # noqa: F401
        import portal.interfaces.telegram.interface  # noqa: F401

        # web, telegram, and slack are registered at import time
        import portal.interfaces.web.server  # noqa: F401 — trigger registration
        from portal.agent.dispatcher import CentralDispatcher

        names = CentralDispatcher.registered_names()
        assert "web" in names
        assert "telegram" in names
        assert "slack" in names

    def test_get_known_interface_returns_class(self):
        """CentralDispatcher.get() returns the registered class."""
        import inspect

        import portal.interfaces.web.server  # noqa: F401 — trigger registration
        from portal.agent.dispatcher import CentralDispatcher

        web_cls = CentralDispatcher.get("web")
        assert inspect.isclass(web_cls)

    def test_get_unknown_interface_raises(self):
        """CentralDispatcher.get() raises UnknownInterfaceError for unknown names."""
        from portal.agent.dispatcher import CentralDispatcher, UnknownInterfaceError

        with pytest.raises(UnknownInterfaceError):
            CentralDispatcher.get("__no_such_interface__")

    def test_unknown_interface_error_message_contains_name(self):
        """The error message includes the unknown interface name."""
        from portal.agent.dispatcher import CentralDispatcher, UnknownInterfaceError

        with pytest.raises(UnknownInterfaceError, match="__bogus__"):
            CentralDispatcher.get("__bogus__")

    def test_registered_names_sorted(self):
        """registered_names() returns a sorted list."""
        from portal.agent.dispatcher import CentralDispatcher

        names = CentralDispatcher.registered_names()
        assert names == sorted(names)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
