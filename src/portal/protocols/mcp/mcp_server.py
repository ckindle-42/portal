"""
MCP Server - Bidirectional MCP Support
=======================================

Exposes Portal tools as an MCP server, allowing other
applications to connect to Portal and use its tools.

This enables:
- Other Claude Desktop instances to use Portal tools
- Third-party applications to integrate with Portal
- Bidirectional communication (Portal ↔ Other apps)

Example:
--------
User's Claude Desktop can use Portal's tools while
Portal can use Claude Desktop's tools - full mesh.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import MCP SDK
try:
    from mcp.server import Server, stdio_server
    from mcp.server.models import InitializationOptions
    from mcp import types
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP SDK not available. Install with: pip install mcp==0.9.0")


class MCPServer:
    """
    MCP Server implementation for Portal.

    Exposes Portal's tools via the Model Context Protocol,
    allowing other applications to connect and use them.
    """

    def __init__(self, tool_registry: Optional[Any] = None):
        """
        Initialize MCP server.

        Args:
            tool_registry: Optional tool registry to expose tools from
        """
        if not MCP_AVAILABLE:
            raise RuntimeError("MCP SDK not installed")

        self.tool_registry = tool_registry
        self.server = Server("portal")
        self._setup_handlers()

        logger.info("MCPServer initialized")

    def _setup_handlers(self):
        """Setup MCP protocol handlers"""

        @self.server.list_tools()
        async def list_tools() -> List[types.Tool]:
            """List available tools"""
            if self.tool_registry is None:
                return []

            # Convert Portal tools to MCP tool format
            tools = []

            # Get all registered tools
            available_tools = self.tool_registry.list_tools()

            for tool_name, tool in available_tools.items():
                metadata = tool.get_metadata()

                # Convert to MCP tool schema
                mcp_tool = types.Tool(
                    name=tool_name,
                    description=metadata.get("description", ""),
                    inputSchema={
                        "type": "object",
                        "properties": metadata.get("parameters", {}),
                        "required": [
                            p for p, spec in metadata.get("parameters", {}).items()
                            if spec.get("required", False)
                        ]
                    }
                )

                tools.append(mcp_tool)

            logger.info(f"Listed {len(tools)} tools")
            return tools

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> List[types.TextContent]:
            """Call a tool"""
            if self.tool_registry is None:
                return [types.TextContent(
                    type="text",
                    text="Tool registry not available"
                )]

            try:
                # Get tool from registry
                tool = self.tool_registry.get_tool(name)

                if tool is None:
                    return [types.TextContent(
                        type="text",
                        text=f"Tool not found: {name}"
                    )]

                # Execute tool
                result = await tool.execute(arguments)

                # Convert result to text
                result_text = str(result.get("result", result))

                return [types.TextContent(
                    type="text",
                    text=result_text
                )]

            except Exception as e:
                logger.exception(f"Tool execution failed: {name}")
                return [types.TextContent(
                    type="text",
                    text=f"Error: {str(e)}"
                )]

        @self.server.list_resources()
        async def list_resources() -> List[types.Resource]:
            """List available resources"""
            # Could expose conversation history, knowledge base, etc.
            return []

        @self.server.read_resource()
        async def read_resource(uri: str) -> str:
            """Read a resource"""
            # Could read conversation history, knowledge base entries, etc.
            return f"Resource not found: {uri}"

    async def run_stdio(self):
        """Run server using stdio transport"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="portal",
                    server_version="4.3.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=None,
                        experimental_capabilities={}
                    )
                )
            )

        logger.info("MCP server stopped")


async def start_mcp_server(tool_registry: Optional[Any] = None):
    """
    Start MCP server in stdio mode.

    This allows Portal to be used as an MCP server
    by other applications.

    Args:
        tool_registry: Tool registry to expose
    """
    if not MCP_AVAILABLE:
        logger.error("MCP SDK not installed. Cannot start MCP server.")
        return

    try:
        server = MCPServer(tool_registry=tool_registry)
        logger.info("Starting MCP server...")
        await server.run_stdio()
    except Exception as e:
        logger.exception(f"MCP server failed: {e}")


# =============================================================================
# CLI INTEGRATION
# =============================================================================


def register_mcp_server_command(cli_parser):
    """
    Register MCP server command with CLI.

    Usage:
        portal mcp-server
    """
    parser = cli_parser.add_parser(
        'mcp-server',
        help='Start Portal as an MCP server'
    )

    def handle_mcp_server(args):
        """Handle mcp-server command"""
        print("Starting Portal MCP Server...")
        print("Expose Portal tools to other applications via MCP.")
        print()

        # Import here to avoid circular imports
        from portal.tools import ToolRegistry

        # Create tool registry
        tool_registry = ToolRegistry()
        tool_registry.discover_tools()

        print(f"Exposing {len(tool_registry.list_tools())} tools via MCP")
        print()

        # Run server
        asyncio.run(start_mcp_server(tool_registry=tool_registry))

    parser.set_defaults(func=handle_mcp_server)
