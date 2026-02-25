"""
Integration tests for WebInterface.

All tests use a mocked AgentCore — no live Ollama or other services required.
Run with:  pytest tests/integration/test_web_interface.py -v
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock


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
    agent.stream_response = AsyncMock(
        return_value=aiter(stream_tokens or ["Hello", " world"])
    )
    agent.health_check = AsyncMock(return_value=health_ok)

    config = MagicMock()
    config.interfaces.web.port = 8082
    config.llm.router_port = 8000

    return WebInterface(agent_core=agent, config=config)


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_returns_200():
    """/health returns 200 with status ok."""
    from fastapi.testclient import TestClient

    iface = _make_interface()
    client = TestClient(iface.app)

    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_health_contains_version():
    """/health includes a version field from portal.__version__."""
    from fastapi.testclient import TestClient
    import portal

    iface = _make_interface()
    client = TestClient(iface.app)

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
    client = TestClient(iface.app)

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
    client = TestClient(iface.app)

    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["agent_core"] == "degraded"


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_security_headers_present():
    """/health response includes all mandatory security headers."""
    from fastapi.testclient import TestClient

    iface = _make_interface()
    client = TestClient(iface.app)

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
    client = TestClient(iface.app)

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
    from portal.interfaces.web.server import WebInterface

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
    import os
    from fastapi.testclient import TestClient
    from portal.interfaces.web.server import WebInterface

    monkeypatch.setenv("WEB_API_KEY", "test-secret-key")

    agent = MagicMock()
    agent.stream_response = AsyncMock(return_value=aiter(["hi"]))
    agent.health_check = AsyncMock(return_value=True)
    iface = WebInterface(agent_core=agent, config=MagicMock())
    client = TestClient(iface.app, raise_server_exceptions=False)

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
    import os
    from fastapi.testclient import TestClient
    from portal.interfaces.web.server import WebInterface

    monkeypatch.setenv("WEB_API_KEY", "test-secret-key")

    agent = MagicMock()
    agent.health_check = AsyncMock(return_value=True)
    iface = WebInterface(agent_core=agent, config=MagicMock())
    client = TestClient(iface.app)

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
    from fastapi import FastAPI
    from portal.interfaces.web.server import create_app
    from unittest.mock import patch

    mock_core = MagicMock()
    mock_core.health_check = AsyncMock(return_value=True)

    with patch("portal.interfaces.web.server.create_app") as _:
        app = create_app(agent_core=mock_core, config={})
        assert isinstance(app, FastAPI)
