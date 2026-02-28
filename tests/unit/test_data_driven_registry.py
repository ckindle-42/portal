"""
Tests for data-driven model registry default registration.
"""

from portal.routing.model_registry import ModelCapability, ModelRegistry, SpeedClass


class TestDataDrivenRegistry:
    """Verify the data-driven _register_default_models populates correctly."""

    def test_all_model_ids_unique(self):
        """Every model_id must be unique."""
        registry = ModelRegistry()
        ids = [m.model_id for m in registry.get_all_models()]
        assert len(ids) == len(set(ids))

    def test_specific_model_properties(self):
        """Spot-check a specific model's metadata."""
        registry = ModelRegistry()
        m = registry.get_model("ollama_qwen25_7b")
        assert m is not None
        assert m.display_name == "Qwen2.5 7B"
        assert m.backend == "ollama"
        assert ModelCapability.CODE in m.capabilities
        assert m.speed_class == SpeedClass.FAST

    def test_code_specialist_exists(self):
        """The code specialist model should have high code_quality."""
        registry = ModelRegistry()
        coder = registry.get_model("ollama_qwen25_coder")
        assert coder is not None
        assert coder.code_quality >= 0.9

    def test_vision_model_exists(self):
        """LLaVA vision model should have VISION capability."""
        registry = ModelRegistry()
        llava = registry.get_model("ollama_llava")
        assert llava is not None
        assert ModelCapability.VISION in llava.capabilities

    def test_all_models_available_by_default(self):
        """All default models should be marked available."""
        registry = ModelRegistry()
        for model in registry.get_all_models():
            assert model.available, f"{model.model_id} should be available"

    def test_custom_model_registration(self):
        """Registering a custom model adds it alongside defaults."""
        from portal.routing.model_registry import ModelMetadata

        registry = ModelRegistry()
        custom = ModelMetadata(
            model_id="custom_test",
            backend="test",
            display_name="Test Model",
            parameters="1B",
            quantization="none",
        )
        registry.register(custom)
        assert registry.get_model("custom_test") is not None
        assert len(registry.get_all_models()) == 10
