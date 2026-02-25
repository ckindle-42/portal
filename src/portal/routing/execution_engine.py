"""
Execution Engine - Handles model execution with fallbacks and retries
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from collections import defaultdict
from enum import Enum

from .model_registry import ModelRegistry, ModelMetadata
from .model_backends import OllamaBackend, LMStudioBackend, MLXBackend, GenerationResult
from .intelligent_router import IntelligentRouter, RoutingDecision

logger = logging.getLogger(__name__)


# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failures detected, rejecting requests
    HALF_OPEN = "half_open" # Testing if backend has recovered


class CircuitBreaker:
    """
    Circuit breaker pattern for backend failures.

    Prevents repeatedly trying a failing backend, improving response times
    and reducing wasted resources.
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 60,
                 half_open_max_calls: int = 1):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Failures before opening circuit
            recovery_timeout: Seconds before attempting recovery
            half_open_max_calls: Max calls to allow in half-open state
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        # Per-backend state tracking
        self.failure_counts: Dict[str, int] = defaultdict(int)
        self.states: Dict[str, CircuitState] = defaultdict(lambda: CircuitState.CLOSED)
        self.last_failure_times: Dict[str, float] = {}
        self.half_open_calls: Dict[str, int] = defaultdict(int)

    def should_allow_request(self, backend_id: str) -> tuple[bool, str]:
        """
        Check if request should be allowed to backend.

        Args:
            backend_id: Backend identifier

        Returns:
            (allowed, reason)
        """
        state = self.states[backend_id]

        if state == CircuitState.CLOSED:
            # Normal operation
            return True, "circuit_closed"

        elif state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            last_failure = self.last_failure_times.get(backend_id, 0)
            if time.time() - last_failure >= self.recovery_timeout:
                # Transition to half-open for testing
                self.states[backend_id] = CircuitState.HALF_OPEN
                self.half_open_calls[backend_id] = 0
                logger.info(f"Circuit breaker for {backend_id}: OPEN -> HALF_OPEN")
                return True, "circuit_testing_recovery"
            else:
                # Still in timeout period
                wait_time = int(self.recovery_timeout - (time.time() - last_failure))
                return False, f"circuit_open_wait_{wait_time}s"

        elif state == CircuitState.HALF_OPEN:
            # Allow limited requests for testing
            if self.half_open_calls[backend_id] < self.half_open_max_calls:
                self.half_open_calls[backend_id] += 1
                return True, "circuit_half_open_testing"
            else:
                return False, "circuit_half_open_limit_reached"

        return False, "circuit_unknown_state"

    def record_success(self, backend_id: str):
        """Record successful request"""
        state = self.states[backend_id]

        if state == CircuitState.HALF_OPEN:
            # Recovery successful, close the circuit
            self.states[backend_id] = CircuitState.CLOSED
            self.failure_counts[backend_id] = 0
            self.half_open_calls[backend_id] = 0
            logger.info(f"Circuit breaker for {backend_id}: HALF_OPEN -> CLOSED (recovered)")
        elif state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_counts[backend_id] = max(0, self.failure_counts[backend_id] - 1)

    def record_failure(self, backend_id: str):
        """Record failed request"""
        state = self.states[backend_id]
        self.failure_counts[backend_id] += 1
        self.last_failure_times[backend_id] = time.time()

        if state == CircuitState.HALF_OPEN:
            # Failed during testing, reopen circuit
            self.states[backend_id] = CircuitState.OPEN
            logger.warning(f"Circuit breaker for {backend_id}: HALF_OPEN -> OPEN (test failed)")

        elif state == CircuitState.CLOSED:
            # Check if threshold exceeded
            if self.failure_counts[backend_id] >= self.failure_threshold:
                self.states[backend_id] = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker for {backend_id}: CLOSED -> OPEN "
                    f"({self.failure_counts[backend_id]} failures)"
                )

    def get_state(self, backend_id: str) -> CircuitState:
        """Get current circuit state for backend"""
        return self.states[backend_id]

    def reset(self, backend_id: str):
        """Manually reset circuit for backend"""
        self.states[backend_id] = CircuitState.CLOSED
        self.failure_counts[backend_id] = 0
        self.half_open_calls[backend_id] = 0
        logger.info(f"Circuit breaker for {backend_id}: manually reset to CLOSED")


