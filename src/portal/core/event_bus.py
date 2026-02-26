"""
Event Bus - Asynchronous event system for real-time feedback
============================================================

Allows AgentCore to emit events during processing, enabling
interfaces to provide intermediate feedback to users.

Examples:
- "🔍 Searching knowledge base..."
- "🔧 Running git tool..."
- "🤔 Analyzing with Qwen2.5 14B..."
"""

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Standard event types"""
    PROCESSING_STARTED = "processing_started"
    PROCESSING_COMPLETED = "processing_completed"
    PROCESSING_FAILED = "processing_failed"

    MODEL_SELECTED = "model_selected"
    MODEL_GENERATING = "model_generating"
    MODEL_COMPLETED = "model_completed"

    TOOL_STARTED = "tool_started"
    TOOL_PROGRESS = "tool_progress"
    TOOL_COMPLETED = "tool_completed"
    TOOL_FAILED = "tool_failed"
    TOOL_CONFIRMATION_REQUIRED = "tool_confirmation_required"
    TOOL_CONFIRMATION_APPROVED = "tool_confirmation_approved"
    TOOL_CONFIRMATION_DENIED = "tool_confirmation_denied"

    ROUTING_DECISION = "routing_decision"
    FALLBACK_TRIGGERED = "fallback_triggered"

    CONTEXT_LOADED = "context_loaded"
    CONTEXT_SAVED = "context_saved"

    SECURITY_WARNING = "security_warning"
    RATE_LIMIT_WARNING = "rate_limit_warning"


@dataclass
class Event:
    """Represents an event in the system"""
    event_type: EventType
    chat_id: str
    timestamp: str
    data: dict[str, Any]
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            'event_type': self.event_type.value,
            'chat_id': self.chat_id,
            'timestamp': self.timestamp,
            'data': self.data,
            'trace_id': self.trace_id
        }


class EventBus:
    """
    Event bus for publishing and subscribing to events

    Architecture:
    - Async publish/subscribe pattern
    - Multiple subscribers per event type
    - Non-blocking event delivery
    - Error isolation (one subscriber failure doesn't affect others)

    Event History:
    - By default, event history is disabled to prevent memory leaks in long-running agents
    - Enable via enable_history=True if you need event auditing
    - For production auditing, use the persistence layer instead of in-memory storage
    """

    def __init__(self, enable_history: bool = False, max_history: int = 1000) -> None:
        """
        Initialize event bus

        Args:
            enable_history: Enable in-memory event history (default: False).
                           For long-running agents, prefer using the persistence layer.
            max_history: Maximum number of events to keep in memory (default: 1000)
        """
        self._subscribers: dict[EventType, list[Callable]] = {}
        self._enable_history = enable_history
        self._event_history: deque[Event] = deque(maxlen=max_history) if enable_history else deque()
        self._max_history = max_history

        logger.info("EventBus initialized (history: %s)", enable_history)

    def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """
        Subscribe to an event type

        Args:
            event_type: Type of event to subscribe to
            callback: Async function to call when event occurs
                     Signature: async def callback(event: Event) -> None
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        self._subscribers[event_type].append(callback)
        logger.debug("Subscribed to %s", event_type.value)

    def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """Unsubscribe from an event type"""
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(callback)
                logger.debug("Unsubscribed from %s", event_type.value)
            except ValueError:
                logger.warning("Callback not found in %s subscribers", event_type.value)

    async def publish(
        self,
        event_type: EventType,
        chat_id: str,
        data: dict[str, Any],
        trace_id: str | None = None
    ) -> None:
        """
        Publish an event

        Args:
            event_type: Type of event
            chat_id: Conversation identifier
            data: Event data
            trace_id: Optional trace ID for request tracking
        """
        event = Event(
            event_type=event_type,
            chat_id=chat_id,
            timestamp=datetime.now(tz=UTC).isoformat(),
            data=data,
            trace_id=trace_id
        )

        # Add to history (only if enabled to prevent memory leaks)
        # deque(maxlen=N) automatically evicts the oldest entry in O(1)
        if self._enable_history:
            self._event_history.append(event)

        # Get subscribers for this event type
        subscribers = self._subscribers.get(event_type, [])

        if not subscribers:
            logger.debug("No subscribers for %s", event_type.value)
            return

        # Notify all subscribers (non-blocking, error-isolated)
        tasks = []
        for callback in subscribers:
            task = self._notify_subscriber(callback, event)
            tasks.append(task)

        # Wait for all notifications to complete (SafeTaskFactory pattern)
        # return_exceptions=True ensures one subscriber failure doesn't crash others
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log any exceptions that escaped _notify_subscriber (defense in depth)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(
                        f"Uncaught exception in event subscriber {i} for {event_type.value}: {result}",
                        exc_info=result
                    )

    async def _notify_subscriber(self, callback: Callable, event: Event) -> None:
        """
        Notify a single subscriber with error handling

        Errors in one subscriber don't affect others
        """
        try:
            await callback(event)
        except Exception as e:
            logger.error(
                f"Error in event subscriber for {event.event_type.value}: {e}",
                exc_info=True
            )


# =============================================================================
# HELPER FUNCTIONS FOR COMMON EVENT PATTERNS
# =============================================================================

class EventEmitter:
    """
    Helper class for emitting common events

    Can be mixed into AgentCore or other components
    """

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus

    async def emit_processing_started(self, chat_id: str, message: str, trace_id: str) -> None:
        """Emit processing started event"""
        await self.event_bus.publish(
            EventType.PROCESSING_STARTED,
            chat_id,
            {'message': message},
            trace_id
        )

    async def emit_model_selected(self, chat_id: str, model_name: str, reasoning: str, trace_id: str) -> None:
        """Emit model selection event"""
        await self.event_bus.publish(
            EventType.MODEL_SELECTED,
            chat_id,
            {'model': model_name, 'reasoning': reasoning},
            trace_id
        )

    async def emit_tool_started(self, chat_id: str, tool_name: str, trace_id: str) -> None:
        """Emit tool execution started event"""
        await self.event_bus.publish(
            EventType.TOOL_STARTED,
            chat_id,
            {'tool': tool_name},
            trace_id
        )

    async def emit_tool_completed(self, chat_id: str, tool_name: str, result: str, trace_id: str) -> None:
        """Emit tool execution completed event"""
        await self.event_bus.publish(
            EventType.TOOL_COMPLETED,
            chat_id,
            {'tool': tool_name, 'result': result},
            trace_id
        )

    async def emit_security_warning(self, chat_id: str, warning: str, trace_id: str) -> None:
        """Emit security warning event"""
        await self.event_bus.publish(
            EventType.SECURITY_WARNING,
            chat_id,
            {'warning': warning},
            trace_id
        )
