"""ModelRegistry.discover_from_ollama tests — mocked HTTP."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from portal.routing.model_registry import ModelCapability, ModelRegistry, SpeedClass


def _model_id(ollama_name: str) -> str:
    """Replicate the model_id derivation used in discover_from_ollama."""
    return f"ollama_{ollama_name.replace(':', '_').replace('/', '_')}"


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

    @pytest.mark.asyncio
    async def test_does_not_duplicate_existing_models(self) -> None:
        """Models already in the registry are not registered twice."""
        import httpx

        payload = {"models": [{"name": "qwen2.5:7b", "size": 5_000_000_000}]}
        mock_resp = MagicMock()
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        registry = ModelRegistry()
        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            first = await registry.discover_from_ollama()
            second = await registry.discover_from_ollama()

        assert len(first) == 1
        assert len(second) == 0

    @pytest.mark.asyncio
    async def test_discover_sets_general_capability(self) -> None:
        """Dynamically discovered models receive GENERAL capability by default."""
        import httpx

        payload = {"models": [{"name": "test-model:latest", "size": 1_000_000_000}]}
        mock_resp = MagicMock()
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        registry = ModelRegistry()
        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            await registry.discover_from_ollama()

        mid = _model_id("test-model:latest")
        model = registry.get_model(mid)
        assert model is not None
        assert ModelCapability.GENERAL in model.capabilities
        assert model.backend == "ollama"
        assert model.available is True

    @pytest.mark.asyncio
    async def test_discover_returns_only_new_model_ids(self) -> None:
        """Return value contains only the newly registered model_ids."""
        import httpx

        payload = {
            "models": [
                {"name": "alpha:latest", "size": 1_000_000_000},
                {"name": "beta:latest", "size": 2_000_000_000},
            ]
        }
        mock_resp = MagicMock()
        mock_resp.json.return_value = payload
        mock_resp.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_resp)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        registry = ModelRegistry()
        with patch.object(httpx, "AsyncClient", return_value=mock_client):
            newly = await registry.discover_from_ollama()

        assert set(newly) == {_model_id("alpha:latest"), _model_id("beta:latest")}


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


# ---------------------------------------------------------------------------
# R1: Auto-discovery called during bootstrap
# ---------------------------------------------------------------------------


class TestBootstrapDiscovery:
    """R1: discover_from_ollama must be invoked during Runtime.bootstrap()."""

    @pytest.mark.asyncio
    async def test_discover_from_ollama_called_at_bootstrap(self) -> None:
        """Runtime.bootstrap() triggers Ollama model discovery."""
        import os
        from unittest.mock import AsyncMock, MagicMock, patch

        os.environ.setdefault("PORTAL_ENV", "development")
        os.environ.setdefault("PORTAL_BOOTSTRAP_API_KEY", "portal-dev-key")
        os.environ.setdefault("MCP_API_KEY", "not-changeme")

        from portal.routing.model_registry import ModelRegistry

        # Patch discover_from_ollama to capture the call
        discovery_called = []

        async def mock_discover(self, base_url="http://localhost:11434", **kwargs):
            discovery_called.append(base_url)
            return []  # no new models discovered

        with patch.object(ModelRegistry, "discover_from_ollama", mock_discover):
            from portal.lifecycle import Runtime

            runtime = Runtime()
            # Patch create_agent_core and SecurityMiddleware to avoid real initialization
            mock_agent_core = MagicMock()
            mock_agent_core.model_registry = ModelRegistry()
            mock_agent_core.cleanup = AsyncMock()

            with (
                patch("portal.lifecycle.create_agent_core", return_value=mock_agent_core),
                patch(
                    "portal.lifecycle.SecurityMiddleware",
                    return_value=MagicMock(cleanup=AsyncMock()),
                ),
                patch("portal.lifecycle.load_settings") as mock_settings,
            ):
                settings = MagicMock()
                settings.to_agent_config.return_value = {}
                settings.security.mcp_api_key = "not-changeme"
                settings.data_dir = MagicMock()
                settings.data_dir.__truediv__ = lambda self, other: MagicMock()
                # Provide a backends attribute with ollama_url
                settings.backends = MagicMock()
                settings.backends.ollama_url = "http://localhost:11434"
                mock_settings.return_value = settings

                try:
                    await runtime.bootstrap()
                except Exception:
                    pass  # We only care that discover was called

        assert len(discovery_called) >= 1, "discover_from_ollama was not called during bootstrap"
