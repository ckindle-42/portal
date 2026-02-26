"""
Enhanced Tool Registry - Auto-discovery and management of agent tools
Includes validation, error handling, performance tracking, and plugin support via entry_points
"""

import importlib
import inspect
import logging
import pkgutil
from dataclasses import dataclass
from datetime import datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionStats:
    """Statistics for tool execution"""
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0
    total_execution_time: float = 0.0
    last_execution: datetime | None = None

    @property
    def success_rate(self) -> float:
        if self.total_executions == 0:
            return 0.0
        return self.successful_executions / self.total_executions

    @property
    def average_execution_time(self) -> float:
        if self.successful_executions == 0:
            return 0.0
        return self.total_execution_time / self.successful_executions


class ToolRegistry:
    """Enhanced registry for discovering and managing tools"""

    def __init__(self):
        self.tools: dict[str, Any] = {}
        self.tool_categories: dict[str, list[str]] = {
            'utility': [],
            'data': [],
            'web': [],
            'audio': [],
            'dev': [],
            'automation': [],
            'knowledge': [],
        }
        self.tool_stats: dict[str, ToolExecutionStats] = {}
        self.failed_tools: list[dict[str, str]] = []

    def discover_and_load(self) -> tuple[int, int]:
        """
        Auto-discover and load all tools from:
        1. Internal tools (pkgutil.walk_packages)
        2. External plugins (entry_points)
        Returns (loaded_count, failed_count)
        """

        tools_dir = Path(__file__).parent
        loaded = 0
        failed = 0

        logger.info(f"Scanning for tools in {tools_dir}")

        # 1. Discover internal tools using pkgutil
        internal_loaded, internal_failed = self._discover_internal_tools(tools_dir)
        loaded += internal_loaded
        failed += internal_failed

        # 2. Discover external plugins using entry_points
        plugin_loaded, plugin_failed = self._discover_entry_point_tools()
        loaded += plugin_loaded
        failed += plugin_failed

        # Log summary
        logger.info(f"Tool registry: {loaded} loaded ({internal_loaded} internal, {plugin_loaded} plugins), {failed} failed")

        if failed > 0:
            logger.warning(f"Failed tools: {[t['module'] for t in self.failed_tools]}")

        return loaded, failed

    def _discover_internal_tools(self, tools_dir: Path) -> tuple[int, int]:
        """
        Discover internal tools using pkgutil.walk_packages.
        Returns (loaded_count, failed_count)
        """
        loaded = 0
        failed = 0

        # Import BaseTool from new location (core interfaces)
        from portal.core.interfaces.tool import BaseTool

        # Walk through all packages in the tools directory
        for importer, modname, ispkg in pkgutil.walk_packages(
            path=[str(tools_dir)],
            prefix='portal.tools.'
        ):
            # Skip __init__ files and base_tool
            if modname.endswith('__init__') or modname.endswith('base_tool'):
                continue

            # Skip packages (directories), only process modules (files)
            if ispkg:
                continue

            module_path = modname
            try:
                # Import module
                module = importlib.import_module(module_path)

                # Find all classes in module that inherit from BaseTool
                tool_classes = []
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # Check if it's a subclass of BaseTool (but not BaseTool itself)
                    if (issubclass(obj, BaseTool) and
                        obj is not BaseTool and
                        obj.__module__ == module_path):
                        tool_classes.append((name, obj))

                if not tool_classes:
                    # No tool classes found in this module, skip silently
                    continue

                # Load each tool class found in the module
                for class_name, tool_class in tool_classes:
                    try:
                        tool_instance = tool_class()
                        self._register_tool_instance(tool_instance, class_name, module_path)
                        loaded += 1
                    except Exception as e:
                        failed += 1
                        error_msg = f"Failed to instantiate {class_name} from {module_path}: {str(e)}"
                        logger.error(f"Error: {error_msg}")
                        self.failed_tools.append({
                            'module': module_path,
                            'class': class_name,
                            'error': error_msg,
                            'type': type(e).__name__
                        })

            except ImportError as e:
                failed += 1
                error_msg = f"Import failed for {module_path}: {str(e)}"
                logger.error(f"Import error: {error_msg}")
                self.failed_tools.append({
                    'module': module_path,
                    'class': 'unknown',
                    'error': error_msg,
                    'type': 'ImportError'
                })

            except Exception as e:
                failed += 1
                error_msg = f"Unexpected error loading {module_path}: {str(e)}"
                logger.error(f"Unexpected error: {error_msg}")
                self.failed_tools.append({
                    'module': module_path,
                    'class': 'unknown',
                    'error': error_msg,
                    'type': type(e).__name__
                })

        return loaded, failed

    def _register_tool_instance(self, tool_instance: Any, class_name: str, source: str) -> None:
        """
        Validate and register a single tool instance.

        Shared by both internal discovery and entry-point plugin loading.

        Args:
            tool_instance: Instantiated tool object
            class_name: Class name (for error messages)
            source: Module path or plugin identifier (for logging)

        Raises:
            AttributeError: If tool is missing required attributes
        """
        if not hasattr(tool_instance, 'metadata'):
            raise AttributeError(f"Tool {class_name} missing 'metadata' attribute")
        if not hasattr(tool_instance, 'execute'):
            raise AttributeError(f"Tool {class_name} missing 'execute' method")

        self._validate_tool_metadata(tool_instance, class_name, source)

        tool_name = tool_instance.metadata.name
        self.tools[tool_name] = tool_instance
        self.tool_stats[tool_name] = ToolExecutionStats()

        category = tool_instance.metadata.category.value
        if category in self.tool_categories:
            self.tool_categories[category].append(tool_name)
        else:
            self.tool_categories[category] = [tool_name]

        logger.info(f"Loaded tool: {tool_name} ({category}) from {source}")

    def _validate_tool_metadata(self, tool_instance: Any, class_name: str, module_path: str) -> None:
        """
        Validate tool metadata contract and emit warnings for legacy formats.
        This ensures tools follow current API standards while maintaining backward compatibility.
        """
        metadata = tool_instance.metadata

        # Check 1: Validate parameters field type
        if hasattr(metadata, 'parameters'):
            params = metadata.parameters

            # Legacy format detection: dict instead of List[ToolParameter]
            if isinstance(params, dict):
                logger.warning(
                    f"⚠️  LEGACY METADATA FORMAT in {class_name} ({module_path}): "
                    f"'parameters' is a dict, should be List[ToolParameter]. "
                    f"This format is deprecated and may be removed in future versions. "
                    f"See docs/PLUGIN_DEVELOPMENT.md for migration guide."
                )
            # Empty list is acceptable
            elif isinstance(params, list):
                # Validate each parameter is a ToolParameter instance
                from portal.core.interfaces.tool import ToolParameter
                for idx, param in enumerate(params):
                    if not isinstance(param, ToolParameter):
                        logger.warning(
                            f"⚠️  LEGACY PARAMETER FORMAT in {class_name} ({module_path}): "
                            f"Parameter at index {idx} is not a ToolParameter instance. "
                            f"Type: {type(param).__name__}. Expected: ToolParameter."
                        )
            else:
                logger.warning(
                    f"⚠️  INVALID METADATA in {class_name} ({module_path}): "
                    f"'parameters' field has unexpected type {type(params).__name__}. "
                    f"Expected: List[ToolParameter]."
                )

        # Check 2: Validate required metadata fields
        required_fields = ['name', 'description', 'category']
        for field in required_fields:
            if not hasattr(metadata, field):
                logger.warning(
                    f"⚠️  INCOMPLETE METADATA in {class_name} ({module_path}): "
                    f"Missing required field '{field}'."
                )

    def _discover_entry_point_tools(self) -> tuple[int, int]:
        """
        Discover external plugin tools using Python entry_points.
        Looks for entry points in the 'portal.tools' group.
        Returns (loaded_count, failed_count)
        """
        loaded = 0
        failed = 0

        try:
            # Get entry points for portal.tools
            entry_points = importlib_metadata.entry_points()
            if hasattr(entry_points, 'select'):
                plugin_entry_points = entry_points.select(group='portal.tools')
            else:
                # Fallback for some 3.10 versions
                plugin_entry_points = entry_points.get('portal.tools', [])

            if not plugin_entry_points:
                logger.debug("No plugin tools found via entry_points")
                return 0, 0

            logger.info(f"Found {len(plugin_entry_points)} plugin tool(s) via entry_points")

            # Load each plugin tool
            from portal.core.interfaces.tool import BaseTool

            for entry_point in plugin_entry_points:
                try:
                    tool_class = entry_point.load()

                    if not (inspect.isclass(tool_class) and issubclass(tool_class, BaseTool)):
                        raise TypeError(f"{entry_point.name} is not a valid BaseTool subclass")

                    tool_instance = tool_class()
                    self._register_tool_instance(
                        tool_instance, entry_point.name, f"plugin:{entry_point.value}"
                    )
                    loaded += 1
                except Exception as e:
                    failed += 1
                    error_msg = f"Failed to load plugin {entry_point.name}: {str(e)}"
                    logger.error(f"Plugin error: {error_msg}")
                    self.failed_tools.append({
                        'module': f'plugin:{entry_point.value}',
                        'class': entry_point.name,
                        'error': error_msg,
                        'type': type(e).__name__
                    })

        except Exception as e:
            logger.error(f"Error discovering entry_points: {e}")
            # Don't fail the entire discovery process
            return 0, 0

        return loaded, failed

    def get_tool(self, name: str) -> Any | None:
        """Get tool by name"""
        return self.tools.get(name)

    def get_all_tools(self) -> list[Any]:
        """Get all registered tools"""
        return list(self.tools.values())

    def get_tools_by_category(self, category: str) -> list[Any]:
        """Get tools by category"""
        tool_names = self.tool_categories.get(category, [])
        return [self.tools[name] for name in tool_names if name in self.tools]

    def get_tool_list(self) -> list[dict[str, Any]]:
        """
        Get list of tool metadata for display purposes.
        Returns structured data about each tool.
        """
        tool_list = []

        for tool in self.tools.values():
            metadata = tool.metadata
            stats = self.tool_stats.get(metadata.name, ToolExecutionStats())

            tool_list.append({
                'name': metadata.name,
                'description': metadata.description,
                'category': metadata.category.value,
                'requires_confirmation': metadata.requires_confirmation,
                'version': metadata.version,
                'async_capable': metadata.async_capable,
                'stats': {
                    'executions': stats.total_executions,
                    'success_rate': stats.success_rate,
                    'avg_time': stats.average_execution_time
                }
            })

        return tool_list

    def record_execution(self, tool_name: str, success: bool, execution_time: float):
        """Record tool execution statistics"""
        if tool_name not in self.tool_stats:
            self.tool_stats[tool_name] = ToolExecutionStats()

        stats = self.tool_stats[tool_name]
        stats.total_executions += 1
        stats.last_execution = datetime.now()

        if success:
            stats.successful_executions += 1
            stats.total_execution_time += execution_time
        else:
            stats.failed_executions += 1

    def get_tool_stats(self, tool_name: str) -> ToolExecutionStats | None:
        """Get statistics for a specific tool"""
        return self.tool_stats.get(tool_name)

    def get_all_stats(self) -> dict[str, ToolExecutionStats]:
        """Get statistics for all tools"""
        return self.tool_stats.copy()

    def get_failed_tools(self) -> list[dict[str, str]]:
        """Get list of tools that failed to load"""
        return self.failed_tools.copy()

    def health_check(self) -> dict[str, Any]:
        """
        Perform health check on all tools.
        Returns health status and any issues found.
        """
        health_report = {
            'status': 'healthy',
            'total_tools': len(self.tools),
            'failed_loads': len(self.failed_tools),
            'tools_never_executed': [],
            'tools_high_failure_rate': [],
            'timestamp': datetime.now().isoformat()
        }

        # Check for tools that have never been executed
        for tool_name, stats in self.tool_stats.items():
            if stats.total_executions == 0:
                health_report['tools_never_executed'].append(tool_name)

        # Check for tools with high failure rates
        for tool_name, stats in self.tool_stats.items():
            if stats.total_executions >= 10 and stats.success_rate < 0.5:
                health_report['tools_high_failure_rate'].append({
                    'name': tool_name,
                    'success_rate': stats.success_rate,
                    'executions': stats.total_executions
                })

        # Determine overall status
        if health_report['failed_loads'] > 3:
            health_report['status'] = 'degraded'

        if health_report['tools_high_failure_rate']:
            health_report['status'] = 'degraded'

        return health_report

    def validate_tool_parameters(self, tool_name: str, parameters: dict[str, Any]) -> tuple[bool, str | None]:
        """
        Validate parameters before tool execution.
        Returns (is_valid, error_message)
        """
        tool = self.get_tool(tool_name)

        if not tool:
            return False, f"Tool '{tool_name}' not found"

        # Check if tool has validate_parameters method
        if hasattr(tool, 'validate_parameters'):
            try:
                return tool.validate_parameters(parameters)
            except Exception as e:
                return False, f"Validation error: {str(e)}"

        # Basic validation if no custom validator
        required_params = tool.metadata.parameters
        if isinstance(required_params, dict):
            for param_name, param_spec in required_params.items():
                if param_spec.get('required', False) and param_name not in parameters:
                    return False, f"Missing required parameter: {param_name}"
        elif isinstance(required_params, list):
            for param in required_params:
                if getattr(param, 'required', False) and param.name not in parameters:
                    return False, f"Missing required parameter: {param.name}"

        return True, None


# Global registry instance
registry = ToolRegistry()
