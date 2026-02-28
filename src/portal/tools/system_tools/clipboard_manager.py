"""
Clipboard Manager Tool - Read/write clipboard
"""

import logging
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory

logger = logging.getLogger(__name__)

try:
    import pyperclip

    CLIPBOARD_AVAILABLE = True
except ImportError:
    CLIPBOARD_AVAILABLE = False


class ClipboardManagerTool(BaseTool):
    """Manage system clipboard"""

    METADATA = {
        "name": "clipboard_manager",
        "description": "Read from or write to system clipboard",
        "category": ToolCategory.UTILITY,
        "requires_confirmation": True,
        "parameters": [
            {"name": "action", "param_type": "string", "description": "Clipboard action: read, write, clear", "required": True},
            {"name": "content", "param_type": "string", "description": "Content to write (for write action)", "required": False},
        ],
    }

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute clipboard operation"""

        if not CLIPBOARD_AVAILABLE:
            return self._error_response("Pyperclip not installed. Run: pip install pyperclip")

        action = parameters.get("action")

        try:
            if action == "read":
                content = pyperclip.paste()
                return self._success_response(result=content, metadata={"length": len(content)})

            elif action == "write":
                content = parameters.get("content", "")
                pyperclip.copy(content)
                return self._success_response(
                    result=f"Wrote {len(content)} characters to clipboard",
                    metadata={"length": len(content)},
                )

            elif action == "clear":
                pyperclip.copy("")
                return self._success_response(result="Clipboard cleared")

            else:
                return self._error_response(f"Unknown action: {action}")

        except Exception as e:
            return self._error_response(f"Clipboard operation failed: {str(e)}")
