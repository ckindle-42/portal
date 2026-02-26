import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.modules.setdefault("redis", MagicMock())

from portal.core.agent_core import AgentCore


@pytest.fixture
def agent_core() -> AgentCore:
    model_registry = MagicMock()
    router = MagicMock()
    router.strategy.value = "auto"
    execution_engine = MagicMock()
    context_manager = MagicMock()
    event_bus = MagicMock()
    prompt_manager = MagicMock()
    tool_registry = MagicMock()
    tool_registry.discover_and_load.return_value = (0, 0)

    return AgentCore(
        model_registry=model_registry,
        router=router,
        execution_engine=execution_engine,
        context_manager=context_manager,
        event_bus=event_bus,
        prompt_manager=prompt_manager,
        tool_registry=tool_registry,
        config={},
        mcp_registry=MagicMock(),
        memory_manager=MagicMock(),
    )


def test_dispatch_mcp_tools_uses_stable_user_id_for_token_checks(agent_core: AgentCore):
    agent_core.hitl_middleware = MagicMock()
    agent_core.hitl_middleware.check_approved.return_value = True
    agent_core.mcp_registry.call_tool = AsyncMock(return_value={"ok": True})

    tool_calls = [{"tool": "bash", "arguments": {"approval_token": "approved-token"}}]

    asyncio.run(
        agent_core._dispatch_mcp_tools(
            tool_calls,
            chat_id="ephemeral-chat-id",
            trace_id="trace-id",
            user_id="stable-user-id",
        )
    )

    agent_core.hitl_middleware.check_approved.assert_called_once_with(
        user_id="stable-user-id",
        token="approved-token",
    )


def test_dispatch_mcp_tools_uses_stable_user_id_when_requesting_approval(agent_core: AgentCore):
    agent_core.hitl_middleware = MagicMock()
    agent_core.hitl_middleware.request = AsyncMock(return_value="new-token")

    tool_calls = [{"tool": "filesystem_write", "arguments": {"path": "/tmp/out.txt"}}]

    asyncio.run(
        agent_core._dispatch_mcp_tools(
            tool_calls,
            chat_id="ephemeral-chat-id",
            trace_id="trace-id",
            user_id="stable-user-id",
        )
    )

    agent_core.hitl_middleware.request.assert_awaited_once_with(
        user_id="stable-user-id",
        channel="telegram",
        tool_name="filesystem_write",
        args={"path": "/tmp/out.txt"},
    )
