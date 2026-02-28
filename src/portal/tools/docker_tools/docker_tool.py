"""
Docker Tool - Unified container management (ps, logs, run, stop)

Consolidates DockerPSTool, DockerLogsTool, DockerRunTool, and DockerStopTool
into a single class with action-based dispatch.
"""

import asyncio
import logging
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory

try:
    import docker
    import docker.errors
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    docker = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class DockerTool(BaseTool):
    """Unified Docker container management (ps, logs, run, stop)."""

    METADATA = {
        "name": "docker",
        "description": "Manage Docker containers: list (ps), view logs, run, or stop containers",
        "category": ToolCategory.DEV,
        "requires_confirmation": False,  # set per-action in execute()
        "parameters": [
            {"name": "action", "param_type": "string", "description": "Action: ps, logs, run, stop", "required": True},
            # ps parameters
            {"name": "all", "param_type": "bool", "description": "Show all containers including stopped (ps)", "required": False},
            {"name": "filters", "param_type": "object", "description": "Filter containers (ps)", "required": False},
            # logs parameters
            {"name": "container", "param_type": "string", "description": "Container ID or name (logs, stop)", "required": False},
            {"name": "tail", "param_type": "int", "description": "Number of log lines from end (logs, default: 100)", "required": False},
            {"name": "timestamps", "param_type": "bool", "description": "Show timestamps in logs", "required": False},
            # run parameters
            {"name": "image", "param_type": "string", "description": "Docker image name (run)", "required": False},
            {"name": "name", "param_type": "string", "description": "Container name (run)", "required": False},
            {"name": "ports", "param_type": "object", "description": "Port mappings e.g. {'80/tcp': 8080} (run)", "required": False},
            {"name": "environment", "param_type": "object", "description": "Environment variables (run)", "required": False},
            {"name": "volumes", "param_type": "object", "description": "Volume mappings (run)", "required": False},
            {"name": "detach", "param_type": "bool", "description": "Run in background (run, default: True)", "required": False},
            {"name": "remove", "param_type": "bool", "description": "Auto-remove when stopped (run/stop)", "required": False},
            # stop parameters
            {"name": "containers", "param_type": "list", "description": "Container IDs or names to stop (stop)", "required": False},
            {"name": "timeout", "param_type": "int", "description": "Seconds before kill (stop, default: 10)", "required": False},
        ],
    }

    def __init__(self) -> None:
        super().__init__()
        self.client = None

    def _ensure_client(self) -> bool:
        """Lazy-init Docker client. Returns False if unavailable."""
        if not DOCKER_AVAILABLE:
            return False
        if self.client is None:
            try:
                self.client = docker.from_env()
            except Exception as e:
                logger.error("Failed to connect to Docker: %s", e)
                return False
        return True

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Dispatch to the appropriate Docker action."""
        if not DOCKER_AVAILABLE:
            return self._error_response("Docker SDK not installed. Run: pip install docker")

        action = parameters.get("action", "").lower()
        handler = self._DISPATCH.get(action)
        if not handler:
            return self._error_response(
                f"Unknown action: {action}. Use: {', '.join(self._DISPATCH)}"
            )
        return await handler(self, parameters)

    async def _ps(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """List Docker containers."""
        if not self._ensure_client():
            return self._error_response("Cannot connect to Docker daemon")
        try:
            all_containers = parameters.get("all", False)
            filters = parameters.get("filters", {})
            containers = self.client.containers.list(all=all_containers, filters=filters)
            result = [
                {
                    "id": c.short_id,
                    "name": c.name,
                    "image": c.image.tags[0] if c.image.tags else "unknown",
                    "status": c.status,
                    "ports": c.ports,
                }
                for c in containers
            ]
            return self._success_response(result=result, metadata={"count": len(result)})
        except Exception as e:
            return self._error_response(f"Docker PS failed: {e}")

    async def _logs(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """View Docker container logs."""
        if not self._ensure_client():
            return self._error_response("Cannot connect to Docker daemon")
        container_id = parameters.get("container")
        if not container_id:
            return self._error_response("Container ID or name is required")
        tail = parameters.get("tail", 100)
        timestamps = parameters.get("timestamps", False)
        try:
            container = self.client.containers.get(container_id)
            logs = container.logs(tail=tail, timestamps=timestamps, follow=False)
            log_text = logs.decode("utf-8", errors="replace")
            max_length = 3000
            if len(log_text) > max_length:
                log_text = log_text[-max_length:] + f"\n\n... (showing last {max_length} chars)"
            if not log_text.strip():
                log_text = "(No logs available)"
            return self._success_response(
                result=f"Logs for {container.name}:\n\n{log_text}",
                metadata={"container": container.name, "container_id": container.short_id, "tail": tail},
            )
        except docker.errors.NotFound:
            return self._error_response(f"Container not found: {container_id}")
        except Exception as e:
            return self._error_response(f"Failed to get logs: {e}")

    async def _run(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Run a Docker container."""
        if not self._ensure_client():
            return self._error_response("Cannot connect to Docker daemon")
        image = parameters.get("image")
        if not image:
            return self._error_response("Image name is required")
        name = parameters.get("name")
        ports = parameters.get("ports", {})
        environment = parameters.get("environment", {})
        volumes = parameters.get("volumes", {})
        detach = parameters.get("detach", True)
        remove = parameters.get("remove", False)
        try:
            kwargs: dict[str, Any] = {"detach": detach, "remove": remove}
            if name:
                kwargs["name"] = name
            if ports:
                kwargs["ports"] = ports
            if environment:
                kwargs["environment"] = environment
            if volumes:
                kwargs["volumes"] = volumes
            logger.info("Running container from image: %s", image)
            loop = asyncio.get_event_loop()
            container = await loop.run_in_executor(
                None, lambda: self.client.containers.run(image, **kwargs)
            )
            return self._success_response(
                result=f"Started container {container.name} from {image}",
                metadata={"container_id": container.short_id, "container_name": container.name, "image": image, "status": container.status},
            )
        except docker.errors.ImageNotFound:
            return self._error_response(f"Image not found: {image}. Pull it first with 'docker pull {image}'")
        except docker.errors.APIError as e:
            return self._error_response(f"Docker API error: {e}")
        except Exception as e:
            return self._error_response(f"Failed to run container: {e}")

    async def _stop(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Stop one or more Docker containers."""
        if not self._ensure_client():
            return self._error_response("Cannot connect to Docker daemon")
        containers = parameters.get("containers", [])
        if not containers:
            # Also accept single container param
            single = parameters.get("container")
            if single:
                containers = [single]
        if not containers:
            return self._error_response("At least one container ID or name is required")
        if isinstance(containers, str):
            containers = [containers]
        timeout = parameters.get("timeout", 10)
        remove = parameters.get("remove", False)
        stopped = []
        errors = []
        try:
            for container_id in containers:
                try:
                    container = self.client.containers.get(container_id)
                    logger.info("Stopping container: %s", container.name)
                    container.stop(timeout=timeout)
                    if remove:
                        container.remove()
                        stopped.append(f"{container.name} (removed)")
                    else:
                        stopped.append(container.name)
                except docker.errors.NotFound:
                    errors.append(f"{container_id} (not found)")
                except Exception as e:
                    errors.append(f"{container_id} ({e})")

            result_parts = []
            if stopped:
                result_parts.append(f"Stopped: {', '.join(stopped)}")
            if errors:
                result_parts.append(f"Errors: {', '.join(errors)}")

            if not stopped and errors:
                return self._error_response("\n".join(result_parts))

            return self._success_response(
                result="\n".join(result_parts),
                metadata={"stopped": stopped, "errors": errors, "removed": remove},
            )
        except Exception as e:
            return self._error_response(f"Failed to stop containers: {e}")

    _DISPATCH: dict[str, Any] = {
        "ps": _ps,
        "logs": _logs,
        "run": _run,
        "stop": _stop,
    }
