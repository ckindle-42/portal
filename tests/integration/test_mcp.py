"""
Integration test for MCP protocol layer.
Requires: mcpo running at localhost:9000.
"""

import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_registry_health():
    from portal.protocols.mcp.mcp_registry import MCPRegistry

    registry = MCPRegistry()
    await registry.register(
        "core",
        url="http://localhost:9000",
        transport="openapi",
    )

    healthy = await registry.health_check("core")
    assert healthy, "mcpo at :9000 should be reachable"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_mcp_tool_list():
    from portal.protocols.mcp.mcp_registry import MCPRegistry

    registry = MCPRegistry()
    await registry.register("core", url="http://localhost:9000", transport="openapi")

    tools = await registry.list_tools("core")
    tool_names = [t.get("name", "") for t in tools]

    # These tools must be present
    for expected in ["read_file", "write_file", "search_nodes", "read_query"]:
        assert any(expected in name for name in tool_names), (
            f"Expected MCP tool '{expected}' not found in: {tool_names}"
        )
