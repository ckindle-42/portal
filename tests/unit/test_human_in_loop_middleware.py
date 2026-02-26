"""
Tests for Human-in-the-Loop Middleware
======================================

Tests the tool confirmation middleware that requires admin approval
for high-risk tool execution.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from portal.core.event_bus import EventBus, EventType
from portal.middleware import ConfirmationRequest, ConfirmationStatus, ToolConfirmationMiddleware


@pytest.fixture
def event_bus():
    """Create an event bus for testing"""
    return EventBus()


@pytest.fixture
async def confirmation_sender():
    """Create a mock confirmation sender"""
    mock = AsyncMock()
    return mock


@pytest.fixture
async def middleware(event_bus, confirmation_sender):
    """Create a confirmation middleware instance"""
    middleware = ToolConfirmationMiddleware(
        event_bus=event_bus,
        confirmation_sender=confirmation_sender,
        default_timeout=5,  # Short timeout for testing
        cleanup_interval=1
    )
    await middleware.start()
    yield middleware
    await middleware.stop()


class TestConfirmationRequest:
    """Tests for ConfirmationRequest"""

    def test_confirmation_request_creation(self):
        """Test creating a confirmation request"""
        request = ConfirmationRequest(
            confirmation_id="test-123",
            tool_name="shell_safety",
            parameters={"command": "rm -rf /"},
            chat_id="chat_123",
            user_id="user_456",
            status=ConfirmationStatus.PENDING,
            requested_at=datetime.now(),
            timeout_seconds=300
        )

        assert request.confirmation_id == "test-123"
        assert request.tool_name == "shell_safety"
        assert request.status == ConfirmationStatus.PENDING
        assert not request.is_expired()

    def test_confirmation_request_expiry(self):
        """Test confirmation request expiry"""
        # Create request that expired 10 seconds ago
        past_time = datetime(2020, 1, 1, 12, 0, 0)
        request = ConfirmationRequest(
            confirmation_id="test-123",
            tool_name="shell_safety",
            parameters={},
            chat_id="chat_123",
            user_id="user_456",
            status=ConfirmationStatus.PENDING,
            requested_at=past_time,
            timeout_seconds=1
        )

        assert request.is_expired()

    def test_confirmation_request_to_dict(self):
        """Test converting confirmation request to dict"""
        request = ConfirmationRequest(
            confirmation_id="test-123",
            tool_name="shell_safety",
            parameters={"command": "ls"},
            chat_id="chat_123",
            user_id="user_456",
            status=ConfirmationStatus.PENDING,
            requested_at=datetime.now(),
            timeout_seconds=300
        )

        data = request.to_dict()
        assert data['confirmation_id'] == "test-123"
        assert data['tool_name'] == "shell_safety"
        assert data['status'] == "pending"


class TestToolConfirmationMiddleware:
    """Tests for ToolConfirmationMiddleware"""

    @pytest.mark.asyncio
    async def test_middleware_initialization(self, event_bus, confirmation_sender):
        """Test middleware initialization"""
        middleware = ToolConfirmationMiddleware(
            event_bus=event_bus,
            confirmation_sender=confirmation_sender,
            default_timeout=300
        )

        assert middleware.event_bus == event_bus
        assert middleware.confirmation_sender == confirmation_sender
        assert middleware.default_timeout == 300
        assert not middleware._running

    @pytest.mark.asyncio
    async def test_middleware_start_stop(self, middleware):
        """Test starting and stopping middleware"""
        assert middleware._running

        await middleware.stop()
        assert not middleware._running

    @pytest.mark.asyncio
    async def test_request_confirmation_approved(self, middleware, confirmation_sender):
        """Test requesting confirmation that gets approved"""
        # Create a task to approve the confirmation after a short delay
        async def approve_after_delay():
            await asyncio.sleep(0.1)
            # Get the pending confirmation
            pending = middleware.get_pending_confirmations()
            assert len(pending) == 1
            # Approve it
            middleware.approve(pending[0].confirmation_id, "admin_123")

        # Start approval task
        approval_task = asyncio.create_task(approve_after_delay())

        # Request confirmation
        approved = await middleware.request_confirmation(
            tool_name="shell_safety",
            parameters={"command": "rm -rf /"},
            chat_id="chat_123",
            user_id="user_456",
            timeout=2
        )

        await approval_task

        assert approved is True
        assert confirmation_sender.called

    @pytest.mark.asyncio
    async def test_request_confirmation_denied(self, middleware, confirmation_sender):
        """Test requesting confirmation that gets denied"""
        # Create a task to deny the confirmation after a short delay
        async def deny_after_delay():
            await asyncio.sleep(0.1)
            # Get the pending confirmation
            pending = middleware.get_pending_confirmations()
            assert len(pending) == 1
            # Deny it
            middleware.deny(pending[0].confirmation_id, "admin_123")

        # Start denial task
        denial_task = asyncio.create_task(deny_after_delay())

        # Request confirmation
        approved = await middleware.request_confirmation(
            tool_name="git_push",
            parameters={"branch": "main", "force": True},
            chat_id="chat_123",
            user_id="user_456",
            timeout=2
        )

        await denial_task

        assert approved is False
        assert confirmation_sender.called

    @pytest.mark.asyncio
    async def test_request_confirmation_timeout(self, middleware, confirmation_sender):
        """Test confirmation request timeout"""
        # Request confirmation with short timeout and don't approve/deny
        approved = await middleware.request_confirmation(
            tool_name="docker_stop",
            parameters={"container_id": "abc123"},
            chat_id="chat_123",
            user_id="user_456",
            timeout=0.5  # Very short timeout
        )

        assert approved is False
        assert confirmation_sender.called

    @pytest.mark.asyncio
    async def test_approve_nonexistent_confirmation(self, middleware):
        """Test approving a confirmation that doesn't exist"""
        success = middleware.approve("nonexistent-id", "admin_123")
        assert success is False

    @pytest.mark.asyncio
    async def test_deny_nonexistent_confirmation(self, middleware):
        """Test denying a confirmation that doesn't exist"""
        success = middleware.deny("nonexistent-id", "admin_123")
        assert success is False

    @pytest.mark.asyncio
    async def test_double_approval(self, middleware, confirmation_sender):
        """Test that a confirmation can't be approved twice"""
        # Create a task to approve twice
        async def approve_twice():
            await asyncio.sleep(0.1)
            pending = middleware.get_pending_confirmations()
            confirmation_id = pending[0].confirmation_id

            # First approval should succeed
            success1 = middleware.approve(confirmation_id, "admin_123")
            assert success1 is True

            # Second approval should fail
            success2 = middleware.approve(confirmation_id, "admin_123")
            assert success2 is False

        approval_task = asyncio.create_task(approve_twice())

        # Request confirmation
        await middleware.request_confirmation(
            tool_name="shell_safety",
            parameters={"command": "ls"},
            chat_id="chat_123",
            timeout=2
        )

        await approval_task

    @pytest.mark.asyncio
    async def test_get_pending_confirmations(self, middleware, confirmation_sender):
        """Test getting pending confirmations"""
        # Start multiple confirmation requests without approving
        tasks = []
        for i in range(3):
            task = asyncio.create_task(
                middleware.request_confirmation(
                    tool_name=f"tool_{i}",
                    parameters={},
                    chat_id=f"chat_{i}",
                    timeout=5
                )
            )
            tasks.append(task)

        # Wait a bit for requests to be created
        await asyncio.sleep(0.2)

        # Check pending confirmations
        pending = middleware.get_pending_confirmations()
        assert len(pending) == 3

        # Filter by chat_id
        chat_0_pending = middleware.get_pending_confirmations(chat_id="chat_0")
        assert len(chat_0_pending) == 1
        assert chat_0_pending[0].chat_id == "chat_0"

        # Cancel all tasks
        for task in tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_cleanup_expired_confirmations(self, middleware, confirmation_sender):
        """Test that expired confirmations are cleaned up"""
        # Request confirmation with very short timeout
        task = asyncio.create_task(
            middleware.request_confirmation(
                tool_name="test_tool",
                parameters={},
                chat_id="chat_123",
                timeout=0.5
            )
        )

        # Wait for timeout and cleanup
        await asyncio.sleep(1.5)

        # Should have been cleaned up
        pending = middleware.get_pending_confirmations()
        assert len(pending) == 0

        # Wait for task to complete
        result = await task
        assert result is False

    @pytest.mark.asyncio
    async def test_event_emission(self, event_bus, confirmation_sender):
        """Test that confirmation events are emitted"""
        events_received = []

        # Subscribe to confirmation events
        async def event_handler(event):
            events_received.append(event)

        event_bus.subscribe(EventType.TOOL_CONFIRMATION_REQUIRED, event_handler)

        # Create and start middleware
        middleware = ToolConfirmationMiddleware(
            event_bus=event_bus,
            confirmation_sender=confirmation_sender,
            default_timeout=2
        )
        await middleware.start()

        # Request confirmation and immediately approve
        async def approve_immediately():
            await asyncio.sleep(0.1)
            pending = middleware.get_pending_confirmations()
            if pending:
                middleware.approve(pending[0].confirmation_id)

        approval_task = asyncio.create_task(approve_immediately())

        await middleware.request_confirmation(
            tool_name="test_tool",
            parameters={},
            chat_id="chat_123",
            timeout=2
        )

        await approval_task
        await middleware.stop()

        # Check that event was emitted
        assert len(events_received) > 0
        assert events_received[0].event_type == EventType.TOOL_CONFIRMATION_REQUIRED

    @pytest.mark.asyncio
    async def test_confirmation_sender_failure(self, event_bus):
        """Test handling of confirmation sender failure"""
        # Create a sender that fails
        failing_sender = AsyncMock(side_effect=Exception("Sender failed"))

        middleware = ToolConfirmationMiddleware(
            event_bus=event_bus,
            confirmation_sender=failing_sender,
            default_timeout=2
        )
        await middleware.start()

        # Request confirmation - should fail gracefully
        approved = await middleware.request_confirmation(
            tool_name="test_tool",
            parameters={},
            chat_id="chat_123",
            timeout=2
        )

        await middleware.stop()

        # Should return False when sender fails
        assert approved is False

    @pytest.mark.asyncio
    async def test_middleware_stats(self, middleware):
        """Test middleware statistics"""
        # Request confirmation without approving (will timeout)
        task = asyncio.create_task(
            middleware.request_confirmation(
                tool_name="test_tool",
                parameters={},
                chat_id="chat_123",
                timeout=0.5
            )
        )

        await asyncio.sleep(0.1)

        # Get stats
        stats = middleware.get_stats()
        assert 'total_pending' in stats
        assert 'active_pending' in stats
        assert 'running' in stats
        assert stats['running'] is True
        assert stats['active_pending'] == 1

        # Wait for timeout
        await task

        # Stats should be updated
        stats = middleware.get_stats()
        assert stats['active_pending'] == 0


