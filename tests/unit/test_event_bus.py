"""Tests for portal.core.event_bus"""

from __future__ import annotations

import asyncio
from collections import deque

import pytest

from portal.core.event_bus import Event, EventBus, EventEmitter, EventType


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
        events_a, events_b = [], []

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
        await bus.publish(EventType.TOOL_STARTED, "c1", {}, "t")  # Should not raise

    @pytest.mark.asyncio
    async def test_subscriber_exception_does_not_propagate(self):
        bus = EventBus()

        async def bad_handler(data):
            raise RuntimeError("boom")

        bus.subscribe(EventType.PROCESSING_STARTED, bad_handler)
        await bus.publish(EventType.PROCESSING_STARTED, "c1", {}, "t")  # Should not raise
        await asyncio.sleep(0.05)

    @pytest.mark.asyncio
    async def test_different_event_types_isolated(self):
        bus = EventBus()
        started_events, completed_events = [], []

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

    @pytest.mark.asyncio
    async def test_unsubscribe_unknown_callback_is_safe(self):
        bus = EventBus()

        async def handler(event: Event) -> None:
            pass

        bus.unsubscribe(EventType.PROCESSING_STARTED, handler)  # Never registered
        bus.subscribe(EventType.PROCESSING_STARTED, handler)

        async def other_handler(event: Event) -> None:
            pass

        bus.unsubscribe(EventType.PROCESSING_STARTED, other_handler)


class TestEventBusHistory:
    @pytest.mark.asyncio
    async def test_event_history_evicts_oldest(self):
        bus = EventBus(enable_history=True, max_history=2)
        assert isinstance(bus._event_history, deque)
        assert bus._event_history.maxlen == 2
        await bus.publish(EventType.PROCESSING_STARTED, "c1", {"msg": "first"})
        await bus.publish(EventType.PROCESSING_COMPLETED, "c1", {"msg": "second"})
        await bus.publish(EventType.PROCESSING_FAILED, "c1", {"msg": "third"})
        assert len(bus._event_history) == 2
        events = list(bus._event_history)
        assert events[0].data["msg"] == "second"
        assert events[1].data["msg"] == "third"

    @pytest.mark.asyncio
    async def test_event_history_disabled_stays_empty(self):
        bus = EventBus(enable_history=False)
        await bus.publish(EventType.PROCESSING_STARTED, "c1", {"msg": "test"})
        assert len(bus._event_history) == 0


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
        assert d["trace_id"] is not None
