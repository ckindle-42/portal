"""
Event Broker - Abstract interface for event bus implementations
================================================================

Following the DAO pattern, this module provides an abstract EventBroker
interface and concrete implementations for different backends.

This allows for:
- In-memory event bus for single-process deployments
- Redis event bus for multi-worker deployments
- Custom implementations for specific needs

Architecture:
    EventBroker (ABC)
        ├─ MemoryEventBroker (default, in-memory)
        └─ RedisEventBroker (future, for distributed deployments)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable

from .event_bus import Event, EventType

logger = logging.getLogger(__name__)


class EventBroker(ABC):
    """
    Abstract interface for event broker implementations

    This follows the DAO pattern used throughout Portal,
    allowing for swappable backends (in-memory, Redis, etc.)
    """

    @abstractmethod
    async def publish(self, event: Event) -> None:
        """
        Publish an event to all subscribers

        Args:
            event: Event to publish
        """
        pass

    @abstractmethod
    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """
        Subscribe to an event type

        Args:
            event_type: Type of event to subscribe to
            callback: Async function to call when event occurs
        """
        pass

    @abstractmethod
    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """
        Unsubscribe from an event type

        Args:
            event_type: Type of event to unsubscribe from
            callback: Callback to remove
        """
        pass

    @abstractmethod
    async def get_history(
        self,
        chat_id: str | None = None,
        event_type: EventType | None = None,
        limit: int = 100
    ) -> list[Event]:
        """
        Get event history

        Args:
            chat_id: Optional filter by chat_id
            event_type: Optional filter by event type
            limit: Maximum number of events to return

        Returns:
            List of events matching the criteria
        """
        pass

    @abstractmethod
    async def clear_history(self, chat_id: str | None = None) -> None:
        """
        Clear event history

        Args:
            chat_id: Optional chat_id to clear (clears all if None)
        """
        pass


class MemoryEventBroker(EventBroker):
    """
    In-memory event broker implementation

    Suitable for single-process deployments.
    Events are stored in memory and lost on restart.
    """

    def __init__(self, max_history: int = 1000):
        """
        Initialize memory event broker

        Args:
            max_history: Maximum number of events to keep in history
        """
        self._subscribers: dict[EventType, list[Callable]] = {}
        self._event_history: list[Event] = []
        self._max_history = max_history
        self._lock = asyncio.Lock()

        logger.info("MemoryEventBroker initialized", max_history=max_history)

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers"""
        # Add to history
        async with self._lock:
            self._event_history.append(event)

            # Trim history if needed
            if len(self._event_history) > self._max_history:
                self._event_history = self._event_history[-self._max_history:]

        # Notify subscribers
        if event.event_type in self._subscribers:
            # Run all callbacks concurrently
            tasks = []
            for callback in self._subscribers[event.event_type]:
                tasks.append(self._safe_callback(callback, event))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_callback(self, callback: Callable, event: Event):
        """Execute callback with error isolation"""
        try:
            await callback(event)
        except Exception as e:
            logger.error(
                f"Event subscriber error: {e}",
                event_type=event.event_type.value,
                chat_id=event.chat_id,
                exc_info=True
            )

    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """Subscribe to an event type"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        if callback not in self._subscribers[event_type]:
            self._subscribers[event_type].append(callback)
            logger.debug(
                f"Subscribed to {event_type.value}",
                callback=callback.__name__ if hasattr(callback, '__name__') else str(callback)
            )

    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """Unsubscribe from an event type"""
        if event_type in self._subscribers:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                logger.debug(f"Unsubscribed from {event_type.value}")

    async def get_history(
        self,
        chat_id: str | None = None,
        event_type: EventType | None = None,
        limit: int = 100
    ) -> list[Event]:
        """Get event history with optional filters"""
        async with self._lock:
            events = self._event_history.copy()

        # Apply filters
        if chat_id:
            events = [e for e in events if e.chat_id == chat_id]

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        # Return most recent events up to limit
        return events[-limit:]

    async def clear_history(self, chat_id: str | None = None) -> None:
        """Clear event history"""
        async with self._lock:
            if chat_id:
                self._event_history = [
                    e for e in self._event_history if e.chat_id != chat_id
                ]
            else:
                self._event_history.clear()

        logger.info(
            "Event history cleared",
            chat_id=chat_id if chat_id else "all"
        )


# Factory function for creating event brokers
def create_event_broker(
    backend: str = "memory",
    **kwargs
) -> EventBroker:
    """
    Factory function to create an event broker

    Args:
        backend: Backend type ("memory", "redis", etc.)
        **kwargs: Backend-specific configuration

    Returns:
        EventBroker instance

    Example:
        # Memory backend (default)
        broker = create_event_broker("memory", max_history=1000)

        # Redis backend (future)
        broker = create_event_broker("redis", url="redis://localhost:6379")
    """
    if backend == "memory":
        return MemoryEventBroker(**kwargs)
    elif backend == "redis":
        # Future implementation
        raise NotImplementedError("Redis event broker not yet implemented")
    else:
        raise ValueError(f"Unknown event broker backend: {backend}")
