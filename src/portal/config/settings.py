"""
Pydantic Settings Configuration
=================================

Type-safe configuration management using Pydantic.
Validates all configuration values at startup and fails fast with clear error messages.
"""

from typing import Dict, List, Optional, Any
from pathlib import Path
from importlib import metadata
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_settings import BaseSettings
import yaml
import os


def _project_version() -> str:
    """Resolve the project version from package metadata."""
    try:
        return metadata.version("portal")
    except metadata.PackageNotFoundError:
        return "0.0.0-dev"


_CHANGEME_PREFIXES = ("changeme", "change-me", "your_", "your-", "placeholder", "secret-change-me")


def _is_placeholder(value: str) -> bool:
    """Return True if value looks like an unfilled template placeholder."""
    v = value.lower()
    return any(v.startswith(p) or p in v for p in _CHANGEME_PREFIXES)


_SECRET_MIN_LENGTH = 16


def _is_weak_secret(value: str) -> bool:
    """Return True if value is too short or low-entropy for use as an API key."""
    stripped = value.strip()
    if len(stripped) < _SECRET_MIN_LENGTH:
        return True
    # Check for trivially low entropy (all same character, sequential)
    if len(set(stripped)) < 4:
        return True
    return False


class ModelConfig(BaseModel):
    """Configuration for a single model"""
    name: str = Field(..., description="Model name/identifier")
    backend: str = Field(..., description="Backend type (ollama, mlx, etc.)")
    capabilities: List[str] = Field(default_factory=list, description="Model capabilities")
    speed_class: str = Field(..., description="Speed classification (fast, medium, slow)")
    context_window: Optional[int] = Field(None, description="Maximum context window size")
    max_tokens: Optional[int] = Field(None, description="Maximum output tokens")

    model_config = ConfigDict(extra='allow')


