"""
Unit tests for MCPRegistry — dynamic server add/remove and retry transport.

Uses unittest.mock to avoid real network calls.
"""

from __future__ import annotations

import pickle
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from portal.protocols.mcp.mcp_registry import MCPRegistry


class TestMCPRegistryServerManagement:
    """Tests for registering and removing MCP servers."""

    @pytest.mark.asyncio
    async def test_register_adds_server(self):
        """Registering a server makes it appear in list_servers()."""
        registry = MCPRegistry()
        await registry.register("fs", "http://localhost:9000", transport="openapi")

        assert "fs" in registry.list_servers()
        await registry.close()

    @pytest.mark.asyncio
    async def test_register_stores_metadata(self):
        """Registered server metadata (url, transport, api_key) is preserved."""
        registry = MCPRegistry()
        await registry.register(
            "fs", "http://localhost:9000/", transport="openapi", api_key="secret"
        )

        server = registry._servers["fs"]
        assert server["url"] == "http://localhost:9000"  # trailing slash stripped
        assert server["transport"] == "openapi"
        assert server["api_key"] == "secret"
        await registry.close()

    @pytest.mark.asyncio
    async def test_register_multiple_servers(self):
        """Multiple servers can be registered independently."""
        registry = MCPRegistry()
        await registry.register("alpha", "http://a:9000")
        await registry.register("beta", "http://b:9000", transport="streamable-http")

        names = registry.list_servers()
        assert "alpha" in names
        assert "beta" in names
        await registry.close()

    @pytest.mark.asyncio
    async def test_list_servers_empty_initially(self):
        """A fresh registry has no registered servers."""
        registry = MCPRegistry()
        assert registry.list_servers() == []
        await registry.close()

    @pytest.mark.asyncio
    async def test_overwrite_server(self):
        """Re-registering with the same name overwrites the old entry."""
        registry = MCPRegistry()
        await registry.register("svc", "http://old:9000")
        await registry.register("svc", "http://new:9000")

        assert registry._servers["svc"]["url"] == "http://new:9000"
        assert len(registry.list_servers()) == 1
        await registry.close()


class TestMCPRegistryHealthCheck:
    """Tests for health_check()."""

    @pytest.mark.asyncio
    async def test_health_check_unknown_server_returns_false(self):
        """health_check on an unregistered name returns False."""
        registry = MCPRegistry()
        result = await registry.health_check("nonexistent")
        assert result is False
        await registry.close()

    @pytest.mark.asyncio
    async def test_health_check_ok_returns_true(self):
        """health_check returns True when the server responds with 2xx."""
        registry = MCPRegistry()
        await registry.register("ok-svc", "http://localhost:9001", transport="openapi")

        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch.object(registry, "_request", AsyncMock(return_value=mock_resp)):
            result = await registry.health_check("ok-svc")

        assert result is True
        await registry.close()

    @pytest.mark.asyncio
    async def test_health_check_server_error_returns_false(self):
        """health_check returns False when server responds with 5xx."""
        registry = MCPRegistry()
        await registry.register("bad-svc", "http://localhost:9002", transport="openapi")

        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch.object(registry, "_request", AsyncMock(return_value=mock_resp)):
            result = await registry.health_check("bad-svc")

        assert result is False
        await registry.close()

    @pytest.mark.asyncio
    async def test_health_check_connection_error_returns_false(self):
        """health_check returns False when a network error occurs."""
        registry = MCPRegistry()
        await registry.register("dead-svc", "http://nowhere:9999")

        with patch.object(
            registry, "_request", AsyncMock(side_effect=httpx.ConnectError("refused"))
        ):
            result = await registry.health_check("dead-svc")

        assert result is False
        await registry.close()


class TestMCPRegistryListTools:
    """Tests for list_tools()."""

    @pytest.mark.asyncio
    async def test_list_tools_unknown_server_returns_empty(self):
        """list_tools on an unknown server returns []."""
        registry = MCPRegistry()
        result = await registry.list_tools("no-such-server")
        assert result == []
        await registry.close()

    @pytest.mark.asyncio
    async def test_list_tools_openapi_transport(self):
        """list_tools parses OpenAPI paths into tool dicts."""
        registry = MCPRegistry()
        await registry.register("tools-svc", "http://localhost:9000", transport="openapi")

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "paths": {
                "/read_file": {
                    "post": {"operationId": "read_file", "summary": "Read a file"}
                },
                "/list_dir": {
                    "get": {"operationId": "list_dir", "summary": "List directory"}
                },
            }
        }

        with patch.object(registry, "_request", AsyncMock(return_value=mock_resp)):
            tools = await registry.list_tools("tools-svc")

        names = [t["name"] for t in tools]
        assert "read_file" in names
        assert "list_dir" in names
        await registry.close()

    @pytest.mark.asyncio
    async def test_list_tools_streamable_transport(self):
        """list_tools returns tools list for streamable-http transport."""
        registry = MCPRegistry()
        await registry.register(
            "stream-svc", "http://localhost:9000", transport="streamable-http"
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tools": [{"name": "ping", "description": "Ping the server"}]
        }

        with patch.object(registry, "_request", AsyncMock(return_value=mock_resp)):
            tools = await registry.list_tools("stream-svc")

        assert len(tools) == 1
        assert tools[0]["name"] == "ping"
        await registry.close()


