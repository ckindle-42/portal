"""
Core Type Definitions
=====================

Centralized type definitions for the core module.
Provides type safety and prevents magic strings throughout the codebase.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class InterfaceType(str, Enum):
    """
    Enumeration of supported interface types.

    Using Enum instead of magic strings provides:
    - Type safety at development time
    - IDE autocomplete support
    - Easier refactoring
    - Protection against typos
    """

    TELEGRAM = "telegram"
    WEB = "web"
    SLACK = "slack"
    API = "api"
    CLI = "cli"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        """Return the string value for backward compatibility"""
        return self.value


@dataclass
class IncomingMessage:
    """Standardized incoming message across all interfaces."""
    id: str
    text: str
    model: str = "auto"
    history: list[dict] = field(default_factory=list)
    source: str = "web"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingResult:
    """Standardized result from AgentCore processing."""
    text: str
    model: str = ""
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    tool_results: list[dict] = field(default_factory=list)
    error: Optional[str] = None


__all__ = ['InterfaceType', 'IncomingMessage', 'ProcessingResult']