class SecurityConfig(BaseModel):
    """Security and rate limiting configuration"""
    rate_limit_enabled: bool = Field(True, description="Enable rate limiting")
    rate_limit_requests: int = Field(20, ge=1, description="Max requests per rate-limit window")
    max_requests_per_minute: int = Field(20, ge=1, le=1000, description="Max requests per minute")
    max_requests_per_hour: int = Field(100, ge=1, le=10000, description="Max requests per hour")
    max_file_size_mb: int = Field(10, ge=1, le=1000, description="Max file size in MB")
    allowed_commands: List[str] = Field(default_factory=list, description="Whitelist of allowed shell commands (empty = none allowed, secure by default)")
    sandbox_enabled: bool = Field(False, description="Enable Docker sandboxing for code execution")
    require_approval_for_high_risk: bool = Field(False, description="Require human approval for high-risk actions")
    mcp_api_key: Optional[str] = Field(None, description="MCP server API key (must not be a placeholder in production)")

    @field_validator('mcp_api_key')
    @classmethod
    def validate_mcp_api_key(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if _is_placeholder(v):
            raise ValueError(
                "MCP_API_KEY is still set to a placeholder value. "
                "Set a strong random key before enabling MCP."
            )
        if _is_weak_secret(v):
            raise ValueError(
                f"MCP_API_KEY is too weak (minimum {_SECRET_MIN_LENGTH} characters "
                "with reasonable entropy). Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        return v

    @field_validator('max_requests_per_minute')
    @classmethod
    def validate_rate_limits(cls, v: int, info) -> int:
        """Ensure rate limits are reasonable"""
        if v < 1:
            raise ValueError("Rate limit must be at least 1")
        return v

    @field_validator('sandbox_enabled')
    @classmethod
    def validate_docker_socket(cls, v: bool) -> bool:
        """Validate Docker socket accessibility when sandbox is enabled"""
        if v:  # If sandbox is enabled, check Docker socket
            docker_socket = Path("/var/run/docker.sock")

            # Check if socket exists
            if not docker_socket.exists():
                raise ValueError(
                    "Docker sandbox is enabled but Docker socket not found at /var/run/docker.sock. "
                    "Is Docker installed and running? "
                    "To disable sandbox, set security.sandbox_enabled=false in config."
                )

            # Check if socket is accessible
            if not os.access(docker_socket, os.R_OK):
                raise ValueError(
                    "Docker socket exists but is not accessible. "
                    "Check permissions or add your user to the docker group: "
                    "sudo usermod -aG docker $USER"
                )

        return v

    model_config = ConfigDict(extra='allow')


class TelegramConfig(BaseModel):
    """Telegram interface configuration"""
    bot_token: str = Field(..., description="Telegram bot token from BotFather")
    authorized_users: List[int] = Field(default_factory=list, description="List of authorized Telegram user IDs")
    enable_group_chat: bool = Field(False, description="Allow bot in group chats")
    enable_inline_mode: bool = Field(False, description="Enable inline query mode")
    webhook_url: Optional[str] = Field(None, description="Webhook URL for receiving updates")

    @field_validator('bot_token')
    @classmethod
    def validate_token(cls, v: str) -> str:
        """Validate bot token format"""
        if not v or v.startswith('your_'):
            raise ValueError("Invalid bot token. Get one from @BotFather")
        if _is_placeholder(v):
            raise ValueError(
                "TELEGRAM_BOT_TOKEN is still set to a placeholder value. "
                "Set a real token from @BotFather."
            )
        if ':' not in v:
            raise ValueError("Bot token must be in format: 123456:ABC-DEF...")
        return v

    model_config = ConfigDict(extra='allow')


class SlackConfig(BaseModel):
    """Slack interface configuration"""
    bot_token: str = Field(..., description="Slack bot token (xoxb-...)")
    signing_secret: str = Field(..., description="Slack signing secret for request verification")
    channel_whitelist: List[str] = Field(default_factory=list, description="Channels the bot responds in (empty = all)")

    @field_validator('signing_secret')
    @classmethod
    def validate_signing_secret(cls, v: str) -> str:
        if _is_placeholder(v):
            raise ValueError(
                "SLACK_SIGNING_SECRET is still set to a placeholder value. "
                "Set the real signing secret from your Slack app settings."
            )
        if _is_weak_secret(v):
            raise ValueError(
                f"SLACK_SIGNING_SECRET is too weak (minimum {_SECRET_MIN_LENGTH} characters "
                "with reasonable entropy). Use the signing secret from your Slack app settings."
            )
        return v

    model_config = ConfigDict(extra='allow')


class WebConfig(BaseModel):
    """Web interface configuration"""
    host: str = Field("0.0.0.0", description="Host to bind to")
    port: int = Field(8081, ge=1, le=65535, description="Port to bind to")
    enable_websocket: bool = Field(True, description="Enable WebSocket support")
    enable_cors: bool = Field(False, description="Enable CORS")
    cors_origins: List[str] = Field(default_factory=list, description="Allowed CORS origins")
    ssl_cert: Optional[Path] = Field(None, description="Path to SSL certificate")
    ssl_key: Optional[Path] = Field(None, description="Path to SSL key")

    model_config = ConfigDict(extra='allow')


class InterfacesConfig(BaseModel):
    """Configuration for all interfaces"""
    telegram: Optional[TelegramConfig] = None
    slack: Optional[SlackConfig] = None
    web: Optional[WebConfig] = None

    model_config = ConfigDict(extra='allow')


class BackendsConfig(BaseModel):
    """LLM backend configuration"""
    ollama_url: str = Field("http://localhost:11434", description="Ollama API URL")
    mlx_enabled: bool = Field(False, description="Enable Apple MLX backend")
    default_backend: str = Field("ollama", description="Default backend to use")
    timeout_seconds: int = Field(300, ge=1, le=3600, description="Request timeout in seconds")

    model_config = ConfigDict(extra='allow')


class ToolsConfig(BaseModel):
    """Tools configuration"""
    enabled_categories: List[str] = Field(
        default_factory=lambda: ["system", "git", "data", "web"],
        description="Enabled tool categories"
    )
    disabled_tools: List[str] = Field(default_factory=list, description="Specific tools to disable")
    mcp_servers: Dict[str, Any] = Field(default_factory=dict, description="MCP server configurations")
    browser_headless: bool = Field(True, description="Run browser automation in headless mode")

    model_config = ConfigDict(extra='allow')


class ContextConfig(BaseModel):
    """Context management configuration"""
    max_context_messages: int = Field(100, ge=1, le=10000, description="Maximum messages to keep in context")
    context_window_strategy: str = Field("sliding", description="Context window strategy (sliding, summary)")
    auto_summarize_threshold: int = Field(50, ge=1, description="Messages before auto-summarization")
    persist_context: bool = Field(True, description="Persist context to SQLite")
    context_db_path: str = Field("data/context.db", description="Path to context database")

    model_config = ConfigDict(extra='allow')


class LoggingConfig(BaseModel):
    """Logging configuration"""
    level: str = Field("INFO", description="Log level (DEBUG, INFO, WARNING, ERROR)")
    format: str = Field("json", description="Log format (json, text)")
    output_file: Optional[Path] = Field(None, description="Log file path")
    enable_trace_ids: bool = Field(True, description="Enable trace IDs for request tracking")
    verbose: bool = Field(False, description="Enable verbose output (e.g., routing info in responses)")

    @field_validator('level')
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level"""
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v_upper

    model_config = ConfigDict(extra='allow')


class Settings(BaseSettings):
    """
    Main application settings with type validation.

    Configuration is loaded from:
    1. YAML config file (if provided)
    2. Environment variables with PORTAL_ prefix (override)
    3. Default values (fallback)

    Environment variable mapping uses double-underscore nesting:
      PORTAL_INTERFACES__TELEGRAM__BOT_TOKEN
      PORTAL_BACKENDS__OLLAMA_URL
      PORTAL_SECURITY__SANDBOX_ENABLED
    """

    # Core configuration
    models: Dict[str, ModelConfig] = Field(default_factory=dict, description="Model configurations")
    backends: BackendsConfig = Field(default_factory=BackendsConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    interfaces: InterfacesConfig = Field(default_factory=InterfacesConfig)
    tools: ToolsConfig = Field(default_factory=ToolsConfig)
    context: ContextConfig = Field(default_factory=ContextConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    # Project metadata
    project_name: str = Field("Portal", description="Project name")
    version: str = Field(default_factory=_project_version, description="Project version")
    data_dir: Path = Field(Path("data"), description="Data directory")
    logs_dir: Path = Field(Path("logs"), description="Logs directory")

    model_config = ConfigDict(
        env_prefix='PORTAL_',
        env_nested_delimiter='__',
        extra='allow',
        validate_assignment=True,
    )

    @classmethod
    def from_yaml(cls, config_path: str | Path) -> "Settings":
        """
        Load settings from a YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Settings instance with validated configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}

        return cls(**config_data)

    @classmethod
    def from_env(cls) -> "Settings":
        """
        Load settings from environment variables only.

        Returns:
            Settings instance with environment-based configuration
        """
        return cls()

    def ensure_directories(self) -> None:
        """Create necessary directories if they don't exist"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        # Create screenshots directory if tools are enabled
        if 'browser' in self.tools.enabled_categories:
            Path("screenshots").mkdir(exist_ok=True)

    def validate_required_config(self) -> List[str]:
        """
        Validate that all required configuration is present.

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check if at least one interface is configured
        if not self.interfaces.telegram and not self.interfaces.web:
            errors.append("At least one interface (telegram or web) must be configured")

        # Check if models are configured
        if not self.models:
            errors.append("At least one model must be configured")

        # Check security settings
        if self.security.require_approval_for_high_risk:
            telegram = self.interfaces.telegram
            if not telegram or not telegram.authorized_users:
                errors.append("Human approval requires Telegram interface with authorized_users")

        return errors

    def to_agent_config(self) -> dict:
        """
        Extract a plain dict suitable for DependencyContainer / create_agent_core.

        AgentCore and its factories expect a plain dict, not a Settings object.
        This converts the relevant settings into the dict format they consume.
        """
        return {
            'routing_strategy': 'AUTO',
            'max_context_messages': self.context.max_context_messages,
            'ollama_base_url': self.backends.ollama_url,
            'circuit_breaker_enabled': True,
            'circuit_breaker_threshold': 3,
            'circuit_breaker_timeout': 60,
            'circuit_breaker_half_open_calls': 1,
        }


def load_settings(config_path: Optional[str | Path] = None) -> Settings:
    """
    Load and validate application settings.

    Args:
        config_path: Optional path to YAML config file

    Returns:
        Validated Settings instance

    Raises:
        ValueError: If configuration is invalid
    """
    # Load from YAML if provided, otherwise from environment
    if config_path:
        settings = Settings.from_yaml(config_path)
    else:
        settings = Settings.from_env()

    # Ensure directories exist
    settings.ensure_directories()

    # Validate required configuration
    errors = settings.validate_required_config()
    if errors:
        raise ValueError(
            f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )

    return settings


__all__ = [
    'Settings',
    'ModelConfig',
    'SecurityConfig',
    'TelegramConfig',
    'SlackConfig',
    'WebConfig',
    'InterfacesConfig',
    'BackendsConfig',
    'ToolsConfig',
    'ContextConfig',
    'LoggingConfig',
    'load_settings',
]
