"""ModelRegistry.discover_from_ollama tests — mocked HTTP."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from portal.routing.model_registry import ModelCapability, ModelRegistry, SpeedClass


class TestDiscoverFromOllama:
    @pytest.mark.asyncio
    async def test_registers_new_models(self) -> None:
        registry = ModelRegistry()
        initial_count = len(registry.models)

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "models": [
                {"name": "custom-model:latest", "size": 7_000_000_000},
            ]
        }
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        # httpx is imported lazily inside discover_from_ollama via `import httpx`
        import httpx

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            newly = await registry.discover_from_ollama()

        assert len(newly) == 1
        assert len(registry.models) == initial_count + 1
        model_id = newly[0]
        model = registry.get_model(model_id)
        assert model is not None
        assert model.backend == "ollama"
        assert model.available is True

    @pytest.mark.asyncio
    async def test_marks_others_unavailable(self) -> None:
        registry = ModelRegistry()
        existing = registry.get_model("ollama_qwen25_05b")
        assert existing is not None
        assert existing.available is True

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"models": []}
        mock_resp.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        import httpx

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            await registry.discover_from_ollama(mark_others_unavailable=True)

        assert existing.available is False

    @pytest.mark.asyncio
    async def test_handles_connection_failure_gracefully(self) -> None:
        registry = ModelRegistry()
        initial_count = len(registry.models)

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        import httpx

        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            newly = await registry.discover_from_ollama()

        assert newly == []
        assert len(registry.models) == initial_count


class TestModelRegistryQueries:
    def test_get_fastest_model(self) -> None:
        registry = ModelRegistry()
        fastest = registry.get_fastest_model()
        assert fastest is not None
        assert fastest.speed_class in (SpeedClass.ULTRA_FAST, SpeedClass.FAST)

    def test_get_fastest_model_with_capability(self) -> None:
        registry = ModelRegistry()
        fastest_code = registry.get_fastest_model(ModelCapability.CODE)
        assert fastest_code is not None
        assert ModelCapability.CODE in fastest_code.capabilities

    def test_get_best_quality_code_model(self) -> None:
        registry = ModelRegistry()
        best = registry.get_best_quality_model(ModelCapability.CODE)
        assert best is not None
        assert best.code_quality >= 0.7

    def test_get_models_by_backend(self) -> None:
        registry = ModelRegistry()
        ollama_models = registry.get_models_by_backend("ollama")
        assert len(ollama_models) > 0
        assert all(m.backend == "ollama" for m in ollama_models)

    def test_update_availability(self) -> None:
        registry = ModelRegistry()
        model_id = list(registry.models.keys())[0]
        registry.update_availability(model_id, False)
        assert registry.get_model(model_id).available is False
        registry.update_availability(model_id, True)
        assert registry.get_model(model_id).available is True
