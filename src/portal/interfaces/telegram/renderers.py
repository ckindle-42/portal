"""
Enhanced Telegram Interface with Inline Keyboards
=================================================

Adds interactive inline keyboards for better UX on destructive/important operations.

Features:
- Confirmation buttons for dangerous operations
- Quick action menus
- Paginated results
- Tool selection interface
- Model selection
- Settings management

Benefits:
- Better UX (no typing commands)
- Safety confirmations
- Visual feedback
- Mobile-friendly
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from enum import Enum

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

logger = logging.getLogger(__name__)


# ============================================================================
# CALLBACK DATA PATTERNS
# ============================================================================

class CallbackAction(str, Enum):
    """Callback action types"""
    # Tool confirmations
    CONFIRM_DELETE = "confirm_delete"
    CONFIRM_EXECUTE = "confirm_exec"
    CANCEL = "cancel"
    
    # Tool selection
    SELECT_TOOL = "select_tool"
    TOOL_INFO = "tool_info"
    
    # Model selection
    SELECT_MODEL = "select_model"
    
    # Pagination
    PAGE_NEXT = "page_next"
    PAGE_PREV = "page_prev"
    
    # Settings
    TOGGLE_VERBOSE = "toggle_verbose"
    TOGGLE_NOTIFICATIONS = "toggle_notif"
    
    # Knowledge base
    KB_DELETE = "kb_delete"
    KB_CONFIRM_DELETE = "kb_confirm_delete"


class InlineKeyboardHelper:
    """Helper class for creating inline keyboards"""
    
    @staticmethod
    def confirmation_keyboard(
        action: str,
        data: str = "",
        confirm_text: str = "✅ Confirm",
        cancel_text: str = "❌ Cancel"
    ) -> InlineKeyboardMarkup:
        """
        Create confirmation keyboard
        
        Args:
            action: Callback action (e.g., 'confirm_delete')
            data: Additional data to pass
            confirm_text: Text for confirm button
            cancel_text: Text for cancel button
        """
        keyboard = [
            [
                InlineKeyboardButton(confirm_text, callback_data=f"{action}:{data}"),
                InlineKeyboardButton(cancel_text, callback_data=CallbackAction.CANCEL)
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def tool_selection_keyboard(
        tools: List[Dict[str, Any]],
        page: int = 0,
        per_page: int = 5
    ) -> InlineKeyboardMarkup:
        """Create tool selection keyboard with pagination"""
        
        start = page * per_page
        end = start + per_page
        page_tools = tools[start:end]
        
        keyboard = []
        
        # Tool buttons
        for tool in page_tools:
            confirm_emoji = "🔒 " if tool.get('requires_confirmation') else ""
            keyboard.append([
                InlineKeyboardButton(
                    f"{confirm_emoji}{tool['name']}",
                    callback_data=f"{CallbackAction.SELECT_TOOL}:{tool['name']}"
                )
            ])
        
        # Pagination buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                InlineKeyboardButton("⬅️ Previous", callback_data=f"{CallbackAction.PAGE_PREV}:{page}")
            )
        if end < len(tools):
            nav_buttons.append(
                InlineKeyboardButton("Next ➡️", callback_data=f"{CallbackAction.PAGE_NEXT}:{page}")
            )
        
        if nav_buttons:
            keyboard.append(nav_buttons)
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def model_selection_keyboard(models: List[str]) -> InlineKeyboardMarkup:
        """Create model selection keyboard"""
        
        keyboard = []
        for model in models:
            keyboard.append([
                InlineKeyboardButton(
                    model,
                    callback_data=f"{CallbackAction.SELECT_MODEL}:{model}"
                )
            ])
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def settings_keyboard(current_settings: Dict[str, bool]) -> InlineKeyboardMarkup:
        """Create settings toggle keyboard"""
        
        verbose = current_settings.get('verbose_routing', False)
        notifications = current_settings.get('notifications', True)
        
        keyboard = [
            [
                InlineKeyboardButton(
                    f"{'✅' if verbose else '❌'} Verbose Mode",
                    callback_data=CallbackAction.TOGGLE_VERBOSE
                )
            ],
            [
                InlineKeyboardButton(
                    f"{'✅' if notifications else '❌'} Notifications",
                    callback_data=CallbackAction.TOGGLE_NOTIFICATIONS
                )
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def knowledge_base_actions_keyboard(doc_id: int) -> InlineKeyboardMarkup:
        """Create knowledge base document actions keyboard"""
        
        keyboard = [
            [
                InlineKeyboardButton(
                    "ℹ️ View Details",
                    callback_data=f"kb_view:{doc_id}"
                ),
                InlineKeyboardButton(
                    "🗑️ Delete",
                    callback_data=f"{CallbackAction.KB_DELETE}:{doc_id}"
                )
            ]
        ]
        
        return InlineKeyboardMarkup(keyboard)


# ============================================================================
# ENHANCED TELEGRAM BOT WITH INLINE KEYBOARDS
# ============================================================================

class EnhancedTelegramBot:
    """
    Enhanced Telegram bot with inline keyboards.
    
    This extends the basic Telegram interface with interactive buttons
    for better UX, especially on mobile devices.
    """
    
    def __init__(self, base_bot_instance):
        """
        Initialize with existing bot instance
        
        Args:
            base_bot_instance: Existing TelegramInterface instance
        """
        self.base_bot = base_bot_instance
        self.keyboard_helper = InlineKeyboardHelper()
        
        # Store pending confirmations (user_id -> action data)
        self.pending_confirmations: Dict[int, Dict[str, Any]] = {}
        
        # User settings
        self.user_settings: Dict[int, Dict[str, bool]] = {}
    
    def register_handlers(self, application: Application):
        """Register callback query handlers"""
        
        # Callback query handler (for button clicks)
        application.add_handler(
            CallbackQueryHandler(self.handle_callback_query)
        )
        
        # Enhanced commands
        application.add_handler(
            CommandHandler("tools_menu", self.show_tools_menu)
        )
        application.add_handler(
            CommandHandler("settings", self.show_settings)
        )
        application.add_handler(
            CommandHandler("models", self.show_models)
        )
        
        logger.info("✅ Enhanced Telegram handlers registered")
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline keyboard button clicks"""
        
        query: CallbackQuery = update.callback_query
        await query.answer()  # Acknowledge button click
        
        # Parse callback data
        data = query.data
        action, *params = data.split(":", 1)
        param = params[0] if params else ""
        
        user_id = update.effective_user.id
        
        # Route to appropriate handler
        if action == CallbackAction.CONFIRM_DELETE:
            await self._handle_confirm_delete(query, param)
        
        elif action == CallbackAction.CONFIRM_EXECUTE:
            await self._handle_confirm_execute(query, param)
        
        elif action == CallbackAction.CANCEL:
            await self._handle_cancel(query)
        
        elif action == CallbackAction.SELECT_TOOL:
            await self._handle_tool_selection(query, param)
        
        elif action == CallbackAction.SELECT_MODEL:
            await self._handle_model_selection(query, param)
        
        elif action == CallbackAction.PAGE_NEXT:
            await self._handle_page_next(query, int(param))
        
        elif action == CallbackAction.PAGE_PREV:
            await self._handle_page_prev(query, int(param))
        
        elif action == CallbackAction.TOGGLE_VERBOSE:
            await self._handle_toggle_verbose(query, user_id)
        
        elif action == CallbackAction.TOGGLE_NOTIFICATIONS:
            await self._handle_toggle_notifications(query, user_id)
        
        elif action == CallbackAction.KB_DELETE:
            await self._handle_kb_delete(query, param)
        
        elif action == CallbackAction.KB_CONFIRM_DELETE:
            await self._handle_kb_confirm_delete(query, param)
        
        else:
            await query.edit_message_text(f"❌ Unknown action: {action}")
    
    # ========================================================================
    # COMMAND HANDLERS
    # ========================================================================
    
    async def show_tools_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show interactive tools menu"""
        
        # Get tools from agent core
        tools = self.base_bot.agent_core.get_tool_list()
        
        keyboard = self.keyboard_helper.tool_selection_keyboard(tools, page=0)
        
        message = (
            "🛠️ **Available Tools**\n\n"
            f"Select a tool to see details or execute.\n"
            f"Total: {len(tools)} tools"
        )
        
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show settings menu"""
        
        user_id = update.effective_user.id
        settings = self.user_settings.get(user_id, {
            'verbose_routing': False,
            'notifications': True
        })
        
        keyboard = self.keyboard_helper.settings_keyboard(settings)
        
        message = (
            "⚙️ **Settings**\n\n"
            "Toggle your preferences:"
        )
        
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def show_models(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show model selection menu"""
        
        models = [
            "qwen2.5-7b (Default)",
            "qwen2.5-14b (Balanced)",
            "qwen2.5-32b (Advanced)",
            "claude-3-5-sonnet (Cloud)",
            "gpt-4-turbo (Cloud)"
        ]
        
        keyboard = self.keyboard_helper.model_selection_keyboard(models)
        
        message = (
            "🤖 **Model Selection**\n\n"
            "Choose preferred model:"
        )
        
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    # ========================================================================
    # CALLBACK HANDLERS
    # ========================================================================
    
    async def _handle_confirm_delete(self, query: CallbackQuery, doc_id: str):
        """Handle delete confirmation"""
        
        try:
            # Execute actual deletion
            result = await self.base_bot.agent_core.execute_tool(
                "knowledge_base_enhanced",
                {"action": "delete", "doc_id": int(doc_id)}
            )
            
            if result.get('success'):
                await query.edit_message_text(
                    f"✅ Document {doc_id} deleted successfully"
                )
            else:
                await query.edit_message_text(
                    f"❌ Failed to delete: {result.get('error')}"
                )
        
        except Exception as e:
            await query.edit_message_text(f"❌ Error: {e}")
    
    async def _handle_confirm_execute(self, query: CallbackQuery, tool_params: str):
        """Handle tool execution confirmation"""
        
        await query.edit_message_text("⏳ Executing...")
        
        # Parse tool and params
        # Format: "tool_name|param1=value1|param2=value2"
        parts = tool_params.split("|")
        tool_name = parts[0]
        params = {}
        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                params[key] = value
        
        try:
            result = await self.base_bot.agent_core.execute_tool(tool_name, params)
            
            if result.get('success'):
                response = f"✅ Execution successful\n\n{result.get('result')}"
            else:
                response = f"❌ Execution failed: {result.get('error')}"
            
            await query.message.reply_text(response[:4000])  # Telegram limit
        
        except Exception as e:
            await query.message.reply_text(f"❌ Error: {e}")
    
    async def _handle_cancel(self, query: CallbackQuery):
        """Handle cancellation"""
        await query.edit_message_text("❌ Operation cancelled")
    
    async def _handle_tool_selection(self, query: CallbackQuery, tool_name: str):
        """Handle tool selection from menu"""
        
        # Get tool details
        tools = self.base_bot.agent_core.get_tool_list()
        tool = next((t for t in tools if t['name'] == tool_name), None)
        
        if not tool:
            await query.edit_message_text(f"❌ Tool not found: {tool_name}")
            return
        
        # Show tool details
        message = (
            f"🛠️ **{tool['name']}**\n\n"
            f"**Description:** {tool['description']}\n"
            f"**Category:** {tool['category']}\n"
            f"**Requires Confirmation:** {'Yes' if tool['requires_confirmation'] else 'No'}\n\n"
            f"To use this tool, send a message describing what you want to do."
        )
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def _handle_model_selection(self, query: CallbackQuery, model: str):
        """Handle model selection"""
        
        user_id = query.from_user.id
        
        # Store user preference (you'd implement this properly with persistence)
        if not hasattr(self, 'user_model_preferences'):
            self.user_model_preferences = {}
        
        self.user_model_preferences[user_id] = model
        
        await query.edit_message_text(
            f"✅ Preferred model set to: {model}\n\n"
            "This will be used for your future requests."
        )
    
    async def _handle_page_next(self, query: CallbackQuery, current_page: int):
        """Handle next page"""
        
        tools = self.base_bot.agent_core.get_tool_list()
        keyboard = self.keyboard_helper.tool_selection_keyboard(
            tools,
            page=current_page + 1
        )
        
        await query.edit_message_reply_markup(reply_markup=keyboard)
    
    async def _handle_page_prev(self, query: CallbackQuery, current_page: int):
        """Handle previous page"""
        
        tools = self.base_bot.agent_core.get_tool_list()
        keyboard = self.keyboard_helper.tool_selection_keyboard(
            tools,
            page=current_page - 1
        )
        
        await query.edit_message_reply_markup(reply_markup=keyboard)
    
    async def _handle_toggle_verbose(self, query: CallbackQuery, user_id: int):
        """Toggle verbose mode"""
        
        if user_id not in self.user_settings:
            self.user_settings[user_id] = {'verbose_routing': False, 'notifications': True}
        
        current = self.user_settings[user_id]['verbose_routing']
        self.user_settings[user_id]['verbose_routing'] = not current
        
        keyboard = self.keyboard_helper.settings_keyboard(self.user_settings[user_id])
        
        await query.edit_message_reply_markup(reply_markup=keyboard)
        await query.answer(f"Verbose mode: {'ON' if not current else 'OFF'}")
    
    async def _handle_toggle_notifications(self, query: CallbackQuery, user_id: int):
        """Toggle notifications"""
        
        if user_id not in self.user_settings:
            self.user_settings[user_id] = {'verbose_routing': False, 'notifications': True}
        
        current = self.user_settings[user_id]['notifications']
        self.user_settings[user_id]['notifications'] = not current
        
        keyboard = self.keyboard_helper.settings_keyboard(self.user_settings[user_id])
        
        await query.edit_message_reply_markup(reply_markup=keyboard)
        await query.answer(f"Notifications: {'ON' if not current else 'OFF'}")
    
    async def _handle_kb_delete(self, query: CallbackQuery, doc_id: str):
        """Show delete confirmation for knowledge base document"""
        
        keyboard = self.keyboard_helper.confirmation_keyboard(
            action=CallbackAction.KB_CONFIRM_DELETE,
            data=doc_id,
            confirm_text="🗑️ Yes, Delete",
            cancel_text="❌ Cancel"
        )
        
        await query.edit_message_text(
            f"⚠️ **Confirm Deletion**\n\n"
            f"Are you sure you want to delete document {doc_id}?\n"
            f"This action cannot be undone.",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def _handle_kb_confirm_delete(self, query: CallbackQuery, doc_id: str):
        """Execute knowledge base document deletion"""
        await self._handle_confirm_delete(query, doc_id)
    
    # ========================================================================
    # HELPER METHODS FOR INTEGRATION
    # ========================================================================
    
    async def send_with_confirmation(
        self,
        chat_id: int,
        message: str,
        action: str,
        data: str = ""
    ):
        """Send message with confirmation buttons"""
        
        keyboard = self.keyboard_helper.confirmation_keyboard(action, data)
        
        await self.base_bot.app.bot.send_message(
            chat_id=chat_id,
            text=message,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
    
    async def send_knowledge_base_results(
        self,
        chat_id: int,
        documents: List[Dict[str, Any]]
    ):
        """Send knowledge base search results with action buttons"""
        
        for doc in documents:
            keyboard = self.keyboard_helper.knowledge_base_actions_keyboard(doc['id'])
            
            message = (
                f"📄 **Document {doc['id']}**\n\n"
                f"**Source:** {doc['source']}\n"
                f"**Preview:** {doc.get('preview', doc.get('content', ''))[:200]}...\n"
            )
            
            await self.base_bot.app.bot.send_message(
                chat_id=chat_id,
                text=message,
                reply_markup=keyboard,
                parse_mode='Markdown'
            )


# ============================================================================
# INTEGRATION EXAMPLE
# ============================================================================

"""
To integrate with existing TelegramInterface:

1. In your telegram_interface.py:

from enhanced_telegram_ui import EnhancedTelegramBot

class TelegramInterface:
    def __init__(self):
        # ... existing init code ...
        
        # Add enhanced UI
        self.enhanced_ui = EnhancedTelegramBot(self)
    
    def _register_handlers(self, application):
        # ... existing handlers ...
        
        # Register enhanced handlers
        self.enhanced_ui.register_handlers(application)

2. Use in message handler:

async def handle_message(self, update, context):
    # Check if response requires confirmation
    if requires_confirmation:
        await self.enhanced_ui.send_with_confirmation(
            chat_id=update.effective_chat.id,
            message="⚠️ This will delete files. Continue?",
            action="confirm_delete",
            data="file_id_123"
        )
    else:
        # Normal response
        await update.message.reply_text(response)
"""


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

async def example_usage():
    """Example of how to use inline keyboards"""
    
    # Example 1: Confirmation for dangerous operation
    keyboard = InlineKeyboardHelper.confirmation_keyboard(
        action="confirm_delete",
        data="doc_123"
    )
    # Send with: reply_markup=keyboard
    
    # Example 2: Tool selection menu
    tools = [
        {"name": "qr_generator", "requires_confirmation": False},
        {"name": "shell_execute", "requires_confirmation": True},
    ]
    keyboard = InlineKeyboardHelper.tool_selection_keyboard(tools)
    
    # Example 3: Settings menu
    settings = {"verbose_routing": True, "notifications": False}
    keyboard = InlineKeyboardHelper.settings_keyboard(settings)


if __name__ == "__main__":
    print("Enhanced Telegram UI Module")
    print("Import this module in your telegram_interface.py")
