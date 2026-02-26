"""
Base Tool - Abstract base class for all tools
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Tool categories"""
    UTILITY = "utility"
    DATA = "data"
    WEB = "web"
    AUDIO = "audio"
    DEV = "dev"
    AUTOMATION = "automation"
    KNOWLEDGE = "knowledge"


@dataclass
class ToolParameter:
    """Tool parameter definition"""
    name: str
    param_type: str  # string, int, float, bool, list
    description: str
    required: bool = True
    default: Any = None


@dataclass
class ToolMetadata:
    """Tool metadata"""
    name: str
    description: str
    category: ToolCategory
    version: str = "1.0.0"
    requires_confirmation: bool = False
    parameters: list[ToolParameter] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


class BaseTool(ABC):
    """
    Abstract base class for all tools

    Subclasses must implement:
    - _get_metadata(): Return tool metadata
    - execute(parameters): Execute the tool
    """

    def __init__(self):
        self._metadata: ToolMetadata | None = None

    @property
    def metadata(self) -> ToolMetadata:
        """Get tool metadata (cached)"""
        if self._metadata is None:
            self._metadata = self._get_metadata()
        return self._metadata

    @abstractmethod
    def _get_metadata(self) -> ToolMetadata:
        """Return tool metadata - must be implemented by subclasses"""
        pass

    @abstractmethod
    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the tool

        Args:
            parameters: Dictionary of parameter name -> value

        Returns:
            Dictionary with 'success' (bool) and 'result' or 'error'
        """
        pass

    def validate_parameters(self, parameters: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate parameters against metadata

        Returns:
            (is_valid, error_message)
        """
        for param in self.metadata.parameters:
            if param.required and param.name not in parameters:
                return False, f"Missing required parameter: {param.name}"

            if param.name in parameters:
                value = parameters[param.name]

                # Type validation
                if param.param_type == "string" and not isinstance(value, str):
                    return False, f"Parameter {param.name} must be a string"
                elif param.param_type == "int" and not isinstance(value, int):
                    return False, f"Parameter {param.name} must be an integer"
                elif param.param_type == "float" and not isinstance(value, (int, float)):
                    return False, f"Parameter {param.name} must be a number"
                elif param.param_type == "bool" and not isinstance(value, bool):
                    return False, f"Parameter {param.name} must be a boolean"
                elif param.param_type == "list" and not isinstance(value, list):
                    return False, f"Parameter {param.name} must be a list"

        return True, None

    def _success_response(self, result: Any = None, **kwargs) -> dict[str, Any]:
        """Create success response"""
        response = {"success": True, "result": result}
        response.update(kwargs)
        return response

    def _error_response(self, error: str, **kwargs) -> dict[str, Any]:
        """Create error response"""
        response = {"success": False, "error": error}
        response.update(kwargs)
        return response

    async def safe_execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """
        Execute with validation and error handling
        """
        # Validate parameters
        valid, error = self.validate_parameters(parameters)
        if not valid:
            return self._error_response(error)

        # Apply defaults
        for param in self.metadata.parameters:
            if param.name not in parameters and param.default is not None:
                parameters[param.name] = param.default

        # Execute
        try:
            return await self.execute(parameters)
        except Exception as e:
            logger.error(f"Tool {self.metadata.name} execution error: {e}")
            return self._error_response(str(e))
