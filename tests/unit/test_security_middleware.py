"""Tests for SecurityMiddleware wrapper."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from portal.core.exceptions import PolicyViolationError, ValidationError
from portal.security.middleware import SecurityMiddleware


@pytest.fixture
def mock_agent_core():
    """Mock AgentCore for SecurityMiddleware tests."""
    core = AsyncMock()
    core.process_message = AsyncMock(return_value=MagicMock(
        success=True, response="ok", warnings=[]
    ))
    return core


@pytest.fixture
def middleware(mock_agent_core):
    """SecurityMiddleware with mocked AgentCore."""
    return SecurityMiddleware(
        agent_core=mock_agent_core,
        enable_rate_limiting=False,  # Disable to avoid async rate limiter in non-async tests
        enable_input_sanitization=True,
    )


@pytest.mark.asyncio
async def test_clean_message_passes_through(middleware, mock_agent_core):
    """A clean message passes security checks and reaches AgentCore."""
    result = await middleware.process_message(
        chat_id="test",
        message="Hello world",
        interface="web",
        user_context={"user_id": "user1"},
    )
    assert result.success is True
    mock_agent_core.process_message.assert_called_once()


@pytest.mark.asyncio
async def test_dangerous_command_blocked(middleware):
    """Dangerous system commands are blocked by security policy."""
    with pytest.raises(PolicyViolationError):
        await middleware.process_message(
            chat_id="test",
            message="rm -rf /",
            interface="web",
            user_context={"user_id": "user1"},
        )


@pytest.mark.asyncio
async def test_message_length_limit(middleware):
    """Messages exceeding the length limit raise ValidationError."""
    long_message = "x" * 10001
    with pytest.raises(ValidationError):
        await middleware.process_message(
            chat_id="test",
            message=long_message,
            interface="web",
            user_context={"user_id": "user1"},
        )


@pytest.mark.asyncio
async def test_safe_message_not_blocked(middleware, mock_agent_core):
    """Safe messages are not blocked."""
    safe_messages = [
        "What is the capital of France?",
        "Explain quantum computing",
        "Write a poem about the sea",
    ]
    for msg in safe_messages:
        result = await middleware.process_message(
            chat_id="test",
            message=msg,
            interface="web",
            user_context={"user_id": "user1"},
        )
        assert result.success is True


@pytest.mark.asyncio
async def test_rate_limiting_enforced(tmp_path):
    """When rate limiting is enabled, excessive requests are blocked."""
    core = AsyncMock()
    core.process_message = AsyncMock(return_value=MagicMock(success=True, response="ok", warnings=[]))

    from portal.core.exceptions import RateLimitError
    from portal.security.security_module import RateLimiter

    # Very restrictive: 1 request per window; use tmp_path to avoid persistent state
    rate_limiter = RateLimiter(
        max_requests=1,
        window_seconds=60,
        persist_path=tmp_path / "rate_limits.json",
    )

    mw = SecurityMiddleware(
        agent_core=core,
        rate_limiter=rate_limiter,
        enable_rate_limiting=True,
        enable_input_sanitization=False,
    )

    # First request should go through
    result = await mw.process_message(
        chat_id="chat1", message="hello", interface="web",
        user_context={"user_id": "user_rate_test"}
    )
    assert result.success is True

    # Second request should be blocked
    with pytest.raises(RateLimitError):
        await mw.process_message(
            chat_id="chat1", message="hello again", interface="web",
            user_context={"user_id": "user_rate_test"}
        )


@pytest.mark.asyncio
async def test_no_user_id_skips_rate_limit(mock_agent_core):
    """Requests without user_id skip rate limiting entirely."""
    mw = SecurityMiddleware(
        agent_core=mock_agent_core,
        enable_rate_limiting=True,
        enable_input_sanitization=False,
    )
    # Should not raise even with rate limiting enabled
    result = await mw.process_message(
        chat_id="chat1", message="hello", interface="web",
        user_context={}  # No user_id
    )
    assert result.success is True
