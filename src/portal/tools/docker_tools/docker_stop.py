"""
Docker Stop Tool - Stop containers
"""

import logging
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter
from portal.tools.docker_tools._base import DOCKER_AVAILABLE, docker

logger = logging.getLogger(__name__)


class DockerStopTool(BaseTool):
    """Stop Docker containers"""

    def __init__(self) -> None:
        super().__init__()
        self.client = None

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="docker_stop",
            description="Stop one or more Docker containers",
            category=ToolCategory.DEV,
            requires_confirmation=True,  # Stopping affects running services
            parameters=[
                ToolParameter(
                    name="containers",
                    param_type="list",
                    description="Container IDs or names to stop",
                    required=True
                ),
                ToolParameter(
                    name="timeout",
                    param_type="int",
                    description="Seconds to wait before killing (default: 10)",
                    required=False
                ),
                ToolParameter(
                    name="remove",
                    param_type="bool",
                    description="Remove containers after stopping (default: False)",
                    required=False
                )
            ]
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Stop containers"""

        if not DOCKER_AVAILABLE:
            return self._error_response("Docker SDK not installed. Run: pip install docker")

        containers = parameters.get("containers", [])
        timeout = parameters.get("timeout", 10)
        remove = parameters.get("remove", False)

        if not containers:
            return self._error_response("At least one container ID or name is required")

        if isinstance(containers, str):
            containers = [containers]

        try:
            if not self.client:
                self.client = docker.from_env()

            stopped = []
            errors = []

            # Stop each container
            for container_id in containers:
                try:
                    container = self.client.containers.get(container_id)

                    # Stop container
                    logger.info("Stopping container: %s", container.name)
                    container.stop(timeout=timeout)

                    # Remove if requested
                    if remove:
                        container.remove()
                        stopped.append(f"{container.name} (removed)")
                    else:
                        stopped.append(container.name)

                except docker.errors.NotFound:
                    errors.append(f"{container_id} (not found)")
                except Exception as e:
                    errors.append(f"{container_id} ({str(e)})")

            # Build result message
            result_parts = []
            if stopped:
                result_parts.append(f"Stopped: {', '.join(stopped)}")
            if errors:
                result_parts.append(f"Errors: {', '.join(errors)}")

            if not stopped and errors:
                return self._error_response("\n".join(result_parts))

            return self._success_response(
                result="\n".join(result_parts),
                metadata={
                    "stopped": stopped,
                    "errors": errors,
                    "removed": remove
                }
            )

        except Exception as e:
            return self._error_response(f"Failed to stop containers: {str(e)}")
