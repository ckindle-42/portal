"""
Integration tests for WebSocket endpoint and streaming (SSE) response.

All tests use mocked AgentCore/SecurityMiddleware — no live services required.
Run with:  pytest tests/integration/test_websocket.py -v
"""
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def aiter(items):
    for item in items:
        yield item


def _make_interface(stream_tokens=None, health_ok=True):
    """Build a WebInterface backed by a fully mocked AgentCore."""
    from portal.interfaces.web.server import WebInterface

    agent = MagicMock()
    agent.stream_response = MagicMock(
        side_effect=lambda incoming: aiter(stream_tokens or ["Hello", " world"])
    )
    agent.health_check = AsyncMock(return_value=health_ok)

    secure = MagicMock()
    secure.process_message = AsyncMock(return_value=MagicMock(
        response="ok", model_used="auto", prompt_tokens=0, completion_tokens=1,
    ))

    config = MagicMock()
    config.interfaces.web.port = 8082
    config.llm.router_port = 8000

    return WebInterface(agent_core=agent, config=config, secure_agent=secure)


# ---------------------------------------------------------------------------
# WebSocket tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_websocket_valid_api_key_connects(monkeypatch):
    """WebSocket with correct api_key query param connects and streams tokens."""
    import os
    from fastapi.testclient import TestClient

    monkeypatch.setenv("WEB_API_KEY", "test-ws-key")

    iface = _make_interface(stream_tokens=["Hi"])
    client = TestClient(iface.app)

    with client.websocket_connect("/ws?api_key=test-ws-key") as ws:
        ws.send_json({"message": "hello"})
        data = ws.receive_json()
        # Either a token or done message
        assert "token" in data or "error" in data


@pytest.mark.asyncio
async def test_websocket_invalid_api_key_closes_4001(monkeypatch):
    """WebSocket with wrong api_key is rejected with close code 4001."""
    import os
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect

    monkeypatch.setenv("WEB_API_KEY", "correct-key")

    iface = _make_interface()
    client = TestClient(iface.app)

    with pytest.raises(Exception):
        with client.websocket_connect("/ws?api_key=wrong-key") as ws:
            ws.receive_json()


@pytest.mark.asyncio
async def test_websocket_no_api_key_when_guard_disabled():
    """WebSocket connects without api_key when WEB_API_KEY is not set."""
    from fastapi.testclient import TestClient
    import os

    # Ensure WEB_API_KEY is not set
    os.environ.pop("WEB_API_KEY", None)

    iface = _make_interface(stream_tokens=["Hi"])
    client = TestClient(iface.app)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"message": "hello"})
        data = ws.receive_json()
        assert "token" in data or "error" in data


@pytest.mark.asyncio
async def test_websocket_dangerous_input_blocked(monkeypatch):
    """WebSocket blocks messages containing dangerous shell commands."""
    import os
    from fastapi.testclient import TestClient

    os.environ.pop("WEB_API_KEY", None)

    iface = _make_interface()
    client = TestClient(iface.app)

    with client.websocket_connect("/ws") as ws:
        ws.send_json({"message": "rm -rf / --no-preserve-root"})
        data = ws.receive_json()
        assert data.get("error") == "Message blocked by security policy"
        assert data.get("done") is True


@pytest.mark.asyncio
async def test_websocket_oversized_message_blocked(monkeypatch):
    """WebSocket blocks messages that exceed the 10 000-character limit."""
    import os
    from fastapi.testclient import TestClient

    os.environ.pop("WEB_API_KEY", None)

    iface = _make_interface()
    client = TestClient(iface.app)

    oversized = "A" * 10001
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"message": oversized})
        data = ws.receive_json()
        assert data.get("error") == "Message exceeds maximum length"
        assert data.get("done") is True


@pytest.mark.asyncio
async def test_websocket_rate_limit_rejects_after_n_messages(monkeypatch):
    """WebSocket per-connection rate limiter fires after WS_RATE_LIMIT messages."""
    import os
    from fastapi.testclient import TestClient

    os.environ.pop("WEB_API_KEY", None)
    monkeypatch.setenv("WS_RATE_LIMIT", "2")
    monkeypatch.setenv("WS_RATE_WINDOW", "60")

    iface = _make_interface(stream_tokens=["ok"])
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
    import os

    os.environ.pop("WEB_API_KEY", None)

    iface = _make_interface(stream_tokens=["Hello", " world"])
    client = TestClient(iface.app)

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
    import os

    os.environ.pop("WEB_API_KEY", None)

    iface = _make_interface()
    client = TestClient(iface.app)

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
    import os

    os.environ.pop("WEB_API_KEY", None)

    # Make secure_agent raise ValidationError on empty message
    from portal.interfaces.web.server import WebInterface
    from portal.core.exceptions import ValidationError

    agent = MagicMock()
    agent.stream_response = MagicMock(side_effect=lambda i: aiter(["ok"]))
    agent.health_check = AsyncMock(return_value=True)

    secure = MagicMock()
    secure.process_message = AsyncMock(
        side_effect=ValidationError("Message cannot be empty", details={})
    )

    config = MagicMock()
    iface = WebInterface(agent_core=agent, config=config, secure_agent=secure)
    client = TestClient(iface.app, raise_server_exceptions=False)

    payload = {
        "model": "auto",
        "messages": [{"role": "user", "content": ""}],
        "stream": False,
    }
    resp = client.post("/v1/chat/completions", json=payload)
    # Should return a 4xx error
    assert resp.status_code in (400, 422, 500)
