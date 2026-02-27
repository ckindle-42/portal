"""Tests for AgentCore MCP tool dispatch loop (_run_execution_with_mcp_loop)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_core_with_mcp(config=None):
    """AgentCore with mocked MCP registry."""
    from portal.core.agent_core import AgentCore

    mock_tool_registry = MagicMock()
    mock_tool_registry.discover_and_load.return_value = (0, 0)
    mock_tool_registry.get_tool_list.return_value = []

    mock_model_registry = MagicMock()
    mock_model_registry.models = {}

    mock_router = MagicMock()
    mock_router.strategy = MagicMock(value="auto")
    mock_routing_decision = MagicMock()
    mock_routing_decision.model_id = "test-model"
    mock_routing_decision.reasoning = "test"
    mock_routing_decision.fallback_models = []
    mock_routing_decision.classification = MagicMock()
    mock_routing_decision.classification.complexity = MagicMock(value="simple")
    mock_router.route.return_value = mock_routing_decision

    mock_execution_engine = MagicMock()
    mock_prompt_manager = MagicMock()
    mock_prompt_manager.build_system_prompt.return_value = "You are a helpful assistant."

    mock_context_manager = AsyncMock()
    mock_context_manager.get_history.return_value = []
    mock_context_manager.add_message = AsyncMock()

    mock_event_bus = AsyncMock()
    mock_event_bus.publish = AsyncMock()

    mock_mcp_registry = AsyncMock()

    with patch("portal.core.agent_core.MemoryManager"):
        with patch(
            "portal.core.agent_core.HITLApprovalMiddleware", side_effect=Exception("no redis")
        ):
            core = AgentCore(
                model_registry=mock_model_registry,
                router=mock_router,
                execution_engine=mock_execution_engine,
                context_manager=mock_context_manager,
                event_bus=mock_event_bus,
                prompt_manager=mock_prompt_manager,
                tool_registry=mock_tool_registry,
                config=config or {"mcp_tool_max_rounds": 3},
                mcp_registry=mock_mcp_registry,
            )
    return core


@pytest.mark.asyncio
async def test_mcp_loop_no_tool_calls():
    """When model returns no tool_calls, loop exits after one round."""
    core = _make_core_with_mcp()

    result_mock = MagicMock()
    result_mock.success = True
    result_mock.response = "Hello"
    result_mock.model_used = "test-model"
    result_mock.tool_calls = []
    result_mock.error = None

    core.execution_engine.execute = AsyncMock(return_value=result_mock)

    result, tool_results = await core._run_execution_with_mcp_loop(
        query="hi",
        system_prompt="",
        available_tools=[],
        chat_id="test",
        trace_id="t1",
    )

    assert result.response == "Hello"
    assert tool_results == []
    # Only one execute call (no tool calls → exits immediately)
    assert core.execution_engine.execute.call_count == 1


@pytest.mark.asyncio
async def test_mcp_loop_dispatches_tool_calls():
    """When model returns tool_calls, they are dispatched to MCP registry."""
    core = _make_core_with_mcp()

    call_count = 0

    async def mock_execute(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            m = MagicMock()
            m.success = True
            m.response = ""
            m.model_used = "test-model"
            m.tool_calls = [{"tool": "read_file", "arguments": {"path": "/tmp/x"}}]
            m.error = None
            return m
        m = MagicMock()
        m.success = True
        m.response = "File contents: hello"
        m.model_used = "test-model"
        m.tool_calls = []
        m.error = None
        return m

    core.execution_engine.execute = mock_execute
    core.mcp_registry.call_tool = AsyncMock(return_value={"content": "hello"})

    result, tool_results = await core._run_execution_with_mcp_loop(
        query="read /tmp/x",
        system_prompt="",
        available_tools=[],
        chat_id="test",
        trace_id="t1",
    )

    assert result.response == "File contents: hello"
    assert len(tool_results) >= 1
    core.mcp_registry.call_tool.assert_called()


@pytest.mark.asyncio
async def test_mcp_loop_respects_max_rounds():
    """Loop stops after mcp_tool_max_rounds even if tools keep being requested."""
    core = _make_core_with_mcp(config={"mcp_tool_max_rounds": 2})

    execute_count = 0

    async def always_tool_call(**kwargs):
        nonlocal execute_count
        execute_count += 1
        m = MagicMock()
        m.success = True
        m.response = ""
        m.model_used = "test-model"
        m.tool_calls = [{"tool": "echo", "arguments": {}}]
        m.error = None
        return m

    core.execution_engine.execute = always_tool_call
    core.mcp_registry.call_tool = AsyncMock(return_value={"ok": True})

    result, tool_results = await core._run_execution_with_mcp_loop(
        query="loop",
        system_prompt="",
        available_tools=[],
        chat_id="test",
        trace_id="t1",
    )

    # With max_rounds=2: 2 tool loop iterations + 1 final call = 3 execute calls
    assert execute_count == 3
    # Should collect 2 rounds of tool results
    assert len(tool_results) == 2


@pytest.mark.asyncio
async def test_mcp_loop_no_mcp_registry_skips_tools():
    """Without an MCP registry, tool calls are not dispatched."""
    # Create core WITHOUT mcp_registry
    from portal.core.agent_core import AgentCore

    mock_tool_registry = MagicMock()
    mock_tool_registry.discover_and_load.return_value = (0, 0)
    mock_tool_registry.get_tool_list.return_value = []

    mock_model_registry = MagicMock()
    mock_model_registry.models = {}

    mock_router = MagicMock()
    mock_router.strategy = MagicMock(value="auto")
    mock_routing_decision = MagicMock()
    mock_routing_decision.model_id = "test-model"
    mock_routing_decision.reasoning = "test"
    mock_routing_decision.fallback_models = []
    mock_routing_decision.classification = MagicMock()
    mock_routing_decision.classification.complexity = MagicMock(value="simple")
    mock_router.route.return_value = mock_routing_decision

    mock_execution_engine = MagicMock()
    mock_prompt_manager = MagicMock()
    mock_prompt_manager.build_system_prompt.return_value = ""
    mock_context_manager = AsyncMock()
    mock_context_manager.get_history.return_value = []
    mock_event_bus = AsyncMock()
    mock_event_bus.publish = AsyncMock()

    with patch("portal.core.agent_core.MemoryManager"):
        with patch(
            "portal.core.agent_core.HITLApprovalMiddleware", side_effect=Exception("no redis")
        ):
            core = AgentCore(
                model_registry=mock_model_registry,
                router=mock_router,
                execution_engine=mock_execution_engine,
                context_manager=mock_context_manager,
                event_bus=mock_event_bus,
                prompt_manager=mock_prompt_manager,
                tool_registry=mock_tool_registry,
                config={"mcp_tool_max_rounds": 3},
                mcp_registry=None,  # No MCP registry
            )

    result_mock = MagicMock()
    result_mock.success = True
    result_mock.response = "Direct answer"
    result_mock.model_used = "test-model"
    result_mock.tool_calls = [{"tool": "echo", "arguments": {}}]  # Tool calls present but ignored
    result_mock.error = None
    core.execution_engine.execute = AsyncMock(return_value=result_mock)

    result, tool_results = await core._run_execution_with_mcp_loop(
        query="test",
        system_prompt="",
        available_tools=[],
        chat_id="test",
        trace_id="t1",
    )

    # Without MCP registry, exits immediately with no tool dispatch
    assert result.response == "Direct answer"
    assert tool_results == []
    assert core.execution_engine.execute.call_count == 1


# ---------------------------------------------------------------------------
# Context preservation on final execution (merged from test_mcp_context_preservation.py)
# ---------------------------------------------------------------------------


def _make_core_for_context_preservation():
    """AgentCore with MCP registry that verifies context accumulation."""
    from portal.core.agent_core import AgentCore
    from portal.core.context_manager import ContextManager
    from portal.core.event_bus import EventBus
    from portal.core.prompt_manager import PromptManager
    from portal.routing.execution_engine import ExecutionEngine
    from portal.routing.intelligent_router import IntelligentRouter
    from portal.routing.model_registry import ModelRegistry

    registry = MagicMock(spec=ModelRegistry)
    registry.models = {}

    router = MagicMock(spec=IntelligentRouter)
    router.strategy = MagicMock()
    router.strategy.value = "auto"

    engine = MagicMock(spec=ExecutionEngine)
    event_bus = EventBus()
    context = MagicMock(spec=ContextManager)
    context.get_history = AsyncMock(return_value=[])
    context.get_formatted_history = AsyncMock(return_value=[])
    context.add_message = AsyncMock()
    prompt_mgr = MagicMock(spec=PromptManager)
    prompt_mgr.build_system_prompt = MagicMock(return_value="system prompt")

    tool_registry = MagicMock()
    tool_registry.discover_and_load = MagicMock(return_value=(0, 0))
    tool_registry.get_all_tools = MagicMock(return_value=[])
    tool_registry.get_tool = MagicMock(return_value=None)

    mcp_registry = MagicMock()
    mcp_registry.call_tool = AsyncMock(return_value={"output": "tool result"})

    core = AgentCore(
        model_registry=registry,
        router=router,
        execution_engine=engine,
        context_manager=context,
        event_bus=event_bus,
        prompt_manager=prompt_mgr,
        tool_registry=tool_registry,
        config={"mcp_tool_max_rounds": 2},
        mcp_registry=mcp_registry,
    )

    return core, engine


@pytest.mark.asyncio
async def test_mcp_loop_preserves_context_on_final_execution():
    """
    When the MCP tool loop exhausts max_rounds, the final execution pass
    must include accumulated tool messages (not messages=None).
    """
    from portal.routing.execution_engine import ExecutionResult
    from portal.routing.intelligent_router import RoutingDecision, TaskClassification

    core, engine = _make_core_for_context_preservation()

    classification = MagicMock(spec=TaskClassification)
    classification.complexity = MagicMock()
    classification.complexity.value = "simple"

    decision = MagicMock(spec=RoutingDecision)
    decision.model_id = "test-model"
    decision.reasoning = "test"
    decision.classification = classification
    decision.fallback_models = []

    core.router.route = MagicMock(return_value=decision)

    result_with_tools = MagicMock(spec=ExecutionResult)
    result_with_tools.success = True
    result_with_tools.tool_calls = [{"tool": "test_tool", "arguments": {}}]
    result_with_tools.model_used = "test-model"
    result_with_tools.error = None

    result_final = MagicMock(spec=ExecutionResult)
    result_final.success = True
    result_final.tool_calls = []
    result_final.model_used = "test-model"
    result_final.response = "Final answer"
    result_final.tokens_generated = 10
    result_final.tools_used = []
    result_final.error = None

    engine.execute = AsyncMock(side_effect=[result_with_tools, result_with_tools, result_final])

    result, tool_results = await core._run_execution_with_mcp_loop(
        query="test",
        system_prompt="sys",
        available_tools=[],
        chat_id="c1",
        trace_id="t1",
        messages=[{"role": "user", "content": "test"}],
    )

    assert len(tool_results) == 2
