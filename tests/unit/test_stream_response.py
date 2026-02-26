"""Tests for AgentCore.stream_response()"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from portal.core.types import IncomingMessage


def _make_agent_core(config=None):
    """Create AgentCore with mocked dependencies."""
    from portal.core.agent_core import AgentCore

    mock_tool_registry = MagicMock()
    mock_tool_registry.discover_and_load.return_value = (0, 0)
    mock_tool_registry.get_tool_list.return_value = []

    mock_model_registry = MagicMock()
    mock_model_registry.models = {}

    mock_router = MagicMock()
    mock_router.strategy = MagicMock(value="auto")

    mock_execution_engine = MagicMock()
    mock_prompt_manager = MagicMock()
    mock_prompt_manager.build_system_prompt.return_value = "You are a helpful assistant."

    mock_context_manager = AsyncMock()
    mock_context_manager.get_history.return_value = []
    mock_context_manager.add_message = AsyncMock()

    mock_event_bus = AsyncMock()
    mock_event_bus.publish = AsyncMock()

    with patch("portal.core.agent_core.MemoryManager"):
        with patch("portal.core.agent_core.HITLApprovalMiddleware", side_effect=Exception("no redis")):
            core = AgentCore(
                model_registry=mock_model_registry,
                router=mock_router,
                execution_engine=mock_execution_engine,
                context_manager=mock_context_manager,
                event_bus=mock_event_bus,
                prompt_manager=mock_prompt_manager,
                tool_registry=mock_tool_registry,
                config=config or {},
            )
    return core


@pytest.mark.asyncio
async def test_stream_response_yields_tokens():
    """stream_response yields tokens from execution engine."""
    core = _make_agent_core()

    async def fake_stream(**kwargs):
        for token in ["Hello", " ", "world"]:
            yield token

    core.execution_engine.generate_stream = fake_stream

    incoming = IncomingMessage(id="test-1", text="hi", model="auto")
    tokens = []
    async for token in core.stream_response(incoming):
        tokens.append(token)

    assert tokens == ["Hello", " ", "world"]


@pytest.mark.asyncio
async def test_stream_response_saves_to_context():
    """Completed stream is saved to context manager."""
    core = _make_agent_core()

    async def fake_stream(**kwargs):
        for token in ["Hello", " ", "world"]:
            yield token

    core.execution_engine.generate_stream = fake_stream

    incoming = IncomingMessage(id="test-2", text="hi", model="auto", source="web")
    tokens = []
    async for token in core.stream_response(incoming):
        tokens.append(token)

    # Verify context manager was called to save the response
    core.context_manager.add_message.assert_called()
    # Find the call that saved the assistant response (role='assistant')
    assistant_calls = [
        call for call in core.context_manager.add_message.call_args_list
        if call.kwargs.get('role') == 'assistant' or
           (call.args and 'assistant' in str(call.args))
    ]
    assert len(assistant_calls) >= 1, "Expected at least one assistant message saved"
    # Verify the full response was saved
    save_call = assistant_calls[0]
    content = save_call.kwargs.get('content', '')
    assert content == "Hello world"


@pytest.mark.asyncio
async def test_stream_response_empty_yields_nothing():
    """An empty stream doesn't crash and yields no tokens."""
    core = _make_agent_core()

    async def empty_stream(**kwargs):
        return
        yield  # make it a generator

    core.execution_engine.generate_stream = empty_stream

    incoming = IncomingMessage(id="test-3", text="hi", model="auto")
    tokens = []
    async for token in core.stream_response(incoming):
        tokens.append(token)

    assert tokens == []


@pytest.mark.asyncio
async def test_stream_response_does_not_save_empty_response():
    """An empty stream does not trigger a context save."""
    core = _make_agent_core()

    async def empty_stream(**kwargs):
        return
        yield

    core.execution_engine.generate_stream = empty_stream

    incoming = IncomingMessage(id="test-4", text="hi", model="auto", source="web")
    async for _ in core.stream_response(incoming):
        pass

    # Only user message save should have happened (no assistant save for empty response)
    assistant_saves = [
        call for call in core.context_manager.add_message.call_args_list
        if call.kwargs.get('role') == 'assistant'
    ]
    assert len(assistant_saves) == 0
