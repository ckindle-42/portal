"""
Tool Confirmation Middleware - Human-in-the-Loop for High-Risk Operations
===========================================================================

This middleware intercepts tool execution requests for tools marked as
"requires_confirmation" and sends approval requests to an admin before
allowing execution to proceed.

Architecture:
    Tool Request → Middleware Check → Confirmation Request → Admin Approval → Execute
                                   ↘ Timeout/Deny → Reject

Features:
- Async confirmation waiting with timeout
- Admin notification via Telegram
- Pending confirmation management
- Event emission for monitoring
- Automatic cleanup of stale confirmations
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from portal.core.event_bus import EventBus, EventType

logger = logging.getLogger(__name__)


class ConfirmationStatus(Enum):
    """Status of a confirmation request"""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ConfirmationRequest:
    """Represents a pending tool execution confirmation request"""
    confirmation_id: str
    tool_name: str
    parameters: dict[str, Any]
    chat_id: str
    user_id: str | None
    status: ConfirmationStatus
    requested_at: datetime
    timeout_seconds: int
    trace_id: str | None = None

    # Async primitives for waiting
    response_event: asyncio.Event = None

    def __post_init__(self):
        if self.response_event is None:
            self.response_event = asyncio.Event()

    def is_expired(self) -> bool:
        """Check if confirmation request has expired"""
        expiry_time = self.requested_at + timedelta(seconds=self.timeout_seconds)
        return datetime.now(tz=UTC) > expiry_time

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'confirmation_id': self.confirmation_id,
            'tool_name': self.tool_name,
            'parameters': self.parameters,
            'chat_id': self.chat_id,
            'user_id': self.user_id,
            'status': self.status.value,
            'requested_at': self.requested_at.isoformat(),
            'timeout_seconds': self.timeout_seconds,
            'trace_id': self.trace_id
        }


class ToolConfirmationMiddleware:
    """
    Middleware for handling human-in-the-loop confirmations for high-risk tools

    Usage:
        middleware = ToolConfirmationMiddleware(
            event_bus=event_bus,
            confirmation_sender=send_telegram_confirmation,
            default_timeout=300  # 5 minutes
        )

        # Before executing a tool:
        approved = await middleware.request_confirmation(
            tool_name="shell_safety",
            parameters={"command": "rm -rf /"},
            chat_id="12345",
            user_id="user_123"
        )

        if approved:
            # Execute tool
            pass
        else:
            # Reject execution
            pass
    """

    def __init__(
        self,
        event_bus: EventBus,
        confirmation_sender: Callable[[ConfirmationRequest], Awaitable[None]],
        default_timeout: int = 300,  # 5 minutes
        cleanup_interval: int = 60,  # 1 minute
    ):
        """
        Initialize confirmation middleware

        Args:
            event_bus: Event bus for emitting confirmation events
            confirmation_sender: Async function to send confirmation requests to admin
                                Signature: async def send(request: ConfirmationRequest) -> None
            default_timeout: Default timeout in seconds for confirmations
            cleanup_interval: Interval in seconds for cleaning up expired confirmations
        """
        self.event_bus = event_bus
        self.confirmation_sender = confirmation_sender
        self.default_timeout = default_timeout
        self.cleanup_interval = cleanup_interval

        # Pending confirmations
        self._pending: dict[str, ConfirmationRequest] = {}

        # Cleanup task
        self._cleanup_task = None
        self._running = False

        logger.info(
            "ToolConfirmationMiddleware initialized",
            extra={'default_timeout': default_timeout}
        )

    async def start(self):
        """Start the middleware and background tasks"""
        if self._running:
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("ToolConfirmationMiddleware started")

    async def stop(self):
        """Stop the middleware and cleanup"""
        if not self._running:
            return

        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Cancel all pending confirmations
        for request in self._pending.values():
            if request.status == ConfirmationStatus.PENDING:
                request.status = ConfirmationStatus.CANCELLED
                request.response_event.set()

        self._pending.clear()
        logger.info("ToolConfirmationMiddleware stopped")

    async def request_confirmation(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        chat_id: str,
        user_id: str | None = None,
        timeout: int | None = None,
        trace_id: str | None = None
    ) -> bool:
        """
        Request confirmation for tool execution

        This method will:
        1. Create a confirmation request
        2. Send it to the admin via confirmation_sender
        3. Wait for approval/denial (with timeout)
        4. Return True if approved, False otherwise

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            chat_id: Chat ID where the request originated
            user_id: User ID who made the request
            timeout: Custom timeout in seconds (uses default if None)
            trace_id: Trace ID for request tracking

        Returns:
            True if approved, False if denied/timeout
        """
        confirmation_id = str(uuid.uuid4())
        timeout = timeout or self.default_timeout

        # Create confirmation request
        request = ConfirmationRequest(
            confirmation_id=confirmation_id,
            tool_name=tool_name,
            parameters=parameters,
            chat_id=chat_id,
            user_id=user_id,
            status=ConfirmationStatus.PENDING,
            requested_at=datetime.now(tz=UTC),
            timeout_seconds=timeout,
            trace_id=trace_id
        )

        # Store pending request
        self._pending[confirmation_id] = request

        logger.info(
            f"Confirmation requested for tool: {tool_name}",
            extra={
                'confirmation_id': confirmation_id,
                'chat_id': chat_id,
                'timeout': timeout
            }
        )

        # Emit event
        await self.event_bus.publish(
            EventType.TOOL_CONFIRMATION_REQUIRED,
            chat_id,
            {
                'confirmation_id': confirmation_id,
                'tool_name': tool_name,
                'parameters': parameters,
                'timeout': timeout
            },
            trace_id
        )

        # Send confirmation request to admin
        try:
            await self.confirmation_sender(request)
        except Exception as e:
            logger.error(
                f"Failed to send confirmation request: {e}",
                exc_info=True
            )
            # Clean up and deny
            self._pending.pop(confirmation_id, None)
            return False

        # Wait for response with timeout
        try:
            await asyncio.wait_for(
                request.response_event.wait(),
                timeout=timeout
            )
        except TimeoutError:
            logger.warning(
                f"Confirmation timeout for tool: {tool_name}",
                extra={'confirmation_id': confirmation_id}
            )
            request.status = ConfirmationStatus.TIMEOUT
            self._pending.pop(confirmation_id, None)
            return False

        # Check final status
        approved = request.status == ConfirmationStatus.APPROVED

        logger.info(
            f"Confirmation {'approved' if approved else 'denied'} for tool: {tool_name}",
            extra={'confirmation_id': confirmation_id}
        )

        # Cleanup
        self._pending.pop(confirmation_id, None)

        return approved

    def approve(self, confirmation_id: str, approver_id: str | None = None) -> bool:
        """
        Approve a pending confirmation request

        Args:
            confirmation_id: ID of the confirmation to approve
            approver_id: ID of the user who approved

        Returns:
            True if approved successfully, False if not found or already processed
        """
        request = self._pending.get(confirmation_id)

        if not request:
            logger.warning(f"Confirmation not found: {confirmation_id}")
            return False

        if request.status != ConfirmationStatus.PENDING:
            logger.warning(
                f"Confirmation already processed: {confirmation_id}",
                extra={'status': request.status.value}
            )
            return False

        if request.is_expired():
            logger.warning(f"Confirmation expired: {confirmation_id}")
            request.status = ConfirmationStatus.TIMEOUT
            request.response_event.set()
            return False

        logger.info(
            f"Confirmation approved: {confirmation_id}",
            extra={'approver_id': approver_id}
        )

        request.status = ConfirmationStatus.APPROVED
        request.response_event.set()
        return True

    def deny(self, confirmation_id: str, denier_id: str | None = None) -> bool:
        """
        Deny a pending confirmation request

        Args:
            confirmation_id: ID of the confirmation to deny
            denier_id: ID of the user who denied

        Returns:
            True if denied successfully, False if not found or already processed
        """
        request = self._pending.get(confirmation_id)

        if not request:
            logger.warning(f"Confirmation not found: {confirmation_id}")
            return False

        if request.status != ConfirmationStatus.PENDING:
            logger.warning(
                f"Confirmation already processed: {confirmation_id}",
                extra={'status': request.status.value}
            )
            return False

        logger.info(
            f"Confirmation denied: {confirmation_id}",
            extra={'denier_id': denier_id}
        )

        request.status = ConfirmationStatus.DENIED
        request.response_event.set()
        return True

    def get_pending_confirmations(self, chat_id: str | None = None) -> list[ConfirmationRequest]:
        """
        Get all pending confirmation requests

        Args:
            chat_id: Optional filter by chat ID

        Returns:
            List of pending confirmation requests
        """
        requests = [
            r for r in self._pending.values()
            if r.status == ConfirmationStatus.PENDING
        ]

        if chat_id:
            requests = [r for r in requests if r.chat_id == chat_id]

        return requests

    async def _cleanup_loop(self):
        """Background task to cleanup expired confirmations"""
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)

    async def _cleanup_expired(self):
        """Clean up expired confirmation requests"""
        expired = []

        for confirmation_id, request in self._pending.items():
            if request.is_expired() and request.status == ConfirmationStatus.PENDING:
                expired.append(confirmation_id)

        for confirmation_id in expired:
            request = self._pending.pop(confirmation_id, None)
            if request:
                logger.info(
                    f"Cleaned up expired confirmation: {confirmation_id}",
                    extra={'tool_name': request.tool_name}
                )
                request.status = ConfirmationStatus.TIMEOUT
                request.response_event.set()

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired confirmations")

    def get_stats(self) -> dict[str, Any]:
        """Get middleware statistics"""
        pending_count = sum(
            1 for r in self._pending.values()
            if r.status == ConfirmationStatus.PENDING
        )

        return {
            'total_pending': len(self._pending),
            'active_pending': pending_count,
            'running': self._running
        }