@dataclass
class ExecutionResult:
    """Result from query execution"""
    success: bool
    response: str
    model_used: str
    execution_time_ms: float
    tokens_generated: int
    routing_decision: Optional[RoutingDecision] = None
    fallbacks_used: int = 0
    error: Optional[str] = None


class ExecutionEngine:
    """
    Executes queries with intelligent routing and fallback handling

    RELIABILITY FIX: Now includes circuit breaker pattern to prevent
    repeatedly trying failed backends.
    """

    def __init__(self, registry: ModelRegistry, router: IntelligentRouter,
                 config: Optional[Dict[str, Any]] = None):
        self.registry = registry
        self.router = router
        self.config = config or {}

        # Initialize backends
        self.backends = {
            'ollama': OllamaBackend(
                base_url=self.config.get('ollama_base_url', 'http://localhost:11434')
            ),
            'lmstudio': LMStudioBackend(
                base_url=self.config.get('lmstudio_base_url', 'http://localhost:1234/v1')
            ),
            'mlx': MLXBackend(
                model_path=self.config.get('mlx_model_path')
            )
        }

        # Execution settings
        self.max_retries = self.config.get('max_retries', 3)
        self.timeout_seconds = self.config.get('timeout_seconds', 60)

        # Circuit breaker for backend failure protection (v4.6.2: Made configurable)
        self.circuit_breaker_enabled = self.config.get('circuit_breaker_enabled', True)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=self.config.get('circuit_breaker_threshold', 3),
            recovery_timeout=self.config.get('circuit_breaker_timeout', 60),
            half_open_max_calls=self.config.get('circuit_breaker_half_open_calls', 1)
        ) if self.circuit_breaker_enabled else None

        logger.info(
            f"ExecutionEngine initialized",
            circuit_breaker_enabled=self.circuit_breaker_enabled,
            max_retries=self.max_retries,
            timeout_seconds=self.timeout_seconds
        )
    
    async def execute(self, query: str, system_prompt: Optional[str] = None,
                     max_tokens: int = 2048, temperature: float = 0.7,
                     max_cost: float = 1.0) -> ExecutionResult:
        """
        Execute query with intelligent routing and fallback
        
        Args:
            query: User query
            system_prompt: Optional system prompt
            max_tokens: Maximum output tokens
            temperature: Generation temperature
            max_cost: Maximum cost factor
            
        Returns:
            ExecutionResult with response or error
        """
        start_time = time.time()
        
        # Get routing decision
        decision = self.router.route(query, max_cost)
        
        # Build model chain (primary + fallbacks)
        model_chain = [decision.model_id] + decision.fallback_models
        
        fallbacks_used = 0
        last_error = None
        
        # Try each model in chain
        for model_id in model_chain:
            try:
                model = self.registry.get_model(model_id)
                if not model:
                    continue

                # Get backend
                backend = self.backends.get(model.backend)
                if not backend:
                    logger.warning(f"No backend for {model.backend}")
                    continue

                # Check circuit breaker (v4.6.2: Skip if disabled)
                if self.circuit_breaker:
                    allowed, reason = self.circuit_breaker.should_allow_request(model.backend)
                    if not allowed:
                        logger.info(f"Circuit breaker blocked {model.backend}: {reason}")
                        fallbacks_used += 1
                        continue

                # Check availability
                if not await backend.is_available():
                    logger.warning(f"Backend {model.backend} not available")
                    if self.circuit_breaker:
                        self.circuit_breaker.record_failure(model.backend)
                    continue

                # Execute generation
                result = await self._execute_with_timeout(
                    backend=backend,
                    model=model,
                    query=query,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                )

                if result.success:
                    # Record success in circuit breaker
                    if self.circuit_breaker:
                        self.circuit_breaker.record_success(model.backend)

                    elapsed = (time.time() - start_time) * 1000

                    return ExecutionResult(
                        success=True,
                        response=result.text,
                        model_used=model.display_name,
                        execution_time_ms=elapsed,
                        tokens_generated=result.tokens_generated,
                        routing_decision=decision,
                        fallbacks_used=fallbacks_used
                    )
                else:
                    # Record failure in circuit breaker
                    if self.circuit_breaker:
                        self.circuit_breaker.record_failure(model.backend)
                    last_error = result.error
                    fallbacks_used += 1
                    logger.warning(f"Model {model_id} failed: {result.error}")

            except Exception as e:
                # Record exception as failure
                if model and model.backend and self.circuit_breaker:
                    self.circuit_breaker.record_failure(model.backend)
                last_error = str(e)
                fallbacks_used += 1
                logger.error(f"Error with model {model_id}: {e}")
        
        # All models failed
        elapsed = (time.time() - start_time) * 1000
        
        return ExecutionResult(
            success=False,
            response="",
            model_used="none",
            execution_time_ms=elapsed,
            tokens_generated=0,
            routing_decision=decision,
            fallbacks_used=fallbacks_used,
            error=f"All models failed. Last error: {last_error}"
        )
    
    async def _execute_with_timeout(self, backend, model: ModelMetadata,
                                   query: str, system_prompt: Optional[str],
                                   max_tokens: int, temperature: float) -> GenerationResult:
        """Execute with timeout handling"""
        
        try:
            result = await asyncio.wait_for(
                backend.generate(
                    prompt=query,
                    model_name=model.api_model_name or model.model_id,
                    system_prompt=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature
                ),
                timeout=self.timeout_seconds
            )
            return result
        
        except asyncio.TimeoutError:
            return GenerationResult(
                text="",
                tokens_generated=0,
                time_ms=self.timeout_seconds * 1000,
                model_id=model.model_id,
                success=False,
                error=f"Timeout after {self.timeout_seconds}s"
            )
    
    async def execute_parallel(self, queries: List[str],
                              system_prompt: Optional[str] = None) -> List[ExecutionResult]:
        """Execute multiple queries in parallel"""
        
        tasks = [
            self.execute(query, system_prompt)
            for query in queries
        ]
        
        return await asyncio.gather(*tasks)
    
    async def close(self):
        """Close all backends"""
        for backend in self.backends.values():
            if hasattr(backend, 'close'):
                await backend.close()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of all backends including circuit breaker status

        v4.6.2: Enhanced to handle disabled circuit breaker
        """
        health = {}

        for name, backend in self.backends.items():
            try:
                is_available = await backend.is_available()

                health_info = {
                    'available': is_available
                }

                # Add circuit breaker info if enabled
                if self.circuit_breaker:
                    circuit_state = self.circuit_breaker.get_state(name)
                    health_info['circuit_state'] = circuit_state.value
                    health_info['failure_count'] = self.circuit_breaker.failure_counts[name]
                else:
                    health_info['circuit_state'] = 'disabled'

                health[name] = health_info

            except Exception as e:
                health[name] = {
                    'available': False,
                    'circuit_state': self.circuit_breaker.get_state(name).value if self.circuit_breaker else 'disabled',
                    'error': str(e)
                }
                logger.error(f"Health check failed for {name}: {e}")

        return health

    def get_circuit_breaker_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get detailed circuit breaker status for all backends

        v4.6.2: Returns disabled status when circuit breaker is off
        """
        if not self.circuit_breaker:
            return {
                'enabled': False,
                'backends': {name: {'state': 'disabled'} for name in self.backends.keys()}
            }

        status = {'enabled': True, 'backends': {}}

        for backend_name in self.backends.keys():
            status['backends'][backend_name] = {
                'state': self.circuit_breaker.get_state(backend_name).value,
                'failure_count': self.circuit_breaker.failure_counts[backend_name],
                'last_failure_time': self.circuit_breaker.last_failure_times.get(backend_name)
            }

        return status

    def reset_circuit_breaker(self, backend_name: str):
        """
        Manually reset circuit breaker for a backend

        v4.6.2: Safe handling when circuit breaker is disabled
        """
        if not self.circuit_breaker:
            logger.warning("Circuit breaker is disabled, cannot reset")
            return

        if backend_name in self.backends:
            self.circuit_breaker.reset(backend_name)
            logger.info(f"Manually reset circuit breaker for {backend_name}")
        else:
            logger.warning(f"Unknown backend: {backend_name}")

    async def cleanup(self):
        """
        Cleanup resources

        v4.6.2: Added cleanup method for graceful shutdown
        """
        logger.info("Cleaning up ExecutionEngine...")
        await self.close()
        logger.info("ExecutionEngine cleanup complete")
