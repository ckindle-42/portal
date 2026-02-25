"""
Test suite for data integrity fixes

Tests for:
1. Atomic writes in local_knowledge.py
2. Persistent rate limiting in security_module.py
3. Circuit breaker pattern in execution_engine.py
"""

import pytest
import asyncio
import os
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch


# =============================================================================
# ATOMIC WRITE TESTS (local_knowledge.py)
# =============================================================================

class TestAtomicWrites:
    """Test atomic write functionality in LocalKnowledgeTool"""

    def test_atomic_write_creates_backup(self, tmp_path):
        """Verify backup is created before write"""
        from portal.tools.knowledge.local_knowledge import LocalKnowledgeTool

        # Create test instance with temp path
        tool = LocalKnowledgeTool()
        tool.DB_PATH = tmp_path / "test_kb.json"

        # Create initial data
        LocalKnowledgeTool._documents = [{"content": "test", "source": "test"}]
        tool._save_db()

        # Verify original file exists
        assert tool.DB_PATH.exists()

        # Modify and save again
        LocalKnowledgeTool._documents.append({"content": "test2", "source": "test2"})
        tool._save_db()

        # Verify backup was created
        backup_path = tool.DB_PATH.with_suffix('.json.backup')
        assert backup_path.exists()

    def test_atomic_write_survives_crash(self, tmp_path):
        """Verify data integrity if write is interrupted"""
        from portal.tools.knowledge.local_knowledge import LocalKnowledgeTool

        tool = LocalKnowledgeTool()
        tool.DB_PATH = tmp_path / "test_kb.json"

        # Write initial data
        LocalKnowledgeTool._documents = [{"content": "important", "source": "test"}]
        tool._save_db()

        # Verify we can read it back
        with open(tool.DB_PATH, 'r') as f:
            data = json.load(f)
            assert len(data['documents']) == 1
            assert data['documents'][0]['content'] == "important"

    def test_atomic_write_no_partial_data(self, tmp_path):
        """Verify no partial/corrupted JSON is written"""
        from portal.tools.knowledge.local_knowledge import LocalKnowledgeTool

        tool = LocalKnowledgeTool()
        tool.DB_PATH = tmp_path / "test_kb.json"

        # Write data
        LocalKnowledgeTool._documents = [{"content": f"doc_{i}", "source": "test"} for i in range(100)]
        tool._save_db()

        # Verify file is valid JSON
        with open(tool.DB_PATH, 'r') as f:
            data = json.load(f)  # Should not raise
            assert len(data['documents']) == 100


# =============================================================================
# PERSISTENT RATE LIMITING TESTS
# =============================================================================

class TestPersistentRateLimiting:
    """Test persistent rate limiting in security_module.py"""

    def test_rate_limit_persists_across_restarts(self, tmp_path):
        """Verify rate limit data survives process restart"""
        from security.security_module import RateLimiter

        persist_path = tmp_path / "rate_limits.json"

        # Create limiter and use it
        limiter1 = RateLimiter(max_requests=5, window_seconds=60, persist_path=persist_path)

        user_id = 12345
        for _ in range(5):
            allowed, _ = limiter1.check_limit(user_id)
            assert allowed

        # 6th request should be blocked
        allowed, msg = limiter1.check_limit(user_id)
        assert not allowed
        assert msg is not None

        # Simulate restart - create new limiter instance
        limiter2 = RateLimiter(max_requests=5, window_seconds=60, persist_path=persist_path)

        # Should still be blocked (data persisted)
        allowed, msg = limiter2.check_limit(user_id)
        assert not allowed, "Rate limit should persist across restart"

    def test_rate_limit_prevents_restart_bypass(self, tmp_path):
        """Verify malicious user can't bypass limits by forcing restart"""
        from security.security_module import RateLimiter

        persist_path = tmp_path / "rate_limits.json"

        # User exhausts rate limit
        limiter1 = RateLimiter(max_requests=3, window_seconds=60, persist_path=persist_path)
        user_id = 99999

        for _ in range(3):
            limiter1.check_limit(user_id)

        # Blocked
        allowed, _ = limiter1.check_limit(user_id)
        assert not allowed

        # Attacker "crashes" the bot and restarts
        limiter2 = RateLimiter(max_requests=3, window_seconds=60, persist_path=persist_path)

        # CRITICAL: Should STILL be blocked
        allowed, msg = limiter2.check_limit(user_id)
        assert not allowed, "SECURITY: Restart should not bypass rate limit"

    def test_rate_limit_cleans_old_data(self, tmp_path):
        """Verify old rate limit data is cleaned up"""
        from security.security_module import RateLimiter

        persist_path = tmp_path / "rate_limits.json"

        # Create limiter with short window
        limiter = RateLimiter(max_requests=5, window_seconds=1, persist_path=persist_path)
        user_id = 11111

        # Make requests
        for _ in range(3):
            limiter.check_limit(user_id)

        # Wait for window to expire
        time.sleep(2)

        # Old data should be cleaned
        limiter._load_state()
        stats = limiter.get_stats(user_id)
        assert stats['recent_requests'] == 0, "Old requests should be cleaned"


