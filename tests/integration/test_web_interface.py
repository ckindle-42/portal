"""
Integration tests for WebInterface.

All tests use a mocked AgentCore — no live Ollama or other services required.
Run with:  pytest tests/integration/test_web_interface.py -v
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def aiter(items):
    for item in items:
        yield item


def _make_interface(stream_tokens=None, health_ok=True):
    """Build a WebInterface backed by a fully mocked AgentCore."""
    from portal.interfaces.web.server import WebInterface

    _tokens = stream_tokens or ["Hello", " world"]

    agent = MagicMock()
    # stream_response is called without await, so use MagicMock returning an async gen
    agent.stream_response = MagicMock(side_effect=lambda _: aiter(_tokens))
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

    return WebInterface(agent_core=agent, config=config, secure_agent=secure)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_returns_200():
    """/health returns 200 with status ok (or warming_up during startup)."""
    from fastapi.testclient import TestClient

    iface = _make_interface()
    with TestClient(iface.app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("ok", "warming_up")


@pytest.mark.asyncio
async def test_health_contains_version():
    """/health includes a version field from portal.__version__."""
    from fastapi.testclient import TestClient

    import portal

    iface = _make_interface()
    with TestClient(iface.app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "version" in body
    assert body["version"] == portal.__version__


@pytest.mark.asyncio
async def test_health_contains_build_info():
    """/health includes build metadata (python_version, timestamp)."""
    from fastapi.testclient import TestClient

    iface = _make_interface()
    with TestClient(iface.app) as client:
        resp = client.get("/health")
    body = resp.json()
    assert "build" in body
    assert "python_version" in body["build"]
    assert "timestamp" in body["build"]


@pytest.mark.asyncio
async def test_health_reflects_agent_core_degraded():
    """/health shows 'degraded' when AgentCore.health_check() returns False."""
    from fastapi.testclient import TestClient

    iface = _make_interface(health_ok=False)
    with TestClient(iface.app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    # agent_core is either "degraded" (after warmup) or "warming_up" (before warmup completes)
    assert body.get("agent_core") in ("degraded", "warming_up")


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_security_headers_present():
    """/health response includes all mandatory security headers."""
    from fastapi.testclient import TestClient

    iface = _make_interface()
    with TestClient(iface.app) as client:
        resp = client.get("/health")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("x-xss-protection") == "1; mode=block"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "content-security-policy" in resp.headers


# ---------------------------------------------------------------------------
# Models endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_models_returns_list():
    """/v1/models returns an object-list even when Ollama is unreachable."""
    from fastapi.testclient import TestClient

    iface = _make_interface()
    with TestClient(iface.app) as client:
        resp = client.get("/v1/models")
    assert resp.status_code == 200
    body = resp.json()
    assert body["object"] == "list"
    assert isinstance(body["data"], list)
    assert len(body["data"]) > 0


# ---------------------------------------------------------------------------
# Route completeness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_required_routes_exist():
    """WebInterface exposes all documented routes."""

    iface = _make_interface()
    route_paths = [r.path for r in iface.app.routes]

    assert "/v1/chat/completions" in route_paths
    assert "/v1/models" in route_paths
    assert "/ws" in route_paths
    assert "/health" in route_paths


# ---------------------------------------------------------------------------
# API key guard
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_key_guard_blocks_without_key(monkeypatch):
    """/v1/chat/completions returns 401 when WEB_API_KEY is set and header is missing."""
    from fastapi.testclient import TestClient

    from portal.interfaces.web.server import WebInterface

    monkeypatch.setenv("WEB_API_KEY", "test-secret-key")

    agent = MagicMock()
    agent.stream_response = MagicMock(side_effect=lambda _: aiter(["hi"]))
    agent.health_check = AsyncMock(return_value=True)
    secure = MagicMock()
    secure.process_message = AsyncMock(
        return_value=MagicMock(
            response="ok",
            model_used="auto",
            prompt_tokens=0,
            completion_tokens=1,
        )
    )
    iface = WebInterface(agent_core=agent, config=MagicMock(), secure_agent=secure)
    with TestClient(iface.app, raise_server_exceptions=False) as client:
        payload = {
            "model": "auto",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        }
        resp = client.post("/v1/chat/completions", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_key_guard_passes_with_bearer(monkeypatch):
    """/v1/models returns 200 when correct Bearer token is provided."""
    from fastapi.testclient import TestClient

    from portal.interfaces.web.server import WebInterface

    monkeypatch.setenv("WEB_API_KEY", "test-secret-key")

    agent = MagicMock()
    agent.health_check = AsyncMock(return_value=True)
    secure = MagicMock()
    secure.process_message = AsyncMock(
        return_value=MagicMock(
            response="ok",
            model_used="auto",
            prompt_tokens=0,
            completion_tokens=1,
        )
    )
    iface = WebInterface(agent_core=agent, config=MagicMock(), secure_agent=secure)
    with TestClient(iface.app) as client:
        resp = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer test-secret-key"},
        )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# create_app factory
# ---------------------------------------------------------------------------


def test_create_app_returns_fastapi_instance():
    """create_app() returns a FastAPI instance without raising."""
    from unittest.mock import patch

    from fastapi import FastAPI

    from portal.interfaces.web.server import create_app

    mock_core = MagicMock()
    mock_core.health_check = AsyncMock(return_value=True)

    with patch("portal.interfaces.web.server.create_app") as _:
        app = create_app(agent_core=mock_core, config={})
        assert isinstance(app, FastAPI)


# ---------------------------------------------------------------------------
# Streaming response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_response_emits_sse_done():
    """/v1/chat/completions stream=True emits SSE data: lines ending with [DONE]."""
    import os

    from fastapi.testclient import TestClient

    os.environ.pop("WEB_API_KEY", None)

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
async def test_non_streaming_returns_openai_format():
    """/v1/chat/completions stream=False returns an OpenAI-compatible JSON body."""
    import os

    from fastapi.testclient import TestClient

    os.environ.pop("WEB_API_KEY", None)

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
async def test_empty_message_returns_error():
    """Empty message content causes a non-200 response via SecurityMiddleware."""
    import os

    from fastapi.testclient import TestClient

    from portal.core.exceptions import ValidationError
    from portal.interfaces.web.server import WebInterface

    os.environ.pop("WEB_API_KEY", None)

    agent = MagicMock()
    agent.stream_response = MagicMock(side_effect=lambda _: aiter(["ok"]))
    agent.health_check = AsyncMock(return_value=True)

    secure = MagicMock()
    secure.process_message = AsyncMock(
        side_effect=ValidationError("Message cannot be empty", details={})
    )

    config = MagicMock()
    iface = WebInterface(agent_core=agent, config=config, secure_agent=secure)
    with TestClient(iface.app, raise_server_exceptions=False) as client:
        payload = {
            "model": "auto",
            "messages": [{"role": "user", "content": ""}],
            "stream": False,
        }
        resp = client.post("/v1/chat/completions", json=payload)
    assert resp.status_code in (400, 422, 500)


# ---------------------------------------------------------------------------
# E2: Startup readiness gate — 503 while agent is warming up
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_completions_returns_503_during_warmup():
    """/v1/chat/completions returns 503 with Retry-After while agent is warming up."""
    import asyncio
    import os

    from fastapi.testclient import TestClient

    from portal.interfaces.web.server import WebInterface

    os.environ.pop("WEB_API_KEY", None)

    agent = MagicMock()
    # health_check hangs forever so _agent_ready never gets set during TestClient startup
    hang_event = asyncio.Event()

    async def _slow_health():
        await asyncio.wait_for(hang_event.wait(), timeout=0.01)

    agent.health_check = _slow_health
    secure = MagicMock()
    del secure.rate_limiter

    iface = WebInterface(agent_core=agent, config={}, secure_agent=secure)

    # Use raise_server_exceptions=False so we see the 503 response
    with TestClient(iface.app, raise_server_exceptions=False) as client:
        payload = {
            "model": "auto",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
        }
        resp = client.post("/v1/chat/completions", json=payload)

    # During warmup the server must return 503 with Retry-After
    assert resp.status_code == 503
    body = resp.json()
    assert "error" in body
    assert "starting up" in body["error"]["message"].lower()
    assert "retry-after" in resp.headers
