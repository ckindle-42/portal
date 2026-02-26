"""
Unit tests for ModelRegistry.discover_from_ollama().

Because discover_from_ollama() does a local ``import httpx`` inside the
function, we patch ``httpx.AsyncClient`` directly rather than via the
module's namespace.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from portal.routing.model_registry import ModelCapability, ModelRegistry


def _model_id(ollama_name: str) -> str:
    """Replicate the model_id derivation used in discover_from_ollama."""
    return f"ollama_{ollama_name.replace(':', '_').replace('/', '_')}"


def _make_mock_client(json_payload: dict | None = None, side_effect=None):
    """Return a mocked httpx.AsyncClient context manager."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    if json_payload is not None:
        mock_response.json.return_value = json_payload

    mock_client = AsyncMock()
    if side_effect is not None:
        mock_client.get = AsyncMock(side_effect=side_effect)
    else:
        mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    return mock_client


class TestDiscoverFromOllama:
    """Tests for the dynamic Ollama model discovery."""

    @pytest.mark.asyncio
    async def test_discover_registers_new_models(self):
        """Models returned by Ollama /api/tags are added to the registry."""
        payload = {
            "models": [
                {"name": "llama3.2:3b", "size": 2_000_000_000},
                {"name": "qwen2.5:7b", "size": 5_000_000_000},
            ]
        }
        mock_client = _make_mock_client(payload)

        registry = ModelRegistry()

        with patch("httpx.AsyncClient", return_value=mock_client):
            newly = await registry.discover_from_ollama()

        assert _model_id("llama3.2:3b") in registry.models
        assert _model_id("qwen2.5:7b") in registry.models
        assert len(newly) == 2

    @pytest.mark.asyncio
    async def test_discover_does_not_duplicate_existing_models(self):
        """Models already in the registry are not registered twice."""
        payload = {"models": [{"name": "qwen2.5:7b", "size": 5_000_000_000}]}
        mock_client = _make_mock_client(payload)

        registry = ModelRegistry()
        with patch("httpx.AsyncClient", return_value=mock_client):
            first = await registry.discover_from_ollama()
            second = await registry.discover_from_ollama()

        assert len(first) == 1
        assert len(second) == 0, "Second call should not re-register existing models"

    @pytest.mark.asyncio
    async def test_discover_handles_connection_error_gracefully(self):
        """A network error returns empty list without raising."""
        mock_client = _make_mock_client(side_effect=httpx.ConnectError("refused"))

        registry = ModelRegistry()
        original_count = len(registry.models)

        with patch("httpx.AsyncClient", return_value=mock_client):
            newly = await registry.discover_from_ollama()

        assert newly == []
        assert len(registry.models) == original_count

    @pytest.mark.asyncio
    async def test_discover_sets_general_capability(self):
        """Dynamically discovered models receive GENERAL capability by default."""
        payload = {"models": [{"name": "test-model:latest", "size": 1_000_000_000}]}
        mock_client = _make_mock_client(payload)

        registry = ModelRegistry()
        with patch("httpx.AsyncClient", return_value=mock_client):
            await registry.discover_from_ollama()

        mid = _model_id("test-model:latest")
        model = registry.get_model(mid)
        assert model is not None
        assert ModelCapability.GENERAL in model.capabilities
        assert model.backend == "ollama"
        assert model.available is True

    @pytest.mark.asyncio
    async def test_discover_returns_only_new_model_ids(self):
        """Return value contains only the newly registered model_ids."""
        payload = {
            "models": [
                {"name": "alpha:latest", "size": 1_000_000_000},
                {"name": "beta:latest", "size": 2_000_000_000},
            ]
        }
        mock_client = _make_mock_client(payload)

        registry = ModelRegistry()
        with patch("httpx.AsyncClient", return_value=mock_client):
            newly = await registry.discover_from_ollama()

        assert set(newly) == {_model_id("alpha:latest"), _model_id("beta:latest")}
