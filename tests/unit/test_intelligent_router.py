"""
Comprehensive tests for portal.routing.intelligent_router

Covers:
- RoutingStrategy enum values
- RoutingDecision dataclass
- IntelligentRouter: route(), _route_auto(), _route_speed(), _route_quality(),
  _route_balanced(), _route_cost_optimized()
- _build_fallback_chain, _get_any_available_model, _verify_model_preferences,
  _generate_reasoning
"""

import logging
from unittest.mock import patch

import pytest

from portal.routing.intelligent_router import (
    IntelligentRouter,
    RoutingDecision,
    RoutingStrategy,
)
from portal.routing.model_registry import ModelCapability, ModelMetadata, ModelRegistry, SpeedClass
from portal.routing.task_classifier import TaskCategory, TaskClassification, TaskComplexity

# ---------------------------------------------------------------------------
# Helpers – reusable test model factories
# ---------------------------------------------------------------------------


def _make_model(
    model_id: str = "test_model",
    backend: str = "ollama",
    display_name: str = "Test Model",
    capabilities: list[ModelCapability] | None = None,
    speed_class: SpeedClass = SpeedClass.FAST,
    general_quality: float = 0.7,
    cost: float = 0.3,
    available: bool = True,
    api_model_name: str | None = None,
) -> ModelMetadata:
    return ModelMetadata(
        model_id=model_id,
        backend=backend,
        display_name=display_name,
        parameters="7B",
        quantization="Q4_K_M",
        capabilities=capabilities or [ModelCapability.GENERAL],
        speed_class=speed_class,
        general_quality=general_quality,
        cost=cost,
        available=available,
        api_model_name=api_model_name or model_id,
    )


def _empty_registry() -> ModelRegistry:
    """Return a ModelRegistry with NO default models."""
    reg = ModelRegistry.__new__(ModelRegistry)
    reg.models = {}
    return reg


def _classification(
    complexity: TaskComplexity = TaskComplexity.SIMPLE,
    category: TaskCategory = TaskCategory.GENERAL,
    requires_code: bool = False,
    requires_math: bool = False,
) -> TaskClassification:
    return TaskClassification(
        complexity=complexity,
        category=category,
        estimated_tokens=100,
        requires_reasoning=False,
        requires_code=requires_code,
        requires_math=requires_math,
        is_multi_turn=False,
        confidence=0.8,
    )


# ---------------------------------------------------------------------------
# RoutingStrategy enum
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# RoutingDecision dataclass
# ---------------------------------------------------------------------------


class TestRoutingDecision:
    def test_creation(self):
        model = _make_model()
        cls = _classification()
        rd = RoutingDecision(
            model_id="test_model",
            model_metadata=model,
            classification=cls,
            strategy_used=RoutingStrategy.AUTO,
            fallback_models=["fb1", "fb2"],
            reasoning="some reasoning",
        )
        assert rd.model_id == "test_model"
        assert rd.strategy_used is RoutingStrategy.AUTO
        assert len(rd.fallback_models) == 2
        assert rd.reasoning == "some reasoning"


# ---------------------------------------------------------------------------
# IntelligentRouter
# ---------------------------------------------------------------------------


class TestIntelligentRouterInit:
    def test_default_strategy_is_auto(self):
        reg = _empty_registry()
        router = IntelligentRouter(reg)
        assert router.strategy is RoutingStrategy.AUTO

    def test_custom_strategy(self):
        reg = _empty_registry()
        router = IntelligentRouter(reg, strategy=RoutingStrategy.SPEED)
        assert router.strategy is RoutingStrategy.SPEED

    def test_default_preferences_used_when_none(self):
        reg = _empty_registry()
        router = IntelligentRouter(reg)
        assert router.model_preferences == {}

    def test_custom_preferences_applied(self):
        reg = _empty_registry()
        prefs = {"simple": ["m1"], "complex": ["m2"]}
        router = IntelligentRouter(reg, model_preferences=prefs)
        assert router.model_preferences["simple"] == ["m1"]

    def test_verify_model_preferences_warns_on_missing(self, caplog):
        reg = _empty_registry()
        prefs = {"simple": ["nonexistent_model"]}
        with caplog.at_level(logging.WARNING):
            IntelligentRouter(reg, model_preferences=prefs)
        assert "missing model" in caplog.text.lower()

    def test_verify_model_preferences_no_warning_when_all_present(self, caplog):
        reg = _empty_registry()
        m = _make_model(model_id="m1")
        reg.register(m)
        prefs = {"simple": ["m1"]}
        with caplog.at_level(logging.WARNING):
            IntelligentRouter(reg, model_preferences=prefs)
        assert "missing model" not in caplog.text.lower()


