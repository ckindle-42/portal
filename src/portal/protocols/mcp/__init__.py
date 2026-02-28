"""
Model Context Protocol (MCP)
=============================
MCP client support via MCPRegistry.
Manages HTTP connections to MCP servers (mcpo, Scrapling, etc.)
"""

from .mcp_registry import MCPRegistry

__all__ = ["MCPRegistry"]