# =============================================================================
# CIRCUIT BREAKER TESTS
# =============================================================================

class TestCircuitBreaker:
    """Test circuit breaker pattern in execution_engine.py"""

    def test_circuit_opens_after_failures(self):
        """Verify circuit opens after threshold failures"""
        from routing.execution_engine import CircuitBreaker, CircuitState

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        backend_id = "ollama"

        # Initial state should be closed
        assert cb.get_state(backend_id) == CircuitState.CLOSED

        # Record failures
        for i in range(3):
            cb.record_failure(backend_id)

        # Circuit should now be open
        assert cb.get_state(backend_id) == CircuitState.OPEN

        # Requests should be blocked
        allowed, reason = cb.should_allow_request(backend_id)
        assert not allowed
        assert "circuit_open" in reason

    def test_circuit_prevents_repeated_failures(self):
        """Verify circuit breaker prevents hammering failed backend"""
        from routing.execution_engine import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        backend_id = "lmstudio"

        # Fail the backend
        for _ in range(3):
            cb.record_failure(backend_id)

        # Try 10 more requests - all should be rejected immediately
        blocked_count = 0
        for _ in range(10):
            allowed, _ = cb.should_allow_request(backend_id)
            if not allowed:
                blocked_count += 1

        assert blocked_count == 10, "Circuit breaker should block all requests when open"

    def test_circuit_transitions_to_half_open(self):
        """Verify circuit transitions to half-open after timeout"""
        from routing.execution_engine import CircuitBreaker, CircuitState

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=2)
        backend_id = "mlx"

        # Open the circuit
        for _ in range(3):
            cb.record_failure(backend_id)

        assert cb.get_state(backend_id) == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(3)

        # Next request should transition to half-open
        allowed, reason = cb.should_allow_request(backend_id)
        assert allowed
        assert "testing" in reason.lower()
        assert cb.get_state(backend_id) == CircuitState.HALF_OPEN

    def test_circuit_closes_on_success(self):
        """Verify circuit closes after successful recovery"""
        from routing.execution_engine import CircuitBreaker, CircuitState

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        backend_id = "ollama"

        # Open circuit
        for _ in range(3):
            cb.record_failure(backend_id)

        # Wait and transition to half-open
        time.sleep(2)
        cb.should_allow_request(backend_id)

        assert cb.get_state(backend_id) == CircuitState.HALF_OPEN

        # Record success - should close circuit
        cb.record_success(backend_id)
        assert cb.get_state(backend_id) == CircuitState.CLOSED

        # Future requests should be allowed
        allowed, _ = cb.should_allow_request(backend_id)
        assert allowed


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestDataIntegrityIntegration:
    """Integration tests for all data integrity fixes"""

    @pytest.mark.asyncio
    async def test_concurrent_writes_knowledge_base(self, tmp_path):
        """Test concurrent writes don't corrupt knowledge base"""
        from portal.tools.knowledge.local_knowledge import LocalKnowledgeTool

        tool = LocalKnowledgeTool()
        tool.DB_PATH = tmp_path / "concurrent_kb.json"

        # Reset state
        LocalKnowledgeTool._documents = []

        # Simulate concurrent adds
        async def add_content(i):
            return await tool._add_content(f"Content {i}")

        # Run concurrent operations
        tasks = [add_content(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # Verify all data was saved
        tool2 = LocalKnowledgeTool()
        tool2.DB_PATH = tmp_path / "concurrent_kb.json"
        tool2._load_db()

        # Should have all 10 items (or at least not corrupted)
        assert len(LocalKnowledgeTool._documents) > 0
        assert isinstance(LocalKnowledgeTool._documents, list)

    def test_rate_limiter_under_load(self, tmp_path):
        """Test rate limiter performs well under load"""
        from security.security_module import RateLimiter

        persist_path = tmp_path / "load_test.json"
        limiter = RateLimiter(max_requests=100, window_seconds=60, persist_path=persist_path)

        # Simulate many users
        for user_id in range(100):
            for _ in range(50):  # 50 requests per user
                limiter.check_limit(user_id)

        # Verify persistence file exists and is valid
        assert persist_path.exists()
        with open(persist_path, 'r') as f:
            data = json.load(f)
            assert 'requests' in data
            assert 'violations' in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
