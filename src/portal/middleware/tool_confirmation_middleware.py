"""Tool Confirmation Middleware — human-in-the-loop approval for high-risk tool execution."""

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
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ConfirmationRequest:
    confirmation_id: str
    tool_name: str
    parameters: dict[str, Any]
    chat_id: str
    user_id: str | None
    status: ConfirmationStatus
    requested_at: datetime
    timeout_seconds: int
    trace_id: str | None = None
    response_event: asyncio.Event = None

    def __post_init__(self):
        if self.response_event is None:
            self.response_event = asyncio.Event()

    def is_expired(self) -> bool:
        return datetime.now(tz=UTC) > self.requested_at + timedelta(seconds=self.timeout_seconds)

    def to_dict(self) -> dict[str, Any]:
        return {
            "confirmation_id": self.confirmation_id,
            "tool_name": self.tool_name,
            "parameters": self.parameters,
            "chat_id": self.chat_id,
            "user_id": self.user_id,
            "status": self.status.value,
            "requested_at": self.requested_at.isoformat(),
            "timeout_seconds": self.timeout_seconds,
            "trace_id": self.trace_id,
        }


class ToolConfirmationMiddleware:
    """Middleware for human-in-the-loop confirmations for high-risk tools."""

    def __init__(
        self,
        event_bus: EventBus,
        confirmation_sender: Callable[[ConfirmationRequest], Awaitable[None]],
        default_timeout: int = 300,
        cleanup_interval: int = 60,
    ) -> None:
        self.event_bus = event_bus
        self.confirmation_sender = confirmation_sender
        self.default_timeout = default_timeout
        self.cleanup_interval = cleanup_interval
        self._pending: dict[str, ConfirmationRequest] = {}
        self._cleanup_task = None
        self._running = False
        logger.info(
            "ToolConfirmationMiddleware initialized", extra={"default_timeout": default_timeout}
        )

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("ToolConfirmationMiddleware started")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
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
        trace_id: str | None = None,
    ) -> bool:
        confirmation_id = str(uuid.uuid4())
        timeout = timeout or self.default_timeout
        request = ConfirmationRequest(
            confirmation_id=confirmation_id,
            tool_name=tool_name,
            parameters=parameters,
            chat_id=chat_id,
            user_id=user_id,
            status=ConfirmationStatus.PENDING,
            requested_at=datetime.now(tz=UTC),
            timeout_seconds=timeout,
            trace_id=trace_id,
        )
        self._pending[confirmation_id] = request
        logger.info(
            "Confirmation requested for tool: %s",
            tool_name,
            extra={"confirmation_id": confirmation_id, "chat_id": chat_id, "timeout": timeout},
        )
        await self.event_bus.publish(
            EventType.TOOL_CONFIRMATION_REQUIRED,
            chat_id,
            {
                "confirmation_id": confirmation_id,
                "tool_name": tool_name,
                "parameters": parameters,
                "timeout": timeout,
            },
            trace_id,
        )
        try:
            await self.confirmation_sender(request)
        except Exception as e:
            logger.error("Failed to send confirmation request: %s", e, exc_info=True)
            self._pending.pop(confirmation_id, None)
            return False
        try:
            await asyncio.wait_for(request.response_event.wait(), timeout=timeout)
        except TimeoutError:
            logger.warning(
                "Confirmation timeout for tool: %s",
                tool_name,
                extra={"confirmation_id": confirmation_id},
            )
            request.status = ConfirmationStatus.TIMEOUT
            self._pending.pop(confirmation_id, None)
            return False
        approved = request.status == ConfirmationStatus.APPROVED
        logger.info(
            "Confirmation %s for tool: %s",
            "approved" if approved else "denied",
            tool_name,
            extra={"confirmation_id": confirmation_id},
        )
        self._pending.pop(confirmation_id, None)
        return approved

    def approve(self, confirmation_id: str, approver_id: str | None = None) -> bool:
        request = self._pending.get(confirmation_id)
        if not request:
            logger.warning("Confirmation not found: %s", confirmation_id)
            return False
        if request.status != ConfirmationStatus.PENDING:
            logger.warning(
                "Confirmation already processed: %s",
                confirmation_id,
                extra={"status": request.status.value},
            )
            return False
        if request.is_expired():
            logger.warning("Confirmation expired: %s", confirmation_id)
            request.status = ConfirmationStatus.TIMEOUT
            request.response_event.set()
            return False
        logger.info(
            "Confirmation approved: %s", confirmation_id, extra={"approver_id": approver_id}
        )
        request.status = ConfirmationStatus.APPROVED
        request.response_event.set()
        return True

    def deny(self, confirmation_id: str, denier_id: str | None = None) -> bool:
        request = self._pending.get(confirmation_id)
        if not request:
            logger.warning("Confirmation not found: %s", confirmation_id)
            return False
        if request.status != ConfirmationStatus.PENDING:
            logger.warning(
                "Confirmation already processed: %s",
                confirmation_id,
                extra={"status": request.status.value},
            )
            return False
        logger.info("Confirmation denied: %s", confirmation_id, extra={"denier_id": denier_id})
        request.status = ConfirmationStatus.DENIED
        request.response_event.set()
        return True

    def get_pending_confirmations(self, chat_id: str | None = None) -> list[ConfirmationRequest]:
        requests = [r for r in self._pending.values() if r.status == ConfirmationStatus.PENDING]
        if chat_id:
            requests = [r for r in requests if r.chat_id == chat_id]
        return requests

    async def _cleanup_loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(self.cleanup_interval)
                await self._cleanup_expired()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in cleanup loop: %s", e, exc_info=True)

    async def _cleanup_expired(self) -> None:
        expired = [
            cid
            for cid, r in self._pending.items()
            if r.is_expired() and r.status == ConfirmationStatus.PENDING
        ]
        for cid in expired:
            request = self._pending.pop(cid, None)
            if request:
                logger.info(
                    "Cleaned up expired confirmation: %s",
                    cid,
                    extra={"tool_name": request.tool_name},
                )
                request.status = ConfirmationStatus.TIMEOUT
                request.response_event.set()
        if expired:
            logger.info("Cleaned up %s expired confirmations", len(expired))

    def get_stats(self) -> dict[str, Any]:
        active = sum(1 for r in self._pending.values() if r.status == ConfirmationStatus.PENDING)
        return {
            "total_pending": len(self._pending),
            "active_pending": active,
            "running": self._running,
        }
