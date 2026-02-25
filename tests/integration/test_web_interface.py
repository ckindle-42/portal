"""
Integration test for WebInterface.
Requires: Ollama running with at least one model pulled.
"""
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock


async def aiter(items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_webinterface_health():
    """WebInterface health endpoint returns 200."""
    from portal.interfaces.web.server import WebInterface

    config = MagicMock()
    config.interfaces.web.port = 8082  # Use different port for testing
    config.llm.router_port = 8000

    agent = MagicMock()
    agent.stream_response = AsyncMock(return_value=aiter(["Hello", " world"]))

    iface = WebInterface(agent_core=agent, config=config)

    # Use httpx TestClient (sync, no server needed)
    from fastapi.testclient import TestClient
    client = TestClient(iface.app)

    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_webinterface_models():
    """WebInterface /v1/models returns model list."""
    from portal.interfaces.web.server import WebInterface
    from fastapi.testclient import TestClient

    config = MagicMock()
    config.llm.router_port = 8000

    iface = WebInterface(agent_core=MagicMock(), config=config)
    client = TestClient(iface.app)

    resp = client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert len(data["data"]) > 0


@pytest.mark.asyncio
async def test_webinterface_routes():
    """WebInterface has all required routes."""
    from portal.interfaces.web.server import WebInterface

    config = MagicMock()
    iface = WebInterface(agent_core=MagicMock(), config=config)

    route_paths = [r.path for r in iface.app.routes]
    assert "/v1/chat/completions" in route_paths
    assert "/v1/models" in route_paths
    assert "/ws" in route_paths
    assert "/health" in route_paths
