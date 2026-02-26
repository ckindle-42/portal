"""
Dependency Factories for AgentCore
====================================

This module provides factory functions for creating AgentCore dependencies.
This decouples the creation logic from the core, making it easier to:
- Test with mocked dependencies
- Customize implementations
- Configure different backends

v4.6.1: Extracted from create_agent_core for better separation of concerns
"""

from typing import Any, Protocol

from portal.routing import ExecutionEngine, IntelligentRouter, ModelRegistry, RoutingStrategy

from .context_manager import ContextManager
from .event_bus import EventBus
from .prompt_manager import PromptManager
from .structured_logger import get_logger

logger = get_logger('Factories')


# =============================================================================
# FACTORY PROTOCOLS
# =============================================================================

class DependencyFactory(Protocol):
    """Protocol for dependency factories"""

    def create(self, config: dict[str, Any]) -> Any:
        """Create and return a dependency instance"""
        ...


# =============================================================================
# MODEL REGISTRY FACTORY
# =============================================================================

def create_model_registry(config: dict[str, Any]) -> ModelRegistry:
    """
    Create ModelRegistry instance.

    Args:
        config: Configuration dictionary

    Returns:
        Initialized ModelRegistry
    """
    logger.info("Creating ModelRegistry")
    return ModelRegistry()


# =============================================================================
# ROUTER FACTORY
# =============================================================================

def create_router(
    model_registry: ModelRegistry,
    config: dict[str, Any]
) -> IntelligentRouter:
    """
    Create IntelligentRouter instance.

    Args:
        model_registry: Model registry instance
        config: Configuration dictionary

    Returns:
        Initialized IntelligentRouter
    """
    strategy_name = config.get('routing_strategy', 'AUTO').upper()
    routing_strategy = getattr(RoutingStrategy, strategy_name, RoutingStrategy.AUTO)

    model_preferences = config.get('model_preferences', {})

    logger.info(
        "Creating IntelligentRouter",
        strategy=routing_strategy.value,
        model_preferences=bool(model_preferences)
    )

    return IntelligentRouter(
        model_registry,
        strategy=routing_strategy,
        model_preferences=model_preferences
    )


# =============================================================================
# EXECUTION ENGINE FACTORY
# =============================================================================

def create_execution_engine(
    model_registry: ModelRegistry,
    router: IntelligentRouter,
    config: dict[str, Any]
) -> ExecutionEngine:
    """
    Create ExecutionEngine instance.

    Args:
        model_registry: Model registry instance
        router: Router instance
        config: Configuration dictionary

    Returns:
        Initialized ExecutionEngine
    """
    backend_config = {
        'ollama_base_url': config.get('ollama_base_url', 'http://localhost:11434'),
        'lmstudio_base_url': config.get('lmstudio_base_url', 'http://localhost:1234/v1'),
        # Circuit breaker configuration (v4.6.2)
        'circuit_breaker_enabled': config.get('circuit_breaker_enabled', True),
        'circuit_breaker_threshold': config.get('circuit_breaker_threshold', 3),
        'circuit_breaker_timeout': config.get('circuit_breaker_timeout', 60),
        'circuit_breaker_half_open_calls': config.get('circuit_breaker_half_open_calls', 1),
    }

    logger.info(
        "Creating ExecutionEngine",
        ollama_url=backend_config['ollama_base_url'],
        circuit_breaker=backend_config['circuit_breaker_enabled']
    )

    return ExecutionEngine(
        model_registry,
        router,
        backend_config
    )


# =============================================================================
# CONTEXT MANAGER FACTORY
# =============================================================================

def create_context_manager(config: dict[str, Any]) -> ContextManager:
    """
    Create ContextManager instance.

    Args:
        config: Configuration dictionary

    Returns:
        Initialized ContextManager
    """
    max_messages = config.get('max_context_messages', 50)

    logger.info("Creating ContextManager", max_messages=max_messages)

    return ContextManager(max_context_messages=max_messages)


# =============================================================================
# EVENT BUS FACTORY
# =============================================================================

def create_event_bus_instance(config: dict[str, Any]) -> EventBus:
    """
    Create EventBus instance.

    Args:
        config: Configuration dictionary

    Returns:
        Initialized EventBus
    """
    enable_history = config.get('event_bus_enable_history', False)
    max_history = config.get('event_bus_max_history', 1000)

    logger.info(
        "Creating EventBus",
        enable_history=enable_history,
        max_history=max_history
    )

    return EventBus(enable_history=enable_history, max_history=max_history)


