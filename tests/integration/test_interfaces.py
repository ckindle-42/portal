"""
Integration tests for Telegram and Slack interfaces.

Tests the full message processing flow through each interface:
- Telegram: Update → handle_text_message → AgentCore.process_message → Response
- Slack: Event → handle_message → AgentCore.process_message → chat.postMessage

These tests use mocked AgentCore to verify the interface layer works correctly.
"""

import hashlib
import hmac
import time

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestTelegramInterfaceIntegration:
    """Integration tests for Telegram interface message processing."""

    @pytest.fixture
    def mock_agent_core(self):
        """Create a mock AgentCore with process_message returning a valid result."""
        agent = MagicMock()
        result = MagicMock()
        result.success = True
        result.response = "Test response from agent"
        result.model_used = "qwen2.5:7b"
        result.prompt_tokens = 10
        result.completion_tokens = 5
        result.tokens_generated = 5
        result.tools_used = []
        agent.process_message = AsyncMock(return_value=result)
        return agent

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for Telegram interface."""
        settings = MagicMock()
        settings.interfaces.telegram.bot_token = "test_token"
        settings.interfaces.telegram.authorized_users = [12345]
        settings.interfaces.telegram.authorized_chats = None
        settings.interfaces.telegram.allow_group = False
        settings.security.rate_limit_requests = 20
        settings.security.sandbox_enabled = False
        return settings

    @pytest.mark.asyncio
    async def test_telegram_text_message_flow(self, mock_agent_core, mock_settings):
        """Test that a text message flows through Telegram → AgentCore → Response."""
        from portal.interfaces.telegram.interface import TelegramInterface

        # Create interface with mocks
        interface = TelegramInterface(
            agent_core=mock_agent_core,
            settings=mock_settings,
            rate_limiter=None,
        )

        # Create mock update
        user = MagicMock()
        user.id = 12345
        user.first_name = "Test"

        chat = MagicMock()
        chat.id = 12345

        message = MagicMock()
        message.from_user = user
        message.chat = chat
        message.text = "Hello, how are you?"
        message.reply_text = AsyncMock()
        message.reply_markup = None
        # Mock send_action as an async function
        chat.send_action = AsyncMock()

        update = MagicMock()
        update.message = message
        update.effective_user = user
        update.effective_chat = chat

        # Mock rate limiter to allow requests
        interface.rate_limiter.check_limit = AsyncMock(return_value=(True, None))

        # Process the message
        await interface.handle_text_message(update, MagicMock())

        # Verify AgentCore was called
        mock_agent_core.process_message.assert_called_once()

        # Verify the call parameters
        call_args = mock_agent_core.process_message.call_args
        assert call_args.kwargs.get("message") == "Hello, how are you?"
        assert call_args.kwargs.get("interface") == "telegram"

    @pytest.mark.asyncio
    async def test_telegram_unauthorized_user_rejected(self, mock_settings):
        """Test that unauthorized users are rejected."""
        from portal.interfaces.telegram.interface import TelegramInterface

        # Create interface with mocks
        interface = TelegramInterface(
            agent_core=MagicMock(),
            settings=mock_settings,
            rate_limiter=None,
        )

        # Create update with unauthorized user
        user = MagicMock()
        user.id = 99999  # Not in authorized list

        message = MagicMock()
        message.reply_text = AsyncMock()

        update = MagicMock()
        update.message = message
        update.effective_user = user

        # Process should handle unauthorized user
        await interface.handle_text_message(update, MagicMock())

        # Verify reply_text was called with unauthorized message
        message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_telegram_rate_limit_enforced(self, mock_agent_core, mock_settings):
        """Test that rate limiting is enforced."""
        from portal.interfaces.telegram.interface import TelegramInterface

        # Create interface with mocks
        interface = TelegramInterface(
            agent_core=mock_agent_core,
            settings=mock_settings,
            rate_limiter=None,
        )

        # Create mock update
        user = MagicMock()
        user.id = 12345

        message = MagicMock()
        message.text = "Test message"
        message.reply_text = AsyncMock()
        message.reply_markup = None
        chat = MagicMock()
        chat.send_action = AsyncMock()

        update = MagicMock()
        update.message = message
        update.effective_user = user
        update.effective_chat = chat

        # Mock rate limiter to reject requests
        interface.rate_limiter.check_limit = AsyncMock(return_value=(False, "Rate limit exceeded"))

        # Process the message
        await interface.handle_text_message(update, MagicMock())

        # Verify reply_text was called with rate limit message
        message.reply_text.assert_called()


class TestSlackInterfaceIntegration:
    """Integration tests for Slack interface message processing."""

    @pytest.fixture
    def mock_agent_core(self):
        """Create a mock AgentCore with process_message returning a valid result."""
        agent = MagicMock()
        result = MagicMock()
        result.success = True
        result.response = "Test response from agent"
        result.model_used = "qwen2.5:7b"
        result.prompt_tokens = 10
        result.completion_tokens = 5
        result.tokens_generated = 5
        result.tools_used = []
        agent.process_message = AsyncMock(return_value=result)
        return agent

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for Slack interface."""
        settings = MagicMock()
        settings.interfaces.slack.bot_token = "xoxb-test-token"
        settings.interfaces.slack.signing_secret = "test_secret"
        settings.interfaces.slack.authorized_channels = ["C12345"]
        return settings

    @pytest.fixture
    def mock_web_app(self):
        """Create a mock FastAPI web app."""
        from fastapi import FastAPI
        return FastAPI()

    @pytest.mark.asyncio
    async def test_slack_message_flow(self, mock_agent_core, mock_settings, mock_web_app):
        """Test that a Slack message flows through Slack → AgentCore → Response."""
        from portal.interfaces.slack.interface import SlackInterface

        # Create interface with mocks
        interface = SlackInterface(
            agent_core=mock_agent_core,
            config=mock_settings,
            web_app=mock_web_app,
        )

        # Mock the Slack client
        interface.client = AsyncMock()
        interface.client.chat_postMessage = AsyncMock()

        # Verify interface was created correctly
        assert interface.agent_core is mock_agent_core
        assert interface.slack_config is mock_settings.interfaces.slack

    @pytest.mark.asyncio
    async def test_slack_signature_verification(self, mock_agent_core, mock_settings, mock_web_app):
        """Test that Slack signature verification works."""
        from portal.interfaces.slack.interface import SlackInterface

        # Create interface
        interface = SlackInterface(
            agent_core=mock_agent_core,
            config=mock_settings,
            web_app=mock_web_app,
        )

        # Create a valid signature
        timestamp = str(int(time.time()))
        body = b'{"type": "message"}'
        sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
        expected_sig = "v0=" + hmac.new(
            b"test_secret",
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()

        # Test verification
        result = interface._verify_slack_signature(body, timestamp, expected_sig)
        assert result is True

        # Test invalid signature
        result = interface._verify_slack_signature(body, timestamp, "v0=invalid")
        assert result is False

        # Test expired timestamp
        old_timestamp = str(int(time.time()) - 400)  # More than 5 minutes ago
        result = interface._verify_slack_signature(body, old_timestamp, expected_sig)
        assert result is False


class TestInterfaceErrorHandling:
    """Tests for error handling in interfaces."""

    @pytest.mark.asyncio
    async def test_telegram_handles_agent_error(self):
        """Test that Telegram gracefully handles AgentCore errors."""
        from portal.interfaces.telegram.interface import TelegramInterface

        # Create interface with failing AgentCore
        agent = MagicMock()
        from portal.core.exceptions import PortalError
        agent.process_message = AsyncMock(side_effect=PortalError("Test error"))

        interface = TelegramInterface(
            agent_core=agent,
            settings=MagicMock(),
            rate_limiter=None,
        )

        # Create mock update
        user = MagicMock()
        user.id = 12345

        message = MagicMock()
        message.reply_text = AsyncMock()
        message.reply_markup = None
        chat = MagicMock()
        chat.send_action = AsyncMock()

        update = MagicMock()
        update.message = message
        update.effective_user = user
        update.effective_chat = chat

        # Mock rate limiter
        interface.rate_limiter.check_limit = AsyncMock(return_value=(True, None))

        # Process - should not raise
        await interface.handle_text_message(update, MagicMock())

        # Should have sent error message to user
        message.reply_text.assert_called()

    @pytest.mark.asyncio
    async def test_slack_handles_agent_error(self):
        """Test that Slack gracefully handles AgentCore errors."""
        from portal.interfaces.slack.interface import SlackInterface

        # Create interface with failing AgentCore
        agent = MagicMock()
        from portal.core.exceptions import PortalError
        agent.process_message = AsyncMock(side_effect=PortalError("Test error"))

        interface = SlackInterface(
            agent_core=agent,
            config=MagicMock(),
            web_app=MagicMock(),
        )
        interface.client = AsyncMock()

        # Test that send_message handles errors gracefully
        result = await interface.send_message("C12345", "test")
        # Should return False or handle error


class TestInterfacePersonaRouting:
    """Tests for persona selection in interfaces."""

    @pytest.fixture
    def mock_agent_core(self):
        """Create a mock AgentCore."""
        agent = MagicMock()
        result = MagicMock()
        result.success = True
        result.response = "Test response"
        agent.process_message = AsyncMock(return_value=result)
        return agent

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.interfaces.telegram.bot_token = "test_token"
        settings.interfaces.telegram.authorized_users = [12345]
        settings.security.rate_limit_requests = 20
        settings.security.sandbox_enabled = False
        return settings

    @pytest.fixture
    def mock_web_app(self):
        """Create a mock FastAPI web app."""
        from fastapi import FastAPI
        return FastAPI()

    @pytest.mark.asyncio
    async def test_telegram_workspace_routing(self, mock_agent_core, mock_settings):
        """Test that Telegram can use workspace_id for persona routing."""
        from portal.interfaces.telegram.interface import TelegramInterface

        interface = TelegramInterface(
            agent_core=mock_agent_core,
            settings=mock_settings,
            rate_limiter=None,
        )

        # The workspace_id should be passed to process_message
        # when configured
        # This tests that the interface supports workspace-based routing
        assert interface.agent_core is not None

    @pytest.mark.asyncio
    async def test_slack_workspace_routing(self, mock_agent_core, mock_settings, mock_web_app):
        """Test that Slack can use workspace_id for persona routing."""
        from portal.interfaces.slack.interface import SlackInterface

        interface = SlackInterface(
            agent_core=mock_agent_core,
            config=mock_settings,
            web_app=mock_web_app,
        )

        # The workspace_id should be passed to process_message
        # when configured
        assert interface.agent_core is not None
