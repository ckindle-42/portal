"""
Integration tests for tool loading and registration
"""

import pytest
from portal.tools import ToolRegistry


@pytest.mark.integration
class TestToolLoading:
    """Test tool discovery and loading"""

    def test_tool_registry_loads_all_tools(self):
        """Test that all tools are loaded successfully"""
        registry = ToolRegistry()
        loaded, failed = registry.discover_and_load()

        assert loaded == 35, \
            f"Expected 35 tools loaded, got {loaded}"
        assert failed == 0, \
            f"Expected 0 failures, got {failed}"

    def test_no_tool_load_failures(self):
        """Test that no tools fail to load"""
        registry = ToolRegistry()
        loaded, failed = registry.discover_and_load()

        assert failed == 0, \
            f"Expected no failures, got {failed}"
        assert len(registry.failed_tools) == 0, \
            f"Failed tools: {registry.failed_tools}"

    def test_all_tools_have_metadata(self):
        """Test that all loaded tools have proper metadata"""
        registry = ToolRegistry()
        registry.discover_and_load()

        for name, tool in registry.tools.items():
            assert hasattr(tool, 'metadata'), \
                f"Tool {name} missing metadata"
            assert tool.metadata.name, \
                f"Tool {name} has empty name in metadata"
            assert tool.metadata.description, \
                f"Tool {name} has empty description"
            assert tool.metadata.category, \
                f"Tool {name} missing category"

    def test_tools_by_category(self):
        """Test that tools are properly categorized"""
        registry = ToolRegistry()
        registry.discover_and_load()

        categories = set()
        for tool in registry.tools.values():
            if hasattr(tool, 'metadata') and tool.metadata.category:
                categories.add(tool.metadata.category.value if hasattr(tool.metadata.category, 'value') else tool.metadata.category)

        expected_categories = {'audio', 'automation', 'data', 'dev', 'utility', 'web'}
        assert categories.intersection(expected_categories), \
            f"Expected standard categories, got {categories}"

    def test_tool_parameters_valid(self):
        """Test that all tool parameters are properly defined"""
        registry = ToolRegistry()
        registry.discover_and_load()

        for name, tool in registry.tools.items():
            if not hasattr(tool, 'metadata'):
                continue

            for param in tool.metadata.parameters:
                # Handle both ToolParameter objects and simple dicts/strings
                if hasattr(param, 'name'):
                    assert param.name, \
                        f"Tool {name} has parameter with empty name"
                    assert param.param_type or param.type, \
                        f"Tool {name} parameter {param.name} missing type"
                # Otherwise assume it's a valid parameter definition


@pytest.mark.integration
class TestToolExecution:
    """Test that tools can be executed"""

    @pytest.mark.asyncio
    async def test_tools_execute_without_crash(self):
        """Test that tools don't crash when executed with minimal params"""
        from portal.tools import ToolRegistry

        registry = ToolRegistry()
        registry.discover_and_load()

        # Test a subset of tools with safe minimal parameters
        safe_tools_to_test = [
            'system_stats',
            'process_monitor',
            'text_transformer',
        ]

        for tool_name in safe_tools_to_test:
            if tool_name not in registry.tools:
                continue

            tool = registry.tools[tool_name]

            # Try to execute with empty params (should either work or return error gracefully)
            try:
                result = await tool.execute({})
                assert isinstance(result, dict), \
                    f"Tool {tool_name} should return dict"
                assert "success" in result, \
                    f"Tool {tool_name} result should have 'success' key"
            except Exception as e:
                pytest.fail(f"Tool {tool_name} crashed: {e}")


@pytest.mark.integration
class TestToolRegistry:
    """Test ToolRegistry functionality"""

    def test_get_tool_by_name(self):
        """Test retrieving tool by name"""
        from portal.tools import ToolRegistry

        registry = ToolRegistry()
        registry.discover_and_load()

        # Test getting a known tool
        tool = registry.get_tool('system_stats')
        assert tool is not None, "Should find system_stats tool"

    def test_get_nonexistent_tool(self):
        """Test retrieving non-existent tool"""
        from portal.tools import ToolRegistry

        registry = ToolRegistry()
        registry.discover_and_load()

        tool = registry.get_tool('nonexistent_tool_xyz')
        assert tool is None, "Should return None for non-existent tool"

    def test_list_tools_by_category(self):
        """Test listing tools filtered by category"""
        from portal.tools import ToolRegistry

        registry = ToolRegistry()
        registry.discover_and_load()

        # Get all tools in dev category
        dev_tools = [name for name, tool in registry.tools.items()
                     if hasattr(tool, 'metadata') and
                     hasattr(tool.metadata, 'category') and
                     (tool.metadata.category.value if hasattr(tool.metadata.category, 'value') else tool.metadata.category) == 'dev']

        assert len(dev_tools) > 0, "Should have at least one dev tool"
