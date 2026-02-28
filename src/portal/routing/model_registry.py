"""
Model Registry - Centralized model catalog with capabilities and metadata
Optimized for M4 Mac Mini Pro with 128GB RAM
"""

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class ModelCapability(Enum):
    """Model capabilities"""

    GENERAL = "general"
    CODE = "code"
    MATH = "math"
    REASONING = "reasoning"
    SPEED = "speed"
    VISION = "vision"
    FUNCTION_CALLING = "function_calling"


class SpeedClass(Enum):
    """Speed classification for models"""

    ULTRA_FAST = "ultra_fast"  # <0.5s
    FAST = "fast"  # 0.5-1.5s
    MEDIUM = "medium"  # 1.5-3s
    SLOW = "slow"  # 3-5s
    VERY_SLOW = "very_slow"  # >5s


@dataclass
class ModelMetadata:
    """Complete model metadata"""

    model_id: str
    backend: str  # ollama, lmstudio, mlx
    display_name: str
    parameters: str  # e.g., "7B", "32B"
    quantization: str  # e.g., "Q4_K_M", "4bit"

    # Capabilities
    capabilities: list[ModelCapability] = field(default_factory=list)

    # Performance characteristics
    speed_class: SpeedClass = SpeedClass.MEDIUM
    context_window: int = 4096
    tokens_per_second: int | None = None

    # Resource requirements
    ram_required_gb: int = 8
    vram_required_gb: int = 0

    # Quality scores (0.0-1.0)
    general_quality: float = 0.7
    code_quality: float = 0.5
    reasoning_quality: float = 0.5

    # Cost factor (0.0-1.0, higher = more expensive)
    cost: float = 0.5

    # Availability
    available: bool = True

    # Backend-specific settings
    model_path: str | None = None  # For MLX
    model_type: str | None = None  # For MLX prompt formatting
    api_model_name: str | None = None  # For API calls


class ModelRegistry:
    """Registry of available models with metadata"""

    def __init__(self) -> None:
        self.models: dict[str, ModelMetadata] = {}
        self._register_default_models()

    def _register_default_models(self) -> None:
        """Load default model catalog from JSON."""
        json_path = Path(__file__).parent / "default_models.json"
        if not json_path.exists():
            logger.warning("default_models.json not found; starting with empty registry")
            return
        with open(json_path) as f:
            models = json.load(f)
        for m in models:
            caps = [ModelCapability(c) for c in m.pop("capabilities", [])]
            speed = SpeedClass(m.pop("speed_class", "medium"))
            self.register(ModelMetadata(**m, capabilities=caps, speed_class=speed))

    def register(self, model: ModelMetadata) -> None:
        """Register a model"""
        self.models[model.model_id] = model

    def get_model(self, model_id: str) -> ModelMetadata | None:
        """Get model by ID"""
        return self.models.get(model_id)

    def get_models_by_backend(self, backend: str) -> list[ModelMetadata]:
        """Get all models for a backend"""
        return [m for m in self.models.values() if m.backend == backend]

    def get_fastest_model(self, capability: ModelCapability | None = None) -> ModelMetadata | None:
        """Get fastest available model"""
        candidates = [m for m in self.models.values() if m.available]

        if capability:
            candidates = [m for m in candidates if capability in m.capabilities]

        if not candidates:
            return None

        # Sort by speed class, then tokens per second
        speed_order = {
            SpeedClass.ULTRA_FAST: 0,
            SpeedClass.FAST: 1,
            SpeedClass.MEDIUM: 2,
            SpeedClass.SLOW: 3,
            SpeedClass.VERY_SLOW: 4,
        }

        return min(
            candidates, key=lambda m: (speed_order[m.speed_class], -(m.tokens_per_second or 0))
        )

    def get_best_quality_model(
        self, capability: ModelCapability, max_cost: float = 1.0
    ) -> ModelMetadata | None:
        """Get highest quality model within cost constraint"""
        candidates = [
            m
            for m in self.models.values()
            if capability in m.capabilities and m.available and m.cost <= max_cost
        ]

        if not candidates:
            return None

        # Select based on quality score
        quality_map = {
            ModelCapability.GENERAL: lambda m: m.general_quality,
            ModelCapability.CODE: lambda m: m.code_quality,
            ModelCapability.REASONING: lambda m: m.reasoning_quality,
        }

        quality_fn = quality_map.get(capability, lambda m: m.general_quality)
        return max(candidates, key=quality_fn)

    def get_all_models(self) -> list[ModelMetadata]:
        """Get all registered models"""
        return list(self.models.values())

    def update_availability(self, model_id: str, available: bool) -> None:
        """Update model availability"""
        if model_id in self.models:
            self.models[model_id].available = available

    async def discover_from_ollama(
        self,
        base_url: str = "http://localhost:11434",
        mark_others_unavailable: bool = False,
    ) -> list[str]:
        """
        Query Ollama and register any models not already in the catalog.

        For each model returned by ``GET /api/tags`` that has no entry in
        ``self.models`` a minimal ``ModelMetadata`` is created and registered
        with sensible defaults so the router can select it immediately.

        Args:
            base_url: Base URL of the Ollama server.
            mark_others_unavailable: When True, mark every previously
                registered Ollama model that is NOT in the live list as
                unavailable.

        Returns:
            List of model_ids that were newly registered.
        """
        try:
            import httpx
        except ImportError:
            logger.warning("httpx not available; skipping Ollama discovery")
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{base_url.rstrip('/')}/api/tags")
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.warning("Ollama discovery failed (%s); using static registry", exc)
            return []

        live_names: set[str] = set()
        newly_registered: list[str] = []

        for entry in data.get("models", []):
            name: str = entry.get("name", "")
            if not name:
                continue
            live_names.add(name)

            # Build a stable model_id from the name
            model_id = f"ollama_{name.replace(':', '_').replace('/', '_')}"

            if model_id not in self.models:
                size_bytes: int = entry.get("size", 0)
                params_b = size_bytes / 1e9
                params_label = (
                    f"{params_b:.0f}B" if params_b >= 1 else f"{size_bytes // 1_000_000}M"
                )

                metadata = ModelMetadata(
                    model_id=model_id,
                    backend="ollama",
                    display_name=name,
                    parameters=params_label,
                    quantization="unknown",
                    capabilities=[ModelCapability.GENERAL, ModelCapability.FUNCTION_CALLING],
                    speed_class=SpeedClass.MEDIUM,
                    context_window=8192,
                    general_quality=0.7,
                    code_quality=0.6,
                    reasoning_quality=0.6,
                    cost=0.3,
                    available=True,
                    api_model_name=name,
                )
                self.register(metadata)
                newly_registered.append(model_id)
                logger.info("Discovered Ollama model: %s → %s", name, model_id)
            else:
                self.models[model_id].available = True

        if mark_others_unavailable:
            for model in self.models.values():
                if model.backend == "ollama" and model.api_model_name not in live_names:
                    model.available = False

        if newly_registered:
            logger.info(
                "Registered %d new Ollama model(s): %s", len(newly_registered), newly_registered
            )
        return newly_registered
