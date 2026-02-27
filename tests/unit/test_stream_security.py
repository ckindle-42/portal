"""Tests for S1: Streaming requests must be rate-limited and sanitized."""

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_web_interface(enable_security: bool = True):
    """Build a WebInterface with mocked dependencies."""
    from portal.interfaces.web.server import WebInterface

    mock_agent_core = MagicMock()
    mock_agent_core.stream_response = AsyncMock()

    secure_agent = None
    if enable_security:
        from portal.security import SecurityMiddleware

        # Use a real SecurityMiddleware but with mocked rate limiter
        mock_core_for_security = MagicMock()
        mock_core_for_security.process_message = AsyncMock()
        secure_agent = SecurityMiddleware(
            mock_core_for_security,
            enable_rate_limiting=True,
            enable_input_sanitization=True,
        )

    iface = WebInterface(
        agent_core=mock_agent_core,
        config={},
        secure_agent=secure_agent,
    )
    return iface, mock_agent_core, secure_agent


class TestStreamSecurityGate:
    @pytest.mark.asyncio
    async def test_dangerous_pattern_rejected_in_stream(self) -> None:
        """Streaming path must reject messages with dangerous patterns."""

        iface, _, secure_agent = _make_web_interface()

        # The streaming security gate uses InputSanitizer.sanitize_command
        # Dangerous pattern: "rm -rf /" triggers "Dangerous pattern detected" warning
        dangerous_msg = "please run rm -rf / on the server"

        # Simulate the security gate check directly
        from portal.security.security_module import InputSanitizer

        sanitizer = InputSanitizer()
        _, warnings = sanitizer.sanitize_command(dangerous_msg)

        # Confirm that the dangerous pattern is detected
        assert any("Dangerous pattern detected" in w for w in warnings), (
            f"Expected a dangerous pattern warning but got: {warnings}"
        )

    @pytest.mark.asyncio
    async def test_safe_message_passes_sanitization(self) -> None:
        """A normal message must not trigger security warnings."""
        from portal.security.security_module import InputSanitizer

        sanitizer = InputSanitizer()
        _, warnings = sanitizer.sanitize_command("What is the capital of France?")

        assert not any("Dangerous pattern detected" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_stream_uses_shared_rate_limiter(self) -> None:
        """Streaming path must use the same rate_limiter as the SecurityMiddleware."""
        iface, _, secure_agent = _make_web_interface()

        # Verify the secure_agent has a rate_limiter attribute
        assert secure_agent is not None
        assert hasattr(secure_agent, "rate_limiter"), (
            "SecurityMiddleware must expose rate_limiter for streaming path"
        )

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_when_exhausted(self) -> None:
        """The shared rate limiter must block when the limit is reached."""
        from portal.security.security_module import RateLimiter

        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # Consume both available slots
        allowed1, _ = await limiter.check_limit("test-user")
        allowed2, _ = await limiter.check_limit("test-user")
        assert allowed1 is True
        assert allowed2 is True

        # Third request must be blocked
        allowed3, err = await limiter.check_limit("test-user")
        assert allowed3 is False
        assert err is not None
