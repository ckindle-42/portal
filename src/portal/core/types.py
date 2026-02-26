"""
Core Type Definitions
=====================

Centralized type definitions for the core module.
Provides type safety and prevents magic strings throughout the codebase.

ProcessingResult is the single canonical result object returned by AgentCore
and consumed by all interfaces (Web, Telegram, Slack).  Fields cover both the
response text and the richer metadata that Telegram/debug views surface.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
    history: list[dict[str, Any]] = field(default_factory=list)
    source: str = "web"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingResult:
    """
    Unified result from AgentCore.process_message().

    This is the single source of truth for processing results — the local
    ProcessingResult that previously lived in agent_core.py has been removed
    and all code now imports from here.

    Fields used by WebInterface:
        response, prompt_tokens, completion_tokens

    Fields used by TelegramInterface:
        response, success, model_used, execution_time, tools_used, warnings

    Fields used internally / for debugging:
        trace_id, metadata, tool_results, error
    """
    # Primary response text
    response: str

    # Execution metadata
    success: bool = True
    model_used: str = ""
    execution_time: float = 0.0

    # Tool usage
    tools_used: list[str] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)

    # Token accounting (for OpenAI-compat /v1/chat/completions usage block)
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    # Warnings and errors
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    # Tracing
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


__all__ = ['InterfaceType', 'IncomingMessage', 'ProcessingResult']
