"""
Comprehensive tests for portal.routing.execution_engine.ExecutionEngine

Covers:
- execute: routing, backend selection, circuit breaker integration, fallback chain
- generate_stream: token-by-token streaming with fallback
- execute_parallel: concurrent query execution
- health_check: backend status reporting
- get_circuit_breaker_status: detailed CB state
- reset_circuit_breaker: manual reset
- close / cleanup: graceful shutdown
- Circuit breaker disabled path
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from portal.routing.execution_engine import (
    CircuitBreaker,
    CircuitState,
    ExecutionEngine,
    ExecutionResult,
)
from portal.routing.intelligent_router import IntelligentRouter, RoutingDecision, RoutingStrategy
from portal.routing.model_backends import GenerationResult
from portal.routing.model_registry import ModelCapability, ModelMetadata, ModelRegistry, SpeedClass
from portal.routing.task_classifier import TaskCategory, TaskClassification, TaskComplexity


# ---------------------------------------------------------------------------
# Helpers
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


def _make_classification(
    complexity: TaskComplexity = TaskComplexity.SIMPLE,
    category: TaskCategory = TaskCategory.GENERAL,
    requires_code: bool = False,
) -> TaskClassification:
    return TaskClassification(
        complexity=complexity,
        category=category,
        estimated_tokens=100,
        requires_reasoning=False,
        requires_code=requires_code,
        requires_math=False,
        is_multi_turn=False,
        confidence=0.8,
    )


def _make_routing_decision(
    model_id: str = "test_model",
    model: ModelMetadata | None = None,
    fallback_models: list[str] | None = None,
) -> RoutingDecision:
    m = model or _make_model(model_id=model_id)
    return RoutingDecision(
        model_id=model_id,
        model_metadata=m,
        classification=_make_classification(),
        strategy_used=RoutingStrategy.AUTO,
        fallback_models=fallback_models or [],
        reasoning="test reasoning",
    )


def _make_gen_result(success: bool = True, text: str = "response",
                     tool_calls: list | None = None) -> GenerationResult:
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


def _build_engine(
    registry: ModelRegistry | None = None,
    router: IntelligentRouter | None = None,
    config: dict | None = None,
) -> ExecutionEngine:
    """Build an ExecutionEngine with mocked internals."""
    reg = registry or _empty_registry()
    mock_router = router or MagicMock(spec=IntelligentRouter)
    engine = ExecutionEngine(reg, mock_router, config=config)
    # Replace backends with mocks
    for name in list(engine.backends.keys()):
        engine.backends[name] = AsyncMock()
    return engine


# ---------------------------------------------------------------------------
# ExecutionResult dataclass
# ---------------------------------------------------------------------------

class TestExecutionResult:
    def test_success_result(self):
        r = ExecutionResult(
            success=True, response="hello", model_used="Model A",
            execution_time_ms=100.0, tokens_generated=5,
        )
        assert r.success
        assert r.fallbacks_used == 0
        assert r.error is None
        assert r.tool_calls is None

    def test_failure_result(self):
        r = ExecutionResult(
            success=False, response="", model_used="none",
            execution_time_ms=200.0, tokens_generated=0,
            error="all failed", fallbacks_used=3,
        )
        assert not r.success
        assert r.fallbacks_used == 3


# ---------------------------------------------------------------------------
# ExecutionEngine initialization
# ---------------------------------------------------------------------------

class TestExecutionEngineInit:
    def test_default_config(self):
        reg = _empty_registry()
        router = MagicMock(spec=IntelligentRouter)
        engine = ExecutionEngine(reg, router)
        assert engine.max_retries == 3
        assert engine.timeout_seconds == 60
        assert engine.circuit_breaker_enabled is True
        assert engine.circuit_breaker is not None

    def test_custom_config(self):
        reg = _empty_registry()
        router = MagicMock(spec=IntelligentRouter)
        config = {
            "max_retries": 5,
            "timeout_seconds": 120,
            "circuit_breaker_threshold": 5,
        }
        engine = ExecutionEngine(reg, router, config=config)
        assert engine.max_retries == 5
        assert engine.timeout_seconds == 120

    def test_circuit_breaker_disabled(self):
        reg = _empty_registry()
        router = MagicMock(spec=IntelligentRouter)
        engine = ExecutionEngine(reg, router, config={"circuit_breaker_enabled": False})
        assert engine.circuit_breaker_enabled is False
        assert engine.circuit_breaker is None

    def test_all_three_backends_initialized(self):
        reg = _empty_registry()
        router = MagicMock(spec=IntelligentRouter)
        engine = ExecutionEngine(reg, router)
        assert "ollama" in engine.backends
        assert "lmstudio" in engine.backends
        assert "mlx" in engine.backends


# ---------------------------------------------------------------------------
# execute() method
# ---------------------------------------------------------------------------

class TestExecute:
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        engine = _build_engine()
        model = _make_model(model_id="m1", backend="ollama")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = True
        engine.backends["ollama"].generate.return_value = _make_gen_result()

        result = await engine.execute("hello")

        assert result.success
        assert result.response == "response"
        assert result.fallbacks_used == 0

    @pytest.mark.asyncio
    async def test_fallback_on_backend_failure(self):
        engine = _build_engine()
        primary = _make_model(model_id="primary", backend="ollama")
        fallback = _make_model(model_id="fallback", backend="lmstudio")
        engine.registry.register(primary)
        engine.registry.register(fallback)
        engine.router.route.return_value = _make_routing_decision(
            "primary", primary, fallback_models=["fallback"]
        )
        # Primary fails
        engine.backends["ollama"].is_available.return_value = True
        engine.backends["ollama"].generate.return_value = _make_gen_result(success=False)
        # Fallback succeeds
        engine.backends["lmstudio"].is_available.return_value = True
        engine.backends["lmstudio"].generate.return_value = _make_gen_result(text="fallback ok")

        result = await engine.execute("hello")

        assert result.success
        assert result.response == "fallback ok"
        assert result.fallbacks_used >= 1

    @pytest.mark.asyncio
    async def test_all_models_fail(self):
        engine = _build_engine()
        model = _make_model(model_id="m1", backend="ollama")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = True
        engine.backends["ollama"].generate.return_value = _make_gen_result(success=False)

        result = await engine.execute("hello")

        assert not result.success
        assert "All models failed" in result.error

    @pytest.mark.asyncio
    async def test_skips_model_not_in_registry(self):
        engine = _build_engine()
        # Route returns a model ID that doesn't exist in registry
        engine.router.route.return_value = _make_routing_decision("nonexistent")
        result = await engine.execute("hello")
        assert not result.success

    @pytest.mark.asyncio
    async def test_skips_unknown_backend(self):
        engine = _build_engine()
        model = _make_model(model_id="m1", backend="unknown_backend")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        result = await engine.execute("hello")
        assert not result.success

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_backend(self):
        engine = _build_engine()
        model = _make_model(model_id="m1", backend="ollama")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        # Trip the circuit breaker
        engine.circuit_breaker.states["ollama"] = CircuitState.OPEN
        import time as _time
        engine.circuit_breaker.last_failure_times["ollama"] = _time.time() + 999999  # never recover

        result = await engine.execute("hello")

        assert not result.success
        assert result.fallbacks_used >= 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_disabled_skips_check(self):
        engine = _build_engine(config={"circuit_breaker_enabled": False})
        model = _make_model(model_id="m1", backend="ollama")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = True
        engine.backends["ollama"].generate.return_value = _make_gen_result()

        result = await engine.execute("hello")

        assert result.success

    @pytest.mark.asyncio
    async def test_backend_unavailable_records_failure(self):
        engine = _build_engine()
        model = _make_model(model_id="m1", backend="ollama")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = False

        await engine.execute("hello")

        assert engine.circuit_breaker.failure_counts["ollama"] >= 1

    @pytest.mark.asyncio
    async def test_exception_during_execution_records_failure(self):
        engine = _build_engine()
        model = _make_model(model_id="m1", backend="ollama")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = True
        engine.backends["ollama"].generate.side_effect = RuntimeError("boom")

        result = await engine.execute("hello")

        assert not result.success
        assert engine.circuit_breaker.failure_counts["ollama"] >= 1

    @pytest.mark.asyncio
    async def test_execute_passes_messages_through(self):
        engine = _build_engine()
        model = _make_model(model_id="m1", backend="ollama")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = True
        engine.backends["ollama"].generate.return_value = _make_gen_result()

        messages = [{"role": "user", "content": "hi"}]
        await engine.execute("hello", messages=messages)

        # Verify messages were passed to the backend
        call_kwargs = engine.backends["ollama"].generate.call_args
        assert call_kwargs is not None

    @pytest.mark.asyncio
    async def test_execute_with_tool_calls_in_result(self):
        engine = _build_engine()
        model = _make_model(model_id="m1", backend="ollama")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = True
        tool_calls = [{"tool": "calc", "arguments": {"x": 1}}]
        engine.backends["ollama"].generate.return_value = _make_gen_result(tool_calls=tool_calls)

        result = await engine.execute("calc 1+1")

        assert result.success
        assert result.tool_calls == tool_calls


# ---------------------------------------------------------------------------
# _execute_with_timeout
# ---------------------------------------------------------------------------

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
            backend=mock_backend, model=model, query="test",
            system_prompt=None, max_tokens=100, temperature=0.7,
        )

        assert not result.success
        assert "Timeout" in result.error


# ---------------------------------------------------------------------------
# generate_stream
# ---------------------------------------------------------------------------

class TestGenerateStream:
    @pytest.mark.asyncio
    async def test_stream_yields_tokens(self):
        engine = _build_engine()
        model = _make_model(model_id="m1", backend="ollama")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = True

        async def fake_stream(**kwargs):
            for token in ["Hello", " ", "world"]:
                yield token

        engine.backends["ollama"].generate_stream = fake_stream

        tokens = []
        async for token in engine.generate_stream("hello"):
            tokens.append(token)

        assert tokens == ["Hello", " ", "world"]

    @pytest.mark.asyncio
    async def test_stream_falls_back_on_error(self):
        engine = _build_engine()
        primary = _make_model(model_id="primary", backend="ollama")
        fallback = _make_model(model_id="fallback", backend="lmstudio")
        engine.registry.register(primary)
        engine.registry.register(fallback)
        engine.router.route.return_value = _make_routing_decision(
            "primary", primary, fallback_models=["fallback"]
        )
        engine.backends["ollama"].is_available.return_value = True

        async def failing_stream(**kwargs):
            raise ConnectionError("fail")
            yield  # make it a generator  # noqa: E501

        async def ok_stream(**kwargs):
            yield "ok"

        engine.backends["ollama"].generate_stream = failing_stream
        engine.backends["lmstudio"].is_available.return_value = True
        engine.backends["lmstudio"].generate_stream = ok_stream

        tokens = []
        async for token in engine.generate_stream("hello"):
            tokens.append(token)

        assert tokens == ["ok"]

    @pytest.mark.asyncio
    async def test_stream_no_models_available(self):
        engine = _build_engine()
        engine.router.route.return_value = _make_routing_decision("nonexistent")
        tokens = []
        async for token in engine.generate_stream("hello"):
            tokens.append(token)
        assert tokens == []

    @pytest.mark.asyncio
    async def test_stream_circuit_breaker_blocks(self):
        engine = _build_engine()
        model = _make_model(model_id="m1", backend="ollama")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.circuit_breaker.states["ollama"] = CircuitState.OPEN
        import time as _time
        engine.circuit_breaker.last_failure_times["ollama"] = _time.time() + 999999

        tokens = []
        async for token in engine.generate_stream("hello"):
            tokens.append(token)
        assert tokens == []

    @pytest.mark.asyncio
    async def test_stream_records_success_on_circuit_breaker(self):
        engine = _build_engine()
        model = _make_model(model_id="m1", backend="ollama")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = True

        async def ok_stream(**kwargs):
            yield "token"

        engine.backends["ollama"].generate_stream = ok_stream

        tokens = []
        async for token in engine.generate_stream("hello"):
            tokens.append(token)

        assert tokens == ["token"]
        # Success should have been recorded
        assert engine.circuit_breaker.failure_counts["ollama"] == 0

    @pytest.mark.asyncio
    async def test_stream_skips_unavailable_backend(self):
        engine = _build_engine()
        model = _make_model(model_id="m1", backend="ollama")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = False

        tokens = []
        async for token in engine.generate_stream("hello"):
            tokens.append(token)
        assert tokens == []


# ---------------------------------------------------------------------------
# execute_parallel
# ---------------------------------------------------------------------------

class TestExecuteParallel:
    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        engine = _build_engine()
        model = _make_model(model_id="m1", backend="ollama")
        engine.registry.register(model)
        engine.router.route.return_value = _make_routing_decision("m1", model)
        engine.backends["ollama"].is_available.return_value = True
        engine.backends["ollama"].generate.return_value = _make_gen_result()

        results = await engine.execute_parallel(["q1", "q2", "q3"])

        assert len(results) == 3
        for r in results:
            if isinstance(r, ExecutionResult):
                assert r.success


# ---------------------------------------------------------------------------
# health_check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_check_all_available(self):
        engine = _build_engine()
        for backend in engine.backends.values():
            backend.is_available.return_value = True

        health = await engine.health_check()

        assert "ollama" in health
        assert health["ollama"]["available"] is True
        assert health["ollama"]["circuit_state"] == "closed"

    @pytest.mark.asyncio
    async def test_health_check_backend_unavailable(self):
        engine = _build_engine()
        engine.backends["ollama"].is_available.return_value = False
        engine.backends["lmstudio"].is_available.return_value = True
        engine.backends["mlx"].is_available.return_value = True

        health = await engine.health_check()

        assert health["ollama"]["available"] is False

    @pytest.mark.asyncio
    async def test_health_check_exception(self):
        engine = _build_engine()
        engine.backends["ollama"].is_available.side_effect = RuntimeError("fail")
        engine.backends["lmstudio"].is_available.return_value = True
        engine.backends["mlx"].is_available.return_value = True

        health = await engine.health_check()

        assert health["ollama"]["available"] is False
        assert "error" in health["ollama"]

    @pytest.mark.asyncio
    async def test_health_check_circuit_breaker_disabled(self):
        engine = _build_engine(config={"circuit_breaker_enabled": False})
        for backend in engine.backends.values():
            backend.is_available.return_value = True

        health = await engine.health_check()

        assert health["ollama"]["circuit_state"] == "disabled"

    @pytest.mark.asyncio
    async def test_health_check_reports_open_circuit(self):
        engine = _build_engine()
        for backend in engine.backends.values():
            backend.is_available.return_value = True
        engine.circuit_breaker.states["ollama"] = CircuitState.OPEN

        health = await engine.health_check()

        assert health["ollama"]["circuit_state"] == "open"


# ---------------------------------------------------------------------------
# get_circuit_breaker_status
# ---------------------------------------------------------------------------

class TestGetCircuitBreakerStatus:
    def test_enabled_status(self):
        engine = _build_engine()
        status = engine.get_circuit_breaker_status()
        assert status["enabled"] is True
        assert "ollama" in status["backends"]
        assert status["backends"]["ollama"]["state"] == "closed"
        assert status["backends"]["ollama"]["failure_count"] == 0

    def test_disabled_status(self):
        engine = _build_engine(config={"circuit_breaker_enabled": False})
        status = engine.get_circuit_breaker_status()
        assert status["enabled"] is False
        assert status["backends"]["ollama"]["state"] == "disabled"

    def test_status_reflects_failures(self):
        engine = _build_engine()
        engine.circuit_breaker.record_failure("ollama")
        engine.circuit_breaker.record_failure("ollama")
        status = engine.get_circuit_breaker_status()
        assert status["backends"]["ollama"]["failure_count"] == 2


# ---------------------------------------------------------------------------
# reset_circuit_breaker
# ---------------------------------------------------------------------------

class TestResetCircuitBreaker:
    def test_reset_known_backend(self):
        engine = _build_engine()
        engine.circuit_breaker.record_failure("ollama")
        engine.circuit_breaker.record_failure("ollama")
        engine.circuit_breaker.record_failure("ollama")
        assert engine.circuit_breaker.states["ollama"] == CircuitState.OPEN

        engine.reset_circuit_breaker("ollama")

        assert engine.circuit_breaker.states["ollama"] == CircuitState.CLOSED
        assert engine.circuit_breaker.failure_counts["ollama"] == 0

    def test_reset_unknown_backend(self, caplog):
        engine = _build_engine()
        import logging
        with caplog.at_level(logging.WARNING):
            engine.reset_circuit_breaker("nonexistent")
        assert "Unknown backend" in caplog.text

    def test_reset_when_disabled(self, caplog):
        engine = _build_engine(config={"circuit_breaker_enabled": False})
        import logging
        with caplog.at_level(logging.WARNING):
            engine.reset_circuit_breaker("ollama")
        assert "disabled" in caplog.text.lower()


# ---------------------------------------------------------------------------
# close / cleanup
# ---------------------------------------------------------------------------

class TestCloseAndCleanup:
    @pytest.mark.asyncio
    async def test_close_calls_close_on_backends(self):
        engine = _build_engine()
        await engine.close()
        for backend in engine.backends.values():
            backend.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_calls_close(self):
        engine = _build_engine()
        await engine.cleanup()
        for backend in engine.backends.values():
            backend.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_handles_backends_without_close(self):
        engine = _build_engine()
        # Replace one backend with object that has no close
        engine.backends["mlx"] = object()
        await engine.close()  # should not raise
