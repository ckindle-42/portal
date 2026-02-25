"""
Core Interfaces - Abstract interfaces and contracts
===================================================

This module contains the core contracts and interfaces that define
how different components of the system interact.
"""

from .tool import (
    BaseTool,
    ToolMetadata,
    ToolParameter,
    ToolCategory,
)
from .agent_interface import (
    BaseInterface,
    InterfaceManager,
    Message,
    Response,
)

__all__ = [
    'BaseTool',
    'ToolMetadata',
    'ToolParameter',
    'ToolCategory',
    'BaseInterface',
    'InterfaceManager',
    'Message',
    'Response',
]
