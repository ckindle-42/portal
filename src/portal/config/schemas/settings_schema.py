"""
Settings Schema
================

Pydantic models for Portal configuration.

This provides:
- Type validation for all config fields
- Default values
- Environment variable support
- Documentation for each setting
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator
from pathlib import Path


class InterfaceConfig(BaseModel):
    """Configuration for interfaces (Telegram, Web, etc.)"""

    telegram: bool = Field(
        default=False,
        description="Enable Telegram interface"
    )
    web: bool = Field(
        default=False,
        description="Enable Web interface"
    )
    api: bool = Field(
        default=False,
        description="Enable REST API interface"
    )

    # Telegram-specific settings
    telegram_token: Optional[str] = Field(
        default=None,
        description="Telegram bot token"
    )
    telegram_allowed_users: List[int] = Field(
        default_factory=list,
        description="List of allowed Telegram user IDs (empty = allow all)"
    )

    # Web-specific settings
    web_host: str = Field(
        default="0.0.0.0",
        description="Web interface host"
    )
    web_port: int = Field(
        default=8000,
        description="Web interface port",
        ge=1,
        le=65535
    )


class SecurityConfig(BaseModel):
    """Security and rate limiting configuration"""

    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable rate limiting"
    )
    rate_limit_requests: int = Field(
        default=10,
        description="Max requests per window",
        ge=1
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        description="Rate limit window in seconds",
        ge=1
    )

    sandbox_enabled: bool = Field(
        default=False,
        description="Enable Docker sandbox for untrusted code"
    )
    sandbox_timeout_seconds: int = Field(
        default=30,
        description="Sandbox execution timeout",
        ge=1,
        le=300
    )


class LLMConfig(BaseModel):
    """LLM backend configuration (v4.6.2: Enhanced with circuit breaker)"""

    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API base URL"
    )
    router_port: int = Field(
        default=8000,
        description="Model router port"
    )
    default_model: str = Field(
        default="llama2",
        description="Default LLM model"
    )
    temperature: float = Field(
        default=0.7,
        description="LLM temperature (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    max_tokens: int = Field(
        default=2000,
        description="Max tokens per response",
        ge=100,
        le=100000
    )
    timeout_seconds: int = Field(
        default=60,
        description="LLM request timeout",
        ge=1,
        le=300
    )

    # v4.6.2: Circuit Breaker Configuration
    circuit_breaker_enabled: bool = Field(
        default=True,
        description="Enable circuit breaker pattern for backend failures"
    )
    circuit_breaker_threshold: int = Field(
        default=3,
        description="Failures before opening circuit",
        ge=1
    )
    circuit_breaker_timeout: int = Field(
        default=60,
        description="Seconds before attempting recovery",
        ge=10
    )
    circuit_breaker_half_open_calls: int = Field(
        default=1,
        description="Test calls allowed in half-open state",
        ge=1
    )


class ObservabilityConfig(BaseModel):
    """Observability and monitoring configuration (v4.7.0: Enhanced)"""

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    log_format: str = Field(
        default="json",
        description="Log format (json or text)"
    )

    # v4.7.0: Log Rotation
    log_rotation_enabled: bool = Field(
        default=True,
        description="Enable automatic log rotation"
    )
    log_max_bytes: int = Field(
        default=10 * 1024 * 1024,  # 10 MB
        description="Maximum log file size before rotation (bytes)",
        ge=1024 * 1024
    )
    log_rotation_interval_hours: int = Field(
        default=24,
        description="Time-based rotation interval (hours)",
        ge=1
    )
    log_backup_count: int = Field(
        default=7,
        description="Number of rotated log files to keep",
        ge=1
    )
    log_compress_rotated: bool = Field(
        default=True,
        description="Compress rotated log files"
    )

    # v4.7.0: Watchdog
    watchdog_enabled: bool = Field(
        default=False,
        description="Enable watchdog monitoring and auto-recovery"
    )
    watchdog_check_interval_seconds: int = Field(
        default=30,
        description="Watchdog health check interval (seconds)",
        ge=10
    )
    watchdog_max_consecutive_failures: int = Field(
        default=3,
        description="Failures before component restart",
        ge=1
    )
    watchdog_restart_on_failure: bool = Field(
        default=True,
        description="Automatically restart failed components"
    )

    # OpenTelemetry
    telemetry_enabled: bool = Field(
        default=False,
        description="Enable OpenTelemetry tracing"
    )
    telemetry_endpoint: Optional[str] = Field(
        default=None,
        description="OTLP exporter endpoint (e.g., http://localhost:4317)"
    )
    telemetry_service_name: str = Field(
        default="portal",
        description="Service name for tracing"
    )

    # Metrics
    metrics_enabled: bool = Field(
        default=True,
        description="Enable Prometheus metrics"
    )
    metrics_port: int = Field(
        default=9090,
        description="Prometheus metrics port",
        ge=1,
        le=65535
    )

    # Health checks
    health_checks_enabled: bool = Field(
        default=True,
        description="Enable health check endpoints"
    )

    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()


class JobQueueConfig(BaseModel):
    """Job queue configuration"""

    enabled: bool = Field(
        default=True,
        description="Enable async job queue"
    )
    worker_count: int = Field(
        default=4,
        description="Number of concurrent workers",
        ge=1,
        le=100
    )
    max_retries: int = Field(
        default=3,
        description="Max retry attempts for failed jobs",
        ge=0,
        le=10
    )
    stale_job_timeout_minutes: int = Field(
        default=30,
        description="Timeout for detecting stale jobs",
        ge=1,
        le=1440
    )
    cleanup_interval_hours: int = Field(
        default=24,
        description="Interval for cleaning up old jobs",
        ge=1,
        le=168
    )


class WebInterfaceConfig(BaseModel):
    enabled: bool = True
    port: int = 8081          # Portal's own WebInterface FastAPI port
    ui: str = "openwebui"     # openwebui | librechat


class TelegramInterfaceConfig(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    authorized_users: list[int] = []


class SlackInterfaceConfig(BaseModel):
    enabled: bool = False
    bot_token: str = ""
    signing_secret: str = ""
    channel_whitelist: list[str] = []


class InterfacesConfig(BaseModel):
    web: WebInterfaceConfig = Field(default_factory=WebInterfaceConfig)
    telegram: TelegramInterfaceConfig = Field(default_factory=TelegramInterfaceConfig)
    slack: SlackInterfaceConfig = Field(default_factory=SlackInterfaceConfig)


class MCPConfig(BaseModel):
    enabled: bool = True
    transport: str = "mcpo"   # mcpo | native
    mcpo_url: str = "http://localhost:9000"
    mcpo_api_key: str = ""
    scrapling_url: str = "http://localhost:8900"
    generation_enabled: bool = True
    comfyui_url: str = "http://localhost:8188"
    music_url: str = "http://localhost:8001"
    voice_url: str = "http://localhost:5002"
    docgen_url: str = "http://localhost:8002"


class HardwareConfig(BaseModel):
    compute_backend: str = "mps"   # mps | cuda | cpu
    docker_host_ip: str = "host.docker.internal"
    supervisor_type: str = "launchagent"
    generation_services: bool = True


class SettingsSchema(BaseModel):
    """
    Root settings schema for Portal.

    This is the top-level configuration object that contains all settings.
    """

    # Sub-configurations
    interfaces: InterfacesConfig = Field(
        default_factory=InterfacesConfig,
        description="Interface configurations"
    )
    security: SecurityConfig = Field(
        default_factory=SecurityConfig,
        description="Security settings"
    )
    llm: LLMConfig = Field(
        default_factory=LLMConfig,
        description="LLM backend settings"
    )
    observability: ObservabilityConfig = Field(
        default_factory=ObservabilityConfig,
        description="Observability settings"
    )
    job_queue: JobQueueConfig = Field(
        default_factory=JobQueueConfig,
        description="Job queue settings"
    )
    mcp: MCPConfig = Field(
        default_factory=MCPConfig,
        description="MCP protocol settings"
    )
    hardware: HardwareConfig = Field(
        default_factory=HardwareConfig,
        description="Hardware-specific settings"
    )

    # General settings
    data_dir: Path = Field(
        default=Path.home() / ".portal",
        description="Data directory for persistent storage"
    )

    # v4.7.0: Graceful Shutdown Configuration
    shutdown_timeout_seconds: float = Field(
        default=30.0,
        description="Maximum time to wait for graceful shutdown",
        ge=5.0,
        le=300.0
    )

    class Config:
        """Pydantic config"""
        validate_assignment = True
        extra = "forbid"  # Reject unknown fields