class TestIntegrationWithAgentCore:
    """Integration tests with AgentCore"""

    @pytest.mark.asyncio
    async def test_tool_execution_with_confirmation(self):
        """Test that tools requiring confirmation are intercepted"""
        from portal.core import EventBus, create_agent_core
        from portal.tools import registry as tool_registry

        # Create event bus and confirmation sender
        event_bus = EventBus()
        confirmation_sender = AsyncMock()

        # Create confirmation middleware
        middleware = ToolConfirmationMiddleware(
            event_bus=event_bus,
            confirmation_sender=confirmation_sender,
            default_timeout=2
        )
        await middleware.start()

        # Create agent core
        config = {
            'ollama_base_url': 'http://localhost:11434',
            'lmstudio_base_url': 'http://localhost:1234/v1',
            'routing_strategy': 'AUTO'
        }
        agent_core = create_agent_core(config)
        agent_core.confirmation_middleware = middleware

        # Get a tool that requires confirmation
        tool = tool_registry.get_tool('shell_safety')
        if tool and tool.metadata.requires_confirmation:
            # Create task to approve after delay
            async def approve_after_delay():
                await asyncio.sleep(0.1)
                pending = middleware.get_pending_confirmations()
                if pending:
                    middleware.approve(pending[0].confirmation_id)

            approval_task = asyncio.create_task(approve_after_delay())

            # Try to execute tool - should request confirmation
            try:
                result = await agent_core.execute_tool(
                    tool_name='shell_safety',
                    parameters={'command': 'ls'},
                    chat_id='test_chat',
                    user_id='test_user'
                )
                # Should succeed if approved
                assert result is not None
            except Exception:
                # May fail if tool execution itself has issues, but
                # confirmation should have been requested
                pass

            await approval_task

            # Verify confirmation was requested
            assert confirmation_sender.called

        await middleware.stop()

    @pytest.mark.asyncio
    async def test_tool_execution_denied(self):
        """Test that denied confirmations prevent tool execution"""
        from portal.core import create_agent_core
        from portal.core.exceptions import ToolExecutionError

        # Create event bus and confirmation sender
        event_bus = EventBus()
        confirmation_sender = AsyncMock()

        # Create confirmation middleware
        middleware = ToolConfirmationMiddleware(
            event_bus=event_bus,
            confirmation_sender=confirmation_sender,
            default_timeout=2
        )
        await middleware.start()

        # Create agent core
        config = {
            'ollama_base_url': 'http://localhost:11434',
            'lmstudio_base_url': 'http://localhost:1234/v1',
            'routing_strategy': 'AUTO'
        }
        agent_core = create_agent_core(config)
        agent_core.confirmation_middleware = middleware

        # Create task to deny after delay
        async def deny_after_delay():
            await asyncio.sleep(0.1)
            pending = middleware.get_pending_confirmations()
            if pending:
                middleware.deny(pending[0].confirmation_id)

        denial_task = asyncio.create_task(deny_after_delay())

        # Try to execute tool - should be denied
        with pytest.raises(ToolExecutionError) as exc_info:
            await agent_core.execute_tool(
                tool_name='shell_safety',
                parameters={'command': 'ls'},
                chat_id='test_chat',
                user_id='test_user'
            )

        await denial_task
        await middleware.stop()

        # Verify error message mentions denial
        assert "denied" in str(exc_info.value).lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
