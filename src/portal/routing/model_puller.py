"""
Model Puller — Auto-pull missing models from Ollama and HuggingFace

Handles automatic downloading of models defined in default_models.json that aren't
already installed in Ollama. Supports HuggingFace to Ollama conversion.
"""

import logging
import shutil
import subprocess

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
        """HuggingFace models: auto-import to Ollama via huggingface-cli or manual conversion."""
        hf_models = model_registry.get_models_by_backend("huggingface")
        pulled: list[str] = []

        # Check if we have the tools for auto-import
        has_huggingface_cli = shutil.which("huggingface-cli") or shutil.which("huggingface")
        has_llamafile = shutil.which("llamafile")

        if not has_huggingface_cli and not has_llamafile:
            logger.info(
                "HuggingFace CLI or llamafile not available. "
                "To auto-import HuggingFace models, install: pip install huggingface-hub"
            )

        for model in hf_models:
            model_path = model.model_path
            if not model_path:
                continue

            # Check if already in Ollama
            installed = await self._get_installed_ollama_models()
            if installed and any(model_path.split("/")[-1] in m for m in installed):
                logger.debug("Model %s already in Ollama, skipping", model_path)
                continue

            # Try to auto-import
            success = await self._import_huggingface_model(model_path)
            if success:
                pulled.append(model_path)
                model_registry.update_availability(model.model_id, True)
                logger.info("Successfully imported HuggingFace model: %s", model_path)
            else:
                logger.info(
                    "Could not auto-import %s. Manual import: "
                    "huggingface-cli download %s && ollama import",
                    model_path,
                    model_path,
                )

        if pulled:
            logger.info("Auto-imported %d HuggingFace model(s): %s", len(pulled), pulled)

        return pulled

    async def _import_huggingface_model(self, model_path: str) -> bool:
        """Import a HuggingFace model to Ollama.

        Tries multiple methods:
        1. huggingface-cli download + ollama import
        2. Direct ollama pull (for models in Ollama library)
        3. llamafile conversion

        Returns True if import succeeded, False otherwise.
        """
        logger.info("Attempting to import HuggingFace model: %s", model_path)

        # Method 1: Try direct Ollama pull (works for models in Ollama library)
        # Many HuggingFace models are also in Ollama library
        model_name = model_path.replace("/", "-").replace("_", "-").lower()
        if await self._pull_ollama_model(model_name):
            logger.info("Found model in Ollama library: %s", model_name)
            return True

        # Method 2: Try using huggingface-cli to download and convert
        if shutil.which("huggingface-cli") or shutil.which("huggingface"):
            try:
                # Download model files
                result = subprocess.run(
                    [
                        "huggingface-cli",
                        "download",
                        model_path,
                        "--local-dir",
                        f"/tmp/{model_path.split('/')[-1]}",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                if result.returncode == 0:
                    # Try to import to Ollama
                    gguf_path = f"/tmp/{model_path.split('/')[-1]}/*.gguf"
                    import_result = subprocess.run(
                        [
                            "ollama",
                            "import",
                            "--source",
                            "gguf",
                            "--model",
                            model_name,
                            "--files",
                            gguf_path,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    if import_result.returncode == 0:
                        return True
            except Exception as e:
                logger.debug("huggingface-cli import failed: %s", e)

        # Method 3: Try llamafile
        if shutil.which("llamafile"):
            logger.info("llamafile available but auto-conversion not yet implemented")

        logger.debug("All import methods failed for %s", model_path)
        return False

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
