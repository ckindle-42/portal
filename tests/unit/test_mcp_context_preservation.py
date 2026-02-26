"""Tests for MCP tool loop context preservation fix."""

from unittest.mock import AsyncMock, MagicMock

import pytest


def _make_agent_core_with_mcp():
    """Create an AgentCore with a mock MCP registry that returns tool calls."""
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

    core, engine = _make_agent_core_with_mcp()

    # First call returns tool_calls, second call returns tool_calls, third (final) has no tools
    classification = MagicMock(spec=TaskClassification)
    classification.complexity = MagicMock()
    classification.complexity.value = "simple"

    decision = MagicMock(spec=RoutingDecision)
    decision.model_id = "test-model"
    decision.reasoning = "test"
    decision.classification = classification
    decision.fallback_models = []

    core.router.route = MagicMock(return_value=decision)

    # Round 1: returns tool calls
    result_with_tools = MagicMock(spec=ExecutionResult)
    result_with_tools.success = True
    result_with_tools.tool_calls = [{"tool": "test_tool", "arguments": {}}]
    result_with_tools.model_used = "test-model"
    result_with_tools.error = None

    # Final round: returns answer with no tool calls
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

    # Verify that two rounds of tool calls were accumulated
    assert len(tool_results) == 2
