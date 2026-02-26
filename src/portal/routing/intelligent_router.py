"""
Intelligent Router - Model selection based on task analysis
"""

import logging
from dataclasses import dataclass
from enum import Enum

from .model_registry import ModelCapability, ModelMetadata, ModelRegistry
from .task_classifier import TaskCategory, TaskClassification, TaskClassifier, TaskComplexity

logger = logging.getLogger(__name__)

# Default complexity→model-preference mapping.
# Each tier is intentionally empty so the router falls back to
# capability-based selection when the caller provides no preferences.
_DEFAULT_PREFERENCES: dict[str, list[str]] = {
    "trivial": [],
    "simple": [],
    "moderate": [],
    "complex": [],
    "expert": [],
    "code": [],
}


class RoutingStrategy(Enum):
    """Available routing strategies"""
    AUTO = "auto"                    # Balanced automatic selection
    SPEED = "speed"                  # Prioritize fastest response
    QUALITY = "quality"              # Prioritize best quality
    BALANCED = "balanced"            # Balance speed and quality
    COST_OPTIMIZED = "cost_optimized"  # Minimize resource usage


@dataclass
class RoutingDecision:
    """Result of routing decision"""
    model_id: str
    model_metadata: ModelMetadata
    classification: TaskClassification
    strategy_used: RoutingStrategy
    fallback_models: list[str]
    reasoning: str


