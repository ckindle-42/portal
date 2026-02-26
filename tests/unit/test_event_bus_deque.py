"""Tests for EventBus deque-based history optimization."""

import pytest

from portal.core.event_bus import EventBus, EventType


@pytest.mark.asyncio
async def test_event_history_uses_deque():
    """Verify that EventBus uses deque with maxlen for O(1) eviction."""
    from collections import deque

    bus = EventBus(enable_history=True, max_history=3)
    assert isinstance(bus._event_history, deque)
    assert bus._event_history.maxlen == 3


@pytest.mark.asyncio
async def test_event_history_evicts_oldest():
    """Verify that publishing beyond max_history evicts oldest events."""
    bus = EventBus(enable_history=True, max_history=2)

    await bus.publish(EventType.PROCESSING_STARTED, "c1", {"msg": "first"})
    await bus.publish(EventType.PROCESSING_COMPLETED, "c1", {"msg": "second"})
    await bus.publish(EventType.PROCESSING_FAILED, "c1", {"msg": "third"})

    assert len(bus._event_history) == 2
    # Oldest ("first") should have been evicted
    events = list(bus._event_history)
    assert events[0].data["msg"] == "second"
    assert events[1].data["msg"] == "third"


@pytest.mark.asyncio
async def test_event_history_disabled_is_empty_deque():
    """Verify that disabled history still uses deque but never grows."""
    bus = EventBus(enable_history=False)
    await bus.publish(EventType.PROCESSING_STARTED, "c1", {"msg": "test"})

    assert len(bus._event_history) == 0
