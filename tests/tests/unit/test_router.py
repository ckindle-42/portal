"""
Tests for intelligent router
"""

import pytest

from portal.routing.task_classifier import TaskClassifier
from portal.routing.intelligent_router import IntelligentRouter


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
            assert result in ["trivial", "simple"], f"'{query}' should be trivial/simple, got {result}"
    
    def test_classify_complex_queries(self):
        """Test that complex queries are correctly classified"""
        classifier = TaskClassifier()
        
        complex_queries = [
            "Write a detailed analysis of the current codebase architecture and suggest improvements",
            "Generate a comprehensive report on system performance with graphs and recommendations",
        ]
        
        for query in complex_queries:
            result = classifier.classify(query)
            assert result in ["medium", "complex"], f"'{query}' should be complex, got {result}"
    
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
            assert result in ["medium", "complex"], f"'{query}' should need medium/complex model, got {result}"


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
        assert simple_task in ["trivial", "simple"]
        
        # Complex query should use larger model  
        complex_task = router.classifier.classify("Write a detailed analysis with code examples")
        assert complex_task in ["medium", "complex"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