class IntelligentRouter:
    """
    Routes queries to optimal models based on task classification

    Supports multiple strategies and automatic fallback selection
    """

    def __init__(
        self,
        registry: ModelRegistry,
        strategy: RoutingStrategy = RoutingStrategy.AUTO,
        model_preferences: dict[str, list[str]] | None = None,
    ) -> None:
        self.registry = registry
        self.strategy = strategy
        self.classifier = TaskClassifier()
        self.model_preferences = model_preferences if model_preferences is not None else dict(_DEFAULT_PREFERENCES)
        self._verify_model_preferences()

    def route(self, query: str, max_cost: float = 1.0) -> RoutingDecision:
        """
        Route query to optimal model
        
        Args:
            query: User query
            max_cost: Maximum cost factor (0.0-1.0)
            
        Returns:
            RoutingDecision with selected model and fallbacks
        """

        # Classify the task
        classification = self.classifier.classify(query)

        # Select model based on strategy
        if self.strategy == RoutingStrategy.AUTO:
            model = self._route_auto(classification, max_cost)
        elif self.strategy == RoutingStrategy.SPEED:
            model = self._route_speed(classification)
        elif self.strategy == RoutingStrategy.QUALITY:
            model = self._route_quality(classification, max_cost)
        elif self.strategy == RoutingStrategy.BALANCED:
            model = self._route_balanced(classification, max_cost)
        elif self.strategy == RoutingStrategy.COST_OPTIMIZED:
            model = self._route_cost_optimized(classification)
        else:
            model = self._route_auto(classification, max_cost)

        # Build fallback chain
        fallbacks = self._build_fallback_chain(model, classification)

        # Generate reasoning
        reasoning = self._generate_reasoning(model, classification)

        return RoutingDecision(
            model_id=model.model_id,
            model_metadata=model,
            classification=classification,
            strategy_used=self.strategy,
            fallback_models=fallbacks,
            reasoning=reasoning
        )

    def _route_auto(self, classification: TaskClassification,
                   max_cost: float) -> ModelMetadata:
        """Automatic balanced routing using configurable model preferences"""

        # Get category-specific preferences (configurable via constructor)
        if classification.category == TaskCategory.CODE and classification.requires_code:
            preferred = self.model_preferences.get('code', [])
        else:
            # Map complexity to preference key
            complexity_key = classification.complexity.value.lower()  # 'trivial', 'simple', etc.
            preferred = self.model_preferences.get(complexity_key, self.model_preferences.get('simple', []))

        # Find first available model from preferences
        for model_id in preferred:
            model = self.registry.get_model(model_id)
            if model and model.available and model.cost <= max_cost:
                return model

        # If no preferred model available, try capability-based fallback
        if classification.requires_code:
            capability_fallback = self.registry.get_fastest_model(ModelCapability.CODE)
            if capability_fallback and capability_fallback.available:
                logger.info(f"Using capability-based fallback: {capability_fallback.model_id}")
                return capability_fallback

        # Fallback to any available model
        logger.warning("No preferred models available, using fallback")
        return self._get_any_available_model()

    def _route_speed(self, classification: TaskClassification) -> ModelMetadata:
        """Route for maximum speed"""

        # Get capability based on task
        capability = None
        if classification.requires_code:
            capability = ModelCapability.CODE
        elif classification.requires_math:
            capability = ModelCapability.MATH

        fastest = self.registry.get_fastest_model(capability)
        if fastest:
            return fastest

        # Fallback to any available
        return self._get_any_available_model()

    def _route_quality(self, classification: TaskClassification,
                      max_cost: float) -> ModelMetadata:
        """Route for maximum quality"""

        # Determine capability
        if classification.requires_code:
            capability = ModelCapability.CODE
        elif classification.requires_math:
            capability = ModelCapability.MATH
        elif classification.category == TaskCategory.ANALYSIS:
            capability = ModelCapability.REASONING
        else:
            capability = ModelCapability.GENERAL

        best = self.registry.get_best_quality_model(capability, max_cost)
        if best:
            return best

        return self._get_any_available_model()

    def _route_balanced(self, classification: TaskClassification,
                       max_cost: float) -> ModelMetadata:
        """Balanced routing - quality vs speed tradeoff"""

        # For simple tasks, prioritize speed
        if classification.complexity in [TaskComplexity.TRIVIAL, TaskComplexity.SIMPLE]:
            return self._route_speed(classification)

        # For complex tasks, prioritize quality
        if classification.complexity in [TaskComplexity.COMPLEX, TaskComplexity.EXPERT]:
            return self._route_quality(classification, max_cost)

        # For moderate, find middle ground
        return self._route_auto(classification, max_cost * 0.7)

    def _route_cost_optimized(self, classification: TaskClassification) -> ModelMetadata:
        """Route for minimum resource usage"""

        # Always use smallest model that can handle the task
        all_models = self.registry.get_all_models()
        available = [m for m in all_models if m.available]

        if not available:
            return self._get_any_available_model()

        # Sort by cost
        available.sort(key=lambda m: m.cost)

        # For code tasks, need at least moderate capability
        if classification.requires_code:
            code_capable = [m for m in available if ModelCapability.CODE in m.capabilities]
            if code_capable:
                return code_capable[0]

        return available[0]

    def _build_fallback_chain(self, primary: ModelMetadata,
                             classification: TaskClassification) -> list[str]:
        """Build fallback model chain"""

        fallbacks = []
        all_models = self.registry.get_all_models()
        available = [m for m in all_models if m.available and m.model_id != primary.model_id]

        # Sort by quality (descending)
        available.sort(key=lambda m: m.general_quality, reverse=True)

        # Add up to 3 fallbacks
        for model in available[:3]:
            fallbacks.append(model.model_id)

        return fallbacks

    def _get_any_available_model(self) -> ModelMetadata:
        """Get any available model as last resort"""
        all_models = self.registry.get_all_models()
        available = [m for m in all_models if m.available]

        if available:
            return available[0]

        # Return first registered model even if marked unavailable
        if all_models:
            return all_models[0]

        raise RuntimeError("No models available in registry")

    def _verify_model_preferences(self) -> None:
        """Warn if any preferred model IDs are absent from the registry."""
        missing = [
            m_id
            for tier in self.model_preferences.values()
            for m_id in tier
            if not self.registry.get_model(m_id)
        ]
        if missing:
            logger.warning(
                "Routing preferences reference %d missing model(s): %s%s. "
                "Falling back to capability-based selection.",
                len(missing),
                ", ".join(missing[:3]),
                "..." if len(missing) > 3 else "",
            )

    def _generate_reasoning(self, model: ModelMetadata,
                           classification: TaskClassification) -> str:
        """Generate human-readable reasoning for selection"""

        parts = []

        # Complexity
        parts.append(f"Task: {classification.complexity.value} complexity")

        # Category
        parts.append(f"Category: {classification.category.value}")

        # Model choice
        parts.append(f"Selected: {model.display_name}")

        # Speed/quality tradeoff
        parts.append(f"Speed: {model.speed_class.value}")

        return " | ".join(parts)
