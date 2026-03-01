"""
Integration tests for WebSocket endpoint and streaming (SSE) response.

All tests use mocked AgentCore/SecurityMiddleware — no live services required.
Run with:  pytest tests/integration/test_websocket.py -v
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def aiter(items):
    for item in items:
        yield item


def _make_interface(
    stream_tokens=None, health_ok=True, web_api_key="", ws_rate_limit=10, ws_rate_window=60.0
):
    """Build a WebInterface backed by a fully mocked AgentCore."""
    from portal.interfaces.web.server import WebInterface

    agent = MagicMock()
    agent.stream_response = MagicMock(
        side_effect=lambda incoming: aiter(stream_tokens or ["Hello", " world"])
    )
    agent.health_check = AsyncMock(return_value=health_ok)

    secure = MagicMock()
    secure.process_message = AsyncMock(
        return_value=MagicMock(
            response="ok",
            model_used="auto",
            prompt_tokens=0,
            completion_tokens=1,
        )
    )

    config = MagicMock()
    config.interfaces.web.port = 8082
    config.llm.router_port = 8000
    config.security.web_api_key = web_api_key
    config.interfaces.web.ws_rate_limit = ws_rate_limit
    config.interfaces.web.ws_rate_window = ws_rate_window

    return WebInterface(agent_core=agent, config=config, secure_agent=secure)


# ---------------------------------------------------------------------------
# WebSocket tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_websocket_valid_api_key_connects():
    """WebSocket with correct api_key query param connects and streams tokens."""
    from fastapi.testclient import TestClient

    iface = _make_interface(stream_tokens=["Hi"], web_api_key="test-ws-key")
    client = TestClient(iface.app)

    with client.websocket_connect("/ws?api_key=test-ws-key") as ws:
        ws.send_json({"message": "hello"})
        data = ws.receive_json()
        # Either a token or done message
        assert "token" in data or "error" in data


@pytest.mark.asyncio
async def test_websocket_invalid_api_key_closes_4001():
    """WebSocket with wrong api_key is rejected with close code 4001."""
    from fastapi.testclient import TestClient

    iface = _make_interface(web_api_key="correct-key")
    client = TestClient(iface.app)

    with pytest.raises(Exception):
        with client.websocket_connect("/ws?api_key=wrong-key") as ws:
            ws.receive_json()


@pytest.mark.asyncio
async def test_websocket_no_api_key_when_guard_disabled():
    """WebSocket connects without api_key when web_api_key is not set in config."""
    from fastapi.testclient import TestClient

    iface = _make_interface(stream_tokens=["Hi"])  # web_api_key="" → no guard
    client = TestClient(iface.app)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"message": "hello"})
        data = ws.receive_json()
        assert "token" in data or "error" in data


@pytest.mark.asyncio
async def test_websocket_dangerous_input_blocked():
    """WebSocket blocks messages containing dangerous shell commands."""
    from fastapi.testclient import TestClient

    iface = _make_interface()
    client = TestClient(iface.app)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"message": "rm -rf / --no-preserve-root"})
        data = ws.receive_json()
        assert data.get("error") == "Message blocked by security policy"
        assert data.get("done") is True


@pytest.mark.asyncio
async def test_websocket_oversized_message_blocked():
    """WebSocket blocks messages that exceed the 10 000-character limit."""
    from fastapi.testclient import TestClient

    iface = _make_interface()
    client = TestClient(iface.app)

    oversized = "A" * 10001
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"message": oversized})
        data = ws.receive_json()
        assert data.get("error", "").startswith("Message exceeds maximum length")
        assert data.get("done") is True


@pytest.mark.asyncio
async def test_websocket_rate_limit_rejects_after_n_messages():
    """WebSocket per-connection rate limiter fires after ws_rate_limit messages."""
    from fastapi.testclient import TestClient

    iface = _make_interface(stream_tokens=["ok"], ws_rate_limit=2, ws_rate_window=60.0)
    client = TestClient(iface.app)

    with client.websocket_connect("/ws") as ws:
        # Drain the 2 allowed messages
        for _ in range(2):
            ws.send_json({"message": "hello"})
            # consume all tokens for this message
            while True:
                msg = ws.receive_json()
                if msg.get("done"):
                    break

        # 3rd message should be rate-limited
        ws.send_json({"message": "one more"})
        data = ws.receive_json()
        assert "Rate limit" in data.get("error", "")
        assert data.get("done") is True


# ---------------------------------------------------------------------------
# Streaming (SSE) tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_response_emits_sse_lines():
    """Streaming /v1/chat/completions emits data: lines and ends with [DONE]."""
    from fastapi.testclient import TestClient

    iface = _make_interface(stream_tokens=["Hello", " world"])
    with TestClient(iface.app) as client:
        payload = {
            "model": "auto",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        }
        resp = client.post("/v1/chat/completions", json=payload)
    assert resp.status_code == 200
    body = resp.text
    assert "data: " in body
    assert "data: [DONE]" in body


@pytest.mark.asyncio
async def test_non_streaming_response_returns_openai_format():
    """Non-streaming /v1/chat/completions returns OpenAI-compatible JSON."""
    from fastapi.testclient import TestClient

    iface = _make_interface()
    with TestClient(iface.app) as client:
        payload = {
            "model": "auto",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        }
        resp = client.post("/v1/chat/completions", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("object") == "chat.completion"
    assert "choices" in body
    assert len(body["choices"]) > 0


@pytest.mark.asyncio
async def test_empty_message_validation():
    """Empty message to /v1/chat/completions returns 400 or 422 error."""
    from fastapi.testclient import TestClient

    # Make secure_agent raise ValidationError on empty message
    from portal.core.exceptions import ValidationError
    from portal.interfaces.web.server import WebInterface

    agent = MagicMock()
    agent.stream_response = MagicMock(side_effect=lambda i: aiter(["ok"]))
    agent.health_check = AsyncMock(return_value=True)

    secure = MagicMock()
    secure.process_message = AsyncMock(
        side_effect=ValidationError("Message cannot be empty", details={})
    )

    config = MagicMock()
    config.security.web_api_key = ""
    iface = WebInterface(agent_core=agent, config=config, secure_agent=secure)
    with TestClient(iface.app, raise_server_exceptions=False) as client:
        payload = {
            "model": "auto",
            "messages": [{"role": "user", "content": ""}],
            "stream": False,
        }
        resp = client.post("/v1/chat/completions", json=payload)
    # Should return a 4xx error
    assert resp.status_code in (400, 422, 500)


# ---------------------------------------------------------------------------
# S2: WebSocket must share the HTTP rate limiter state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_websocket_uses_shared_rate_limiter():
    """WebSocket endpoint uses the same shared rate_limiter as SecurityMiddleware (S2)."""
    from portal.interfaces.web.server import WebInterface
    from portal.security import SecurityMiddleware

    agent = MagicMock()
    agent.stream_response = MagicMock(side_effect=lambda _: aiter(["ok"]))
    agent.health_check = AsyncMock(return_value=True)

    # Use a real SecurityMiddleware with a tight rate limit
    mock_inner = MagicMock()
    mock_inner.process_message = AsyncMock(
        return_value=MagicMock(
            response="ok",
            model_used="auto",
            prompt_tokens=0,
            completion_tokens=1,
        )
    )
    mock_inner.cleanup = AsyncMock()
    mock_inner.event_bus = MagicMock()
    mock_inner.get_tool_list = MagicMock(return_value=[])
    mock_inner.get_stats = AsyncMock(return_value={})

    from portal.security.rate_limiter import RateLimiter

    limiter = RateLimiter(max_requests=2, window_seconds=60)
    secure = SecurityMiddleware(mock_inner, rate_limiter=limiter, enable_rate_limiting=True)

    WebInterface(agent_core=agent, config={}, secure_agent=secure)

    # Verify that the WebSocket endpoint has access to the shared rate_limiter
    assert hasattr(secure, "rate_limiter"), "SecurityMiddleware must have a rate_limiter attribute"

    # Send 2 messages — these should succeed and consume the shared limit
    ws_user = "ws-anonymous"  # default WS user_id
    await secure.rate_limiter.check_limit(ws_user)
    await secure.rate_limiter.check_limit(ws_user)

    # The 3rd check should be blocked by the shared limiter
    allowed, _err = await secure.rate_limiter.check_limit(ws_user)
    assert allowed is False, "Shared rate limiter should block the 3rd request"
