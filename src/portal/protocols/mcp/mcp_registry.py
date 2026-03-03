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
                    logger.debug(
                        "MCP request attempt %d failed (%s); retrying in %.1fs", attempt, exc, delay
                    )
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
        api_key: str | None = None,
    ) -> None:
        """Register an MCP server endpoint."""
        self._servers[name] = {
            "url": url.rstrip("/"),
            "transport": transport,
            "api_key": api_key,
        }
        logger.info("Registered MCP server '%s' at %s (%s)", name, url, transport)

    async def health_check(self, name: str) -> bool:
        """Return True if the named server is reachable."""
        result = await self.health_check_detailed(name)
        return result["status"] == "healthy"

    async def health_check_detailed(self, name: str) -> dict:
        """Return detailed health status for the named server.

        Returns:
            dict with keys: status ("healthy" | "degraded" | "unreachable" | "not_found"),
                           message, server_url, error_type (optional)
        """
        server = self._servers.get(name)
        if not server:
            return {
                "status": "not_found",
                "message": f"MCP server '{name}' is not registered",
                "server_name": name,
            }

        headers = self._auth_headers(server)
        url = f"{server['url']}/openapi.json" if server["transport"] == "openapi" else server["url"]

        try:
            resp = await self._request("GET", url, headers=headers, timeout=5.0)
            if resp.status_code < 500:
                return {
                    "status": "healthy",
                    "message": "Server is reachable",
                    "server_url": server["url"],
                    "status_code": resp.status_code,
                }
            elif resp.status_code >= 500:
                return {
                    "status": "unreachable",
                    "message": f"Server returned {resp.status_code}",
                    "server_url": server["url"],
                    "status_code": resp.status_code,
                    "error_type": "server_error",
                }
        except httpx.ConnectError as exc:
            return {
                "status": "unreachable",
                "message": f"Connection failed: {exc}",
                "server_url": server["url"],
                "error_type": "connection_error",
            }
        except httpx.TimeoutException as exc:
            return {
                "status": "degraded",
                "message": f"Connection timed out: {exc}",
                "server_url": server["url"],
                "error_type": "timeout",
            }
        except Exception as exc:
            return {
                "status": "unreachable",
                "message": str(exc),
                "server_url": server["url"],
                "error_type": type(exc).__name__,
            }

        return {
            "status": "unreachable",
            "message": "Unknown error",
            "server_url": server["url"],
        }

    async def health_check_all(self) -> dict[str, bool]:
        """Check all registered servers. Returns {name: is_healthy}."""
        results = {}
        for name in self._servers:
            results[name] = await self.health_check(name)
        return results

    async def health_check_all_detailed(self) -> dict[str, dict]:
        """Check all registered servers with detailed status. Returns {name: details}."""
        results = {}
        for name in self._servers:
            results[name] = await self.health_check_detailed(name)
        return results

    async def list_tools(self, server_name: str) -> list[dict]:
        """Return the tool manifest from a specific server."""
        server = self._servers.get(server_name)
        if not server:
            return []

        headers = self._auth_headers(server)
        try:
            if server["transport"] == "openapi":
                resp = await self._request(
                    "GET", f"{server['url']}/openapi.json", headers=headers, timeout=10.0
                )
                resp.raise_for_status()
                spec = resp.json()
                tools = []
                for path, methods in spec.get("paths", {}).items():
                    for method, details in methods.items():
                        if method in ("get", "post"):
                            tools.append(
                                {
                                    "name": details.get("operationId", path.strip("/")),
                                    "description": details.get("summary", ""),
                                    "path": path,
                                    "method": method,
                                }
                            )
                return tools
            else:
                resp = await self._request(
                    "GET", f"{server['url']}/tools", headers=headers, timeout=10.0
                )
                if resp.status_code == 200:
                    return resp.json().get("tools", [])
                return []
        except Exception as exc:
            logger.warning("list_tools failed for %r: %s", server_name, exc)
            return []

    def list_tools_sync(self, server_name: str) -> list[dict]:
        """Synchronous wrapper for list_tools (for use in non-async contexts)."""
        return asyncio.get_event_loop().run_until_complete(self.list_tools(server_name))

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict,
    ) -> dict:
        """
        Execute a tool on the named MCP server.

        For openapi transport the URL is constructed as:
            POST {server_url}/{tool_name}
        e.g. POST http://localhost:9000/read_file
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
