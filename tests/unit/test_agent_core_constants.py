"""Verify AgentCore module-level constants and configuration."""

from portal.core.agent_core import DEFAULT_MCP_TOOL_MAX_ROUNDS, HIGH_RISK_TOOLS


class TestAgentCoreConstants:
    def test_default_mcp_rounds_is_reasonable(self) -> None:
        assert isinstance(DEFAULT_MCP_TOOL_MAX_ROUNDS, int)
        assert 1 <= DEFAULT_MCP_TOOL_MAX_ROUNDS <= 10

    def test_high_risk_tools_is_frozenset(self) -> None:
        assert isinstance(HIGH_RISK_TOOLS, frozenset)

    def test_high_risk_tools_contains_expected(self) -> None:
        assert "bash" in HIGH_RISK_TOOLS
        assert "filesystem_write" in HIGH_RISK_TOOLS
        assert "web_fetch" in HIGH_RISK_TOOLS

    def test_high_risk_tools_is_immutable(self) -> None:
        try:
            HIGH_RISK_TOOLS.add("evil")  # type: ignore[attr-defined]
            assert False, "frozenset should not allow add"
        except AttributeError:
            pass
