"""Unit tests for music_generator tool"""

import inspect

from portal.tools.media_tools.music_generator import (
    MusicGenResult,
    _check_audiocraft_available,
    generate_music,
)


class TestMusicGeneratorTool:
    """Tests for MusicGenerator tool"""

    def test_music_generator_import(self):
        """Test that music_generator can be imported"""
        assert callable(generate_music)

    def test_music_generator_module_exists(self):
        """Test music_generator module exists"""
        from portal.tools.media_tools import music_generator

        assert music_generator is not None

    def test_generate_music_signature(self):
        """Test generate_music has expected parameters"""
        sig = inspect.signature(generate_music)
        params = list(sig.parameters.keys())
        # Verify it has the expected parameters
        assert "prompt" in params
        assert "duration" in params
        assert "model_size" in params

    def test_generate_music_accepts_prompt(self):
        """Test generate_music accepts a prompt parameter"""
        sig = inspect.signature(generate_music)
        prompt_param = sig.parameters.get("prompt")
        assert prompt_param is not None

    def test_check_audiocraft_available_exists(self):
        """Test AudioCraft availability detection function exists"""
        assert callable(_check_audiocraft_available)


class TestMusicGenResult:
    """Tests for MusicGenResult"""

    def test_music_gen_result_import(self):
        """Test MusicGenResult can be imported"""
        assert MusicGenResult is not None