# ---------------------------------------------------------------------------
# route() dispatch to each strategy
# ---------------------------------------------------------------------------


class TestRouteDispatch:
    """Verify route() delegates to the correct _route_* method."""

    def _setup_router(self, strategy: RoutingStrategy) -> IntelligentRouter:
        reg = _empty_registry()
        fast = _make_model(
            "fast",
            speed_class=SpeedClass.FAST,
            general_quality=0.6,
            cost=0.1,
            capabilities=[ModelCapability.GENERAL, ModelCapability.CODE],
        )
        slow = _make_model(
            "slow",
            speed_class=SpeedClass.SLOW,
            general_quality=0.9,
            cost=0.8,
            capabilities=[ModelCapability.GENERAL, ModelCapability.CODE, ModelCapability.REASONING],
        )
        reg.register(fast)
        reg.register(slow)
        return IntelligentRouter(reg, strategy=strategy)

    def test_route_returns_routing_decision(self):
        router = self._setup_router(RoutingStrategy.AUTO)
        decision = router.route("hello")
        assert isinstance(decision, RoutingDecision)
        assert decision.strategy_used is RoutingStrategy.AUTO

    @pytest.mark.parametrize("strategy", [RoutingStrategy.SPEED, RoutingStrategy.COST_OPTIMIZED])
    def test_route_speed_and_cost_selects_fast(self, strategy):
        router = self._setup_router(strategy)
        decision = router.route("hello")
        assert decision.model_id == "fast"

    def test_route_quality_selects_best(self):
        router = self._setup_router(RoutingStrategy.QUALITY)
        # Use a general analysis query so quality routing uses GENERAL capability
        cls = _classification(category=TaskCategory.GENERAL)
        with patch.object(router.classifier, "classify", return_value=cls):
            decision = router.route("Tell me something interesting")
        assert decision.model_id == "slow"

    def test_route_balanced_simple_prefers_speed(self):
        router = self._setup_router(RoutingStrategy.BALANCED)
        decision = router.route("hi")
        assert decision.model_id == "fast"

    def test_route_balanced_complex_prefers_quality(self):
        router = self._setup_router(RoutingStrategy.BALANCED)
        # Force COMPLEX classification with GENERAL category so quality routing
        # picks the highest general_quality model
        cls = _classification(complexity=TaskComplexity.COMPLEX, category=TaskCategory.GENERAL)
        with patch.object(router.classifier, "classify", return_value=cls):
            decision = router.route("complex task")
        assert decision.model_id == "slow"


# ---------------------------------------------------------------------------
# _route_auto
# ---------------------------------------------------------------------------


class TestRouteAuto:
    def test_prefers_configured_model(self):
        reg = _empty_registry()
        preferred = _make_model("preferred", cost=0.2)
        other = _make_model("other", cost=0.1)
        reg.register(preferred)
        reg.register(other)
        prefs = {"simple": ["preferred"], "trivial": ["preferred"]}
        router = IntelligentRouter(reg, model_preferences=prefs)
        decision = router.route("what is 2+2?")
        assert decision.model_id == "preferred"

    def test_skips_unavailable_preferred_model(self):
        reg = _empty_registry()
        unavail = _make_model("preferred", available=False)
        fallback = _make_model("fallback", cost=0.1)
        reg.register(unavail)
        reg.register(fallback)
        prefs = {"simple": ["preferred"], "trivial": ["preferred"]}
        router = IntelligentRouter(reg, model_preferences=prefs)
        decision = router.route("what is 2+2?")
        assert decision.model_id == "fallback"

    def test_skips_preferred_model_exceeding_cost(self):
        reg = _empty_registry()
        expensive = _make_model("expensive", cost=0.9)
        cheap = _make_model("cheap", cost=0.1)
        # Register cheap first so _get_any_available_model picks it
        reg.register(cheap)
        reg.register(expensive)
        prefs = {"simple": ["expensive"], "trivial": ["expensive"]}
        router = IntelligentRouter(reg, model_preferences=prefs)
        # Force a SIMPLE classification so it looks up the "simple" preference
        cls = _classification(complexity=TaskComplexity.SIMPLE, category=TaskCategory.GENERAL)
        with patch.object(router.classifier, "classify", return_value=cls):
            decision = router.route("what time is it?", max_cost=0.5)
        assert decision.model_id == "cheap"

    def test_code_task_uses_code_preferences(self):
        reg = _empty_registry()
        code_model = _make_model(
            "coder", capabilities=[ModelCapability.CODE, ModelCapability.GENERAL]
        )
        general = _make_model("general")
        reg.register(code_model)
        reg.register(general)
        prefs = {"code": ["coder"], "simple": ["general"], "moderate": ["general"]}
        router = IntelligentRouter(reg, model_preferences=prefs)
        decision = router.route("Write a Python function to sort a list using code")
        assert decision.model_id == "coder"

    def test_code_fallback_via_capability_when_no_pref_match(self):
        reg = _empty_registry()
        code_model = _make_model(
            "coder", capabilities=[ModelCapability.CODE], speed_class=SpeedClass.FAST
        )
        reg.register(code_model)
        # No code preference configured, but task requires code
        router = IntelligentRouter(
            reg, model_preferences={"code": [], "simple": [], "moderate": []}
        )
        cls = _classification(requires_code=True, category=TaskCategory.CODE)
        with patch.object(router.classifier, "classify", return_value=cls):
            decision = router.route("implement a function")
        assert decision.model_id == "coder"