# =============================================================================
# PROMPT MANAGER FACTORY
# =============================================================================

def create_prompt_manager(config: dict[str, Any]) -> PromptManager:
    """
    Create PromptManager instance.

    Args:
        config: Configuration dictionary

    Returns:
        Initialized PromptManager
    """
    prompts_dir = config.get('prompts_dir')

    logger.info("Creating PromptManager", prompts_dir=prompts_dir)

    return PromptManager(prompts_dir=prompts_dir)


# =============================================================================
# TOOL REGISTRY FACTORY
# =============================================================================

def create_tool_registry(config: dict[str, Any]) -> 'ToolRegistry':
    """
    Create ToolRegistry instance.

    Args:
        config: Configuration dictionary

    Returns:
        ToolRegistry instance
    """
    # Import here to avoid circular dependency
    from portal.tools import registry

    logger.info("Creating ToolRegistry (using global registry)")

    return registry


# =============================================================================
# MASTER FACTORY - Creates all dependencies
# =============================================================================

class DependencyContainer:
    """
    Container for all AgentCore dependencies.

    This makes it easy to create, configure, and inject dependencies.
    """

    def __init__(self, config: dict[str, Any]):
        """
        Initialize dependency container.

        Args:
            config: Configuration dictionary
        """
        self.config = config

        # Create all dependencies
        self.model_registry = create_model_registry(config)
        self.router = create_router(self.model_registry, config)
        self.execution_engine = create_execution_engine(
            self.model_registry,
            self.router,
            config
        )
        self.context_manager = create_context_manager(config)
        self.event_bus = create_event_bus_instance(config)
        self.prompt_manager = create_prompt_manager(config)
        self.tool_registry = create_tool_registry(config)

        self.mcp_registry = None  # Populated via create_mcp_registry()

        logger.info("DependencyContainer initialized with all components")

    async def create_mcp_registry(self, mcp_config=None) -> "MCPRegistry":
        """Create and populate the MCP server registry from config."""
        from portal.protocols.mcp.mcp_registry import MCPRegistry

        registry = MCPRegistry()

        if mcp_config is None:
            return registry

        if not getattr(mcp_config, "enabled", True):
            return registry

        # Core servers via mcpo or LibreChat native
        transport = getattr(mcp_config, "transport", "mcpo")
        if transport == "mcpo":
            mcpo_url = getattr(mcp_config, "mcpo_url", "http://localhost:9000")
            mcpo_api_key = getattr(mcp_config, "mcpo_api_key", "") or None
            await registry.register(
                name="core",
                url=mcpo_url,
                transport="openapi",
                api_key=mcpo_api_key,
            )

        # Scrapling — always external HTTP MCP
        scrapling_url = getattr(mcp_config, "scrapling_url", "http://localhost:8900")
        await registry.register(
            name="scrapling",
            url=scrapling_url + "/mcp",
            transport="streamable-http",
        )

        self.mcp_registry = registry
        return registry

    def create_agent_core(self, mcp_registry=None) -> "AgentCore":
        """
        Create an AgentCore using all dependencies held by this container.

        The optional mcp_registry argument allows callers to supply an already-
        initialised MCPRegistry; otherwise self.mcp_registry is used (which may
        be None if create_mcp_registry() has not been awaited yet).
        """
        from portal.core.agent_core import AgentCore
        deps = self.get_all()
        if mcp_registry is not None:
            deps['mcp_registry'] = mcp_registry
        return AgentCore(**deps)

    def get_all(self) -> dict[str, Any]:
        """
        Get all dependencies as a dictionary, including mcp_registry.

        Returns:
            Dictionary of all dependencies
        """
        return {
            'model_registry': self.model_registry,
            'router': self.router,
            'execution_engine': self.execution_engine,
            'context_manager': self.context_manager,
            'event_bus': self.event_bus,
            'prompt_manager': self.prompt_manager,
            'tool_registry': self.tool_registry,
            'config': self.config,
            'mcp_registry': self.mcp_registry,
        }


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def create_dependencies(config: dict[str, Any]) -> DependencyContainer:
    """
    Create all AgentCore dependencies in a single call.

    This is the recommended way to create dependencies for AgentCore.

    Args:
        config: Configuration dictionary

    Returns:
        DependencyContainer with all initialized components

    Example:
        >>> config = {'routing_strategy': 'AUTO', 'max_context_messages': 100}
        >>> deps = create_dependencies(config)
        >>> agent_core = AgentCore(**deps.get_all())
    """
    return DependencyContainer(config)
