"""
MCP Registry
============
Registry of connected MCP servers.
Manages HTTP connections, health checks, and tool discovery.

Supports two transports:
  - openapi: mcpo-style OpenAPI HTTP proxy (Open WebUI path)
  - streamable-http: native MCP streamable HTTP (LibreChat path)
"""

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_RETRY_DELAYS = (1.0, 2.0, 4.0)  # seconds between attempts (3 retries total)


class MCPRegistry:
    """
    Registry of connected MCP servers.
    Manages connections, health checks, and tool discovery.
    """

    def __init__(self):
        self._servers: dict[str, dict] = {}
        transport = httpx.AsyncHTTPTransport(retries=3)
        self._client = httpx.AsyncClient(transport=transport, timeout=60.0)

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Execute an HTTP request with simple retry logic on transient errors."""
        last_exc: Exception = RuntimeError("no attempts made")
        for attempt, delay in enumerate((*_RETRY_DELAYS, None), start=1):
            try:
                resp = await self._client.request(method, url, **kwargs)
                return resp
            except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                if delay is not None:
                    logger.debug("MCP request attempt %d failed (%s); retrying in %.1fs", attempt, exc, delay)
                    await asyncio.sleep(delay)
                else:
                    logger.warning("MCP request failed after %d attempts: %s", attempt, exc)
        raise last_exc

    async def close(self) -> None:
        """Close the shared HTTP client. Call during application shutdown."""
        await self._client.aclose()

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
        url = (
            f"{server['url']}/openapi.json"
            if server["transport"] == "openapi"
            else server["url"]
        )
        try:
            resp = await self._request("GET", url, headers=headers, timeout=5.0)
            return resp.status_code < 500
        except Exception as exc:
            logger.debug("Health check failed for %r: %s", name, exc)
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
            if server["transport"] == "openapi":
                resp = await self._request("GET", f"{server['url']}/openapi.json", headers=headers, timeout=10.0)
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
                resp = await self._request("GET", f"{server['url']}/tools", headers=headers, timeout=10.0)
                if resp.status_code == 200:
                    return resp.json().get("tools", [])
                return []
        except Exception as exc:
            logger.warning("list_tools failed for %r: %s", server_name, exc)
            return []

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict,
    ) -> dict:
        """
        Execute a tool on the named MCP server.

        QUAL-3 NOTE — mcpo endpoint format (needs live verification):
        For openapi transport the URL is constructed as:
            POST {server_url}/{tool_name}
        e.g. POST http://localhost:9000/read_file

        If the mcpo instance mounts servers under a prefix (e.g.
        /filesystem/read_file), the server should be registered at
        the mounted sub-URL (http://localhost:9000/filesystem) so
        that {server_url}/{tool_name} resolves correctly.
        Verify against a live mcpo instance before enabling MCP tool
        dispatch in production (see QUAL-3 in the quality review).
        """
        server = self._servers.get(server_name)
        if not server:
            return {"error": f"Unknown MCP server: {server_name}"}

        headers = self._auth_headers(server)
        headers["Content-Type"] = "application/json"

        try:
            if server["transport"] == "openapi":
                resp = await self._request(
                    "POST", f"{server['url']}/{tool_name}", headers=headers, json=arguments
                )
            else:
                resp = await self._request(
                    "POST",
                    f"{server['url']}/call",
                    headers=headers,
                    json={"tool": tool_name, "arguments": arguments},
                )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error("call_tool %r on %r failed: %s", tool_name, server_name, exc)
            return {"error": str(exc)}

    def _auth_headers(self, server: dict) -> dict:
        headers = {}
        if server.get("api_key"):
            headers["Authorization"] = f"Bearer {server['api_key']}"
        return headers

    def list_servers(self) -> list[str]:
        return list(self._servers.keys())
