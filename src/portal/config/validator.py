"""
Configuration Validator - Type-safe configuration management
Validates .env settings before agent startup to catch issues early
"""

import os
import sys
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field, validator, ValidationError
from dotenv import load_dotenv


class AgentConfig(BaseModel):
    """Type-safe configuration model"""
    
    # Telegram Configuration
    telegram_bot_token: str = Field(
        min_length=30,
        description="Telegram bot token from @BotFather"
    )
    telegram_user_id: int = Field(
        gt=0,
        description="Authorized user's Telegram ID"
    )
    
    # LLM Backend
    llm_backend: str = Field(
        default="ollama",
        pattern="^(ollama|lmstudio|mlx)$",
        description="LLM backend to use"
    )
    
    # Backend URLs
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama API endpoint"
    )
    lmstudio_base_url: str = Field(
        default="http://localhost:1234/v1",
        description="LM Studio API endpoint"
    )
    
    # MLX Configuration (optional)
    mlx_model_path: Optional[str] = Field(
        default=None,
        description="Path to MLX model"
    )
    
    # Routing Configuration
    routing_strategy: str = Field(
        default="auto",
        pattern="^(auto|speed|quality|balanced|cost_optimized)$",
        description="Model routing strategy"
    )
    routing_max_cost: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Maximum computational cost for model selection"
    )
    
    # Tool Configuration
    tools_require_confirmation: bool = Field(
        default=True,
        description="Require confirmation for dangerous operations"
    )
    tools_admin_chat_id: Optional[int] = Field(
        default=None,
        description="Admin chat ID for tool confirmations (uses telegram_user_id if not set)"
    )
    tools_confirmation_timeout: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="Timeout in seconds for tool confirmation requests"
    )
    max_parallel_tools: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum parallel tool executions"
    )
    
    # Browser Configuration
    browser_headless: bool = Field(
        default=True,
        description="Run browser in headless mode"
    )
    browser_data_dir: Path = Field(
        default=Path.home() / "telegram-agent" / "browser_data",
        description="Browser profile directory"
    )
    
    # Memory Configuration
    memory_enabled: bool = Field(
        default=True,
        description="Enable persistent memory"
    )
    memory_encryption_key: Optional[str] = Field(
        default=None,
        description="Encryption key for sensitive memory data"
    )
    
    # Rate Limiting
    rate_limit_messages: int = Field(
        default=30,
        ge=1,
        le=100,
        description="Maximum messages per window"
    )
    rate_limit_window: int = Field(
        default=60,
        ge=10,
        le=3600,
        description="Rate limit window in seconds"
    )
    
    # Logging
    log_level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Logging level"
    )
    log_file: Path = Field(
        default=Path.home() / "telegram-agent" / "logs" / "agent.log",
        description="Log file path"
    )
    log_format_json: bool = Field(
        default=False,
        description="Use JSON format for logs (better for programmatic parsing)"
    )
    
    # Paths
    screenshots_dir: Path = Field(
        default=Path.home() / "telegram-agent" / "screenshots",
        description="Screenshot storage directory"
    )
    temp_dir: Path = Field(
        default=Path("/tmp/telegram_agent"),
        description="Temporary file directory"
    )
    venvs_dir: Path = Field(
        default=Path.home() / ".telegram_agent" / "venvs",
        description="Python virtual environments directory"
    )
    knowledge_base_dir: Path = Field(
        default=Path.home() / ".telegram_agent" / "knowledge_base",
        description="Knowledge base storage directory"
    )
    
    # Optional Features
    verbose_routing: bool = Field(
        default=False,
        description="Show routing decisions in responses"
    )

    # Docker Tools Configuration
    docker_tools_enabled: bool = Field(
        default=False,
        description="Enable Docker management tools"
    )
    docker_socket_path: str = Field(
        default="/var/run/docker.sock",
        description="Path to Docker socket"
    )

    # Health Check HTTP Server
    health_check_enabled: bool = Field(
        default=True,
        description="Enable HTTP health check endpoint for monitoring"
    )
    health_check_port: int = Field(
        default=8765,
        ge=1024,
        le=65535,
        description="Port for health check HTTP server (localhost only)"
    )

    # Model Preferences (configurable model routing)
    # These can be overridden in .env to match your available models
    model_pref_trivial: str = Field(
        default="ollama_qwen25_05b,ollama_qwen25_1.5b",
        description="Comma-separated preferred models for trivial tasks"
    )
    model_pref_simple: str = Field(
        default="ollama_qwen25_1.5b,ollama_llama32_3b,ollama_qwen25_7b",
        description="Comma-separated preferred models for simple tasks"
    )
    model_pref_moderate: str = Field(
        default="ollama_qwen25_7b,ollama_qwen25_14b",
        description="Comma-separated preferred models for moderate tasks"
    )
    model_pref_complex: str = Field(
        default="ollama_qwen25_14b,ollama_qwen25_32b",
        description="Comma-separated preferred models for complex tasks"
    )
    model_pref_expert: str = Field(
        default="ollama_qwen25_32b,ollama_qwen25_14b",
        description="Comma-separated preferred models for expert tasks"
    )
    model_pref_code: str = Field(
        default="ollama_qwen25_coder,ollama_deepseek_coder,ollama_qwen25_14b",
        description="Comma-separated preferred models for code tasks"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @validator('ollama_base_url', 'lmstudio_base_url')
    def validate_url(cls, v):
        """Ensure URLs are properly formatted"""
        if not v.startswith('http://') and not v.startswith('https://'):
            raise ValueError('URL must start with http:// or https://')
        return v
    
    @validator('browser_data_dir', 'log_file', 'screenshots_dir', 'temp_dir', 'venvs_dir', 'knowledge_base_dir')
    def expand_path(cls, v):
        """Expand user paths"""
        return Path(v).expanduser().absolute()

    @validator('docker_socket_path')
    def validate_docker_socket(cls, v, values):
        """
        Validate Docker socket exists if Docker tools are enabled.
        Fail fast at startup if docker_tools_enabled=True but socket is missing.
        """
        # Only validate if Docker tools are explicitly enabled
        docker_enabled = values.get('docker_tools_enabled', False)

        if docker_enabled:
            socket_path = Path(v)

            # Check if socket exists
            if not socket_path.exists():
                raise ValueError(
                    f"Docker socket not found at {v}. "
                    f"Either disable Docker tools (DOCKER_TOOLS_ENABLED=false) "
                    f"or ensure Docker is running and the socket path is correct."
                )

            # Check if it's a socket (not a regular file)
            import stat
            if not stat.S_ISSOCK(socket_path.stat().st_mode):
                raise ValueError(
                    f"Path {v} exists but is not a socket. "
                    f"Please verify Docker is installed correctly."
                )

        return v

    def create_directories(self):
        """Create all required directories"""
        dirs_to_create = [
            self.browser_data_dir,
            self.log_file.parent,
            self.screenshots_dir,
            self.temp_dir,
            self.venvs_dir,
            self.knowledge_base_dir
        ]
        
        for directory in dirs_to_create:
            directory.mkdir(parents=True, exist_ok=True)


def load_and_validate_config() -> Optional[AgentConfig]:
    """
    Load and validate configuration from .env file.
    Returns validated config or None if validation fails.
    """
    
    # Load .env file
    env_path = Path(".env")
    
    if not env_path.exists():
        print("âŒ Error: .env file not found")
        print("   Create a .env file with required configuration")
        print("   See .env.example for template")
        return None
    
    load_dotenv(env_path)
    
    # Prepare configuration dictionary
    config_dict = {
        'telegram_bot_token': os.getenv('TELEGRAM_BOT_TOKEN'),
        'telegram_user_id': os.getenv('TELEGRAM_USER_ID'),
        'llm_backend': os.getenv('LLM_BACKEND', 'ollama'),
        'ollama_base_url': os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'),
        'lmstudio_base_url': os.getenv('LMSTUDIO_BASE_URL', 'http://localhost:1234/v1'),
        'mlx_model_path': os.getenv('MLX_MODEL_PATH'),
        'routing_strategy': os.getenv('ROUTING_STRATEGY', 'auto'),
        'routing_max_cost': float(os.getenv('ROUTING_MAX_COST', '0.7')),
        'tools_require_confirmation': os.getenv('TOOLS_REQUIRE_CONFIRMATION', 'true').lower() == 'true',
        'max_parallel_tools': int(os.getenv('MAX_PARALLEL_TOOLS', '3')),
        'browser_headless': os.getenv('BROWSER_HEADLESS', 'true').lower() == 'true',
        'browser_data_dir': os.getenv('BROWSER_DATA_DIR', '~/telegram-agent/browser_data'),
        'memory_enabled': os.getenv('MEMORY_ENABLED', 'true').lower() == 'true',
        'memory_encryption_key': os.getenv('MEMORY_ENCRYPTION_KEY'),
        'rate_limit_messages': int(os.getenv('RATE_LIMIT_MESSAGES', '30')),
        'rate_limit_window': int(os.getenv('RATE_LIMIT_WINDOW', '60')),
        'log_level': os.getenv('LOG_LEVEL', 'INFO'),
        'log_file': os.getenv('LOG_FILE', '~/telegram-agent/logs/agent.log'),
        'log_format_json': os.getenv('LOG_FORMAT_JSON', 'false').lower() == 'true',
        'screenshots_dir': os.getenv('SCREENSHOTS_DIR', '~/telegram-agent/screenshots'),
        'temp_dir': os.getenv('TEMP_DIR', '/tmp/telegram_agent'),
        'venvs_dir': os.getenv('VENVS_DIR', '~/.telegram_agent/venvs'),
        'knowledge_base_dir': os.getenv('KNOWLEDGE_BASE_DIR', '~/.telegram_agent/knowledge_base'),
        'verbose_routing': os.getenv('VERBOSE_ROUTING', 'false').lower() == 'true',
        'docker_tools_enabled': os.getenv('DOCKER_TOOLS_ENABLED', 'false').lower() == 'true',
        'docker_socket_path': os.getenv('DOCKER_SOCKET_PATH', '/var/run/docker.sock'),
        'health_check_enabled': os.getenv('HEALTH_CHECK_ENABLED', 'true').lower() == 'true',
        'health_check_port': int(os.getenv('HEALTH_CHECK_PORT', '8765')),
        'model_pref_trivial': os.getenv('MODEL_PREF_TRIVIAL', 'ollama_qwen25_05b,ollama_qwen25_1.5b'),
        'model_pref_simple': os.getenv('MODEL_PREF_SIMPLE', 'ollama_qwen25_1.5b,ollama_llama32_3b,ollama_qwen25_7b'),
        'model_pref_moderate': os.getenv('MODEL_PREF_MODERATE', 'ollama_qwen25_7b,ollama_qwen25_14b'),
        'model_pref_complex': os.getenv('MODEL_PREF_COMPLEX', 'ollama_qwen25_14b,ollama_qwen25_32b'),
        'model_pref_expert': os.getenv('MODEL_PREF_EXPERT', 'ollama_qwen25_32b,ollama_qwen25_14b'),
        'model_pref_code': os.getenv('MODEL_PREF_CODE', 'ollama_qwen25_coder,ollama_deepseek_coder,ollama_qwen25_14b'),
    }
    
    try:
        # Validate configuration
        config = AgentConfig(**config_dict)
        
        # Create required directories
        config.create_directories()
        
        print("âœ… Configuration validated successfully")
        return config
    
    except ValidationError as e:
        print("âŒ Configuration validation failed:")
        print()
        for error in e.errors():
            field = " -> ".join(str(loc) for loc in error['loc'])
            message = error['msg']
            print(f"   â€¢ {field}: {message}")
        print()
        print("Please fix the issues in your .env file")
        return None
    
    except ValueError as e:
        print(f"âŒ Configuration error: {str(e)}")
        return None


def generate_example_env():
    """Generate example .env file"""

    example = """# Portal 4.1 Configuration
# Copy this to .env and fill in your values

# ============================================================================
# REQUIRED CONFIGURATION
# ============================================================================

# Get from @BotFather on Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Get from @userinfobot on Telegram
TELEGRAM_USER_ID=your_user_id_here

# ============================================================================
# LLM BACKEND CONFIGURATION
# ============================================================================

# Backend selection: ollama, lmstudio, or mlx
LLM_BACKEND=ollama

# Ollama configuration
OLLAMA_BASE_URL=http://localhost:11434

# LM Studio configuration (if using lmstudio backend)
LMSTUDIO_BASE_URL=http://localhost:1234/v1

# MLX configuration (if using mlx backend on Apple Silicon)
# MLX_MODEL_PATH=/path/to/mlx/model

# ============================================================================
# ROUTING CONFIGURATION
# ============================================================================

# Strategy: auto, speed, quality, balanced, cost_optimized
ROUTING_STRATEGY=auto

# Maximum computational cost (0.0-1.0)
ROUTING_MAX_COST=0.7

# ============================================================================
# TOOL CONFIGURATION
# ============================================================================

# Require confirmation for dangerous operations
TOOLS_REQUIRE_CONFIRMATION=true

# Maximum parallel tool executions
MAX_PARALLEL_TOOLS=3

# ============================================================================
# BROWSER CONFIGURATION
# ============================================================================

BROWSER_HEADLESS=true
BROWSER_DATA_DIR=~/telegram-agent/browser_data

# ============================================================================
# MEMORY CONFIGURATION
# ============================================================================

MEMORY_ENABLED=true

# Encryption key (leave empty to auto-generate)
MEMORY_ENCRYPTION_KEY=

# ============================================================================
# RATE LIMITING
# ============================================================================

# Maximum messages per window
RATE_LIMIT_MESSAGES=30

# Window duration in seconds
RATE_LIMIT_WINDOW=60

# ============================================================================
# LOGGING
# ============================================================================

# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Log file path
LOG_FILE=~/telegram-agent/logs/agent.log

# ============================================================================
# DIRECTORY PATHS
# ============================================================================

SCREENSHOTS_DIR=~/telegram-agent/screenshots
TEMP_DIR=/tmp/telegram_agent
VENVS_DIR=~/.telegram_agent/venvs
KNOWLEDGE_BASE_DIR=~/.telegram_agent/knowledge_base

# ============================================================================
# OPTIONAL FEATURES
# ============================================================================

# Show routing decisions in responses
VERBOSE_ROUTING=false
"""
    
    with open(".env.example", "w") as f:
        f.write(example)
    
    print("âœ… Generated .env.example")
    print("   Copy to .env and fill in your values:")
    print("   cp .env.example .env")


if __name__ == "__main__":
    """Run validation or generate example"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Configuration validator")
    parser.add_argument('--generate', action='store_true', help='Generate example .env file')
    parser.add_argument('--validate', action='store_true', help='Validate current configuration')
    
    args = parser.parse_args()
    
    if args.generate:
        generate_example_env()
    elif args.validate or not args.generate:
        config = load_and_validate_config()
        if config:
            print()
            print("Configuration Summary:")
            print(f"  Backend: {config.llm_backend}")
            print(f"  Strategy: {config.routing_strategy}")
            print(f"  Rate Limit: {config.rate_limit_messages} msgs / {config.rate_limit_window}s")
            print(f"  Log Level: {config.log_level}")
            sys.exit(0)
        else:
            sys.exit(1)
