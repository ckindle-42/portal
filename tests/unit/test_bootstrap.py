"""
Bootstrap smoke tests.

Verifies that DependencyContainer can be constructed and that
create_agent_core() returns a fully wired AgentCore — all without
requiring Docker, Ollama, or any external service.

These are unit-level tests using mocks; they confirm the DI wiring is
correct without executing any real LLM calls.
"""

from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_registry():
    """Return a mock ToolRegistry that satisfies AgentCore.__init__."""
    mock = MagicMock()
    mock.discover_and_load.return_value = (0, 0)
    mock.get_all_tools.return_value = []
    mock.get_tool_list.return_value = []
    mock.get_tool.return_value = None
    return mock


# ---------------------------------------------------------------------------
# DependencyContainer tests
# ---------------------------------------------------------------------------


def test_dependency_container_initialises():
    """DependencyContainer can be created with a minimal config dict."""
    with patch("portal.tools.registry", _make_mock_registry()):
        from portal.core.factories import DependencyContainer

        container = DependencyContainer({"routing_strategy": "AUTO"})

    assert container.model_registry is not None
    assert container.router is not None
    assert container.execution_engine is not None
    assert container.context_manager is not None
    assert container.event_bus is not None
    assert container.prompt_manager is not None
    assert container.tool_registry is not None


def test_get_all_includes_mcp_registry():
    """get_all() must include mcp_registry so AgentCore.__init__ receives it."""
    with patch("portal.tools.registry", _make_mock_registry()):
        from portal.core.factories import DependencyContainer

        container = DependencyContainer({"routing_strategy": "AUTO"})
        deps = container.get_all()

    assert "model_registry" in deps
    assert "router" in deps
    assert "execution_engine" in deps
    assert "context_manager" in deps
    assert "event_bus" in deps
    assert "prompt_manager" in deps
    assert "tool_registry" in deps
    assert "config" in deps
    assert "mcp_registry" in deps


def test_create_agent_core_returns_agent_core():
    """create_agent_core() returns a fully wired AgentCore instance."""
    mock_registry = _make_mock_registry()

    with patch("portal.tools.registry", mock_registry):
        from portal.core.factories import DependencyContainer

        container = DependencyContainer({"routing_strategy": "AUTO"})
        agent = container.create_agent_core()

    assert agent is not None
    assert hasattr(agent, "process_message")
    assert hasattr(agent, "stream_response")
    assert hasattr(agent, "health_check")
    assert hasattr(agent, "mcp_registry")


def test_create_agent_core_callable_methods():
    """process_message and stream_response are coroutine/async-generator callables."""
    import asyncio
    import inspect

    mock_registry = _make_mock_registry()

    with patch("portal.tools.registry", mock_registry):
        from portal.core.factories import DependencyContainer

        container = DependencyContainer({"routing_strategy": "AUTO"})
        agent = container.create_agent_core()

    assert asyncio.iscoroutinefunction(agent.process_message)
    assert inspect.isasyncgenfunction(agent.stream_response)


# ---------------------------------------------------------------------------
# Module-level factory function
# ---------------------------------------------------------------------------


def test_module_level_create_agent_core_accepts_dict():
    """The module-level create_agent_core() works with a plain dict."""
    mock_registry = _make_mock_registry()

    with patch("portal.tools.registry", mock_registry):
        from portal.core.agent_core import create_agent_core

        agent = create_agent_core({"routing_strategy": "AUTO"})

    assert agent is not None
    assert hasattr(agent, "process_message")


def test_module_level_create_agent_core_accepts_settings_object():
    """
    create_agent_core() gracefully handles a Settings-like object that
    has a to_agent_config() method (lifecycle.py path).
    """
    mock_registry = _make_mock_registry()

    class FakeSettings:
        def to_agent_config(self):
            return {"routing_strategy": "AUTO"}

    with patch("portal.tools.registry", mock_registry):
        from portal.core.agent_core import create_agent_core

        agent = create_agent_core(FakeSettings())

    assert agent is not None
