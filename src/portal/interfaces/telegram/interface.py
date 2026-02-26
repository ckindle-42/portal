"""
Telegram Interface - Passive Adapter for AgentCore
====================================================

This is a PASSIVE ADAPTER that connects Telegram to the unified AgentCore.
It relies on Dependency Injection - all dependencies are passed in, not created.

Architecture:
    CLI → AgentCore (injected) → TelegramInterface (adapter) → Telegram Bot

Key Principle: This interface is a "dumb" adapter, not a factory.
It does NOT create its own AgentCore or load configuration.
All dependencies are injected via the constructor.
"""

import asyncio
import logging
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from portal.agent.dispatcher import CentralDispatcher

# Import types
from portal.core.types import InterfaceType, ProcessingResult

# Import confirmation middleware
from portal.middleware import ConfirmationRequest, ToolConfirmationMiddleware

# Import security module
from portal.security.security_module import RateLimiter

if TYPE_CHECKING:
    from portal.config.settings import Settings
    from portal.core import AgentCore

logger = logging.getLogger(__name__)


@CentralDispatcher.register("telegram")
class TelegramInterface:
    """
    Telegram Bot Interface - Passive Adapter Pattern

    This class handles ONLY Telegram-specific concerns:
    - Authorization (checking user IDs)
    - Rate limiting (per-user throttling)
    - Message formatting (Markdown, chunking)
    - Telegram Bot API interaction

    The actual AI processing is delegated to the INJECTED AgentCore.
    This interface does NOT create its own core or load configuration.

    Dependencies (injected via constructor):
    - agent_core: Pre-configured AgentCore instance
    - settings: Application settings (for telegram, security, tools config)
    """

    def __init__(self, agent_core: 'AgentCore', settings: 'Settings') -> None:
        """
        Initialize Telegram interface with injected dependencies

        Args:
            agent_core: Pre-configured AgentCore instance (already wrapped in SecurityMiddleware by CLI)
            settings: Application settings object (Pydantic Settings)

        Raises:
            ValueError: If telegram config is missing or invalid
        """

        logger.info("=" * 60)
        logger.info("Initializing Telegram Interface (Passive Adapter)")
        logger.info("=" * 60)

        # Store injected dependencies
        self.agent_core = agent_core
        self.settings = settings

        # Validate telegram configuration
        if not settings.interfaces.telegram:
            raise ValueError("Telegram interface configuration missing in settings")

        telegram_config = settings.interfaces.telegram

        # Telegram-specific config
        self.bot_token = telegram_config.bot_token

        # Support legacy single user ID or new list of allowed user IDs
        if telegram_config.authorized_users:
            self.authorized_user_ids = set(telegram_config.authorized_users)
        else:
            # Fallback: try to get from environment (backward compatibility)
            import os
            user_id_str = os.getenv('TELEGRAM_USER_ID')
            if user_id_str:
                self.authorized_user_ids = {int(user_id_str)}
            else:
                raise ValueError("No authorized user IDs configured. Set authorized_users in config.")

        # Initialize rate limiter from security config
        security_config = settings.security
        self.rate_limiter = RateLimiter(
            max_requests=security_config.rate_limit_requests,
            window_seconds=60  # 1 minute window
        )

        # Initialize confirmation middleware if enabled
        self.confirmation_middleware = None

        # Check if tools require confirmation (use security config)
        if security_config.sandbox_enabled:
            logger.info("Initializing Tool Confirmation Middleware...")

            # Admin chat ID is the first authorized user
            self.admin_chat_id = list(self.authorized_user_ids)[0] if self.authorized_user_ids else None

            if not self.admin_chat_id:
                logger.warning("Cannot enable confirmation middleware: no authorized users configured")
            else:
                self.confirmation_middleware = ToolConfirmationMiddleware(
                    event_bus=self.agent_core.event_bus,
                    confirmation_sender=self._send_confirmation_request,
                    default_timeout=300  # 5 minutes default
                )

                # Inject middleware into agent core
                self.agent_core.confirmation_middleware = self.confirmation_middleware

                logger.info(
                    "Confirmation middleware enabled (admin_chat_id: %s)",
                    self.admin_chat_id,
                )

        # Telegram application
        self.application = None

        logger.info("=" * 60)
        logger.info("Telegram Interface ready!")
        logger.info("  Bot token: %s...", self.bot_token[:20])
        logger.info("  Authorized users: %s", len(self.authorized_user_ids))
        logger.info("  Dependency Injection: ✓")
        logger.info("=" * 60)

    # ========================================================================
    # AUTHORIZATION & SECURITY
    # ========================================================================

    def _is_authorized(self, update: Update) -> bool:
        """Check if user is authorized"""
        return update.effective_user.id in self.authorized_user_ids

    async def _check_rate_limit(self, user_id: int) -> tuple[bool, str | None]:
        """Check rate limiting"""
        return await self.rate_limiter.check_limit(user_id)

    # ========================================================================
    # CONFIRMATION MIDDLEWARE INTEGRATION
    # ========================================================================

    async def _send_confirmation_request(self, request: ConfirmationRequest) -> None:
        """
        Send a confirmation request to the admin via Telegram

        This is called by the confirmation middleware when a high-risk tool
        needs approval before execution.

        Args:
            request: The confirmation request to send
        """
        try:
            # Format tool parameters for display
            params_str = "\n".join([
                f"  • {key}: {value}"
                for key, value in request.parameters.items()
            ])

            message = (
                f"⚠️ **Tool Confirmation Required**\n\n"
                f"**Tool:** `{request.tool_name}`\n"
                f"**User Chat:** {request.chat_id}\n"
                f"**User ID:** {request.user_id or 'Unknown'}\n\n"
                f"**Parameters:**\n{params_str}\n\n"
                f"**Timeout:** {request.timeout_seconds}s\n\n"
                f"This tool requires your approval before execution. "
                f"Please review and approve or deny."
            )

            # Create inline keyboard with Approve/Deny buttons
            keyboard = [
                [
                    InlineKeyboardButton(
                        "✅ Approve",
                        callback_data=f"confirm_approve:{request.confirmation_id}"
                    ),
                    InlineKeyboardButton(
                        "❌ Deny",
                        callback_data=f"confirm_deny:{request.confirmation_id}"
                    )
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Send to admin chat
            await self.application.bot.send_message(
                chat_id=self.admin_chat_id,
                text=message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

            logger.info(
                "Confirmation request sent to admin: %s",
                request.confirmation_id,
                extra={
                    'tool_name': request.tool_name,
                    'confirmation_id': request.confirmation_id,
                    'admin_chat_id': self.admin_chat_id
                }
            )

        except Exception as e:
            logger.error(
                "Failed to send confirmation request: %s",
                e,
                exc_info=True
            )
            raise

    async def _handle_confirmation_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Handle confirmation approval/denial callbacks

        This is called when the admin clicks Approve or Deny on a confirmation request.
        """
        query = update.callback_query
        await query.answer()

        # Check authorization
        if query.from_user.id != self.admin_chat_id:
            await query.edit_message_text("⛔ Unauthorized")
            return

        # Parse callback data
        callback_data = query.data
        if not callback_data:
            return

        try:
            action, confirmation_id = callback_data.split(':', 1)

            if action == "confirm_approve":
                # Approve the confirmation
                success = self.confirmation_middleware.approve(
                    confirmation_id,
                    approver_id=str(query.from_user.id)
                )

                if success:
                    await query.edit_message_text(
                        f"✅ **Tool Execution Approved**\n\n"
                        f"Confirmation ID: `{confirmation_id}`\n\n"
                        f"The tool will now be executed.",
                        parse_mode='Markdown'
                    )
                    logger.info("Tool execution approved: %s", confirmation_id)
                else:
                    await query.edit_message_text(
                        "⚠️ **Confirmation Not Found**\n\n"
                        "The confirmation may have already been processed or expired.",
                        parse_mode='Markdown'
                    )

            elif action == "confirm_deny":
                # Deny the confirmation
                success = self.confirmation_middleware.deny(
                    confirmation_id,
                    denier_id=str(query.from_user.id)
                )

                if success:
                    await query.edit_message_text(
                        f"❌ **Tool Execution Denied**\n\n"
                        f"Confirmation ID: `{confirmation_id}`\n\n"
                        f"The tool execution has been cancelled.",
                        parse_mode='Markdown'
                    )
                    logger.info("Tool execution denied: %s", confirmation_id)
                else:
                    await query.edit_message_text(
                        "⚠️ **Confirmation Not Found**\n\n"
                        "The confirmation may have already been processed or expired.",
                        parse_mode='Markdown'
                    )

        except ValueError:
            logger.error("Invalid callback data: %s", callback_data, exc_info=True)
            await query.edit_message_text("⚠️ Invalid callback data")
        except Exception as e:
            logger.error("Error handling confirmation callback: %s", e, exc_info=True)
            await query.edit_message_text(f"⚠️ Error: {str(e)}")

    # ========================================================================
    # COMMAND HANDLERS
    # ========================================================================

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command"""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized")
            return

        welcome = (
            "🤖 **Portal Agent v3.1**\n\n"
            "🧠 Unified core architecture\n"
            "🔧 11+ tools ready\n"
            "🚀 Intelligent routing\n\n"
            "**Commands:**\n"
            "• `/help` - Show help\n"
            "• `/tools` - List tools\n"
            "• `/stats` - Show stats\n"
            "• `/health` - System health\n\n"
            "Just send me a message to get started!"
        )

        await update.message.reply_text(welcome, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command"""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized")
            return

        help_text = (
            "**Available Commands:**\n\n"
            "• `/start` - Welcome message\n"
            "• `/help` - This help message\n"
            "• `/tools` - List available tools\n"
            "• `/stats` - Processing statistics\n"
            "• `/health` - System health check\n\n"
            "**How to use:**\n"
            "Just send me a message with your request. "
            "I'll automatically select the best model and tools to help you!"
        )

        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def tools_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /tools command"""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized")
            return

        tools = self.agent_core.get_tool_list()

        message = f"**Available Tools ({len(tools)}):**\n\n"

        # Group by category
        by_category = {}
        for tool in tools:
            cat = tool['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(tool)

        for category, cat_tools in sorted(by_category.items()):
            message += f"**{category.upper()}:**\n"
            for tool in cat_tools:
                confirm = "🔒" if tool['requires_confirmation'] else ""
                message += f"  • {confirm} {tool['name']}: {tool['description']}\n"
            message += "\n"

        await update.message.reply_text(message, parse_mode='Markdown')

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /stats command"""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized")
            return

        stats = await self.agent_core.get_stats()

        message = (
            "**📊 Processing Statistics:**\n\n"
            f"• Messages processed: {stats['messages_processed']}\n"
            f"• Tools executed: {stats['tools_executed']}\n"
            f"• Avg execution time: {stats['avg_execution_time']:.2f}s\n"
            f"• Uptime: {stats['uptime_seconds']:.0f}s\n\n"
            "**By Interface:**\n"
        )

        for interface, count in stats['by_interface'].items():
            message += f"  • {interface}: {count}\n"

        await update.message.reply_text(message, parse_mode='Markdown')

    async def health_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /health command"""
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized")
            return

        # Get stats
        stats = await self.agent_core.get_stats()
        tools = self.agent_core.get_tool_list()

        health = (
            "**🏥 System Health:**\n\n"
            f"✅ Core: Running\n"
            f"✅ Tools: {len(tools)} loaded\n"
            f"✅ Models: Available\n"
            f"✅ Messages: {stats['messages_processed']} processed\n"
            f"✅ Uptime: {stats['uptime_seconds']:.0f}s\n\n"
            "All systems operational! 🚀"
        )

        await update.message.reply_text(health, parse_mode='Markdown')

    # ========================================================================
    # MESSAGE HANDLER
    # ========================================================================

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages - the main interaction"""

        # Authorization check
        if not self._is_authorized(update):
            await update.message.reply_text("⛔ Unauthorized")
            return

        # Rate limiting check
        user_id = update.effective_user.id
        allowed, error_msg = await self._check_rate_limit(user_id)
        if not allowed:
            await update.message.reply_text(error_msg)
            return

        message = update.message.text
        chat_id = f"telegram_{update.effective_chat.id}"

        logger.info("Received message from user %s: %s...", user_id, message[:50])

        # Show typing indicator
        await update.message.chat.send_action(ChatAction.TYPING)

        try:
            # Process with unified core
            result: ProcessingResult = await self.agent_core.process_message(
                chat_id=chat_id,
                message=message,
                interface=InterfaceType.TELEGRAM,
                user_context={'user_id': user_id},
            )

            # Show warnings if any
            if result.warnings:
                warning_text = "⚠️ Security warnings:\n" + "\n".join(result.warnings)
                await update.message.reply_text(warning_text)

            # Format response for Telegram
            response_text = result.response

            # Add footer with model info if verbose mode
            # (verbose_routing would be in logging config or a future feature flag)
            verbose_routing = getattr(self.settings.logging, 'verbose', False) or \
                             getattr(self.settings, 'verbose_routing', False)

            if verbose_routing:
                footer = (
                    f"\n\n_Model: {result.model_used} "
                    f"({result.execution_time:.2f}s)"
                )
                if result.tools_used:
                    footer += f" | Tools: {', '.join(result.tools_used)}"
                footer += "_"
                response_text += footer

            # Send response (handle long messages)
            if len(response_text) > 4096:
                # Split into chunks
                chunks = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode='Markdown')
            else:
                await update.message.reply_text(response_text, parse_mode='Markdown')

        except Exception as e:
            logger.error("Error handling message: %s", e, exc_info=True)
            await update.message.reply_text(
                f"⚠️ Error processing your request: {str(e)}"
            )

    # ========================================================================
    # STARTUP & RUN
    # ========================================================================

    def run(self) -> None:
        """Start the Telegram bot"""

        logger.info("Building Telegram application...")

        # Create application
        self.application = Application.builder().token(self.bot_token).build()

        # Register command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("tools", self.tools_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("health", self.health_command))

        # Register callback handler for confirmations
        if self.confirmation_middleware:
            self.application.add_handler(
                CallbackQueryHandler(
                    self._handle_confirmation_callback,
                    pattern=r"^confirm_(approve|deny):"
                )
            )
            logger.info("Confirmation callback handler registered")

        # Register message handler
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message)
        )

        # Start confirmation middleware
        if self.confirmation_middleware:
            asyncio.create_task(self.confirmation_middleware.start())
            logger.info("Confirmation middleware started")

        logger.info("=" * 60)
        logger.info("🚀 Telegram Bot Starting!")
        logger.info("=" * 60)

        # Start polling
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
