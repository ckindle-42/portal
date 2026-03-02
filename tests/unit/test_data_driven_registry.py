"""
Tests for data-driven model registry default registration.
"""

import pytest

from portal.routing.model_registry import ModelCapability, ModelRegistry, SpeedClass
from portal.routing.task_classifier import TaskCategory, TaskClassifier


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
        m = registry.get_model("ollama_dolphin_llama3_8b")
        assert m is not None
        assert m.display_name == "Dolphin 3.0 Llama3 8B"
        assert m.backend == "ollama"
        assert ModelCapability.GENERAL in m.capabilities
        assert m.speed_class == SpeedClass.FAST

    def test_code_specialist_exists(self):
        """The code specialist model should have high code_quality."""
        registry = ModelRegistry()
        coder = registry.get_model("ollama_qwen3_coder_30b")
        assert coder is not None
        assert coder.code_quality >= 0.9

    def test_vision_model_exists(self):
        """Multimodal model should have VISION and MULTIMODAL capabilities."""
        registry = ModelRegistry()
        omni = registry.get_model("ollama_qwen3_omni_30b")
        assert omni is not None
        assert ModelCapability.VISION in omni.capabilities
        assert ModelCapability.MULTIMODAL in omni.capabilities

    def test_all_models_available_by_default(self):
        """All default Ollama models should be marked available. MLX models are unavailable by default."""
        registry = ModelRegistry()
        for model in registry.get_all_models():
            if model.backend == "mlx":
                # MLX models require mlx_lm.server to be running
                assert not model.available, (
                    f"{model.model_id} should be unavailable by default (requires MLX server)"
                )
            else:
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
<<<<<<< HEAD
        # 10 Ollama + 3 MLX + 1 custom = 14 (after merge)
        assert len(registry.get_all_models()) >= 13

    def test_security_quality_field_on_models(self):
        """All default models carry a security_quality score."""
        registry = ModelRegistry()
        for model in registry.get_all_models():
            assert hasattr(model, "security_quality")
            assert 0.0 <= model.security_quality <= 1.0


class TestTaskClassifierNewCategories:
    """Tests for new TaskCategory values added in the model expansion."""

    @pytest.fixture
    def classifier(self):
        return TaskClassifier()

    @pytest.mark.parametrize("query", [
        "explain kerberoasting and mimikatz",
        "write a reverse shell exploit in python",
        "perform recon on target using nmap",
        "what is a buffer overflow and how do you exploit it",
        "help me bypass EDR detection",
    ])
    def test_security_queries_classify_as_security(self, classifier, query):
        result = classifier.classify(query)
        assert result.category == TaskCategory.SECURITY

    @pytest.mark.parametrize("query", [
        "generate an image of a mountain landscape",
        "create an illustration of a robot",
        "draw a portrait of a wizard",
    ])
    def test_image_queries_classify_as_image_gen(self, classifier, query):
        result = classifier.classify(query)
        assert result.category == TaskCategory.IMAGE_GEN

    @pytest.mark.parametrize("query", [
        "use tts to read this paragraph aloud",
        "clone my voice using cosyvoice",
        "generate audio with text to speech",
    ])
    def test_audio_queries_classify_as_audio_gen(self, classifier, query):
        result = classifier.classify(query)
        assert result.category == TaskCategory.AUDIO_GEN

    def test_security_takes_priority_over_code(self, classifier):
        """SECURITY takes priority even when code patterns also match."""
        result = classifier.classify("write a python payload to exploit CVE-2024-1234")
        assert result.category == TaskCategory.SECURITY
