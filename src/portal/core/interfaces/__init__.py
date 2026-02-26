"""
Core Interfaces - Abstract interfaces and contracts
===================================================

This module contains the core contracts and interfaces that define
how different components of the system interact.
"""

from .agent_interface import (
    BaseInterface,
    InterfaceManager,
    Message,
    Response,
)
from .tool import (
    BaseTool,
    ToolCategory,
    ToolMetadata,
    ToolParameter,
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