class TestMCPRegistryRetryLogic:
    """Tests for _request() retry behaviour."""

    @pytest.mark.asyncio
    async def test_request_succeeds_first_attempt(self):
        """_request returns immediately when first attempt succeeds."""
        registry = MCPRegistry()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        call_count = 0

        async def fake_request(method, url, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_resp

        with patch.object(registry._client, "request", side_effect=fake_request):
            result = await registry._request("GET", "http://example.com")

        assert result.status_code == 200
        assert call_count == 1
        await registry.close()

    @pytest.mark.asyncio
    async def test_request_retries_on_connect_error(self):
        """_request retries ConnectError up to _RETRY_DELAYS times then raises."""
        from portal.protocols.mcp.mcp_registry import _RETRY_DELAYS

        registry = MCPRegistry()

        call_count = 0

        async def always_fail(method, url, **kwargs):
            nonlocal call_count
            call_count += 1
            raise httpx.ConnectError("refused")

        with patch.object(registry._client, "request", side_effect=always_fail):
            with patch("portal.protocols.mcp.mcp_registry.asyncio.sleep", AsyncMock()):
                with pytest.raises(httpx.ConnectError):
                    await registry._request("GET", "http://example.com")

        # 1 initial + len(_RETRY_DELAYS) retries
        assert call_count == 1 + len(_RETRY_DELAYS)
        await registry.close()

    @pytest.mark.asyncio
    async def test_request_succeeds_on_second_attempt(self):
        """_request returns successfully if a retry attempt succeeds."""
        registry = MCPRegistry()
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        attempts = []

        async def flaky(method, url, **kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise httpx.ConnectError("temporary failure")
            return mock_resp

        with patch.object(registry._client, "request", side_effect=flaky):
            with patch("portal.protocols.mcp.mcp_registry.asyncio.sleep", AsyncMock()):
                result = await registry._request("GET", "http://example.com")

        assert result.status_code == 200
        assert len(attempts) == 2
        await registry.close()


# ---------------------------------------------------------------------------
# Pickle deserialization gating (merged from test_pickle_gating.py)
# ---------------------------------------------------------------------------


class TestPickleGating:
    """Verify KnowledgeBaseSQLite pickle deserialization security gate."""

    def _make_instance(self):
        """Create an EnhancedKnowledgeTool instance (no DB needed for unit test)."""
        import unittest.mock as mock

        from portal.tools.knowledge.knowledge_base_sqlite import EnhancedKnowledgeTool
        with mock.patch("sqlite3.connect"):
            inst = EnhancedKnowledgeTool.__new__(EnhancedKnowledgeTool)
            inst.conn = None
            inst.db_path = ":memory:"
        return inst

    def _pickle_blob(self, arr) -> bytes:
        return pickle.dumps(arr)

    def test_default_returns_none_for_pickle_blob(self, monkeypatch):
        """Without the env flag, pickle blobs must return None."""
        np = pytest.importorskip("numpy")
        monkeypatch.delenv("ALLOW_LEGACY_PICKLE_EMBEDDINGS", raising=False)
        result = self._make_instance()._deserialize_embedding(self._pickle_blob(np.array([0.1, 0.2, 0.3])))
        assert result is None

    def test_flag_false_returns_none(self, monkeypatch):
        np = pytest.importorskip("numpy")
        monkeypatch.setenv("ALLOW_LEGACY_PICKLE_EMBEDDINGS", "false")
        result = self._make_instance()._deserialize_embedding(self._pickle_blob(np.array([0.1, 0.2, 0.3])))
        assert result is None

    @pytest.mark.parametrize("flag_value", ["true", "1", "yes"])
    def test_flag_enabled_loads_correctly(self, monkeypatch, flag_value):
        np = pytest.importorskip("numpy")
        monkeypatch.setenv("ALLOW_LEGACY_PICKLE_EMBEDDINGS", flag_value)
        arr = np.array([1.0, 2.0, 3.0])
        result = self._make_instance()._deserialize_embedding(self._pickle_blob(arr))
        assert result is not None
        np.testing.assert_allclose(result, arr)

    def test_json_blob_always_works(self, monkeypatch):
        import json

        np = pytest.importorskip("numpy")
        monkeypatch.delenv("ALLOW_LEGACY_PICKLE_EMBEDDINGS", raising=False)
        arr = np.array([0.5, 0.6, 0.7])
        json_blob = json.dumps(arr.tolist()).encode("utf-8")
        result = self._make_instance()._deserialize_embedding(json_blob)
        assert result is not None
        np.testing.assert_allclose(result, arr)
