"""Dependency factories for AgentCore — decouples creation from core logic."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from portal.routing import ExecutionEngine, IntelligentRouter, ModelRegistry, RoutingStrategy

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


def create_router(model_registry: ModelRegistry, config: dict[str, Any]) -> IntelligentRouter:
    """Return an IntelligentRouter configured from *config*."""
    strategy_name = config.get("routing_strategy", "AUTO").upper()
    routing_strategy = getattr(RoutingStrategy, strategy_name, RoutingStrategy.AUTO)
    model_preferences = config.get("model_preferences", {})
    logger.info("Creating IntelligentRouter", strategy=routing_strategy.value)
    return IntelligentRouter(
        model_registry, strategy=routing_strategy, model_preferences=model_preferences
    )


def create_execution_engine(
    model_registry: ModelRegistry,
    router: IntelligentRouter,
    config: dict[str, Any],
) -> ExecutionEngine:
    """Return an ExecutionEngine with backend/circuit-breaker config."""
    backend_config = {
        "ollama_base_url": config.get("ollama_base_url", "http://localhost:11434"),
        "circuit_breaker_enabled": config.get("circuit_breaker_enabled", True),
        "circuit_breaker_threshold": config.get("circuit_breaker_threshold", 3),
        "circuit_breaker_timeout": config.get("circuit_breaker_timeout", 60),
        "circuit_breaker_half_open_calls": config.get("circuit_breaker_half_open_calls", 1),
    }
    logger.info(
        "Creating ExecutionEngine",
        ollama_url=backend_config["ollama_base_url"],
        circuit_breaker=backend_config["circuit_breaker_enabled"],
    )
    return ExecutionEngine(model_registry, router, backend_config)


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
        self.router = create_router(self.model_registry, config)
        self.execution_engine = create_execution_engine(self.model_registry, self.router, config)
        self.context_manager = create_context_manager(config)
        self.event_bus = create_event_bus_instance(config)
        self.prompt_manager = create_prompt_manager(config)
        self.tool_registry = create_tool_registry(config)
        self.mcp_registry = None  # populated via create_mcp_registry()
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
