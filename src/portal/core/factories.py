"""Dependency factories for AgentCore — decouples creation from core logic."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from portal.routing import ExecutionEngine, IntelligentRouter, ModelRegistry, RoutingStrategy
from portal.routing.backend_registry import BackendRegistry
from portal.routing.model_backends import MLXServerBackend, OllamaBackend
from portal.routing.workspace_registry import WorkspaceRegistry

from .context_manager import ContextManager
from .event_bus import EventBus
from .prompt_manager import PromptManager
from .structured_logger import get_logger

if TYPE_CHECKING:
    from portal.core.agent_core import AgentCore
    from portal.protocols.mcp.mcp_registry import MCPRegistry
    from portal.tools import ToolRegistry

logger = get_logger("Factories")


def create_model_registry(config: dict[str, Any]) -> ModelRegistry:  # noqa: ARG001
    """Return a new ModelRegistry."""
    logger.info("Creating ModelRegistry")
    return ModelRegistry()


def create_workspace_registry(config: dict[str, Any]) -> WorkspaceRegistry:
    """Return a WorkspaceRegistry from *config* workspaces dict."""
    workspaces = config.get("workspaces", {})
    logger.info("Creating WorkspaceRegistry", count=len(workspaces))
    return WorkspaceRegistry(workspaces)


def create_router(
    model_registry: ModelRegistry,
    config: dict[str, Any],
    workspace_registry: WorkspaceRegistry | None = None,
) -> IntelligentRouter:
    """Return an IntelligentRouter configured from *config*."""
    strategy_name = config.get("routing_strategy", "AUTO").upper()
    routing_strategy = getattr(RoutingStrategy, strategy_name, RoutingStrategy.AUTO)
    model_preferences = config.get("model_preferences", {})
    logger.info("Creating IntelligentRouter", strategy=routing_strategy.value)
    return IntelligentRouter(
        model_registry,
        strategy=routing_strategy,
        model_preferences=model_preferences,
        workspace_registry=workspace_registry,
    )


def create_execution_engine(
    model_registry: ModelRegistry,
    router: IntelligentRouter,
    config: dict[str, Any],
) -> ExecutionEngine:
    """Return an ExecutionEngine with backend/circuit-breaker config."""
    ollama_url = config.get("ollama_base_url", "http://localhost:11434")
    backend_config = {
        "ollama_base_url": ollama_url,
        "circuit_breaker_enabled": config.get("circuit_breaker_enabled", True),
        "circuit_breaker_threshold": config.get("circuit_breaker_threshold", 3),
        "circuit_breaker_timeout": config.get("circuit_breaker_timeout", 60),
        "circuit_breaker_half_open_calls": config.get("circuit_breaker_half_open_calls", 1),
    }

    registry = BackendRegistry()
    registry.register("ollama", OllamaBackend(base_url=ollama_url))

    # Register MLX backend if enabled
    mlx_url = config.get("mlx_url", "http://localhost:8800")
    if config.get("enable_mlx", False):
        registry.register("mlx", MLXServerBackend(base_url=mlx_url))

    logger.info(
        "Creating ExecutionEngine",
        ollama_url=ollama_url,
        circuit_breaker=backend_config["circuit_breaker_enabled"],
        backends=registry.available(),
    )
    return ExecutionEngine(model_registry, router, backend_config, backends=registry._backends)


def create_context_manager(config: dict[str, Any]) -> ContextManager:
    """Return a ContextManager with configured message limit."""
    max_messages = config.get("max_context_messages", 50)
    logger.info("Creating ContextManager", max_messages=max_messages)
    return ContextManager(max_context_messages=max_messages)


def create_event_bus_instance(config: dict[str, Any]) -> EventBus:
    """Return an EventBus with optional history enabled."""
    enable_history = config.get("event_bus_enable_history", False)
    max_history = config.get("event_bus_max_history", 1000)
    logger.info("Creating EventBus", enable_history=enable_history, max_history=max_history)
    return EventBus(enable_history=enable_history, max_history=max_history)


def create_prompt_manager(config: dict[str, Any]) -> PromptManager:
    """Return a PromptManager, optionally loading from *prompts_dir*."""
    prompts_dir = config.get("prompts_dir")
    logger.info("Creating PromptManager", prompts_dir=prompts_dir)
    return PromptManager(prompts_dir=prompts_dir)


def create_tool_registry(config: dict[str, Any]) -> ToolRegistry:  # noqa: ARG001
    """Return the global ToolRegistry singleton."""
    from portal.tools import registry  # avoid circular import

    logger.info("Creating ToolRegistry (using global registry)")
    return registry


class DependencyContainer:
    """Container that wires all AgentCore dependencies from a config dict."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.model_registry = create_model_registry(config)
        self.workspace_registry = create_workspace_registry(config)
        self.router = create_router(self.model_registry, config, self.workspace_registry)
        self.execution_engine = create_execution_engine(self.model_registry, self.router, config)
        self.context_manager = create_context_manager(config)
        self.event_bus = create_event_bus_instance(config)
        self.prompt_manager = create_prompt_manager(config)
        self.tool_registry = create_tool_registry(config)
        self.mcp_registry: MCPRegistry | None = None  # populated via create_mcp_registry()
        logger.info("DependencyContainer initialized with all components")

    async def create_mcp_registry(self, mcp_config=None) -> MCPRegistry:
        """Create and populate the MCP server registry from *mcp_config*."""
        from portal.protocols.mcp.mcp_registry import MCPRegistry

        registry = MCPRegistry()
        if mcp_config is None or not getattr(mcp_config, "enabled", True):
            return registry

        transport = getattr(mcp_config, "transport", "mcpo")
        if transport == "mcpo":
            mcpo_url = getattr(mcp_config, "mcpo_url", "http://localhost:9000")
            mcpo_api_key = getattr(mcp_config, "mcpo_api_key", "") or None
            await registry.register(
                name="core", url=mcpo_url, transport="openapi", api_key=mcpo_api_key
            )

        scrapling_url = getattr(mcp_config, "scrapling_url", "http://localhost:8900")
        await registry.register(
            name="scrapling", url=scrapling_url + "/mcp", transport="streamable-http"
        )

        # Document tools (always available — lightweight, no GPU needed)
        documents_url = os.getenv("DOCUMENTS_MCP_URL", f"http://localhost:{os.getenv('DOCUMENTS_MCP_PORT', '8913')}")
        await registry.register(name="documents", url=documents_url, transport="streamable-http")

        # Generation services (when GENERATION_SERVICES=true)
        generation_enabled = os.getenv("GENERATION_SERVICES", "false").lower() == "true"

        if generation_enabled:
            comfyui_url = os.getenv("COMFYUI_MCP_URL", "http://localhost:8910")
            await registry.register(name="comfyui", url=comfyui_url, transport="streamable-http")

            whisper_url = os.getenv("WHISPER_MCP_URL", "http://localhost:8915")
            await registry.register(name="whisper", url=whisper_url, transport="streamable-http")

            video_url = os.getenv("VIDEO_MCP_URL", f"http://localhost:{os.getenv('VIDEO_MCP_PORT', '8911')}")
            await registry.register(name="video", url=video_url, transport="streamable-http")

            music_url = os.getenv("MUSIC_MCP_URL", f"http://localhost:{os.getenv('MUSIC_MCP_PORT', '8912')}")
            await registry.register(name="music", url=music_url, transport="streamable-http")

            # TTS (Fish Speech or CosyVoice)
            tts_url = os.getenv("TTS_MCP_URL", f"http://localhost:{os.getenv('TTS_MCP_PORT', '8916')}")
            await registry.register(name="tts", url=tts_url, transport="streamable-http")

        # Sandbox (when SANDBOX_ENABLED=true)
        if os.getenv("SANDBOX_ENABLED", "false").lower() == "true":
            sandbox_url = os.getenv("SANDBOX_MCP_URL", f"http://localhost:{os.getenv('SANDBOX_MCP_PORT', '8914')}")
            await registry.register(name="sandbox", url=sandbox_url, transport="streamable-http")

        self.mcp_registry = registry
        return registry

    def create_agent_core(self, mcp_registry=None) -> AgentCore:
        """Build an AgentCore from this container's dependencies."""
        from portal.core.agent_core import AgentCore

        deps = self.get_all()
        if mcp_registry is not None:
            deps["mcp_registry"] = mcp_registry
        return AgentCore(**deps)

    def get_all(self) -> dict[str, Any]:
        """Return all dependencies as a flat dict suitable for AgentCore(**deps)."""
        return {
            "model_registry": self.model_registry,
            "router": self.router,
            "execution_engine": self.execution_engine,
            "context_manager": self.context_manager,
            "event_bus": self.event_bus,
            "prompt_manager": self.prompt_manager,
            "tool_registry": self.tool_registry,
            "config": self.config,
            "mcp_registry": self.mcp_registry,
        }


def create_dependencies(config: dict[str, Any]) -> DependencyContainer:
    """Convenience wrapper — create all AgentCore dependencies in one call."""
    return DependencyContainer(config)
