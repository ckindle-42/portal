"""
Interfaces module - Adapters for different platforms
====================================================

Modularized interface packages for better organization:
- web/:      FastAPI + WebSocket web interface (OpenAI-compatible)
- telegram/: Telegram bot interface and renderers
- slack/:    Slack Events API interface
"""

from portal.core.interfaces.agent_interface import BaseInterface, InterfaceManager, Message, Response
from portal.interfaces.web import WebInterface

__all__ = [
    'BaseInterface',
    'InterfaceManager',
    'Message',
    'Response',
    'WebInterface',
]
