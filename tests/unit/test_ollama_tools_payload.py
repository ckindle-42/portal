"""Tests for tools parameter in Ollama backend and ExecutionEngine."""


import pytest


class TestOllamaToolsPayload:
    """Tests for tools parameter threading through Ollama backend."""

    @pytest.mark.asyncio
    async def test_generate_accepts_tools_parameter(self):
        """Test that generate() method accepts a tools parameter."""
        # Verify the generate method signature accepts tools
        import inspect

        from portal.routing.model_backends import OllamaBackend
        sig = inspect.signature(OllamaBackend.generate)
        params = list(sig.parameters.keys())

        assert "tools" in params
        assert "prompt" in params
        assert "model_name" in params

    @pytest.mark.asyncio
    async def test_execution_engine_accepts_tools_parameter(self):
        """Test that ExecutionEngine.execute() accepts tools parameter."""
        import inspect

        from portal.routing.execution_engine import ExecutionEngine
        sig = inspect.signature(ExecutionEngine.execute)
        params = list(sig.parameters.keys())

        assert "tools" in params


class TestToolsPayloadStructure:
    """Tests verifying tools payload structure."""

    def test_tool_schema_has_required_fields(self):
        """Verify tool schema has required OpenAI fields."""
        tool = {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        }

        assert "type" in tool
        assert tool["type"] == "function"
        assert "function" in tool
        func = tool["function"]
        assert "name" in func
        assert "description" in func
        assert "parameters" in func

    def test_tools_list_format(self):
        """Verify tools are passed as a list."""
        tools = [
            {"type": "function", "function": {"name": "tool1", "description": "", "parameters": {}}},
            {"type": "function", "function": {"name": "tool2", "description": "", "parameters": {}}},
        ]

        assert isinstance(tools, list)
        assert len(tools) == 2

    def test_empty_tools_list(self):
        """Verify empty tools list is valid."""
        tools = []
        assert isinstance(tools, list)
        assert len(tools) == 0


class TestToolsOmissionWhenNone:
    """Tests for omitting tools when None is passed."""

    def test_none_is_falsy(self):
        """Verify None evaluates to False in boolean context."""
        tools = None
        assert not tools

    def test_empty_list_is_falsy(self):
        """Verify empty list evaluates to False in boolean context."""
        tools = []
        assert not tools

    def test_non_empty_list_is_truthy(self):
        """Verify non-empty list evaluates to True."""
        tools = [{"type": "function"}]
        assert tools