# ---------------------------------------------------------------------------
# _route_speed
# ---------------------------------------------------------------------------


class TestRouteSpeed:
    @pytest.mark.parametrize(
        "capability,fast_speed,cls_kwargs",
        [
            (ModelCapability.CODE, SpeedClass.ULTRA_FAST, {"requires_code": True}),
            (ModelCapability.MATH, SpeedClass.FAST, {"requires_math": True}),
        ],
    )
    def test_selects_fastest_with_capability(self, capability, fast_speed, cls_kwargs):
        reg = _empty_registry()
        fast = _make_model("fast", speed_class=fast_speed, capabilities=[capability])
        slow = _make_model("slow", speed_class=SpeedClass.SLOW, capabilities=[capability])
        reg.register(fast)
        reg.register(slow)
        router = IntelligentRouter(reg, strategy=RoutingStrategy.SPEED)
        cls = _classification(**cls_kwargs)
        with patch.object(router.classifier, "classify", return_value=cls):
            decision = router.route("task")
        assert decision.model_id == "fast"

    def test_falls_back_when_no_fastest(self):
        reg = _empty_registry()
        m = _make_model("only", capabilities=[ModelCapability.GENERAL])
        reg.register(m)
        router = IntelligentRouter(reg, strategy=RoutingStrategy.SPEED)
        cls = _classification(requires_code=True)
        with patch.object(router.classifier, "classify", return_value=cls):
            decision = router.route("code task")
        # No CODE-capable model, falls back to any available
        assert decision.model_id == "only"


# ---------------------------------------------------------------------------
# _route_quality
# ---------------------------------------------------------------------------


class TestRouteQuality:
    @pytest.mark.parametrize(
        "model_a,model_b,category,expected",
        [
            (
                {
                    "model_id": "low",
                    "general_quality": 0.5,
                    "capabilities": [ModelCapability.GENERAL],
                },
                {
                    "model_id": "high",
                    "general_quality": 0.95,
                    "capabilities": [ModelCapability.GENERAL],
                },
                TaskCategory.GENERAL,
                "high",
            ),
            (
                {
                    "model_id": "reason",
                    "general_quality": 0.9,
                    "capabilities": [ModelCapability.REASONING],
                },
                {
                    "model_id": "general",
                    "general_quality": 0.7,
                    "capabilities": [ModelCapability.GENERAL],
                },
                TaskCategory.ANALYSIS,
                "reason",
            ),
        ],
    )
    def test_selects_best_model_for_category(self, model_a, model_b, category, expected):
        reg = _empty_registry()
        reg.register(_make_model(**model_a))
        reg.register(_make_model(**model_b))
        router = IntelligentRouter(reg, strategy=RoutingStrategy.QUALITY)
        cls = _classification(category=category)
        with patch.object(router.classifier, "classify", return_value=cls):
            decision = router.route("question")
        assert decision.model_id == expected

    def test_respects_max_cost(self):
        reg = _empty_registry()
        expensive = _make_model(
            "expensive", general_quality=0.99, cost=0.9, capabilities=[ModelCapability.GENERAL]
        )
        cheap = _make_model(
            "cheap", general_quality=0.6, cost=0.1, capabilities=[ModelCapability.GENERAL]
        )
        reg.register(expensive)
        reg.register(cheap)
        router = IntelligentRouter(reg, strategy=RoutingStrategy.QUALITY)
        cls = _classification(category=TaskCategory.GENERAL)
        with patch.object(router.classifier, "classify", return_value=cls):
            decision = router.route("tell me something", max_cost=0.5)
        assert decision.model_id == "cheap"


