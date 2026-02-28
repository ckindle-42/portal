"""Tests for ExecutionEngine — routing, circuit breaker, streaming, health."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from portal.routing.execution_engine import CircuitState, ExecutionEngine, ExecutionResult
from portal.routing.intelligent_router import IntelligentRouter, RoutingDecision, RoutingStrategy
from portal.routing.model_backends import GenerationResult
from portal.routing.model_registry import ModelCapability, ModelMetadata, ModelRegistry, SpeedClass
from portal.routing.task_classifier import TaskCategory, TaskClassification, TaskComplexity


def _make_model(
    model_id="test_model", backend="ollama", available=True, cost=0.3, general_quality=0.7
) -> ModelMetadata:
    return ModelMetadata(
        model_id=model_id,
        backend=backend,
        display_name="Test Model",
        parameters="7B",
        quantization="Q4_K_M",
        capabilities=[ModelCapability.GENERAL],
        speed_class=SpeedClass.FAST,
        general_quality=general_quality,
        cost=cost,
        available=available,
        api_model_name=model_id,
    )


def _make_classification() -> TaskClassification:
    return TaskClassification(
        complexity=TaskComplexity.SIMPLE,
        category=TaskCategory.GENERAL,
        estimated_tokens=100,
        requires_reasoning=False,
        requires_code=False,
        requires_math=False,
        is_multi_turn=False,
        confidence=0.8,
    )


def _make_routing_decision(
    model_id="test_model", model=None, fallback_models=None
) -> RoutingDecision:
    m = model or _make_model(model_id=model_id)
    return RoutingDecision(
        model_id=model_id,
        model_metadata=m,
        classification=_make_classification(),
        strategy_used=RoutingStrategy.AUTO,
        fallback_models=fallback_models or [],
        reasoning="test",
    )


def _make_gen_result(success=True, text="response", tool_calls=None) -> GenerationResult:
    return GenerationResult(
        text=text,
        tokens_generated=10,
        time_ms=50.0,
        model_id="test_model",
        success=success,
        error=None if success else "backend error",
        tool_calls=tool_calls,
    )


def _empty_registry() -> ModelRegistry:
    reg = ModelRegistry.__new__(ModelRegistry)
    reg.models = {}
    return reg


def _build_engine(registry=None, router=None, config=None) -> ExecutionEngine:
    reg = registry or _empty_registry()
    mock_router = router or MagicMock(spec=IntelligentRouter)
    engine = ExecutionEngine(reg, mock_router, config=config)
    for name in list(engine.backends.keys()):
        engine.backends[name] = AsyncMock()
    return engine


class TestExecutionResult:
    def test_defaults(self):
        r = ExecutionResult(
            success=True,
            response="hello",
            model_used="M",
            execution_time_ms=100.0,
            tokens_generated=5,
        )
        assert r.fallbacks_used == 0
        assert r.error is None
        assert r.tool_calls is None

    def test_failure(self):
        r = ExecutionResult(
            success=False,
            response="",
            model_used="none",
            execution_time_ms=200.0,
            tokens_generated=0,
            error="all failed",
            fallbacks_used=3,
        )
        assert not r.success
        assert r.fallbacks_used == 3


class TestExecutionEngineInit:
    def test_defaults(self):
        engine = ExecutionEngine(_empty_registry(), MagicMock(spec=IntelligentRouter))
        assert engine.timeout_seconds == 60
        assert engine.circuit_breaker_enabled is True

    def test_circuit_breaker_disabled(self):
        engine = ExecutionEngine(
            _empty_registry(),
            MagicMock(spec=IntelligentRouter),
            config={"circuit_breaker_enabled": False},
        )
        assert engine.circuit_breaker_enabled is False
        assert engine.circuit_breaker is None

    def test_all_backends_initialized(self):
        engine = ExecutionEngine(_empty_registry(), MagicMock(spec=IntelligentRouter))
        assert {"ollama"} == set(engine.backends.keys())


class TestExecute:
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        engine = _build_engine()
        model = _make_model("m1")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = True
        engine.backends["ollama"].generate.return_value = _make_gen_result()
        result = await engine.execute("hello")
        assert result.success and result.fallbacks_used == 0

    @pytest.mark.asyncio
    async def test_fallback_on_backend_failure(self):
        engine = _build_engine()
        primary = _make_model("primary", "ollama")
        fallback = _make_model("fallback", "ollama")
        engine.registry.register(primary)
        engine.registry.register(fallback)
        engine.router.route.return_value = _make_routing_decision("primary", primary, ["fallback"])
        engine.backends["ollama"].is_available.return_value = True
        engine.backends["ollama"].generate.side_effect = [
            _make_gen_result(success=False),
            _make_gen_result(text="fallback ok"),
        ]
        result = await engine.execute("hello")
        assert result.success and result.response == "fallback ok" and result.fallbacks_used >= 1

    @pytest.mark.asyncio
    async def test_all_models_fail(self):
        engine = _build_engine()
        model = _make_model("m1")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = True
        engine.backends["ollama"].generate.return_value = _make_gen_result(success=False)
        result = await engine.execute("hello")
        assert not result.success and "All models failed" in result.error

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "model_id,backend,expected_fail_reason",
        [
            ("nonexistent", "ollama", None),
            ("m1", "unknown_backend", None),
        ],
    )
    async def test_missing_model_or_backend(self, model_id, backend, expected_fail_reason):
        engine = _build_engine()
        if model_id != "nonexistent":
            engine.registry.register(_make_model(model_id, backend))
        engine.router.route.return_value = _make_routing_decision(model_id)
        result = await engine.execute("hello")
        assert not result.success

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_backend(self):
        engine = _build_engine()
        model = _make_model("m1")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.circuit_breaker.states["ollama"] = CircuitState.OPEN
        import time

        engine.circuit_breaker.last_failure_times["ollama"] = time.time() + 999999
        result = await engine.execute("hello")
        assert not result.success

    @pytest.mark.asyncio
    async def test_exception_records_circuit_failure(self):
        engine = _build_engine()
        model = _make_model("m1")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = True
        engine.backends["ollama"].generate.side_effect = RuntimeError("boom")
        result = await engine.execute("hello")
        assert not result.success and engine.circuit_breaker.failure_counts["ollama"] >= 1

    @pytest.mark.asyncio
    async def test_tool_calls_propagated(self):
        engine = _build_engine()
        model = _make_model("m1")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = True
        tool_calls = [{"tool": "calc", "arguments": {"x": 1}}]
        engine.backends["ollama"].generate.return_value = _make_gen_result(tool_calls=tool_calls)
        result = await engine.execute("calc 1+1")
        assert result.success and result.tool_calls == tool_calls


class TestExecuteWithTimeout:
    @pytest.mark.asyncio
    async def test_timeout_returns_failure(self):
        engine = _build_engine(config={"timeout_seconds": 0.01})
        model = _make_model()

        async def slow_generate(**kwargs):
            await asyncio.sleep(10)
            return _make_gen_result()

        mock_backend = AsyncMock()
        mock_backend.generate = slow_generate
        result = await engine._execute_with_timeout(
            backend=mock_backend,
            model=model,
            query="test",
            system_prompt=None,
            max_tokens=100,
            temperature=0.7,
        )
        assert not result.success and "Timeout" in result.error


class TestGenerateStream:
    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self):
        engine = _build_engine()
        model = _make_model("m1")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = True

        async def fake_stream(**kwargs):
            for t in ["Hello", " ", "world"]:
                yield t

        engine.backends["ollama"].generate_stream = fake_stream
        tokens = [t async for t in engine.generate_stream("hello")]
        assert tokens == ["Hello", " ", "world"]

    @pytest.mark.asyncio
    async def test_stream_falls_back_on_error(self):
        engine = _build_engine()
        primary = _make_model("primary", "ollama")
        fallback = _make_model("fallback_alt", "ollama")
        engine.registry.register(primary)
        engine.registry.register(fallback)
        engine.router.route.return_value = _make_routing_decision(
            "primary", primary, ["fallback_alt"]
        )
        call_count = 0

        async def stream_with_fallback(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("fail")
                yield  # noqa: F704
            else:
                yield "ok"

        engine.backends["ollama"].is_available.return_value = True
        engine.backends["ollama"].generate_stream = stream_with_fallback
        tokens = [t async for t in engine.generate_stream("hello")]
        assert tokens == ["ok"]

    @pytest.mark.asyncio
    async def test_stream_no_models_available(self):
        engine = _build_engine()
        engine.router.route.return_value = _make_routing_decision("nonexistent")
        tokens = [t async for t in engine.generate_stream("hello")]
        assert tokens == []


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_all_available(self):
        engine = _build_engine()
        for b in engine.backends.values():
            b.is_available.return_value = True
        health = await engine.health_check()
        assert health["ollama"]["available"] is True
        assert health["ollama"]["circuit_state"] == "closed"

    @pytest.mark.asyncio
    async def test_backend_unavailable(self):
        engine = _build_engine()
        engine.backends["ollama"].is_available.return_value = False
        health = await engine.health_check()
        assert health["ollama"]["available"] is False

    @pytest.mark.asyncio
    async def test_exception_handled(self):
        engine = _build_engine()
        engine.backends["ollama"].is_available.side_effect = RuntimeError("fail")
        health = await engine.health_check()
        assert health["ollama"]["available"] is False and "error" in health["ollama"]

    @pytest.mark.asyncio
    async def test_open_circuit_reported(self):
        engine = _build_engine()
        for b in engine.backends.values():
            b.is_available.return_value = True
        engine.circuit_breaker.states["ollama"] = CircuitState.OPEN
        health = await engine.health_check()
        assert health["ollama"]["circuit_state"] == "open"


class TestCircuitBreakerOps:
    def test_status_enabled(self):
        engine = _build_engine()
        status = engine.get_circuit_breaker_status()
        assert status["enabled"] is True
        assert status["backends"]["ollama"]["failure_count"] == 0

    def test_status_disabled(self):
        engine = _build_engine(config={"circuit_breaker_enabled": False})
        assert engine.get_circuit_breaker_status()["backends"]["ollama"]["state"] == "disabled"

    def test_reset_known_backend(self):
        engine = _build_engine()
        for _ in range(3):
            engine.circuit_breaker.record_failure("ollama")
        assert engine.circuit_breaker.states["ollama"] == CircuitState.OPEN
        engine.reset_circuit_breaker("ollama")
        assert engine.circuit_breaker.states["ollama"] == CircuitState.CLOSED


class TestCloseAndCleanup:
    @pytest.mark.asyncio
    async def test_close_calls_backends(self):
        engine = _build_engine()
        await engine.close()
        for b in engine.backends.values():
            b.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_missing_close(self):
        engine = _build_engine()
        engine.backends["extra"] = object()
        await engine.close()  # must not raise
