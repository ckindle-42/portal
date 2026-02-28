"""Tool Registry — auto-discovery and management of agent tools."""

import importlib
import inspect
import logging
import pkgutil
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from portal.core.interfaces.tool import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for discovering, validating, and managing agent tools."""

    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}
        self.failed_tools: list[dict[str, str]] = []

    def discover_and_load(self) -> tuple[int, int]:
        """Auto-discover internal tools and entry-point plugins. Returns (loaded, failed)."""
        tools_dir = Path(__file__).parent
        internal = self._discover_internal_tools(tools_dir)
        plugins = self._discover_entry_point_tools()
        loaded, failed = internal[0] + plugins[0], internal[1] + plugins[1]
        logger.info(
            "Tool registry: %s loaded (%s internal, %s plugins), %s failed",
            loaded,
            internal[0],
            plugins[0],
            failed,
        )
        if failed:
            logger.warning("Failed tools: %s", [t["module"] for t in self.failed_tools])
        return loaded, failed

    def _discover_internal_tools(self, tools_dir: Path) -> tuple[int, int]:
        """Walk pkgutil packages under tools_dir and register all BaseTool subclasses."""
        from portal.core.interfaces.tool import BaseTool

        loaded = failed = 0
        for _importer, modname, ispkg in pkgutil.walk_packages(
            path=[str(tools_dir)], prefix="portal.tools."
        ):
            if ispkg or modname.endswith(("__init__", "base_tool")):
                continue
            try:
                module = importlib.import_module(modname)
                tool_classes = [
                    (name, obj)
                    for name, obj in inspect.getmembers(module, inspect.isclass)
                    if issubclass(obj, BaseTool)
                    and obj is not BaseTool
                    and obj.__module__ == modname
                ]
                for class_name, tool_class in tool_classes:
                    try:
                        self._register_tool_instance(tool_class(), class_name, modname)
                        loaded += 1
                    except Exception as e:
                        failed += 1
                        self._record_failure(modname, class_name, e)
            except Exception as e:
                failed += 1
                self._record_failure(modname, "unknown", e)
        return loaded, failed

    def _record_failure(self, module: str, class_name: str, exc: Exception) -> None:
        """Append a failure entry and log it."""
        msg = f"{type(exc).__name__} loading {class_name} from {module}: {exc}"
        logger.error(msg)
        self.failed_tools.append(
            {"module": module, "class": class_name, "error": msg, "type": type(exc).__name__}
        )

    def _register_tool_instance(self, tool_instance: Any, class_name: str, source: str) -> None:
        """Validate and register a single tool instance."""
        if not hasattr(tool_instance, "metadata"):
            raise AttributeError(f"Tool {class_name} missing 'metadata' attribute")
        if not hasattr(tool_instance, "execute"):
            raise AttributeError(f"Tool {class_name} missing 'execute' method")
        self._validate_tool_metadata(tool_instance, class_name, source)
        tool_name = tool_instance.metadata.name
        self.tools[tool_name] = tool_instance
        logger.info(
            "Loaded tool: %s (%s) from %s", tool_name, tool_instance.metadata.category.value, source
        )

    def _validate_tool_metadata(
        self, tool_instance: Any, class_name: str, module_path: str
    ) -> None:
        """Warn on legacy or invalid metadata formats."""
        metadata = tool_instance.metadata
        if hasattr(metadata, "parameters"):
            params = metadata.parameters
            if isinstance(params, dict):
                logger.warning(
                    "Legacy dict parameters in %s (%s); expected List[ToolParameter]",
                    class_name,
                    module_path,
                )
            elif isinstance(params, list):
                from portal.core.interfaces.tool import ToolParameter

                for idx, param in enumerate(params):
                    if not isinstance(param, ToolParameter):
                        logger.warning(
                            "Non-ToolParameter at index %s in %s (%s)", idx, class_name, module_path
                        )
            else:
                logger.warning(
                    "Invalid parameters type %s in %s (%s)",
                    type(params).__name__,
                    class_name,
                    module_path,
                )
        for field in ("name", "description", "category"):
            if not hasattr(metadata, field):
                logger.warning(
                    "Missing metadata field '%s' in %s (%s)", field, class_name, module_path
                )

    def _discover_entry_point_tools(self) -> tuple[int, int]:
        """Discover and load external plugin tools via Python entry_points."""
        loaded = failed = 0
        try:
            eps = importlib_metadata.entry_points()
            plugin_eps = (
                eps.select(group="portal.tools")
                if hasattr(eps, "select")
                else eps.get("portal.tools", [])
            )
            if not plugin_eps:
                return 0, 0
            from portal.core.interfaces.tool import BaseTool

            logger.info("Found %s plugin tool(s) via entry_points", len(plugin_eps))
            for ep in plugin_eps:
                try:
                    tool_class = ep.load()
                    if not (inspect.isclass(tool_class) and issubclass(tool_class, BaseTool)):
                        raise TypeError(f"{ep.name} is not a valid BaseTool subclass")
                    self._register_tool_instance(tool_class(), ep.name, f"plugin:{ep.value}")
                    loaded += 1
                except Exception as e:
                    failed += 1
                    self._record_failure(f"plugin:{ep.value}", ep.name, e)
        except Exception as e:
            logger.error("Error discovering entry_points: %s", e)
        return loaded, failed

    def get_tool(self, name: str) -> "BaseTool | None":
        return self.tools.get(name)

    def get_all_tools(self) -> list[Any]:
        return list(self.tools.values())

    def get_tool_list(self) -> list[dict[str, Any]]:
        """Return structured metadata for all tools."""
        result = []
        for tool in self.tools.values():
            md = tool.metadata
            result.append(
                {
                    "name": md.name,
                    "description": md.description,
                    "category": md.category.value,
                    "requires_confirmation": md.requires_confirmation,
                    "version": md.version,
                    "async_capable": md.async_capable,
                }
            )
        return result

    def health_check(self) -> dict[str, Any]:
        """Return health status and degradation indicators."""
        status = "degraded" if len(self.failed_tools) > 3 else "healthy"
        return {
            "status": status,
            "total_tools": len(self.tools),
            "failed_loads": len(self.failed_tools),
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }


registry = ToolRegistry()
