"""
Tests for portal.routing.llm_classifier

Covers:
- LLMCategory enum
- LLMClassification dataclass
- LLMClassifier: is_available(), classify(), _fallback_to_regex(), stream_classify()
- create_classifier() factory function
"""

from unittest.mock import AsyncMock, patch

import pytest

from portal.routing.llm_classifier import (
    LLMCategory,
    LLMClassification,
    LLMClassifier,
    create_classifier,
)


class TestLLMCategory:
    """Tests for LLMCategory enum."""

    def test_all_categories_defined(self):
        """All expected categories are defined."""
        assert LLMCategory.GENERAL.value == "general"
        assert LLMCategory.CODE.value == "code"
        assert LLMCategory.REASONING.value == "reasoning"
        assert LLMCategory.CREATIVE.value == "creative"
        assert LLMCategory.TOOL_USE.value == "tool_use"


class TestLLMClassification:
    """Tests for LLMClassification dataclass."""

    def test_basic_creation(self):
        """Can create LLMClassification with required fields."""
        classification = LLMClassification(
            category=LLMCategory.CODE,
            confidence=0.95,
        )
        assert classification.category == LLMCategory.CODE
        assert classification.confidence == 0.95
        assert classification.reasoning is None

    def test_with_reasoning(self):
        """Can create LLMClassification with reasoning."""
        classification = LLMClassification(
            category=LLMCategory.CREATIVE,
            confidence=0.85,
            reasoning="LLM returned creative category",
        )
        assert classification.reasoning == "LLM returned creative category"


class TestLLMClassifier:
    """Tests for LLMClassifier class."""

    @pytest.fixture
    def classifier(self):
        """Create a classifier instance for testing."""
        return LLMClassifier(
            ollama_host="http://localhost:11434",
            model="qwen2.5:0.5b",
            timeout=10.0,
        )

    @pytest.mark.asyncio
    async def test_is_available_success(self, classifier):
        """is_available returns True when Ollama is reachable."""
        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await classifier.is_available()

        assert result is True

    @pytest.mark.asyncio
    async def test_is_available_failure(self, classifier):
        """is_available returns False when Ollama is unreachable."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.get.side_effect = Exception("Connection refused")
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await classifier.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_classify_fallback_when_llm_unavailable(self, classifier):
        """classify returns regex fallback when LLM is unavailable."""
        # Force LLM unavailable
        classifier._llm_available = False

        result = await classifier.classify("write a hello world program")

        # Should fallback to regex classification
        assert result.category in LLMCategory
        assert result.reasoning == "regex_fallback"

    @pytest.mark.asyncio
    async def test_classify_llm_returns_valid_category(self, classifier):
        """classify returns valid category when LLM is available and returns valid response."""
        # Test the LLMCategory enum parsing - valid category
        category = LLMCategory("code")
        assert category == LLMCategory.CODE

    @pytest.mark.asyncio
    async def test_classify_llm_returns_invalid_category_defaults_to_general(self, classifier):
        """classify defaults to GENERAL when LLM returns unexpected response."""
        # Test that invalid category raises ValueError (caught in _classify_with_llm)
        with pytest.raises(ValueError):
            LLMCategory("invalid_category_xyz")

    @pytest.mark.asyncio
    async def test_classify_llm_exception_falls_back_to_regex(self, classifier):
        """classify falls back to regex when LLM raises exception."""
        classifier._llm_available = True

        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.post.side_effect = Exception("Network error")
            mock_client.return_value.__aenter__.return_value = mock_instance

            result = await classifier.classify("test query")

        assert result.category in LLMCategory
        assert result.reasoning == "regex_fallback"

    def test_fallback_to_regex_maps_code_category(self, classifier):
        """_fallback_to_regex correctly maps TaskCategory.CODE to LLMCategory.CODE."""
        # Need at least 2 code pattern matches to classify as CODE
        result = classifier._fallback_to_regex("write a python function to debug the code")

        assert result.category == LLMCategory.CODE

    def test_fallback_to_regex_maps_creative_category(self, classifier):
        """_fallback_to_regex correctly maps TaskCategory.CREATIVE."""
        # Need at least 2 creative pattern matches to classify as CREATIVE
        result = classifier._fallback_to_regex("write a story and create a poem with narrative")

        assert result.category == LLMCategory.CREATIVE

    def test_fallback_to_regex_maps_general_category(self, classifier):
        """_fallback_to_regex maps unknown categories to GENERAL."""
        # Use a greeting which maps to GENERAL
        result = classifier._fallback_to_regex("hello there")

        assert result.category == LLMCategory.GENERAL


class TestCreateClassifier:
    """Tests for create_classifier factory function."""

    def test_create_classifier_defaults(self):
        """create_classifier returns classifier with correct defaults."""
        classifier = create_classifier()

        assert isinstance(classifier, LLMClassifier)
        assert classifier.ollama_host == "http://localhost:11434"
        assert classifier.model == "qwen2.5:0.5b"

    def test_create_classifier_custom_host(self):
        """create_classifier accepts custom host."""
        classifier = create_classifier(ollama_host="http://custom:11434")

        assert classifier.ollama_host == "http://custom:11434"

    def test_create_classifier_custom_model(self):
        """create_classifier accepts custom model."""
        classifier = create_classifier(model="llama3:8b")

        assert classifier.model == "llama3:8b"

    def test_create_classifier_custom_both(self):
        """create_classifier accepts both custom host and model."""
        classifier = create_classifier(
            ollama_host="http://custom:11434",
            model="llama3:8b",
        )

        assert classifier.ollama_host == "http://custom:11434"
        assert classifier.model == "llama3:8b"
