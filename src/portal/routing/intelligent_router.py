"""Intelligent Router — model selection based on task analysis."""

import logging
from dataclasses import dataclass
from enum import Enum

from .model_registry import ModelCapability, ModelMetadata, ModelRegistry
from .task_classifier import TaskCategory, TaskClassification, TaskClassifier, TaskComplexity

logger = logging.getLogger(__name__)

class RoutingStrategy(Enum):
    AUTO = "auto"
    SPEED = "speed"
    QUALITY = "quality"
    BALANCED = "balanced"
    COST_OPTIMIZED = "cost_optimized"


@dataclass
class RoutingDecision:
    model_id: str
    model_metadata: ModelMetadata
    classification: TaskClassification
    strategy_used: RoutingStrategy
    fallback_models: list[str]
    reasoning: str


class IntelligentRouter:
    """Routes queries to optimal models via task classification and configurable strategies."""

    def __init__(
        self,
        registry: ModelRegistry,
        strategy: RoutingStrategy = RoutingStrategy.AUTO,
        model_preferences: dict[str, list[str]] | None = None,
    ) -> None:
        self.registry = registry
        self.strategy = strategy
        self.classifier = TaskClassifier()
        self.model_preferences = model_preferences if model_preferences is not None else {}
        self._verify_model_preferences()

    def route(self, query: str, max_cost: float = 1.0) -> RoutingDecision:
        """Route query to optimal model. Returns RoutingDecision with fallbacks."""
        classification = self.classifier.classify(query)
        strategy_dispatch = {
            RoutingStrategy.SPEED: lambda c: self._route_speed(c),
            RoutingStrategy.COST_OPTIMIZED: lambda c: self._route_cost_optimized(c),
            RoutingStrategy.QUALITY: lambda c: self._route_quality(c, max_cost),
            RoutingStrategy.BALANCED: lambda c: self._route_balanced(c, max_cost),
        }
        model = strategy_dispatch.get(self.strategy, lambda c: self._route_auto(c, max_cost))(classification)
        return RoutingDecision(
            model_id=model.model_id,
            model_metadata=model,
            classification=classification,
            strategy_used=self.strategy,
            fallback_models=self._build_fallback_chain(model, classification),
            reasoning=self._generate_reasoning(model, classification),
        )

    def _route_auto(self, classification: TaskClassification, max_cost: float) -> ModelMetadata:
        """Automatic balanced routing using configurable model preferences."""
        if classification.category == TaskCategory.CODE and classification.requires_code:
            preferred = self.model_preferences.get('code', [])
        else:
            complexity_key = classification.complexity.value.lower()
            preferred = self.model_preferences.get(complexity_key, self.model_preferences.get('simple', []))

        for model_id in preferred:
            model = self.registry.get_model(model_id)
            if model and model.available and model.cost <= max_cost:
                return model

        if classification.requires_code:
            fallback = self.registry.get_fastest_model(ModelCapability.CODE)
            if fallback and fallback.available:
                logger.info("Using capability-based fallback: %s", fallback.model_id)
                return fallback

        logger.warning("No preferred models available, using fallback")
        return self._get_any_available_model()

    def _route_speed(self, classification: TaskClassification) -> ModelMetadata:
        """Route for maximum speed."""
        capability = ModelCapability.CODE if classification.requires_code else (
            ModelCapability.MATH if classification.requires_math else None
        )
        fastest = self.registry.get_fastest_model(capability)
        return fastest if fastest else self._get_any_available_model()

    def _route_quality(self, classification: TaskClassification, max_cost: float) -> ModelMetadata:
        """Route for maximum quality."""
        if classification.requires_code:
            capability = ModelCapability.CODE
        elif classification.requires_math:
            capability = ModelCapability.MATH
        elif classification.category == TaskCategory.ANALYSIS:
            capability = ModelCapability.REASONING
        else:
            capability = ModelCapability.GENERAL
        best = self.registry.get_best_quality_model(capability, max_cost)
        return best if best else self._get_any_available_model()

    def _route_balanced(self, classification: TaskClassification, max_cost: float) -> ModelMetadata:
        """Balanced routing — speed for simple tasks, quality for complex ones."""
        if classification.complexity in (TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE):
            return self._route_speed(classification)
        if classification.complexity in (TaskComplexity.COMPLEX, TaskComplexity.EXPERT):
            return self._route_quality(classification, max_cost)
        return self._route_auto(classification, max_cost * 0.7)

    def _route_cost_optimized(self, classification: TaskClassification) -> ModelMetadata:
        """Route for minimum resource usage."""
        available = sorted(
            [m for m in self.registry.get_all_models() if m.available],
            key=lambda m: m.cost,
        )
        if not available:
            return self._get_any_available_model()
        if classification.requires_code:
            code_capable = [m for m in available if ModelCapability.CODE in m.capabilities]
            if code_capable:
                return code_capable[0]
        return available[0]

    def _build_fallback_chain(self, primary: ModelMetadata, classification: TaskClassification) -> list[str]:  # noqa: ARG002
        """Build fallback model chain (up to 3, sorted by quality descending)."""
        available = sorted(
            (m for m in self.registry.get_all_models() if m.available and m.model_id != primary.model_id),
            key=lambda m: m.general_quality,
            reverse=True,
        )
        return [m.model_id for m in available[:3]]

    def _get_any_available_model(self) -> ModelMetadata:
        """Return any available model as last resort."""
        all_models = self.registry.get_all_models()
        available = [m for m in all_models if m.available]
        if available:
            return available[0]
        if all_models:
            return all_models[0]
        raise RuntimeError("No models available in registry")

    def _verify_model_preferences(self) -> None:
        """Warn if any preferred model IDs are absent from the registry."""
        missing = [
            m_id for tier in self.model_preferences.values()
            for m_id in tier if not self.registry.get_model(m_id)
        ]
        if missing:
            logger.warning(
                "Routing preferences reference %d missing model(s): %s%s.",
                len(missing), ", ".join(missing[:3]), "..." if len(missing) > 3 else "",
            )

    def _generate_reasoning(self, model: ModelMetadata, classification: TaskClassification) -> str:
        """Generate human-readable reasoning for the routing decision."""
        return " | ".join([
            f"Task: {classification.complexity.value} complexity",
            f"Category: {classification.category.value}",
            f"Selected: {model.display_name}",
            f"Speed: {model.speed_class.value}",
        ])
