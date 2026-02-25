"""
MCP Registry
============
Registry of connected MCP servers.
Manages HTTP connections, health checks, and tool discovery.

Supports two transports:
  - openapi: mcpo-style OpenAPI HTTP proxy (Open WebUI path)
  - streamable-http: native MCP streamable HTTP (LibreChat path)
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class MCPRegistry:
    """
    Registry of connected MCP servers.
    Manages connections, health checks, and tool discovery.
    """

    def __init__(self):
        self._servers: dict[str, dict] = {}

    async def register(
        self,
        name: str,
        url: str,
        transport: str = "openapi",  # openapi | streamable-http
        api_key: Optional[str] = None,
    ) -> None:
        """Register an MCP server endpoint."""
        self._servers[name] = {
            "url": url.rstrip("/"),
            "transport": transport,
            "api_key": api_key,
        }
        logger.info(f"Registered MCP server '{name}' at {url} ({transport})")

    async def health_check(self, name: str) -> bool:
        """Return True if the named server is reachable."""
        server = self._servers.get(name)
        if not server:
            return False

        headers = self._auth_headers(server)
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                if server["transport"] == "openapi":
                    resp = await client.get(f"{server['url']}/openapi.json", headers=headers)
                else:
                    resp = await client.get(f"{server['url']}", headers=headers)
                return resp.status_code < 500
        except Exception as e:
            logger.debug(f"Health check failed for '{name}': {e}")
            return False

    async def health_check_all(self) -> dict[str, bool]:
        """Check all registered servers. Returns {name: is_healthy}."""
        results = {}
        for name in self._servers:
            results[name] = await self.health_check(name)
        return results

    async def list_tools(self, server_name: str) -> list[dict]:
        """Return the tool manifest from a specific server."""
        server = self._servers.get(server_name)
        if not server:
            return []

        headers = self._auth_headers(server)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if server["transport"] == "openapi":
                    resp = await client.get(f"{server['url']}/openapi.json", headers=headers)
                    resp.raise_for_status()
                    spec = resp.json()
                    tools = []
                    for path, methods in spec.get("paths", {}).items():
                        for method, details in methods.items():
                            if method in ("get", "post"):
                                tools.append({
                                    "name": details.get("operationId", path.strip("/")),
                                    "description": details.get("summary", ""),
                                    "path": path,
                                    "method": method,
                                })
                    return tools
                else:
                    # streamable-http: query /tools endpoint
                    resp = await client.get(f"{server['url']}/tools", headers=headers)
                    if resp.status_code == 200:
                        return resp.json().get("tools", [])
                    return []
        except Exception as e:
            logger.warning(f"list_tools failed for '{server_name}': {e}")
            return []

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict,
    ) -> dict:
        """Execute a tool on the named MCP server."""
        server = self._servers.get(server_name)
        if not server:
            return {"error": f"Unknown MCP server: {server_name}"}

        headers = self._auth_headers(server)
        headers["Content-Type"] = "application/json"

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                if server["transport"] == "openapi":
                    resp = await client.post(
                        f"{server['url']}/{tool_name}",
                        headers=headers,
                        json=arguments,
                    )
                else:
                    resp = await client.post(
                        f"{server['url']}/call",
                        headers=headers,
                        json={"tool": tool_name, "arguments": arguments},
                    )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"call_tool '{tool_name}' on '{server_name}' failed: {e}")
            return {"error": str(e)}

    def _auth_headers(self, server: dict) -> dict:
        headers = {}
        if server.get("api_key"):
            headers["Authorization"] = f"Bearer {server['api_key']}"
        return headers

    def list_servers(self) -> list[str]:
        return list(self._servers.keys())