# ---------------------------------------------------------------------------
# _route_balanced
# ---------------------------------------------------------------------------


class TestRouteBalanced:
    def test_moderate_delegates_to_auto_with_reduced_cost(self):
        reg = _empty_registry()
        m = _make_model("m1", cost=0.3)
        reg.register(m)
        router = IntelligentRouter(reg, strategy=RoutingStrategy.BALANCED)
        cls = _classification(complexity=TaskComplexity.MODERATE)
        with patch.object(router.classifier, "classify", return_value=cls):
            with patch.object(router, "_route_auto", wraps=router._route_auto) as spy:
                router.route("moderate task")
                spy.assert_called_once()
                # max_cost passed should be 1.0 * 0.7 = 0.7
                call_args = spy.call_args
                assert call_args[0][1] == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# _route_cost_optimized
# ---------------------------------------------------------------------------


class TestRouteCostOptimized:
    def test_picks_cheapest_available(self):
        reg = _empty_registry()
        expensive = _make_model("expensive", cost=0.8)
        cheap = _make_model("cheap", cost=0.1)
        mid = _make_model("mid", cost=0.4)
        reg.register(expensive)
        reg.register(cheap)
        reg.register(mid)
        router = IntelligentRouter(reg, strategy=RoutingStrategy.COST_OPTIMIZED)
        decision = router.route("hi")
        assert decision.model_id == "cheap"

    def test_prefers_code_capable_for_code_tasks(self):
        reg = _empty_registry()
        cheap_no_code = _make_model("cheap", cost=0.05, capabilities=[ModelCapability.GENERAL])
        cheap_code = _make_model("code", cost=0.2, capabilities=[ModelCapability.CODE])
        reg.register(cheap_no_code)
        reg.register(cheap_code)
        router = IntelligentRouter(reg, strategy=RoutingStrategy.COST_OPTIMIZED)
        cls = _classification(requires_code=True, category=TaskCategory.CODE)
        with patch.object(router.classifier, "classify", return_value=cls):
            decision = router.route("write code")
        assert decision.model_id == "code"

    def test_cheapest_code_model_selected(self):
        reg = _empty_registry()
        cheap_code = _make_model("cheap_code", cost=0.1, capabilities=[ModelCapability.CODE])
        expensive_code = _make_model("exp_code", cost=0.9, capabilities=[ModelCapability.CODE])
        reg.register(expensive_code)
        reg.register(cheap_code)
        router = IntelligentRouter(reg, strategy=RoutingStrategy.COST_OPTIMIZED)
        cls = _classification(requires_code=True, category=TaskCategory.CODE)
        with patch.object(router.classifier, "classify", return_value=cls):
            decision = router.route("write code")
        assert decision.model_id == "cheap_code"

    def test_no_available_falls_back(self):
        reg = _empty_registry()
        unavail = _make_model("unavail", available=False)
        reg.register(unavail)
        router = IntelligentRouter(reg, strategy=RoutingStrategy.COST_OPTIMIZED)
        decision = router.route("hi")
        # _get_any_available_model will return the first model even if unavailable
        assert decision.model_id == "unavail"


# ---------------------------------------------------------------------------
# _build_fallback_chain
# ---------------------------------------------------------------------------


