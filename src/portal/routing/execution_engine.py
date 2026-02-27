"""Execution Engine — model execution with fallback chains and circuit breaker."""

import asyncio
import logging
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .intelligent_router import IntelligentRouter, RoutingDecision
from .model_backends import GenerationResult, LMStudioBackend, MLXBackend, OllamaBackend
from .model_registry import ModelMetadata, ModelRegistry

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Prevents retrying repeatedly failing backends (circuit breaker pattern)."""

    def __init__(
        self, failure_threshold: int = 3, recovery_timeout: int = 60, half_open_max_calls: int = 1
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.failure_counts: dict[str, int] = defaultdict(int)
        self.states: dict[str, CircuitState] = defaultdict(lambda: CircuitState.CLOSED)
        self.last_failure_times: dict[str, float] = {}
        self.half_open_calls: dict[str, int] = defaultdict(int)

    def should_allow_request(self, backend_id: str) -> tuple[bool, str]:
        """Return (allowed, reason) for the given backend."""
        state = self.states[backend_id]
        if state == CircuitState.CLOSED:
            return True, "circuit_closed"
        if state == CircuitState.OPEN:
            last_failure = self.last_failure_times.get(backend_id, 0)
            if time.time() - last_failure >= self.recovery_timeout:
                self.states[backend_id] = CircuitState.HALF_OPEN
                self.half_open_calls[backend_id] = 0
                logger.info("Circuit breaker for %s: OPEN -> HALF_OPEN", backend_id)
                return True, "circuit_testing_recovery"
            wait_time = int(self.recovery_timeout - (time.time() - last_failure))
            return False, f"circuit_open_wait_{wait_time}s"
        if state == CircuitState.HALF_OPEN:
            if self.half_open_calls[backend_id] < self.half_open_max_calls:
                self.half_open_calls[backend_id] += 1
                return True, "circuit_half_open_testing"
            return False, "circuit_half_open_limit_reached"
        return False, "circuit_unknown_state"

    def record_success(self, backend_id: str) -> None:
        """Record a successful request; recovers half-open circuits."""
        state = self.states[backend_id]
        if state == CircuitState.HALF_OPEN:
            self.states[backend_id] = CircuitState.CLOSED
            self.failure_counts[backend_id] = 0
            self.half_open_calls[backend_id] = 0
            logger.info("Circuit breaker for %s: HALF_OPEN -> CLOSED (recovered)", backend_id)
        elif state == CircuitState.CLOSED:
            self.failure_counts[backend_id] = max(0, self.failure_counts[backend_id] - 1)

    def record_failure(self, backend_id: str) -> None:
        """Record a failed request; may open the circuit."""
        state = self.states[backend_id]
        self.failure_counts[backend_id] += 1
        self.last_failure_times[backend_id] = time.time()
        if state == CircuitState.HALF_OPEN:
            self.states[backend_id] = CircuitState.OPEN
            logger.warning("Circuit breaker for %s: HALF_OPEN -> OPEN (test failed)", backend_id)
        elif (
            state == CircuitState.CLOSED
            and self.failure_counts[backend_id] >= self.failure_threshold
        ):
            self.states[backend_id] = CircuitState.OPEN
            logger.warning(
                "Circuit breaker for %s: CLOSED -> OPEN (%s failures)",
                backend_id,
                self.failure_counts[backend_id],
            )

    def get_state(self, backend_id: str) -> CircuitState:
        """Get current circuit state for backend"""
        return self.states[backend_id]

    def reset(self, backend_id: str) -> None:
        """Manually reset circuit for backend"""
        self.states[backend_id] = CircuitState.CLOSED
        self.failure_counts[backend_id] = 0
        self.half_open_calls[backend_id] = 0
        logger.info("Circuit breaker for %s: manually reset to CLOSED", backend_id)


@dataclass
class ExecutionResult:
    """Result from query execution"""

    success: bool
    response: str
    model_used: str
    execution_time_ms: float
    tokens_generated: int
    routing_decision: RoutingDecision | None = None
    fallbacks_used: int = 0
    error: str | None = None
    tool_calls: list[dict[str, Any]] | None = None  # LLM-requested tool calls (MCP dispatch)


class ExecutionEngine:
    """Executes queries with intelligent routing, fallback chains, and circuit breaker."""

    def __init__(
        self,
        registry: ModelRegistry,
        router: IntelligentRouter,
        config: dict[str, Any] | None = None,
    ):
        self.registry = registry
        self.router = router
        self.config = config or {}
        self.backends = {
            "ollama": OllamaBackend(
                base_url=self.config.get("ollama_base_url", "http://localhost:11434")
            ),
            "lmstudio": LMStudioBackend(
                base_url=self.config.get("lmstudio_base_url", "http://localhost:1234/v1")
            ),
            "mlx": MLXBackend(model_path=self.config.get("mlx_model_path")),
        }

        self.timeout_seconds = self.config.get("timeout_seconds", 60)
        self.circuit_breaker_enabled = self.config.get("circuit_breaker_enabled", True)
        self.circuit_breaker = (
            CircuitBreaker(
                failure_threshold=self.config.get("circuit_breaker_threshold", 3),
                recovery_timeout=self.config.get("circuit_breaker_timeout", 60),
                half_open_max_calls=self.config.get("circuit_breaker_half_open_calls", 1),
            )
            if self.circuit_breaker_enabled
            else None
        )

        logger.info(
            "ExecutionEngine initialized: circuit_breaker=%s, timeout=%ss",
            self.circuit_breaker_enabled,
            self.timeout_seconds,
        )

    async def _backend_ready(self, backend, backend_id: str) -> bool:
        """Return True if the backend passes circuit-breaker and availability checks."""
        if self.circuit_breaker:
            allowed, reason = self.circuit_breaker.should_allow_request(backend_id)
            if not allowed:
                logger.info("Circuit breaker blocked %s: %s", backend_id, reason)
                return False
        if not await backend.is_available():
            logger.warning("Backend %s not available", backend_id)
            if self.circuit_breaker:
                self.circuit_breaker.record_failure(backend_id)
            return False
        return True

    async def execute(
        self,
        query: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        max_cost: float = 1.0,
        messages: list[dict[str, Any]] | None = None,
    ) -> ExecutionResult:
        """Execute query with routing and fallback. Returns ExecutionResult."""
        start_time = time.time()
        decision = self.router.route(query, max_cost)
        model_chain = [decision.model_id] + decision.fallback_models
        fallbacks_used = 0
        last_error = None

        for model_id in model_chain:
            try:
                model = self.registry.get_model(model_id)
                if not model:
                    continue
                backend = self.backends.get(model.backend)
                if not backend:
                    logger.warning("No backend for %s", model.backend)
                    continue
                if not await self._backend_ready(backend, model.backend):
                    fallbacks_used += 1
                    continue
                result = await self._execute_with_timeout(
                    backend=backend,
                    model=model,
                    query=query,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=messages,
                )
                if result.success:
                    if self.circuit_breaker:
                        self.circuit_breaker.record_success(model.backend)
                    return ExecutionResult(
                        success=True,
                        response=result.text,
                        model_used=model.display_name,
                        execution_time_ms=(time.time() - start_time) * 1000,
                        tokens_generated=result.tokens_generated,
                        routing_decision=decision,
                        fallbacks_used=fallbacks_used,
                        tool_calls=result.tool_calls or [],
                    )
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure(model.backend)
                last_error = result.error
                fallbacks_used += 1
                logger.warning("Model %s failed: %s", model_id, result.error)
            except Exception as e:
                if model and model.backend and self.circuit_breaker:
                    self.circuit_breaker.record_failure(model.backend)
                last_error = str(e)
                fallbacks_used += 1
                logger.error("Error with model %s: %s", model_id, e)

        return ExecutionResult(
            success=False,
            response="",
            model_used="none",
            execution_time_ms=(time.time() - start_time) * 1000,
            tokens_generated=0,
            routing_decision=decision,
            fallbacks_used=fallbacks_used,
            error=f"All models failed. Last error: {last_error}",
        )

    async def _execute_with_timeout(
        self,
        backend,
        model: ModelMetadata,
        query: str,
        system_prompt: str | None,
        max_tokens: int,
        temperature: float,
        messages: list[dict[str, Any]] | None = None,
    ) -> GenerationResult:
        """Execute with timeout handling"""

        try:
            result = await asyncio.wait_for(
                backend.generate(
                    prompt=query,
                    model_name=model.api_model_name or model.model_id,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=messages,
                ),
                timeout=self.timeout_seconds,
            )
            return result

        except TimeoutError:
            return GenerationResult(
                text="",
                tokens_generated=0,
                time_ms=self.timeout_seconds * 1000,
                model_id=model.model_id,
                success=False,
                error=f"Timeout after {self.timeout_seconds}s",
            )

    async def generate_stream(
        self,
        query: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream generation token-by-token from the best available backend.

        Follows the same model-chain / circuit-breaker logic as execute() but
        calls each backend's generate_stream() so tokens flow to the caller as
        they are produced by Ollama rather than being buffered.
        """
        decision = self.router.route(query)
        model_chain = [decision.model_id] + decision.fallback_models

        for model_id in model_chain:
            model = self.registry.get_model(model_id)
            if not model:
                continue

            backend = self.backends.get(model.backend)
            if not backend:
                logger.warning("No backend for %s", model.backend)
                continue

            if not await self._backend_ready(backend, model.backend):
                continue

            try:
                yielded = False
                async for token in backend.generate_stream(
                    prompt=query,
                    model_name=model.api_model_name or model.model_id,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=messages,
                ):
                    yielded = True
                    yield token
                if yielded and self.circuit_breaker:
                    self.circuit_breaker.record_success(model.backend)
                return
            except Exception as e:
                logger.error("Streaming error with model %s: %s", model_id, e)
                if self.circuit_breaker:
                    self.circuit_breaker.record_failure(model.backend)
                continue

        logger.error("No models available for streaming")
        return

    async def close(self) -> None:
        """Close all backends"""
        for backend in self.backends.values():
            if hasattr(backend, "close"):
                await backend.close()

    async def health_check(self) -> dict[str, Any]:
        """Check health of all backends including circuit breaker status."""
        health = {}
        for name, backend in self.backends.items():
            try:
                info: dict[str, Any] = {"available": await backend.is_available()}
                if self.circuit_breaker:
                    info["circuit_state"] = self.circuit_breaker.get_state(name).value
                    info["failure_count"] = self.circuit_breaker.failure_counts[name]
                else:
                    info["circuit_state"] = "disabled"
                health[name] = info
            except Exception as e:
                health[name] = {
                    "available": False,
                    "circuit_state": self.circuit_breaker.get_state(name).value
                    if self.circuit_breaker
                    else "disabled",
                    "error": str(e),
                }
                logger.error("Health check failed for %s: %s", name, e)
        return health

    def get_circuit_breaker_status(self) -> dict[str, Any]:
        """Get circuit breaker status for all backends."""
        if not self.circuit_breaker:
            return {"enabled": False, "backends": {n: {"state": "disabled"} for n in self.backends}}
        return {
            "enabled": True,
            "backends": {
                name: {
                    "state": self.circuit_breaker.get_state(name).value,
                    "failure_count": self.circuit_breaker.failure_counts[name],
                    "last_failure_time": self.circuit_breaker.last_failure_times.get(name),
                }
                for name in self.backends
            },
        }

    def reset_circuit_breaker(self, backend_name: str) -> None:
        """Manually reset circuit breaker for a backend."""
        if not self.circuit_breaker:
            logger.warning("Circuit breaker is disabled, cannot reset")
            return

        if backend_name in self.backends:
            self.circuit_breaker.reset(backend_name)
            logger.info("Manually reset circuit breaker for %s", backend_name)
        else:
            logger.warning("Unknown backend: %s", backend_name)

    async def cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("Cleaning up ExecutionEngine...")
        await self.close()
        logger.info("ExecutionEngine cleanup complete")
