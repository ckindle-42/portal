"""
Unit tests for EventBus subscriber patterns — subscribe, unsubscribe,
error isolation, and EventEmitter helper.
"""

from __future__ import annotations

import pytest

from portal.core.event_bus import Event, EventBus, EventEmitter, EventType


@pytest.mark.asyncio
async def test_subscribe_and_receive():
    """Subscriber receives events published after subscription."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(EventType.PROCESSING_STARTED, handler)
    await bus.publish(EventType.PROCESSING_STARTED, "chat-1", {"msg": "hello"})

    assert len(received) == 1
    assert received[0].chat_id == "chat-1"
    assert received[0].data["msg"] == "hello"


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    """After unsubscribe, handler no longer receives events."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(EventType.PROCESSING_STARTED, handler)
    bus.unsubscribe(EventType.PROCESSING_STARTED, handler)
    await bus.publish(EventType.PROCESSING_STARTED, "chat-1", {"msg": "hello"})

    assert len(received) == 0


@pytest.mark.asyncio
async def test_unsubscribe_unknown_callback_is_safe():
    """Unsubscribing a callback that was never registered does not crash."""
    bus = EventBus()

    async def handler(event: Event):
        pass

    # Unsubscribe from an event type that has no subscribers
    bus.unsubscribe(EventType.PROCESSING_STARTED, handler)
    # Also subscribe one, then unsubscribe a different one
    bus.subscribe(EventType.PROCESSING_STARTED, handler)

    async def other_handler(event: Event):
        pass

    bus.unsubscribe(EventType.PROCESSING_STARTED, other_handler)


@pytest.mark.asyncio
async def test_subscriber_error_isolation():
    """One subscriber failing does not prevent others from receiving events."""
    bus = EventBus()
    results: list[str] = []

    async def failing_handler(event: Event):
        raise ValueError("deliberate failure")

    async def good_handler(event: Event):
        results.append("ok")

    bus.subscribe(EventType.PROCESSING_STARTED, failing_handler)
    bus.subscribe(EventType.PROCESSING_STARTED, good_handler)

    await bus.publish(EventType.PROCESSING_STARTED, "c1", {"msg": "test"})

    assert results == ["ok"]


@pytest.mark.asyncio
async def test_multiple_event_types():
    """Subscribers only receive events for their subscribed types."""
    bus = EventBus()
    started: list[Event] = []
    completed: list[Event] = []

    async def on_start(event: Event):
        started.append(event)

    async def on_complete(event: Event):
        completed.append(event)

    bus.subscribe(EventType.PROCESSING_STARTED, on_start)
    bus.subscribe(EventType.PROCESSING_COMPLETED, on_complete)

    await bus.publish(EventType.PROCESSING_STARTED, "c1", {"msg": "start"})
    await bus.publish(EventType.PROCESSING_COMPLETED, "c1", {"msg": "done"})

    assert len(started) == 1
    assert len(completed) == 1
    assert started[0].data["msg"] == "start"
    assert completed[0].data["msg"] == "done"


@pytest.mark.asyncio
async def test_event_emitter_processing_started():
    """EventEmitter.emit_processing_started publishes correct event."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(EventType.PROCESSING_STARTED, handler)
    emitter = EventEmitter(bus)
    await emitter.emit_processing_started("c1", "hello", "trace-123")

    assert len(received) == 1
    assert received[0].data["message"] == "hello"
    assert received[0].trace_id == "trace-123"


@pytest.mark.asyncio
async def test_event_emitter_model_selected():
    """EventEmitter.emit_model_selected publishes correct event."""
    bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event):
        received.append(event)

    bus.subscribe(EventType.MODEL_SELECTED, handler)
    emitter = EventEmitter(bus)
    await emitter.emit_model_selected("c1", "qwen2.5:7b", "fast query", "t-1")

    assert len(received) == 1
    assert received[0].data["model"] == "qwen2.5:7b"
    assert received[0].data["reasoning"] == "fast query"


@pytest.mark.asyncio
async def test_event_to_dict():
    """Event.to_dict() serializes all fields."""
    event = Event(
        event_type=EventType.TOOL_STARTED,
        chat_id="chat-1",
        timestamp="2026-02-26T00:00:00Z",
        data={"tool": "git_status"},
        trace_id="abc-123",
    )
    d = event.to_dict()
    assert d["event_type"] == "tool_started"
    assert d["chat_id"] == "chat-1"
    assert d["trace_id"] == "abc-123"
    assert d["data"]["tool"] == "git_status"


@pytest.mark.asyncio
async def test_no_subscribers_is_noop():
    """Publishing to an event type with no subscribers does not crash."""
    bus = EventBus()
    await bus.publish(EventType.SECURITY_WARNING, "c1", {"warning": "test"})
    # No error, no subscribers = no-op