class TestBuildFallbackChain:
    def test_excludes_primary_model(self):
        reg = _empty_registry()
        primary = _make_model("primary", general_quality=0.9)
        fb1 = _make_model("fb1", general_quality=0.8)
        fb2 = _make_model("fb2", general_quality=0.7)
        reg.register(primary)
        reg.register(fb1)
        reg.register(fb2)
        router = IntelligentRouter(reg)
        chain = router._build_fallback_chain(primary, _classification())
        assert "primary" not in chain

    def test_returns_up_to_three_fallbacks(self):
        reg = _empty_registry()
        primary = _make_model("primary")
        for i in range(5):
            reg.register(_make_model(f"fb{i}", general_quality=0.5 + i * 0.05))
        reg.register(primary)
        router = IntelligentRouter(reg)
        chain = router._build_fallback_chain(primary, _classification())
        assert len(chain) <= 3

    def test_sorted_by_quality_descending(self):
        reg = _empty_registry()
        primary = _make_model("primary", general_quality=0.5)
        low = _make_model("low", general_quality=0.3)
        mid = _make_model("mid", general_quality=0.6)
        high = _make_model("high", general_quality=0.9)
        reg.register(primary)
        reg.register(low)
        reg.register(mid)
        reg.register(high)
        router = IntelligentRouter(reg)
        chain = router._build_fallback_chain(primary, _classification())
        assert chain[0] == "high"

    def test_only_available_models_in_chain(self):
        reg = _empty_registry()
        primary = _make_model("primary")
        unavail = _make_model("unavail", available=False, general_quality=0.99)
        avail = _make_model("avail", general_quality=0.5)
        reg.register(primary)
        reg.register(unavail)
        reg.register(avail)
        router = IntelligentRouter(reg)
        chain = router._build_fallback_chain(primary, _classification())
        assert "unavail" not in chain
        assert "avail" in chain


# ---------------------------------------------------------------------------
# _get_any_available_model
# ---------------------------------------------------------------------------


class TestGetAnyAvailableModel:
    def test_returns_first_available(self):
        reg = _empty_registry()
        m1 = _make_model("m1", available=False)
        m2 = _make_model("m2", available=True)
        reg.register(m1)
        reg.register(m2)
        router = IntelligentRouter(reg)
        result = router._get_any_available_model()
        assert result.model_id == "m2"

    def test_returns_unavailable_when_no_available(self):
        reg = _empty_registry()
        m = _make_model("only", available=False)
        reg.register(m)
        router = IntelligentRouter(reg)
        result = router._get_any_available_model()
        assert result.model_id == "only"

    def test_raises_when_registry_empty(self):
        reg = _empty_registry()
        router = IntelligentRouter(reg)
        with pytest.raises(RuntimeError, match="No models available"):
            router._get_any_available_model()


# ---------------------------------------------------------------------------
# _generate_reasoning
# ---------------------------------------------------------------------------


class TestGenerateReasoning:
    def test_contains_all_parts(self):
        reg = _empty_registry()
        m = _make_model("m1", display_name="Test Model")
        reg.register(m)
        router = IntelligentRouter(reg)
        cls = _classification(
            complexity=TaskComplexity.MODERATE,
            category=TaskCategory.CODE,
        )
        reasoning = router._generate_reasoning(m, cls)
        assert "moderate" in reasoning.lower()
        assert "code" in reasoning.lower()
        assert "Test Model" in reasoning
        assert "fast" in reasoning.lower()

    def test_pipe_delimited(self):
        reg = _empty_registry()
        m = _make_model("m1")
        reg.register(m)
        router = IntelligentRouter(reg)
        cls = _classification()
        reasoning = router._generate_reasoning(m, cls)
        assert " | " in reasoning
        parts = reasoning.split(" | ")
        assert len(parts) == 4


# ---------------------------------------------------------------------------
# Integration: full route() end-to-end
# ---------------------------------------------------------------------------


class TestRouteEndToEnd:
    def test_decision_has_all_fields(self):
        reg = _empty_registry()
        m = _make_model("m1")
        reg.register(m)
        router = IntelligentRouter(reg)
        decision = router.route("hello world")
        assert decision.model_id
        assert decision.model_metadata is not None
        assert decision.classification is not None
        assert isinstance(decision.fallback_models, list)
        assert isinstance(decision.reasoning, str)

    def test_route_with_default_registry(self):
        """Ensure routing works with the full default model catalog."""
        reg = ModelRegistry()
        router = IntelligentRouter(reg)
        decision = router.route("Write a Python function to parse JSON")
        assert decision.model_id
        assert decision.classification.requires_code

    def test_route_with_all_strategies(self):
        reg = _empty_registry()
        m = _make_model("m1")
        reg.register(m)
        for strategy in RoutingStrategy:
            router = IntelligentRouter(reg, strategy=strategy)
            decision = router.route("hello")
            assert decision.strategy_used is strategy

    def test_verify_preferences_warns_on_four_or_more_missing(self, caplog):
        reg = _empty_registry()
        prefs = {"simple": ["a", "b", "c", "d"]}
        with caplog.at_level(logging.WARNING):
            IntelligentRouter(reg, model_preferences=prefs)
        assert "..." in caplog.text
