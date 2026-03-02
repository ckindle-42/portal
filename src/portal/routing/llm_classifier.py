"""
LLM-Based Task Classifier - Uses a small Ollama model for intelligent query classification.

This classifier replaces regex-based heuristics with LLM classification while
keeping TaskClassifier as a zero-latency fallback.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache

import httpx

from portal.routing.task_classifier import TaskCategory, TaskClassification, TaskClassifier

logger = logging.getLogger(__name__)


class LLMCategory(Enum):
    """Categories returned by LLM classifier."""

    GENERAL = "general"
    CODE = "code"
    REASONING = "reasoning"
    CREATIVE = "creative"
    TOOL_USE = "tool_use"


@dataclass
class LLMClassification:
    """Result of LLM-based classification."""

    category: LLMCategory
    confidence: float
    reasoning: str | None = None


class LLMClassifier:
    """
    LLM-based task classifier using a small Ollama model.

    Falls back to TaskClassifier if LLM is unavailable.
    LRU cache avoids reclassifying identical prompts.
    """

    # Default classification prompt
    CLASSIFY_PROMPT = """Classify this query into one of these categories:
- general: Simple questions, greetings, casual conversation
- code: Programming, debugging, technical tasks
- reasoning: Analysis, math, logic problems
- creative: Writing, brainstorming, storytelling
- tool_use: Using tools like QR codes, conversions, file operations

Respond with ONLY the category name (e.g., "code").
Query: {query}"""

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        model: str = "qwen2.5:0.5b",
        timeout: float = 30.0,
        cache_size: int = 128,
    ):
        self.ollama_host = ollama_host
        self.model = model
        self.timeout = timeout
        # Fallback to regex-based classifier
        self._fallback = TaskClassifier()
        # Track LLM availability
        self._llm_available: bool | None = None

    async def is_available(self) -> bool:
        """Check if LLM classifier is available."""
        if self._llm_available is not None:
            return self._llm_available

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.ollama_host}/api/tags")
                self._llm_available = resp.status_code == 200
        except Exception:
            self._llm_available = False

        logger.info("LLM classifier available: %s", self._llm_available)
        return self._llm_available

    async def classify(self, query: str) -> LLMClassification:
        """
        Classify a query using LLM.

        Falls back to TaskClassifier if LLM is unavailable.
        Results are cached to avoid reclassifying identical prompts.
        """
        if not await self.is_available():
            return self._fallback_to_regex(query)

        try:
            return await self._classify_with_llm(query)
        except Exception as e:
            logger.warning("LLM classification failed: %s, falling back to regex", e)
            return self._fallback_to_regex(query)

    @lru_cache(maxsize=128)
    def _cached_classify(self, query: str) -> TaskClassification:
        """Synchronous fallback using regex classifier."""
        return self._fallback.classify(query)

    def _fallback_to_regex(self, query: str) -> LLMClassification:
        """Fallback to regex-based TaskClassifier."""
        task_class = self._cached_classify(query)

        # Map TaskCategory to LLMCategory
        category_map = {
            TaskCategory.CODE: LLMCategory.CODE,
            TaskCategory.MATH: LLMCategory.REASONING,
            TaskCategory.ANALYSIS: LLMCategory.REASONING,
            TaskCategory.CREATIVE: LLMCategory.CREATIVE,
            TaskCategory.TOOL_USE: LLMCategory.TOOL_USE,
            TaskCategory.GREETING: LLMCategory.GENERAL,
            TaskCategory.QUESTION: LLMCategory.GENERAL,
            TaskCategory.SUMMARIZATION: LLMCategory.GENERAL,
            TaskCategory.TRANSLATION: LLMCategory.GENERAL,
            TaskCategory.GENERAL: LLMCategory.GENERAL,
        }

        return LLMClassification(
            category=category_map.get(task_class.category, LLMCategory.GENERAL),
            confidence=task_class.confidence,
            reasoning="regex_fallback",
        )

    async def _classify_with_llm(self, query: str) -> LLMClassification:
        """Classify using the LLM."""
        prompt = self.CLASSIFY_PROMPT.format(query=query)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.ollama_host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            result = resp.json()

        response_text = result.get("response", "").strip().lower()

        # Parse category from response
        try:
            category = LLMCategory(response_text)
        except ValueError:
            # Default to general if response is unexpected
            category = LLMCategory.GENERAL
            logger.debug("Unexpected LLM response: %s, defaulting to general", response_text)

        return LLMClassification(
            category=category,
            confidence=0.9,  # LLM classification is assumed high confidence
            reasoning=response_text,
        )


def create_classifier(
    ollama_host: str | None = None,
    model: str | None = None,
) -> LLMClassifier:
    """Factory function to create an LLMClassifier with config from settings."""
    import os

    _default_host = "http://localhost:11434"
    _default_model = "qwen2.5:0.5b"

    host: str = (
        ollama_host
        if ollama_host is not None
        else os.getenv("OLLAMA_HOST", _default_host) or _default_host
    )
    classifier_model: str = (
        model
        if model is not None
        else os.getenv("ROUTING_LLM_MODEL", _default_model) or _default_model
    )

    return LLMClassifier(ollama_host=host, model=classifier_model)
