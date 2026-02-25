"""
Base Tool - Abstract base class for all tools
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

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
    parameters: List[ToolParameter] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)


class BaseTool(ABC):
    """
    Abstract base class for all tools
    
    Subclasses must implement:
    - _get_metadata(): Return tool metadata
    - execute(parameters): Execute the tool
    """
    
    def __init__(self):
        self._metadata: Optional[ToolMetadata] = None
    
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
    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the tool
        
        Args:
            parameters: Dictionary of parameter name -> value
            
        Returns:
            Dictionary with 'success' (bool) and 'result' or 'error'
        """
        pass
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> tuple[bool, Optional[str]]:
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
    
    def _success_response(self, result: Any) -> Dict[str, Any]:
        """Create success response"""
        return {"success": True, "result": result}
    
    def _error_response(self, error: str) -> Dict[str, Any]:
        """Create error response"""
        return {"success": False, "error": error}
    
    async def safe_execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
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
