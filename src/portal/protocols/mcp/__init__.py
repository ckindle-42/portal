"""
Model Context Protocol (MCP)
=============================

Bidirectional MCP support:
- MCP Client: Connect to other MCP servers
- MCP Server: Expose Portal tools via MCP
- MCP Registry: Manage MCP server configurations

This enables full mesh networking between Portal
and other MCP-compatible applications.
"""

from .mcp_registry import MCPRegistry

# Connector is optional (requires base_tool)
try:
    from .mcp_connector import MCPConnectorTool
    MCP_CONNECTOR_AVAILABLE = True
except ImportError:
    MCP_CONNECTOR_AVAILABLE = False
    MCPConnectorTool = None

# Server is optional (requires MCP SDK)
try:
    from .mcp_server import MCPServer, start_mcp_server
    MCP_SERVER_AVAILABLE = True
except ImportError:
    MCP_SERVER_AVAILABLE = False
    MCPServer = None
    start_mcp_server = None

__all__ = [
    'MCPRegistry',
    'MCPConnectorTool',
    'MCPServer',
    'start_mcp_server',
    'MCP_SERVER_AVAILABLE',
    'MCP_CONNECTOR_AVAILABLE',
]
