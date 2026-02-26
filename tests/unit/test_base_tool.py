"""
Tests for base tool framework
"""

import pytest

from portal.core.interfaces.tool import BaseTool, ToolMetadata, ToolCategory, ToolParameter


class MockTool(BaseTool):
    """Mock tool for testing"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="mock_tool",
            description="A mock tool for testing",
            category=ToolCategory.UTILITY,
            parameters=[
                ToolParameter(
                    name="required_param",
                    param_type="string",
                    description="A required parameter",
                    required=True
                ),
                ToolParameter(
                    name="optional_param",
                    param_type="int",
                    description="An optional parameter",
                    required=False,
                    default=42
                )
            ]
        )
    
    async def execute(self, parameters):
        return self._success_response(
            result="Mock execution successful",
            metadata=parameters
        )


class TestBaseTool:
    """Test base tool functionality"""
    
    def test_tool_metadata(self):
        """Test tool metadata is properly defined"""
        tool = MockTool()
        metadata = tool.metadata
        
        assert metadata.name == "mock_tool"
        assert metadata.description == "A mock tool for testing"
        assert metadata.category == ToolCategory.UTILITY
        assert len(metadata.parameters) == 2
    
    def test_parameter_validation_success(self):
        """Test parameter validation passes with valid input"""
        tool = MockTool()
        
        valid_params = {
            "required_param": "test_value",
            "optional_param": 100
        }
        
        is_valid, error = tool.validate_parameters(valid_params)
        assert is_valid
        assert error is None
    
    def test_parameter_validation_missing_required(self):
        """Test parameter validation fails when required param missing"""
        tool = MockTool()
        
        invalid_params = {
            "optional_param": 100
            # Missing required_param
        }
        
        is_valid, error = tool.validate_parameters(invalid_params)
        assert not is_valid
        assert "required_param" in error
    
    def test_parameter_validation_wrong_type(self):
        """Test parameter validation fails with wrong type"""
        tool = MockTool()
        
        invalid_params = {
            "required_param": 123,  # Should be string
        }
        
        is_valid, error = tool.validate_parameters(invalid_params)
        assert not is_valid
        assert "string" in error.lower() or "required_param" in error
    
    @pytest.mark.asyncio
    async def test_tool_execution(self):
        """Test tool execution returns proper response format"""
        tool = MockTool()
        
        params = {"required_param": "test"}
        result = await tool.execute(params)
        
        assert "success" in result
        assert result["success"] is True
        assert "result" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
