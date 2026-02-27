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
    async_capable: bool = True
    parameters: list[ToolParameter] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)


class BaseTool(ABC):
    """
    Abstract base class for all tools

    Subclasses must implement:
    - _get_metadata(): Return tool metadata
    - execute(parameters): Execute the tool
    """

    def __init__(self) -> None:
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

    _TYPE_VALIDATORS: dict[str, tuple[type, ...]] = {
        "string": (str,),
        "int": (int,),
        "float": (int, float),
        "bool": (bool,),
        "list": (list,),
    }
    _TYPE_MESSAGES: dict[str, str] = {
        "string": "must be a string",
        "int": "must be an integer",
        "float": "must be a number",
        "bool": "must be a boolean",
        "list": "must be a list",
    }

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
                expected_types = self._TYPE_VALIDATORS.get(param.param_type)
                if expected_types and not isinstance(value, expected_types):
                    msg = self._TYPE_MESSAGES.get(
                        param.param_type, f"must be of type {param.param_type}"
                    )
                    return False, f"Parameter {param.name} {msg}"

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
