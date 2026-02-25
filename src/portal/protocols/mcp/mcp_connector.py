"""
MCP Connector Tool - Model Context Protocol Integration
Connects to 400+ services via MCP standard protocol

This tool enables the Telegram agent to connect to external services
using the Model Context Protocol (MCP) standard adopted by major AI providers.
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
from pathlib import Path
import sys
import json

# Add parent directory to path for base_tool import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from base_tool import BaseTool, ToolMetadata, ToolCategory

logger = logging.getLogger(__name__)

# Try to import MCP SDK
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP SDK not installed. Run: pip install mcp==0.9.0")


class MCPConnectorTool(BaseTool):
    """Connect to and interact with MCP servers"""
    
    def __init__(self):
        super().__init__()
        self.active_sessions: Dict[str, ClientSession] = {}
        self.server_configs = self._load_server_configs()
        self.server_tools_cache: Dict[str, List[Dict]] = {}
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="mcp_connect",
            description="Connect to external services via Model Context Protocol (400+ services available)",
            category=ToolCategory.WEB,
            requires_confirmation=True,
            parameters={
                "action": {
                    "type": "string",
                    "required": True,
                    "options": ["connect", "list_servers", "list_tools", "call_tool", "disconnect", "disconnect_all"],
                    "description": "Action to perform"
                },
                "server_name": {
                    "type": "string",
                    "required": False,
                    "description": "MCP server name (e.g., 'filesystem', 'github', 'gdrive')"
                },
                "tool_name": {
                    "type": "string",
                    "required": False,
                    "description": "MCP tool to call on the server"
                },
                "arguments": {
                    "type": "object",
                    "required": False,
                    "description": "Tool arguments (JSON object)"
                }
            }
        )
    
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute MCP operation"""
        
        if not MCP_AVAILABLE:
            return self._error_response(
                "MCP SDK not installed. Install with: pip install mcp==0.9.0"
            )
        
        valid, error = await self.validate_parameters(parameters)
        if not valid:
            return self._error_response(error)
        
        try:
            action = parameters.get("action")
            
            if action == "connect":
                return await self._connect_server(parameters)
            elif action == "list_servers":
                return await self._list_servers()
            elif action == "list_tools":
                return await self._list_tools(parameters)
            elif action == "call_tool":
                return await self._call_tool(parameters)
            elif action == "disconnect":
                return await self._disconnect_server(parameters)
            elif action == "disconnect_all":
                return await self._disconnect_all()
            else:
                return self._error_response(f"Unknown action: {action}")
        
        except Exception as e:
            logger.exception("MCP operation failed")
            return self._error_response(f"MCP operation failed: {str(e)}")
    
    async def validate_parameters(self, parameters: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate parameters"""
        if "action" not in parameters:
            return False, "Missing required parameter: action"
        
        action = parameters.get("action")
        
        # Actions that require server_name
        if action in ["connect", "list_tools", "call_tool", "disconnect"]:
            if "server_name" not in parameters:
                return False, f"{action} action requires 'server_name' parameter"
        
        # call_tool requires tool_name
        if action == "call_tool":
            if "tool_name" not in parameters:
                return False, "call_tool action requires 'tool_name' parameter"
        
        return True, None
    
    def _load_server_configs(self) -> Dict[str, Dict]:
        """Load MCP server configurations
        
        These are the default MCP servers. Users can add custom servers
        via configuration file or environment variables.
        """
        return {
            # No authentication required
            "filesystem": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", str(Path.home())],
                "description": "Local filesystem access",
                "auth_required": False
            },
            
            # Requires GitHub token
            "github": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "description": "GitHub repositories and issues",
                "auth_required": True,
                "env_vars": ["GITHUB_TOKEN"]
            },
            
            # Requires Google OAuth
            "gdrive": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-gdrive"],
                "description": "Google Drive files and folders",
                "auth_required": True,
                "env_vars": ["GDRIVE_CREDENTIALS_PATH"]
            },
            
            # Requires Gmail OAuth
            "gmail": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-gmail"],
                "description": "Gmail email management",
                "auth_required": True,
                "env_vars": ["GMAIL_CREDENTIALS_PATH"]
            },
            
            # Requires Slack token
            "slack": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-slack"],
                "description": "Slack workspace integration",
                "auth_required": True,
                "env_vars": ["SLACK_TOKEN"]
            },
            
            # Requires Notion token
            "notion": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-notion"],
                "description": "Notion workspace integration",
                "auth_required": True,
                "env_vars": ["NOTION_TOKEN"]
            },
            
            # Requires Google OAuth
            "calendar": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-google-calendar"],
                "description": "Google Calendar integration",
                "auth_required": True,
                "env_vars": ["CALENDAR_CREDENTIALS_PATH"]
            },
            
            # Requires PostgreSQL connection
            "postgres": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-postgres"],
                "description": "PostgreSQL database",
                "auth_required": True,
                "env_vars": ["POSTGRES_CONNECTION_STRING"]
            },
        }
    
    async def _connect_server(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Connect to MCP server"""
        server_name = parameters.get("server_name")
        
        if server_name in self.active_sessions:
            return self._error_response(f"Already connected to {server_name}")
        
        if server_name not in self.server_configs:
            return self._error_response(
                f"Unknown server: {server_name}. Use 'list_servers' action to see available servers."
            )
        
        config = self.server_configs[server_name]
        
        # Check authentication requirements
        if config.get("auth_required", False):
            env_vars = config.get("env_vars", [])
            missing_vars = [var for var in env_vars if var not in os.environ]
            if missing_vars:
                return self._error_response(
                    f"Missing required environment variables for {server_name}: {', '.join(missing_vars)}"
                )
        
        try:
            # Security: Create safe environment with only necessary variables
            # to prevent leaking sensitive tokens/keys to MCP subprocesses
            safe_env = {
                # System essentials
                'PATH': os.environ.get('PATH', ''),
                'HOME': os.environ.get('HOME', ''),
                'LANG': os.environ.get('LANG', 'en_US.UTF-8'),
                'USER': os.environ.get('USER', ''),
                'SHELL': os.environ.get('SHELL', ''),
            }

            # Add only specific required environment variables for this server
            for var_name in config.get("env_vars", []):
                if var_name in os.environ:
                    safe_env[var_name] = os.environ[var_name]
                    logger.info(f"Added {var_name} to MCP environment for {server_name}")

            # Create server parameters
            server_params = StdioServerParameters(
                command=config["command"],
                args=config["args"],
                env=safe_env  # Pass sanitized environment
            )
            
            # Connect to server
            logger.info(f"Connecting to MCP server: {server_name}")
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize session
                    await session.initialize()
                    
                    # Store session (in production, handle session persistence)
                    self.active_sessions[server_name] = session
                    
                    # Get available tools
                    response = await session.list_tools()
                    tool_count = len(response.tools)
                    
                    # Cache tools
                    self.server_tools_cache[server_name] = [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        }
                        for tool in response.tools
                    ]
                    
                    logger.info(f"Connected to {server_name} with {tool_count} tools")
                    
                    return self._success_response(
                        result=f"Successfully connected to {server_name}",
                        metadata={
                            "server": server_name,
                            "description": config["description"],
                            "tools_available": tool_count,
                            "auth_required": config.get("auth_required", False)
                        }
                    )
        
        except Exception as e:
            logger.exception(f"Failed to connect to {server_name}")
            return self._error_response(f"Connection failed: {str(e)}")
    
    async def _list_servers(self) -> Dict[str, Any]:
        """List available MCP servers"""
        servers = []
        
        for name, config in self.server_configs.items():
            servers.append({
                "name": name,
                "description": config["description"],
                "connected": name in self.active_sessions,
                "auth_required": config.get("auth_required", False),
                "tools_count": len(self.server_tools_cache.get(name, []))
            })
        
        # Sort: connected first, then alphabetically
        servers.sort(key=lambda x: (not x["connected"], x["name"]))
        
        return self._success_response(
            result=servers,
            metadata={
                "total_servers": len(servers),
                "connected_servers": len(self.active_sessions)
            }
        )
    
    async def _list_tools(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """List tools available on a server"""
        server_name = parameters.get("server_name")
        
        if server_name not in self.active_sessions:
            return self._error_response(
                f"Not connected to {server_name}. Use 'connect' action first."
            )
        
        # Check cache first
        if server_name in self.server_tools_cache:
            tools = self.server_tools_cache[server_name]
        else:
            # Query server
            session = self.active_sessions[server_name]
            try:
                response = await session.list_tools()
                tools = [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": tool.inputSchema
                    }
                    for tool in response.tools
                ]
                self.server_tools_cache[server_name] = tools
            except Exception as e:
                logger.exception(f"Failed to list tools for {server_name}")
                return self._error_response(f"Failed to list tools: {str(e)}")
        
        return self._success_response(
            result=tools,
            metadata={
                "server": server_name,
                "tool_count": len(tools)
            }
        )
    
    async def _call_tool(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on an MCP server"""
        server_name = parameters.get("server_name")
        tool_name = parameters.get("tool_name")
        arguments = parameters.get("arguments", {})
        
        if server_name not in self.active_sessions:
            return self._error_response(
                f"Not connected to {server_name}. Use 'connect' action first."
            )
        
        session = self.active_sessions[server_name]
        
        try:
            logger.info(f"Calling {tool_name} on {server_name} with args: {arguments}")
            
            # Call the tool
            result = await session.call_tool(tool_name, arguments=arguments)
            
            # Parse result
            tool_result = {
                "content": result.content if hasattr(result, 'content') else str(result),
                "isError": result.isError if hasattr(result, 'isError') else False
            }
            
            if tool_result["isError"]:
                logger.error(f"Tool {tool_name} returned error: {tool_result['content']}")
                return self._error_response(f"Tool execution failed: {tool_result['content']}")
            
            return self._success_response(
                result=tool_result["content"],
                metadata={
                    "server": server_name,
                    "tool": tool_name,
                    "arguments": arguments
                }
            )
        
        except Exception as e:
            logger.exception(f"Failed to call {tool_name} on {server_name}")
            return self._error_response(f"Tool execution failed: {str(e)}")
    
    async def _disconnect_server(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Disconnect from an MCP server"""
        server_name = parameters.get("server_name")
        
        if server_name not in self.active_sessions:
            return self._error_response(f"Not connected to {server_name}")
        
        try:
            # Close session
            session = self.active_sessions.pop(server_name)
            # Note: Session cleanup happens automatically when context manager exits
            
            logger.info(f"Disconnected from {server_name}")
            
            return self._success_response(
                result=f"Disconnected from {server_name}",
                metadata={"server": server_name}
            )
        
        except Exception as e:
            logger.exception(f"Failed to disconnect from {server_name}")
            return self._error_response(f"Disconnect failed: {str(e)}")
    
    async def _disconnect_all(self) -> Dict[str, Any]:
        """Disconnect from all MCP servers"""
        disconnected = []
        errors = []
        
        for server_name in list(self.active_sessions.keys()):
            try:
                self.active_sessions.pop(server_name)
                disconnected.append(server_name)
                logger.info(f"Disconnected from {server_name}")
            except Exception as e:
                errors.append(f"{server_name}: {str(e)}")
                logger.exception(f"Failed to disconnect from {server_name}")
        
        if errors:
            return self._error_response(
                f"Disconnected from {len(disconnected)} servers, {len(errors)} failures: {'; '.join(errors)}"
            )
        
        return self._success_response(
            result=f"Disconnected from all {len(disconnected)} servers",
            metadata={"disconnected": disconnected}
        )
    
    def cleanup(self):
        """Cleanup on shutdown"""
        # Close all active sessions
        for server_name in list(self.active_sessions.keys()):
            try:
                self.active_sessions.pop(server_name)
                logger.info(f"Cleaned up connection to {server_name}")
            except Exception as e:
                logger.exception(f"Failed to cleanup {server_name}")


# For testing
async def test_mcp():
    """Test MCP connector"""
    print("="*60)
    print("MCP Connector Test")
    print("="*60)
    
    tool = MCPConnectorTool()
    
    # Test 1: List available servers
    print("\n🔍 Test 1: List MCP servers")
    result = await tool.execute({"action": "list_servers"})
    
    if result["success"]:
        print(f"✅ Found {result['metadata']['total_servers']} servers:")
        for server in result['result'][:5]:  # Show first 5
            status = "🟢 Connected" if server['connected'] else "⚪ Available"
            auth = "🔒 Auth Required" if server['auth_required'] else "🔓 No Auth"
            print(f"   {status} {server['name']}: {server['description']} ({auth})")
    else:
        print(f"❌ Failed: {result['error']}")
    
    # Test 2: Connect to filesystem server (no auth required)
    print("\n🔍 Test 2: Connect to filesystem server")
    result = await tool.execute({
        "action": "connect",
        "server_name": "filesystem"
    })
    
    if result["success"]:
        print(f"✅ {result['result']}")
        print(f"   Tools available: {result['metadata']['tools_available']}")
    else:
        print(f"❌ Failed: {result['error']}")
        return  # Can't proceed without connection
    
    # Test 3: List tools on server
    print("\n🔍 Test 3: List filesystem tools")
    result = await tool.execute({
        "action": "list_tools",
        "server_name": "filesystem"
    })
    
    if result["success"]:
        print(f"✅ Found {result['metadata']['tool_count']} tools:")
        for tool_info in result['result'][:5]:  # Show first 5
            print(f"   - {tool_info['name']}: {tool_info['description']}")
    else:
        print(f"❌ Failed: {result['error']}")
    
    # Test 4: Call a tool (read directory)
    print("\n🔍 Test 4: Call filesystem tool (read directory)")
    result = await tool.execute({
        "action": "call_tool",
        "server_name": "filesystem",
        "tool_name": "read_directory",
        "arguments": {"path": str(Path.home())}
    })
    
    if result["success"]:
        print(f"✅ Tool executed successfully")
        # Don't print full result (could be large)
        print(f"   Result type: {type(result['result'])}")
    else:
        print(f"❌ Failed: {result['error']}")
    
    # Cleanup
    await tool._disconnect_all()
    
    print("\n" + "="*60)
    print("✅ MCP test complete!")
    print("="*60)


if __name__ == "__main__":
    import os
    asyncio.run(test_mcp())
