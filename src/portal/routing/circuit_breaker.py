"""Circuit Breaker — prevents retrying repeatedly failing backends."""

import logging
import time
from collections import defaultdict
from enum import Enum

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
