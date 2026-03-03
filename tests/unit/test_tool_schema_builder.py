"""Tests for portal.core.tool_schema_builder."""

from unittest.mock import MagicMock


class TestToolSchemaBuilder:
    """Tests for build_tool_schemas and related functions."""

    def test_build_tool_schemas_empty(self):
        """Test build_tool_schemas returns empty list when no registries provided."""
        from portal.core.tool_schema_builder import build_tool_schemas

        result = build_tool_schemas(tool_registry=None, mcp_registry=None)
        assert result == []

    def test_convert_internal_tool_with_metadata(self):
        """Test _convert_internal_tool with a tool that has metadata."""
        from portal.core.tool_schema_builder import _convert_internal_tool

        # Create a mock tool with metadata
        mock_tool = MagicMock()
        mock_metadata = MagicMock()
        mock_metadata.name = "test_tool"
        mock_metadata.description = "A test tool"
        mock_metadata.parameters = [
            {"name": "prompt", "type": "string", "description": "Input prompt", "required": True},
            {"name": "count", "type": "integer", "description": "Number of items", "default": 5},
        ]
        mock_tool.metadata = mock_metadata

        result = _convert_internal_tool(mock_tool)

        assert result is not None
        assert result["type"] == "function"
        assert result["function"]["name"] == "test_tool"
        assert result["function"]["description"] == "A test tool"
        assert "prompt" in result["function"]["parameters"]["properties"]
        assert "count" in result["function"]["parameters"]["properties"]
        assert "prompt" in result["function"]["parameters"]["required"]

    def test_convert_internal_tool_without_metadata(self):
        """Test _convert_internal_tool with a tool that has no metadata."""
        from portal.core.tool_schema_builder import _convert_internal_tool

        # Create a mock tool without metadata
        mock_tool = MagicMock()
        mock_tool.name = "simple_tool"
        mock_tool.description = "A simple tool"
        mock_tool.metadata = None
        mock_tool._metadata = None

        result = _convert_internal_tool(mock_tool)

        assert result is not None
        assert result["type"] == "function"
        assert result["function"]["name"] == "simple_tool"
        assert result["function"]["description"] == "A simple tool"

    def test_convert_internal_tool_missing_name_returns_none(self):
        """Test _convert_internal_tool returns None when tool has no name."""
        from portal.core.tool_schema_builder import _convert_internal_tool

        mock_tool = MagicMock()
        mock_tool.metadata = None
        mock_tool._metadata = None
        mock_tool.name = None
        mock_tool.__name__ = None

        result = _convert_internal_tool(mock_tool)
        assert result is None

    def test_convert_internal_tool_with_dict_metadata(self):
        """Test _convert_internal_tool with dict-style metadata."""
        from portal.core.tool_schema_builder import _convert_internal_tool

        mock_tool = MagicMock()
        mock_tool.metadata = {
            "name": "dict_tool",
            "description": "Tool with dict metadata",
            "parameters": [
                {"name": "text", "type": "string", "required": True},
            ],
        }

        result = _convert_internal_tool(mock_tool)

        assert result is not None
        assert result["function"]["name"] == "dict_tool"
        assert "text" in result["function"]["parameters"]["required"]

    def test_convert_mcp_tool(self):
        """Test _convert_mcp_tool with standard MCP tool format."""
        from portal.core.tool_schema_builder import _convert_mcp_tool

        tool = {
            "name": "mcp_generate",
            "description": "Generate something",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The prompt"}
                },
                "required": ["prompt"],
            },
        }

        result = _convert_mcp_tool("test_server", tool)

        assert result is not None
        assert result["type"] == "function"
        assert result["function"]["name"] == "mcp_generate"
        assert "prompt" in result["function"]["parameters"]["properties"]

    def test_convert_mcp_tool_missing_name_returns_none(self):
        """Test _convert_mcp_tool returns None when tool has no name."""
        from portal.core.tool_schema_builder import _convert_mcp_tool

        tool = {"description": "No name tool"}
        result = _convert_mcp_tool("server", tool)
        assert result is None

    def test_build_tool_schemas_with_mock_registry(self):
        """Test build_tool_schemas with mocked registries."""
        from portal.core.tool_schema_builder import build_tool_schemas

        # Create mock tool registry
        mock_registry = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "mock_tool"
        mock_tool.description = "Mock tool description"
        mock_tool.metadata = None
        mock_tool._metadata = None
        mock_registry.get_all_tools.return_value = [mock_tool]

        result = build_tool_schemas(tool_registry=mock_registry, mcp_registry=None)

        assert len(result) == 1
        assert result[0]["function"]["name"] == "mock_tool"


class TestToolSchemaBuilderIntegration:
    """Integration-style tests for tool schema building."""

    def test_output_format_matches_openai_spec(self):
        """Verify output format matches OpenAI function-calling spec."""
        from portal.core.tool_schema_builder import _convert_internal_tool

        mock_tool = MagicMock()
        mock_tool.metadata = {
            "name": "openai_spec_tool",
            "description": "Test tool",
            "parameters": [{"name": "arg1", "type": "string", "required": True}],
        }

        result = _convert_internal_tool(mock_tool)

        # Verify OpenAI spec format
        assert "type" in result
        assert result["type"] == "function"
        assert "function" in result
        func = result["function"]
        assert "name" in func
        assert "description" in func
        assert "parameters" in func
        assert func["parameters"]["type"] == "object"

    def test_graceful_handling_of_tools_with_missing_metadata(self):
        """Test that tools with missing/incomplete metadata are handled gracefully."""
        from portal.core.tool_schema_builder import _convert_internal_tool

        # Tool with minimal attributes
        mock_tool = MagicMock()
        mock_tool.metadata = None
        mock_tool._metadata = None
        mock_tool.name = "minimal_tool"
        mock_tool.description = None
        mock_tool.__name__ = None
        mock_tool.__doc__ = None

        result = _convert_internal_tool(mock_tool)

        # Should return a valid schema, not crash
        assert result is not None
        assert result["function"]["name"] == "minimal_tool"
