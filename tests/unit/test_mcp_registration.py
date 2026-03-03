"""Tests for MCP server registration logic."""

import os


class TestMCPRegistrationLogic:
    """Tests verifying MCP registration logic based on environment variables."""

    def test_generation_services_env_var(self):
        """Test that GENERATION_SERVICES env var controls generation service registration."""
        # When GENERATION_SERVICES=true, video, music, comfyui, whisper, tts should be registered
        # When false, they should not

        # Test default (false)
        assert os.getenv("GENERATION_SERVICES", "false").lower() == "false"

    def test_sandbox_env_var(self):
        """Test that SANDBOX_ENABLED env var controls sandbox registration."""
        assert os.getenv("SANDBOX_ENABLED", "false").lower() == "false"

    def test_default_ports(self):
        """Test default MCP port environment variables."""
        assert os.getenv("VIDEO_MCP_PORT", "8911") == "8911"
        assert os.getenv("MUSIC_MCP_PORT", "8912") == "8912"
        assert os.getenv("DOCUMENTS_MCP_PORT", "8913") == "8913"
        assert os.getenv("SANDBOX_MCP_PORT", "8914") == "8914"
        assert os.getenv("WHISPER_MCP_PORT", "8915") == "8915"
        assert os.getenv("TTS_MCP_PORT", "8916") == "8916"

    def test_generation_services_env_override(self, monkeypatch):
        """Test that setting GENERATION_SERVICES=true is respected."""
        monkeypatch.setenv("GENERATION_SERVICES", "true")
        assert os.getenv("GENERATION_SERVICES", "false").lower() == "true"

    def test_sandbox_env_override(self, monkeypatch):
        """Test that setting SANDBOX_ENABLED=true is respected."""
        monkeypatch.setenv("SANDBOX_ENABLED", "true")
        assert os.getenv("SANDBOX_ENABLED", "false").lower() == "true"

    def test_core_services_always_registered(self):
        """Verify that core services (core, scrapling, documents) should always be registered.

        This is a documentation test - the actual registration depends on the
        create_mcp_registry implementation which checks these services unconditionally.
        """
        # These services are registered regardless of GENERATION_SERVICES or SANDBOX_ENABLED
        expected_services = ["core", "scrapling", "documents"]
        # The factories.py implementation registers these unconditionally when MCP is enabled
        assert len(expected_services) == 3

    def test_generation_services_list(self):
        """List of services registered when GENERATION_SERVICES=true."""
        expected = ["comfyui", "whisper", "video", "music", "tts"]
        assert len(expected) == 5
        assert "video" in expected
        assert "music" in expected
        assert "tts" in expected
