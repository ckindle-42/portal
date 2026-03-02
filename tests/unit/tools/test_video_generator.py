"""Unit tests for video_generator tool"""

import inspect

from portal.tools.media_tools.video_generator import (
    VideoGenResult,
    generate_video,
)


class TestVideoGeneratorTool:
    """Tests for VideoGenerator tool"""

    def test_video_generator_import(self):
        """Test that video_generator can be imported"""
        assert callable(generate_video)

    def test_video_generator_module_exists(self):
        """Test video_generator module exists"""
        from portal.tools.media_tools import video_generator

        assert video_generator is not None

    def test_generate_video_signature(self):
        """Test generate_video has expected parameters"""
        sig = inspect.signature(generate_video)
        params = list(sig.parameters.keys())
        # Verify it has the expected parameters
        assert "prompt" in params
        assert "output_dir" in params
        assert "seed" in params

    def test_generate_video_accepts_prompt(self):
        """Test generate_video accepts a prompt parameter"""
        sig = inspect.signature(generate_video)
        prompt_param = sig.parameters.get("prompt")
        assert prompt_param is not None


class TestVideoGeneratorResult:
    """Tests for VideoGenResult"""

    def test_video_gen_result_import(self):
        """Test VideoGenResult can be imported"""
        assert VideoGenResult is not None
