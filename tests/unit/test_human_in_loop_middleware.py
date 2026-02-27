"""Tests for ToolConfirmationMiddleware (human-in-the-loop)."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from portal.core.event_bus import EventBus, EventType
from portal.middleware import ConfirmationRequest, ConfirmationStatus, ToolConfirmationMiddleware


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
async def confirmation_sender():
    return AsyncMock()


@pytest.fixture
async def middleware(event_bus, confirmation_sender):
    mw = ToolConfirmationMiddleware(
        event_bus=event_bus,
        confirmation_sender=confirmation_sender,
        default_timeout=5,
        cleanup_interval=1,
    )
    await mw.start()
    yield mw
    await mw.stop()


class TestConfirmationRequest:
    def test_creation_not_expired(self):
        req = ConfirmationRequest(
            confirmation_id="test-123",
            tool_name="shell_safety",
            parameters={"command": "rm -rf /"},
            chat_id="chat_123",
            user_id="user_456",
            status=ConfirmationStatus.PENDING,
            requested_at=datetime.now(tz=UTC),
            timeout_seconds=300,
        )
        assert req.confirmation_id == "test-123"
        assert req.status == ConfirmationStatus.PENDING
        assert not req.is_expired()

    def test_expired(self):
        req = ConfirmationRequest(
            confirmation_id="x",
            tool_name="t",
            parameters={},
            chat_id="c",
            user_id="u",
            status=ConfirmationStatus.PENDING,
            requested_at=datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC),
            timeout_seconds=1,
        )
        assert req.is_expired()

    def test_to_dict(self):
        req = ConfirmationRequest(
            confirmation_id="test-123",
            tool_name="shell_safety",
            parameters={"command": "ls"},
            chat_id="chat_123",
            user_id="user_456",
            status=ConfirmationStatus.PENDING,
            requested_at=datetime.now(tz=UTC),
            timeout_seconds=300,
        )
        d = req.to_dict()
        assert d["confirmation_id"] == "test-123"
        assert d["tool_name"] == "shell_safety"
        assert d["status"] == "pending"


class TestToolConfirmationMiddleware:
    @pytest.mark.asyncio
    async def test_initialization(self, event_bus, confirmation_sender):
        mw = ToolConfirmationMiddleware(
            event_bus=event_bus, confirmation_sender=confirmation_sender
        )
        assert mw.event_bus is event_bus
        assert mw.default_timeout == 300
        assert not mw._running

    @pytest.mark.asyncio
    async def test_start_stop(self, middleware):
        assert middleware._running
        await middleware.stop()
        assert not middleware._running

    @pytest.mark.asyncio
    async def test_approve_confirmation(self, middleware, confirmation_sender):
        async def approve_later():
            await asyncio.sleep(0.1)
            pending = middleware.get_pending_confirmations()
            assert len(pending) == 1
            middleware.approve(pending[0].confirmation_id, "admin_123")

        task = asyncio.create_task(approve_later())
        approved = await middleware.request_confirmation(
            tool_name="shell_safety", parameters={}, chat_id="chat_123", timeout=2
        )
        await task
        assert approved is True and confirmation_sender.called

    @pytest.mark.asyncio
    async def test_deny_confirmation(self, middleware, confirmation_sender):
        async def deny_later():
            await asyncio.sleep(0.1)
            pending = middleware.get_pending_confirmations()
            middleware.deny(pending[0].confirmation_id)

        task = asyncio.create_task(deny_later())
        approved = await middleware.request_confirmation(
            tool_name="git_push", parameters={}, chat_id="chat_123", timeout=2
        )
        await task
        assert approved is False

    @pytest.mark.asyncio
    async def test_confirmation_timeout(self, middleware, confirmation_sender):
        approved = await middleware.request_confirmation(
            tool_name="docker_stop", parameters={}, chat_id="chat_123", timeout=0.3
        )
        assert approved is False and confirmation_sender.called

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,cid", [("approve", "bad-id"), ("deny", "bad-id")])
    async def test_nonexistent_confirmation(self, middleware, method, cid):
        fn = getattr(middleware, method)
        assert fn(cid) is False

    @pytest.mark.asyncio
    async def test_double_approval_fails_second(self, middleware, confirmation_sender):
        async def approve_twice():
            await asyncio.sleep(0.1)
            pending = middleware.get_pending_confirmations()
            cid = pending[0].confirmation_id
            assert middleware.approve(cid) is True
            assert middleware.approve(cid) is False

        task = asyncio.create_task(approve_twice())
        await middleware.request_confirmation(
            tool_name="shell_safety", parameters={}, chat_id="chat_123", timeout=2
        )
        await task

    @pytest.mark.asyncio
    async def test_get_pending_confirmations(self, middleware, confirmation_sender):
        tasks = [
            asyncio.create_task(
                middleware.request_confirmation(
                    tool_name=f"tool_{i}", parameters={}, chat_id=f"chat_{i}", timeout=3
                )
            )
            for i in range(3)
        ]
        await asyncio.sleep(0.2)
        pending = middleware.get_pending_confirmations()
        assert len(pending) == 3
        chat0 = middleware.get_pending_confirmations(chat_id="chat_0")
        assert len(chat0) == 1 and chat0[0].chat_id == "chat_0"
        for t in tasks:
            t.cancel()
            try:
                await t
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, middleware, confirmation_sender):
        task = asyncio.create_task(
            middleware.request_confirmation(
                tool_name="test_tool", parameters={}, chat_id="chat_123", timeout=0.3
            )
        )
        await asyncio.sleep(1.5)
        assert middleware.get_pending_confirmations() == []
        assert await task is False

    @pytest.mark.asyncio
    async def test_event_emitted(self, event_bus, confirmation_sender):
        events = []
        event_bus.subscribe(EventType.TOOL_CONFIRMATION_REQUIRED, lambda e: events.append(e))
        mw = ToolConfirmationMiddleware(
            event_bus=event_bus, confirmation_sender=confirmation_sender, default_timeout=2
        )
        await mw.start()

        async def approve():
            await asyncio.sleep(0.1)
            pending = mw.get_pending_confirmations()
            if pending:
                mw.approve(pending[0].confirmation_id)

        t = asyncio.create_task(approve())
        await mw.request_confirmation(
            tool_name="test_tool", parameters={}, chat_id="chat_123", timeout=2
        )
        await t
        await mw.stop()
        assert len(events) > 0
        assert events[0].event_type == EventType.TOOL_CONFIRMATION_REQUIRED

    @pytest.mark.asyncio
    async def test_sender_failure_returns_false(self, event_bus):
        failing = AsyncMock(side_effect=Exception("fail"))
        mw = ToolConfirmationMiddleware(
            event_bus=event_bus, confirmation_sender=failing, default_timeout=2
        )
        await mw.start()
        approved = await mw.request_confirmation(
            tool_name="test_tool", parameters={}, chat_id="chat_123", timeout=2
        )
        await mw.stop()
        assert approved is False

    @pytest.mark.asyncio
    async def test_stats(self, middleware):
        task = asyncio.create_task(
            middleware.request_confirmation(
                tool_name="test_tool", parameters={}, chat_id="chat_123", timeout=0.5
            )
        )
        await asyncio.sleep(0.1)
        stats = middleware.get_stats()
        assert stats["running"] is True and stats["active_pending"] == 1
        await task
        assert middleware.get_stats()["active_pending"] == 0
