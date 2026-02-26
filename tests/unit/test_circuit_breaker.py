"""
Tests for CircuitBreaker state machine in execution_engine.py.
"""

import time

from portal.routing.execution_engine import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    """Test CircuitBreaker state transitions (per-backend tracking)."""

    @staticmethod
    def _allowed(cb: CircuitBreaker, backend: str) -> bool:
        allowed, _reason = cb.should_allow_request(backend)
        return allowed

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        assert self._allowed(cb, "test-backend")
        assert cb.states["test-backend"] == CircuitState.CLOSED

    def test_failures_below_threshold_stays_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        cb.record_failure("b1")
        cb.record_failure("b1")
        assert cb.states["b1"] == CircuitState.CLOSED
        assert self._allowed(cb, "b1")

    def test_failures_at_threshold_opens_circuit(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        cb.record_failure("b1")
        cb.record_failure("b1")
        cb.record_failure("b1")
        assert cb.states["b1"] == CircuitState.OPEN
        assert not self._allowed(cb, "b1")

    def test_success_decrements_failure_count_in_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        cb.record_failure("b1")
        cb.record_failure("b1")
        cb.record_success("b1")
        assert cb.failure_counts["b1"] <= 1
        assert cb.states["b1"] == CircuitState.CLOSED

    def test_open_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure("b1")
        assert cb.states["b1"] == CircuitState.OPEN
        time.sleep(0.15)
        assert self._allowed(cb, "b1")
        assert cb.states["b1"] == CircuitState.HALF_OPEN

    def test_half_open_success_closes_circuit(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure("b1")
        time.sleep(0.15)
        self._allowed(cb, "b1")  # triggers HALF_OPEN
        assert cb.states["b1"] == CircuitState.HALF_OPEN
        cb.record_success("b1")
        assert cb.states["b1"] == CircuitState.CLOSED
        assert cb.failure_counts["b1"] == 0

    def test_half_open_failure_reopens_circuit(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
        cb.record_failure("b1")
        time.sleep(0.15)
        self._allowed(cb, "b1")  # triggers HALF_OPEN
        cb.record_failure("b1")
        assert cb.states["b1"] == CircuitState.OPEN

    def test_independent_backends(self):
        """Failures on one backend don't affect another."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)
        cb.record_failure("a")
        cb.record_failure("a")
        assert cb.states["a"] == CircuitState.OPEN
        assert self._allowed(cb, "b")
        assert cb.states["b"] == CircuitState.CLOSED

    def test_manual_reset(self):
        """reset() returns a backend to CLOSED with zero failures."""
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        cb.record_failure("b1")
        assert cb.states["b1"] == CircuitState.OPEN
        cb.reset("b1")
        assert cb.states["b1"] == CircuitState.CLOSED
        assert cb.failure_counts["b1"] == 0
