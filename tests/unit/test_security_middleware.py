"""Tests for SecurityMiddleware wrapper."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from portal.core.exceptions import PolicyViolationError, RateLimitError, ValidationError
from portal.security.middleware import SecurityMiddleware


@pytest.fixture
def mock_agent_core():
    """Mock AgentCore for SecurityMiddleware tests."""
    core = AsyncMock()
    core.process_message = AsyncMock(
        return_value=MagicMock(success=True, response="ok", warnings=[])
    )
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
    core.process_message = AsyncMock(
        return_value=MagicMock(success=True, response="ok", warnings=[])
    )

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
        chat_id="chat1",
        message="hello",
        interface="web",
        user_context={"user_id": "user_rate_test"},
    )
    assert result.success is True

    # Second request should be blocked
    with pytest.raises(RateLimitError):
        await mw.process_message(
            chat_id="chat1",
            message="hello again",
            interface="web",
            user_context={"user_id": "user_rate_test"},
        )


@pytest.mark.asyncio
async def test_no_user_id_but_still_rate_limited_by_chat_id(tmp_path):
    """Requests without user_id are still rate limited using chat_id as fallback."""
    from portal.security.security_module import RateLimiter

    core = AsyncMock()
    core.process_message = AsyncMock(
        return_value=MagicMock(success=True, response="ok", warnings=[])
    )

    # Very restrictive: 1 request per window
    rate_limiter = RateLimiter(
        max_requests=1,
        window_seconds=60,
        persist_path=tmp_path / "rate_limits_anon.json",
    )

    mw = SecurityMiddleware(
        agent_core=core,
        rate_limiter=rate_limiter,
        enable_rate_limiting=True,
        enable_input_sanitization=False,
    )
    # First request should go through
    result = await mw.process_message(
        chat_id="chat_anonymous",
        message="hello",
        interface="web",
        user_context={},  # No user_id
    )
    assert result.success is True

    # Second request from same chat_id should be rate limited
    with pytest.raises(RateLimitError):
        await mw.process_message(
            chat_id="chat_anonymous",
            message="hello again",
            interface="web",
            user_context={},  # No user_id - uses chat_id for rate limiting
        )


@pytest.mark.asyncio
async def test_rate_limiting_without_user_id_ip_fallback(tmp_path):
    """Rate limiting uses IP address when user_id and chat_id are unavailable."""
    from portal.security.security_module import RateLimiter

    core = AsyncMock()
    core.process_message = AsyncMock(
        return_value=MagicMock(success=True, response="ok", warnings=[])
    )

    # Very restrictive: 1 request per window
    rate_limiter = RateLimiter(
        max_requests=1,
        window_seconds=60,
        persist_path=tmp_path / "rate_limits_ip.json",
    )

    mw = SecurityMiddleware(
        agent_core=core,
        rate_limiter=rate_limiter,
        enable_rate_limiting=True,
        enable_input_sanitization=False,
    )
    # First request with IP should go through
    result = await mw.process_message(
        chat_id="chat1",
        message="hello",
        interface="web",
        user_context={"ip_address": "192.168.1.100"},
    )
    assert result.success is True

    # Second request from same IP should be rate limited
    with pytest.raises(RateLimitError):
        await mw.process_message(
            chat_id="chat1",
            message="hello again",
            interface="web",
            user_context={"ip_address": "192.168.1.100"},
        )


@pytest.mark.asyncio
async def test_empty_message_blocked():
    """Empty message raises ValidationError."""
    core = AsyncMock()
    mw = SecurityMiddleware(
        agent_core=core,
        enable_rate_limiting=False,
        enable_input_sanitization=False,
    )
    with pytest.raises(ValidationError, match="empty"):
        await mw.process_message("chat1", "", "web")


@pytest.mark.asyncio
async def test_whitespace_only_blocked():
    """Whitespace-only message raises ValidationError."""
    core = AsyncMock()
    mw = SecurityMiddleware(
        agent_core=core,
        enable_rate_limiting=False,
        enable_input_sanitization=False,
    )
    with pytest.raises(ValidationError, match="empty"):
        await mw.process_message("chat1", "   \n\t  ", "web")


@pytest.mark.asyncio
async def test_files_forwarded(mock_agent_core):
    """Files parameter is forwarded to AgentCore."""
    mw = SecurityMiddleware(
        agent_core=mock_agent_core,
        enable_rate_limiting=False,
        enable_input_sanitization=False,
    )
    files = [MagicMock()]
    await mw.process_message("chat1", "hello", "web", files=files)
    call_kwargs = mock_agent_core.process_message.call_args.kwargs
    assert call_kwargs["files"] is files


@pytest.mark.asyncio
async def test_execute_tool_forwards():
    """execute_tool forwards to agent_core."""
    core = AsyncMock()
    core.execute_tool = AsyncMock(return_value={"result": "ok"})
    mw = SecurityMiddleware(core, enable_rate_limiting=False)
    result = await mw.execute_tool("search", {"q": "test"})
    assert result == {"result": "ok"}


def test_get_rate_limit_stats():
    """get_rate_limit_stats delegates to rate_limiter."""
    core = MagicMock()
    limiter = MagicMock()
    limiter.get_stats.return_value = {"requests": 5}
    mw = SecurityMiddleware(core, rate_limiter=limiter)
    assert mw.get_rate_limit_stats("u1") == {"requests": 5}


def test_reset_rate_limit():
    """reset_rate_limit delegates to rate_limiter."""
    core = MagicMock()
    limiter = MagicMock()
    mw = SecurityMiddleware(core, rate_limiter=limiter)
    mw.reset_rate_limit("u1")
    limiter.reset_user.assert_called_once_with("u1")


@pytest.mark.asyncio
async def test_cleanup_forwards():
    """cleanup delegates to agent_core."""
    core = AsyncMock()
    mw = SecurityMiddleware(core)
    await mw.cleanup()
    core.cleanup.assert_called_once()


@pytest.mark.asyncio
async def test_rate_limit_retry_after_extraction():
    """Rate limit error extracts wait seconds from message."""
    from portal.core.exceptions import RateLimitError

    core = AsyncMock()
    limiter = MagicMock()
    limiter.check_limit = AsyncMock(return_value=(False, "Rate limit exceeded, wait 45 seconds"))
    mw = SecurityMiddleware(core, rate_limiter=limiter)
    with pytest.raises(RateLimitError) as exc_info:
        await mw.process_message("chat1", "hello", "web", user_context={"user_id": "u1"})
    assert exc_info.value.retry_after == 45


@pytest.mark.asyncio
async def test_warnings_appended_to_result_no_existing():
    """Warnings are set on result when result has no existing warnings list."""
    core = AsyncMock()
    result_obj = MagicMock(spec=[])  # No warnings attr
    core.process_message = AsyncMock(return_value=result_obj)
    sanitizer = MagicMock()
    sanitizer.sanitize_command.return_value = ("text", ["minor warning"])
    mw = SecurityMiddleware(core, enable_rate_limiting=False, input_sanitizer=sanitizer)
    result = await mw.process_message("chat1", "text", "web")
    assert hasattr(result, "warnings")


@pytest.mark.asyncio
async def test_custom_max_message_length():
    """Custom max_message_length is respected."""
    core = AsyncMock()
    mw = SecurityMiddleware(
        core, enable_rate_limiting=False, enable_input_sanitization=False, max_message_length=20
    )
    with pytest.raises(ValidationError, match="maximum length"):
        await mw.process_message("chat1", "x" * 21, "web")
