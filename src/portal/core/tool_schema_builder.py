"""Build OpenAI-compatible tool schemas from ToolRegistry and MCPRegistry."""

import logging
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from portal.protocols.mcp.mcp_registry import MCPRegistry
    from portal.tools import ToolRegistry


def build_tool_schemas(
    tool_registry: "ToolRegistry | None" = None,
    mcp_registry: "MCPRegistry | None" = None,
) -> list[dict[str, Any]]:
    """
    Build a combined list of tool definitions in OpenAI function-calling format.

    Returns a list of dicts like:
    [
        {
            "type": "function",
            "function": {
                "name": "generate_image",
                "description": "Generate an image using FLUX via ComfyUI",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Image description"},
                        "width": {"type": "integer", "description": "Width in pixels", "default": 1024},
                    },
                    "required": ["prompt"],
                },
            },
        }
    ]
    """
    tools: list[dict[str, Any]] = []

    # Internal tools from ToolRegistry
    if tool_registry:
        try:
            internal_tools = _get_internal_tools(tool_registry)
            for tool_schema in internal_tools:
                if tool_schema:
                    tools.append(tool_schema)
        except Exception as e:
            logger.warning("Failed to get internal tools: %s", e)

    # MCP server tools (discovered at startup via list_tools)
    # These are cached after first discovery - synchronous access to cached data
    if mcp_registry:
        try:
            mcp_tools = _get_cached_mcp_tools(mcp_registry)
            tools.extend(mcp_tools)
        except Exception as e:
            logger.warning("Failed to get MCP tools: %s", e)

    return tools


def _get_internal_tools(tool_registry: "ToolRegistry") -> list[dict[str, Any] | None]:
    """Convert internal tools from ToolRegistry to OpenAI function schema."""
    schemas: list[dict[str, Any] | None] = []

    try:
        # Get all tools from the registry
        all_tools = tool_registry.get_all_tools()
        for tool in all_tools:
            schema = _convert_internal_tool(tool)
            schemas.append(schema)
    except Exception as e:
        logger.warning("Failed to get all tools from registry: %s", e)

    return schemas


def _convert_internal_tool(tool) -> dict[str, Any] | None:
    """Convert a BaseTool instance to OpenAI function schema."""
    try:
        # Try to get metadata from the tool
        metadata = getattr(tool, "metadata", None)
        if metadata is None:
            # Some tools might use a different pattern
            metadata = getattr(tool, "_metadata", None)

        if metadata is None:
            # Try to get name/description directly from tool
            tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", None)
            if not tool_name:
                return None

            # Build minimal schema from tool attributes
            tool_description = (
                getattr(tool, "description", "") or getattr(tool, "__doc__", "") or ""
            )

            return {
                "type": "function",
                "function": {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            }

        # Extract metadata fields
        metadata_dict = dict(metadata) if hasattr(metadata, "items") else {}
        tool_name = metadata_dict.get("name") or getattr(metadata, "name", None)
        tool_description = metadata_dict.get("description") or getattr(metadata, "description", "")

        if not tool_name:
            return None

        # Build parameters from metadata
        properties: dict[str, Any] = {}
        required: list[str] = []

        params = metadata_dict.get("parameters") or getattr(metadata, "parameters", [])
        if isinstance(params, list):
            for param in params:
                if isinstance(param, dict):
                    prop: dict[str, Any] = {"type": param.get("type", "string")}
                    if "description" in param:
                        prop["description"] = param["description"]
                    if "default" in param and param["default"] is not None:
                        prop["default"] = param["default"]
                    properties[param.get("name", "")] = prop
                    if param.get("required", False):
                        required.append(param.get("name", ""))
                elif hasattr(param, "name"):
                    # Pydantic-style parameter
                    prop = {"type": getattr(param, "type", "string")}
                    if hasattr(param, "description"):
                        prop["description"] = param.description
                    if hasattr(param, "default") and param.default is not None:
                        prop["default"] = param.default
                    properties[param.name] = prop
                    if getattr(param, "required", True):
                        required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": tool_description or "",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
    except Exception as e:
        tool_name = getattr(getattr(tool, "metadata", {}), "name", None) or getattr(
            tool, "name", "?"
        )
        logger.warning("Failed to convert tool %s: %s", tool_name, e)
        return None


def _get_cached_mcp_tools(mcp_registry: "MCPRegistry") -> list[dict[str, Any]]:
    """Get tool schemas from registered MCP servers (from cache)."""
    tools: list[dict[str, Any]] = []

    try:
        # Get list of servers
        servers = mcp_registry.list_servers()
        for server_name in servers:
            # Try to get cached tools for this server
            try:
                server_tools = mcp_registry.list_tools(server_name)
                for tool in server_tools:
                    schema = _convert_mcp_tool(server_name, tool)
                    if schema:
                        tools.append(schema)
            except Exception as e:
                logger.debug("Could not get tools for MCP server %s: %s", server_name, e)
                continue
    except Exception as e:
        logger.warning("Failed to list MCP servers: %s", e)

    return tools


def _convert_mcp_tool(server_name: str, tool: dict[str, Any]) -> dict[str, Any] | None:
    """Convert an MCP server tool manifest to OpenAI function schema."""
    try:
        # MCP tools come in various formats - try to normalize
        name = tool.get("name") or tool.get("function", {}).get("name")
        description = tool.get("description") or tool.get("function", {}).get("description", "")
        params = tool.get("parameters") or tool.get("function", {}).get("parameters", {})

        if not name:
            return None

        # Normalize parameters to OpenAI format
        properties: dict[str, Any] = {}
        required: list[str] = []

        if isinstance(params, dict):
            properties = params.get("properties", {})
            required = params.get("required", [])
        elif isinstance(params, list):
            # Some MCP servers send parameters as a list
            for param in params:
                if isinstance(param, dict):
                    prop = {"type": param.get("type", "string")}
                    if "description" in param:
                        prop["description"] = param["description"]
                    properties[param.get("name", "")] = prop

        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description or f"Tool from {server_name}",
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
    except Exception as e:
        logger.debug("Failed to convert MCP tool: %s", e)
        return None


async def discover_mcp_tool_schemas(mcp_registry: "MCPRegistry") -> list[dict[str, Any]]:
    """
    Async discovery of MCP tool schemas - calls list_tools on each server.

    This should be called during startup to populate the cache.
    For runtime, use build_tool_schemas() which reads from cache.
    """
    tools: list[dict[str, Any]] = []

    try:
        servers = mcp_registry.list_servers()
        for server_name in servers:
            try:
                server_tools = await mcp_registry.list_tools(server_name)
                for tool in server_tools:
                    schema = _convert_mcp_tool(server_name, tool)
                    if schema:
                        tools.append(schema)
            except Exception as e:
                logger.debug("Could not discover tools for MCP server %s: %s", server_name, e)
    except Exception as e:
        logger.warning("Failed to discover MCP tools: %s", e)

    return tools

