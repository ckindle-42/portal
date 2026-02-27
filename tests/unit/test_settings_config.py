"""Tests for portal.config.settings — Pydantic configuration"""

from importlib import metadata as importlib_metadata
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from portal.config.settings import (
    BackendsConfig,
    ContextConfig,
    InterfacesConfig,
    LoggingConfig,
    ModelConfig,
    SecurityConfig,
    Settings,
    ToolsConfig,
    WebConfig,
    _is_placeholder,
    _is_weak_secret,
    _project_version,
)


class TestHelpers:
    def test_project_version_returns_string(self):
        v = _project_version()
        assert isinstance(v, str)
        assert len(v) > 0

    @patch(
        "portal.config.settings.metadata.version",
        side_effect=importlib_metadata.PackageNotFoundError,
    )
    def test_project_version_fallback(self, mock_meta):
        v = _project_version()
        assert v == "0.0.0-dev"

    def test_is_placeholder_true(self):
        assert _is_placeholder("changeme") is True
        assert _is_placeholder("change-me-secret") is True
        assert _is_placeholder("your_api_key") is True
        assert _is_placeholder("placeholder_token") is True
        assert _is_placeholder("secret-change-me-now") is True

    def test_is_placeholder_false(self):
        assert _is_placeholder("real_api_key_abc123xyz") is False
        assert _is_placeholder("sk-1234567890abcdef") is False

    def test_is_weak_secret_short(self):
        assert _is_weak_secret("abc") is True
        assert _is_weak_secret("12345") is True

    def test_is_weak_secret_low_entropy(self):
        assert _is_weak_secret("aaaaaaaaaaaaaaaaaaa") is True

    def test_is_weak_secret_valid(self):
        assert _is_weak_secret("xK9!mN2#pL5@qR8&hT4") is False


class TestModelConfig:
    def test_basic(self):
        cfg = ModelConfig(
            name="qwen2.5",
            backend="ollama",
            speed_class="fast",
        )
        assert cfg.name == "qwen2.5"
        assert cfg.backend == "ollama"
        assert cfg.capabilities == []
        assert cfg.context_window is None

    def test_with_all_fields(self):
        cfg = ModelConfig(
            name="llama3",
            backend="ollama",
            capabilities=["code", "math"],
            speed_class="medium",
            context_window=8192,
            max_tokens=4096,
        )
        assert cfg.context_window == 8192
        assert cfg.max_tokens == 4096


class TestSubConfigs:
    def test_security_defaults(self):
        cfg = SecurityConfig()
        assert cfg.rate_limit_enabled is True
        assert cfg.max_requests_per_minute == 20
        assert cfg.sandbox_enabled is False

    def test_security_mcp_key_placeholder_rejected(self):
        with pytest.raises(ValueError, match="placeholder"):
            SecurityConfig(mcp_api_key="changeme_secret")

    def test_security_mcp_key_weak_rejected(self):
        with pytest.raises(ValueError, match="too weak"):
            SecurityConfig(mcp_api_key="short")

    def test_security_mcp_key_valid(self):
        cfg = SecurityConfig(mcp_api_key="xK9!mN2#pL5@qR8&hT4")
        assert cfg.mcp_api_key is not None

    def test_backends_defaults(self):
        cfg = BackendsConfig()
        assert cfg.ollama_url == "http://localhost:11434"
        assert cfg.default_backend == "ollama"

    def test_web_config_defaults(self):
        cfg = WebConfig()
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8081
        assert cfg.enable_websocket is True

    def test_tools_config_defaults(self):
        cfg = ToolsConfig()
        assert "utility" in cfg.enabled_categories
        assert cfg.disabled_tools == []

    def test_context_config_defaults(self):
        cfg = ContextConfig()
        assert cfg.max_context_messages == 100
        assert cfg.persist_context is True

    def test_logging_config_defaults(self):
        cfg = LoggingConfig()
        assert cfg.level == "INFO"
        assert cfg.format == "json"

    def test_logging_invalid_level(self):
        with pytest.raises(ValueError, match="Log level"):
            LoggingConfig(level="VERBOSE")

    def test_interfaces_config(self):
        cfg = InterfacesConfig()
        assert cfg.telegram is None
        assert cfg.web is None


class TestSettings:
    def test_default_settings(self):
        s = Settings()
        assert s.project_name == "Portal"
        assert s.data_dir == Path("data")
        assert isinstance(s.backends, BackendsConfig)
        assert isinstance(s.security, SecurityConfig)

    def test_settings_with_web(self):
        s = Settings(interfaces=InterfacesConfig(web=WebConfig()))
        assert s.interfaces.web is not None
        assert s.interfaces.web.port == 8081

    def test_to_agent_config(self):
        s = Settings(
            models={"test": ModelConfig(name="test", backend="ollama", speed_class="fast")},
            interfaces=InterfacesConfig(web=WebConfig()),
        )
        config = s.to_agent_config()
        assert isinstance(config, dict)
        assert "ollama_base_url" in config

    def test_from_yaml(self, tmp_path):
        config_file = tmp_path / "portal.yaml"
        config_file.write_text(
            yaml.dump(
                {
                    "project_name": "TestPortal",
                    "interfaces": {"web": {"port": 9090}},
                }
            )
        )
        s = Settings.from_yaml(config_file)
        assert s.project_name == "TestPortal"
        assert s.interfaces.web.port == 9090

    def test_from_yaml_not_found(self):
        with pytest.raises(FileNotFoundError):
            Settings.from_yaml("/nonexistent/config.yaml")
