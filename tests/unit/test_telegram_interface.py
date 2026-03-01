"""
Unit tests for Telegram interface None guard handling
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from portal.interfaces.telegram.interface import TelegramInterface


@pytest.mark.unit
class TestTelegramInterfaceNoneGuards:
    """Test that Telegram handlers properly handle None values"""

    def _create_mock_update(
        self, message=None, callback_query=None, effective_user=None, effective_chat=None
    ):
        """Create a mock Update object with optional None attributes"""
        update = MagicMock()
        update.message = message
        update.callback_query = callback_query
        # Explicitly allow None values for testing guards
        update.effective_user = effective_user
        update.effective_chat = effective_chat
        return update

    @pytest.mark.asyncio
    async def test_handle_text_message_with_none_message(self):
        """Test handle_text_message returns silently when update.message is None"""
        # This tests that the None guard prevents AttributeError
        interface = MagicMock()

        # Create Update with message=None
        update = self._create_mock_update(message=None)

        # The handler should return early without raising
        result = await TelegramInterface.handle_text_message(interface, update, MagicMock())

        # Should return None (early return) without raising
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_text_message_with_none_effective_user(self):
        """Test handle_text_message returns silently when effective_user is None"""
        interface = MagicMock()
        interface._check_rate_limit = AsyncMock(return_value=(True, None))

        # Create Update with effective_user=None but message exists
        message = MagicMock()
        message.reply_text = MagicMock()
        update = self._create_mock_update(message=message, effective_user=None)

        # Should return early without raising
        result = await TelegramInterface.handle_text_message(interface, update, MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_text_message_with_none_effective_chat(self):
        """Test handle_text_message returns silently when effective_chat is None"""
        interface = MagicMock()
        interface._check_rate_limit = AsyncMock(return_value=(True, None))

        # Create Update with effective_chat=None but message exists
        message = MagicMock()
        message.reply_text = MagicMock()
        update = self._create_mock_update(message=message, effective_chat=None)

        # Should return early without raising
        result = await TelegramInterface.handle_text_message(interface, update, MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_callback_handler_with_none_callback_query(self):
        """Test _handle_confirmation_callback returns silently when callback_query is None"""
        interface = MagicMock()

        # Create Update with callback_query=None
        update = self._create_mock_update(callback_query=None)

        # Should return early without raising
        result = await TelegramInterface._handle_confirmation_callback(
            interface, update, MagicMock()
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_start_command_with_none_message(self):
        """Test start_command returns silently when update.message is None"""
        interface = MagicMock()

        # Create Update with message=None
        update = self._create_mock_update(message=None)

        result = await TelegramInterface.start_command(interface, update, MagicMock())
        assert result is None

    @pytest.mark.asyncio
    async def test_help_command_with_none_message(self):
        """Test help_command returns silently when update.message is None"""
        interface = MagicMock()

        # Create Update with message=None
        update = self._create_mock_update(message=None)

        result = await TelegramInterface.help_command(interface, update, MagicMock())
        assert result is None
