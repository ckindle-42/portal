"""
Docker Logs Tool - View container logs
"""

import logging
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter

logger = logging.getLogger(__name__)

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False


class DockerLogsTool(BaseTool):
    """View Docker container logs"""

    def __init__(self):
        super().__init__()
        self.client = None

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="docker_logs",
            description="View logs from a Docker container",
            category=ToolCategory.DEV,
            requires_confirmation=False,
            parameters=[
                ToolParameter(
                    name="container",
                    param_type="string",
                    description="Container ID or name",
                    required=True
                ),
                ToolParameter(
                    name="tail",
                    param_type="int",
                    description="Number of lines to show from end (default: 100)",
                    required=False
                ),
                ToolParameter(
                    name="follow",
                    param_type="bool",
                    description="Follow log output (default: False)",
                    required=False
                ),
                ToolParameter(
                    name="timestamps",
                    param_type="bool",
                    description="Show timestamps (default: False)",
                    required=False
                )
            ]
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Get container logs"""

        if not DOCKER_AVAILABLE:
            return self._error_response("Docker SDK not installed. Run: pip install docker")

        container_id = parameters.get("container")
        tail = parameters.get("tail", 100)
        parameters.get("follow", False)
        timestamps = parameters.get("timestamps", False)

        if not container_id:
            return self._error_response("Container ID or name is required")

        try:
            if not self.client:
                self.client = docker.from_env()

            # Get container
            container = self.client.containers.get(container_id)

            # Get logs
            logs = container.logs(
                tail=tail,
                timestamps=timestamps,
                follow=False  # Always False for Telegram response
            )

            # Decode logs
            log_text = logs.decode('utf-8', errors='replace')

            # Truncate if too long for Telegram
            max_length = 3000
            if len(log_text) > max_length:
                log_text = log_text[-max_length:] + f"\n\n... (showing last {max_length} chars)"

            if not log_text.strip():
                log_text = "(No logs available)"

            return self._success_response(
                result=f"Logs for {container.name}:\n\n{log_text}",
                metadata={
                    "container": container.name,
                    "container_id": container.short_id,
                    "tail": tail,
                    "length": len(log_text)
                }
            )

        except docker.errors.NotFound:
            return self._error_response(f"Container not found: {container_id}")
        except Exception as e:
            return self._error_response(f"Failed to get logs: {str(e)}")
