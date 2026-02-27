"""
Docker PS Tool - List containers
"""

import logging
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter
from portal.tools.docker_tools._base import DOCKER_AVAILABLE, docker

logger = logging.getLogger(__name__)


class DockerPSTool(BaseTool):
    """List Docker containers"""

    def __init__(self) -> None:
        super().__init__()
        self.client = None

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="docker_ps",
            description="List Docker containers",
            category=ToolCategory.DEV,
            parameters=[
                ToolParameter(
                    name="all",
                    param_type="bool",
                    description="Show all containers (default: running only)",
                    required=False
                ),
                ToolParameter(
                    name="filters",
                    param_type="object",
                    description="Filter containers",
                    required=False
                )
            ]
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """List containers"""

        if not DOCKER_AVAILABLE:
            return self._error_response("Docker SDK not installed. Run: pip install docker")

        try:
            if not self.client:
                self.client = docker.from_env()

            all_containers = parameters.get("all", False)
            filters = parameters.get("filters", {})

            containers = self.client.containers.list(all=all_containers, filters=filters)

            result = []
            for container in containers:
                result.append({
                    "id": container.short_id,
                    "name": container.name,
                    "image": container.image.tags[0] if container.image.tags else "unknown",
                    "status": container.status,
                    "ports": container.ports
                })

            return self._success_response(
                result=result,
                metadata={"count": len(result)}
            )

        except Exception as e:
            return self._error_response(f"Docker PS failed: {str(e)}")
