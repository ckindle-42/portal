"""Tests for Wan2.2 video workflow in video_generator.py."""

import os
from unittest.mock import patch


class TestWan22Workflow:
    """Tests for Wan2.2 video generation workflow."""

    def test_wan22_workflow_has_unet_loader(self):
        """Test that Wan2.2 workflow uses UNETLoader."""
        from portal.tools.media_tools.video_generator import _WAN22_T2V_WORKFLOW

        # Wan2.2 uses UNETLoader for the model
        assert "1" in _WAN22_T2V_WORKFLOW
        assert _WAN22_T2V_WORKFLOW["1"]["class_type"] == "UNETLoader"
        assert "model_name" in _WAN22_T2V_WORKFLOW["1"]["inputs"]

    def test_wan22_workflow_has_clip_loader(self):
        """Test that Wan2.2 workflow uses CLIPLoader."""
        from portal.tools.media_tools.video_generator import _WAN22_T2V_WORKFLOW

        assert "2" in _WAN22_T2V_WORKFLOW
        assert _WAN22_T2V_WORKFLOW["2"]["class_type"] == "CLIPLoader"

    def test_wan22_workflow_has_vae_loader(self):
        """Test that Wan2.2 workflow uses VAELoader."""
        from portal.tools.media_tools.video_generator import _WAN22_T2V_WORKFLOW

        assert "3" in _WAN22_T2V_WORKFLOW
        assert _WAN22_T2V_WORKFLOW["3"]["class_type"] == "VAELoader"

    def test_wan22_workflow_has_empty_hunyuan_latent_video(self):
        """Test that Wan2.2 workflow uses EmptyHunyuanLatentVideo."""
        from portal.tools.media_tools.video_generator import _WAN22_T2V_WORKFLOW

        assert "6" in _WAN22_T2V_WORKFLOW
        assert _WAN22_T2V_WORKFLOW["6"]["class_type"] == "EmptyHunyuanLatentVideo"

    def test_wan22_default_fps(self):
        """Test that Wan2.2 default fps is 16."""
        from portal.tools.media_tools.video_generator import _WAN22_T2V_WORKFLOW

        # Check the VHS_VideoCombine node
        assert _WAN22_T2V_WORKFLOW["9"]["inputs"]["fps"] == 16

    def test_wan22_default_frames(self):
        """Test that Wan2.2 default frames is 81."""
        from portal.tools.media_tools.video_generator import _WAN22_T2V_WORKFLOW

        assert _WAN22_T2V_WORKFLOW["6"]["inputs"]["video_frames"] == 81


class TestCogVideoXWorkflow:
    """Tests for CogVideoX fallback workflow."""

    def test_cogvideox_workflow_has_checkpoint_loader(self):
        """Test that CogVideoX workflow uses CheckpointLoaderSimple."""
        from portal.tools.media_tools.video_generator import _COGVIDEOX_WORKFLOW

        assert "1" in _COGVIDEOX_WORKFLOW
        assert _COGVIDEOX_WORKFLOW["1"]["class_type"] == "CheckpointLoaderSimple"
        assert "ckpt_name" in _COGVIDEOX_WORKFLOW["1"]["inputs"]

    def test_cogvideox_workflow_has_empty_latent_video(self):
        """Test that CogVideoX workflow uses EmptyLatentVideo."""
        from portal.tools.media_tools.video_generator import _COGVIDEOX_WORKFLOW

        assert "3" in _COGVIDEOX_WORKFLOW
        assert _COGVIDEOX_WORKFLOW["3"]["class_type"] == "EmptyLatentVideo"

    def test_cogvideox_default_fps(self):
        """Test that CogVideoX default fps is 8."""
        from portal.tools.media_tools.video_generator import _COGVIDEOX_WORKFLOW

        assert _COGVIDEOX_WORKFLOW["6"]["inputs"]["fps"] == 8


class TestVideoBackendSelection:
    """Tests for VIDEO_BACKEND environment variable selection."""

    def test_default_backend_is_wan22(self):
        """Test that default VIDEO_BACKEND is wan22."""
        # Import without env override to check default
        from portal.tools.media_tools import video_generator

        assert video_generator.VIDEO_BACKEND == "wan22"

    def test_get_workflow_returns_wan22_by_default(self):
        """Test that _get_workflow returns Wan2.2 workflow by default."""
        from portal.tools.media_tools.video_generator import _get_workflow

        workflow = _get_workflow()
        assert workflow["1"]["class_type"] == "UNETLoader"

    @patch.dict(os.environ, {"VIDEO_BACKEND": "cogvideox"})
    def test_get_workflow_returns_cogvideox_when_set(self):
        """Test that _get_workflow returns CogVideoX when VIDEO_BACKEND=cogvideox."""
        # Re-import to pick up env change
        import importlib

        from portal.tools.media_tools import video_generator
        importlib.reload(video_generator)

        workflow = video_generator._get_workflow()
        assert workflow["1"]["class_type"] == "CheckpointLoaderSimple"

    @patch.dict(os.environ, {"VIDEO_BACKEND": "wan22"})
    def test_get_workflow_returns_wan22_when_set(self):
        """Test that _get_workflow returns Wan2.2 when VIDEO_BACKEND=wan22."""
        import importlib

        from portal.tools.media_tools import video_generator
        importlib.reload(video_generator)

        workflow = video_generator._get_workflow()
        assert workflow["1"]["class_type"] == "UNETLoader"
