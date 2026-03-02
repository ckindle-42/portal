"""
Model Puller — Auto-pull missing models from Ollama and HuggingFace

Handles automatic downloading of models defined in default_models.json that aren't
already installed in Ollama.
"""

import logging

import httpx

from portal.routing.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class ModelPuller:
    """Handles auto-pulling models from Ollama and HuggingFace."""

    def __init__(self, ollama_url: str, mlx_url: str | None = None):
        self.ollama_url = ollama_url.rstrip("/")
        self.mlx_url = mlx_url

    async def ensure_models_available(
        self,
        model_registry: ModelRegistry,
        backend: str = "ollama",
    ) -> list[str]:
        """
        Check defined models and pull any missing ones.

        Args:
            model_registry: The model registry to check against.
            backend: Which backend to ensure models for ("ollama", "mlx", "huggingface").

        Returns:
            List of model IDs that were newly pulled.
        """
        if backend == "ollama":
            return await self._ensure_ollama_models(model_registry)
        elif backend == "mlx":
            return await self._ensure_mlx_models(model_registry)
        elif backend == "huggingface":
            return await self._ensure_huggingface_models(model_registry)
        else:
            logger.warning("Unknown backend for auto-pull: %s", backend)
            return []

    async def _ensure_ollama_models(self, model_registry: ModelRegistry) -> list[str]:
        """Check Ollama models and pull any that are missing."""
        # Get models from registry that match the backend
        ollama_models = model_registry.get_models_by_backend("ollama")
        if not ollama_models:
            return []

        # Get currently installed models from Ollama
        installed = await self._get_installed_ollama_models()
        if installed is None:
            logger.warning("Could not get installed Ollama models, skipping auto-pull")
            return []

        pulled_models: list[str] = []

        for model in ollama_models:
            api_name = model.api_model_name
            if not api_name:
                continue

            # Check if model is installed (without tag means any tag)
            model_base = api_name.split(":")[0]
            is_installed = any(
                installed_name.startswith(model_base) for installed_name in installed
            )

            if not is_installed:
                success = await self._pull_ollama_model(api_name)
                if success:
                    pulled_models.append(model.model_id)
                    model_registry.update_availability(model.model_id, True)

        if pulled_models:
            logger.info("Auto-pulled %d Ollama model(s): %s", len(pulled_models), pulled_models)

        return pulled_models

    async def _ensure_mlx_models(self, model_registry: ModelRegistry) -> list[str]:
        """MLX models are loaded dynamically from the MLX-LM server."""
        # MLX models are handled differently - they're served by the MLX-LM server
        # We just log a message about checking MLX availability
        mlx_models = model_registry.get_models_by_backend("mlx")
        if mlx_models and self.mlx_url:
            logger.info(
                "MLX backend enabled, %d MLX model(s) available in registry", len(mlx_models)
            )
        return []

    async def _ensure_huggingface_models(self, model_registry: ModelRegistry) -> list[str]:
        """HuggingFace models need to be converted to GGUF and pulled into Ollama."""
        hf_models = model_registry.get_models_by_backend("huggingface")
        pulled: list[str] = []

        for model in hf_models:
            model_path = model.model_path
            if not model_path:
                continue

            logger.info(
                "HuggingFace model '%s' requires manual import to Ollama. "
                "Run: ollama pull %s or convert from HuggingFace",
                model_path,
                model_path,
            )

        return pulled

    async def _get_installed_ollama_models(self) -> set[str] | None:
        """Get list of installed model names from Ollama."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.ollama_url}/api/tags")
                resp.raise_for_status()
                data = resp.json()
                return {m["name"] for m in data.get("models", [])}
        except Exception as e:
            logger.warning("Failed to get Ollama models: %s", e)
            return None

    async def _pull_ollama_model(self, model_name: str) -> bool:
        """
        Pull a model from Ollama library.

        Args:
            model_name: The model name to pull (e.g., "llama3.2:3b-instruct-q4_K_M")

        Returns:
            True if pull was successful, False otherwise.
        """
        logger.info("Pulling Ollama model: %s", model_name)

        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                # Start the pull request
                resp = await client.post(
                    f"{self.ollama_url}/api/pull",
                    json={"name": model_name, "stream": False},
                )
                resp.raise_for_status()
                logger.info("Successfully pulled model: %s", model_name)
                return True
        except httpx.HTTPStatusError as e:
            logger.error("Failed to pull model %s: HTTP %s", model_name, e.response.status_code)
        except Exception as e:
            logger.error("Failed to pull model %s: %s", model_name, e)

        return False


__all__ = ["ModelPuller"]
