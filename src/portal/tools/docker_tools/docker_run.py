"""
Docker Run Tool - Run containers
"""

import asyncio
import logging
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter
from portal.tools.docker_tools._base import DOCKER_AVAILABLE, docker

logger = logging.getLogger(__name__)


class DockerRunTool(BaseTool):
    """Run a Docker container"""

    def __init__(self) -> None:
        super().__init__()
        self.client = None

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="docker_run",
            description="Run a Docker container from an image",
            category=ToolCategory.DEV,
            requires_confirmation=True,  # Running containers affects system
            parameters=[
                ToolParameter(
                    name="image",
                    param_type="string",
                    description="Docker image name (e.g., nginx:latest)",
                    required=True,
                ),
                ToolParameter(
                    name="name", param_type="string", description="Container name", required=False
                ),
                ToolParameter(
                    name="ports",
                    param_type="object",
                    description="Port mappings (e.g., {'80/tcp': 8080})",
                    required=False,
                ),
                ToolParameter(
                    name="environment",
                    param_type="object",
                    description="Environment variables",
                    required=False,
                ),
                ToolParameter(
                    name="volumes",
                    param_type="object",
                    description="Volume mappings",
                    required=False,
                ),
                ToolParameter(
                    name="detach",
                    param_type="bool",
                    description="Run in background (default: True)",
                    required=False,
                ),
                ToolParameter(
                    name="remove",
                    param_type="bool",
                    description="Auto-remove when stopped (default: False)",
                    required=False,
                ),
            ],
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Run a container"""

        if not DOCKER_AVAILABLE:
            return self._error_response("Docker SDK not installed. Run: pip install docker")

        image = parameters.get("image")
        name = parameters.get("name")
        ports = parameters.get("ports", {})
        environment = parameters.get("environment", {})
        volumes = parameters.get("volumes", {})
        detach = parameters.get("detach", True)
        remove = parameters.get("remove", False)

        if not image:
            return self._error_response("Image name is required")

        try:
            if not self.client:
                self.client = docker.from_env()

            # Build run arguments
            kwargs = {"detach": detach, "remove": remove}

            if name:
                kwargs["name"] = name
            if ports:
                kwargs["ports"] = ports
            if environment:
                kwargs["environment"] = environment
            if volumes:
                kwargs["volumes"] = volumes

            # Run container asynchronously
            logger.info("Running container from image: %s", image)

            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None, lambda: self.client.containers.run(image, **kwargs)
            )

            return self._success_response(
                result=f"Started container {container.name} from {image}",
                metadata={
                    "container_id": container.short_id,
                    "container_name": container.name,
                    "image": image,
                    "status": container.status,
                },
            )

        except docker.errors.ImageNotFound:
            return self._error_response(
                f"Image not found: {image}. Pull it first with 'docker pull {image}'"
            )
        except docker.errors.APIError as e:
            return self._error_response(f"Docker API error: {str(e)}")
        except Exception as e:
            return self._error_response(f"Failed to run container: {str(e)}")
