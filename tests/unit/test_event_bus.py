"""Tests for portal.core.event_bus"""

import asyncio

import pytest

from portal.core.event_bus import Event, EventBus, EventEmitter, EventType


class TestEventType:
    def test_enum_values(self):
        assert EventType.PROCESSING_STARTED.value == "processing_started"
        assert EventType.PROCESSING_COMPLETED.value == "processing_completed"
        assert EventType.PROCESSING_FAILED.value == "processing_failed"
        assert EventType.ROUTING_DECISION.value == "routing_decision"
        assert EventType.MODEL_GENERATING.value == "model_generating"
        assert EventType.CONTEXT_LOADED.value == "context_loaded"
        assert EventType.TOOL_STARTED.value == "tool_started"
        assert EventType.TOOL_COMPLETED.value == "tool_completed"
        assert EventType.SECURITY_WARNING.value == "security_warning"


class TestEvent:
    def test_to_dict(self):
        event = Event(
            event_type=EventType.PROCESSING_STARTED,
            chat_id="c1",
            timestamp="2024-01-01",
            data={"key": "val"},
            trace_id="t1",
        )
        d = event.to_dict()
        assert d["event_type"] == "processing_started"
        assert d["chat_id"] == "c1"
        assert d["trace_id"] == "t1"

    def test_to_dict_no_trace(self):
        event = Event(
            event_type=EventType.TOOL_COMPLETED,
            chat_id="c2",
            timestamp="now",
            data={},
        )
        d = event.to_dict()
        assert d["trace_id"] is None


class TestEventBus:
    def test_init(self):
        bus = EventBus()
        assert bus is not None

    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        bus = EventBus()
        events = []

        async def handler(data):
            events.append(data)

        bus.subscribe(EventType.PROCESSING_STARTED, handler)
        await bus.publish(EventType.PROCESSING_STARTED, "chat-1", {"key": "val"}, "trace-1")
        await asyncio.sleep(0.05)
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        bus = EventBus()
        events = []

        async def handler(data):
            events.append(data)

        bus.subscribe(EventType.PROCESSING_STARTED, handler)
        bus.unsubscribe(EventType.PROCESSING_STARTED, handler)
        await bus.publish(EventType.PROCESSING_STARTED, "chat-1", {}, "t")
        await asyncio.sleep(0.05)
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        bus = EventBus()
        events_a = []
        events_b = []

        async def handler_a(data):
            events_a.append(data)

        async def handler_b(data):
            events_b.append(data)

        bus.subscribe(EventType.PROCESSING_COMPLETED, handler_a)
        bus.subscribe(EventType.PROCESSING_COMPLETED, handler_b)
        await bus.publish(EventType.PROCESSING_COMPLETED, "c1", {}, "t")
        await asyncio.sleep(0.05)
        assert len(events_a) >= 1
        assert len(events_b) >= 1

    @pytest.mark.asyncio
    async def test_publish_no_subscribers(self):
        bus = EventBus()
        # Should not raise
        await bus.publish(EventType.TOOL_STARTED, "c1", {}, "t")

    @pytest.mark.asyncio
    async def test_subscriber_exception_does_not_propagate(self):
        bus = EventBus()

        async def bad_handler(data):
            raise RuntimeError("boom")

        bus.subscribe(EventType.PROCESSING_STARTED, bad_handler)
        # Should not raise
        await bus.publish(EventType.PROCESSING_STARTED, "c1", {}, "t")
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_different_event_types_isolated(self):
        bus = EventBus()
        started_events = []
        completed_events = []

        async def started_handler(data):
            started_events.append(data)

        async def completed_handler(data):
            completed_events.append(data)

        bus.subscribe(EventType.PROCESSING_STARTED, started_handler)
        bus.subscribe(EventType.PROCESSING_COMPLETED, completed_handler)

        await bus.publish(EventType.PROCESSING_STARTED, "c1", {}, "t")
        await asyncio.sleep(0.05)

        assert len(started_events) >= 1
        assert len(completed_events) == 0


class TestEventEmitter:
    @pytest.mark.asyncio
    async def test_emit_processing_started(self):
        bus = EventBus()
        events = []

        async def handler(data):
            events.append(data)

        bus.subscribe(EventType.PROCESSING_STARTED, handler)
        emitter = EventEmitter(bus)
        await emitter.emit_processing_started("chat-1", "hello", "trace-1")
        await asyncio.sleep(0.05)
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_emit_tool_started(self):
        bus = EventBus()
        events = []

        async def handler(data):
            events.append(data)

        bus.subscribe(EventType.TOOL_STARTED, handler)
        emitter = EventEmitter(bus)
        await emitter.emit_tool_started("chat-1", "search", "trace-1")
        await asyncio.sleep(0.05)
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_emit_tool_completed(self):
        bus = EventBus()
        events = []

        async def handler(data):
            events.append(data)

        bus.subscribe(EventType.TOOL_COMPLETED, handler)
        emitter = EventEmitter(bus)
        await emitter.emit_tool_completed("chat-1", "search", "42 results", "trace-1")
        await asyncio.sleep(0.05)
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_emit_model_selected(self):
        bus = EventBus()
        events = []

        async def handler(data):
            events.append(data)

        bus.subscribe(EventType.MODEL_SELECTED, handler)
        emitter = EventEmitter(bus)
        await emitter.emit_model_selected("chat-1", "qwen", "complexity routing", "trace-1")
        await asyncio.sleep(0.05)
        assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_emit_security_warning(self):
        bus = EventBus()
        events = []

        async def handler(data):
            events.append(data)

        bus.subscribe(EventType.SECURITY_WARNING, handler)
        emitter = EventEmitter(bus)
        await emitter.emit_security_warning("chat-1", "suspicious input", "trace-1")
        await asyncio.sleep(0.05)
        assert len(events) >= 1
