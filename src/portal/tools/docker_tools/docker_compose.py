"""
Docker Compose Tool - Manage Docker Compose stacks
"""

import asyncio
import logging
import os
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter

logger = logging.getLogger(__name__)


class DockerComposeTool(BaseTool):
    """Manage Docker Compose stacks"""

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="docker_compose",
            description="Run Docker Compose commands (up, down, ps, logs)",
            category=ToolCategory.DEV,
            requires_confirmation=True,  # Compose affects multiple containers
            parameters=[
                ToolParameter(
                    name="action",
                    param_type="string",
                    description="Action: up, down, ps, logs, restart",
                    required=True
                ),
                ToolParameter(
                    name="compose_file",
                    param_type="string",
                    description="Path to docker-compose.yml (default: ./docker-compose.yml)",
                    required=False
                ),
                ToolParameter(
                    name="project_name",
                    param_type="string",
                    description="Project name (default: directory name)",
                    required=False
                ),
                ToolParameter(
                    name="services",
                    param_type="list",
                    description="Specific services to target",
                    required=False
                ),
                ToolParameter(
                    name="detach",
                    param_type="bool",
                    description="Run in background (for 'up', default: True)",
                    required=False
                ),
                ToolParameter(
                    name="build",
                    param_type="bool",
                    description="Build images before starting (for 'up', default: False)",
                    required=False
                )
            ]
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute docker-compose command"""

        action = parameters.get("action", "").lower()
        compose_file = parameters.get("compose_file", "docker-compose.yml")
        project_name = parameters.get("project_name")
        services = parameters.get("services", [])
        detach = parameters.get("detach", True)
        build = parameters.get("build", False)

        if action not in ["up", "down", "ps", "logs", "restart"]:
            return self._error_response(f"Unknown action: {action}. Use: up, down, ps, logs, restart")

        if not os.path.exists(compose_file):
            return self._error_response(f"Compose file not found: {compose_file}")

        try:
            # Build docker-compose command
            cmd = ["docker-compose", "-f", compose_file]

            if project_name:
                cmd.extend(["-p", project_name])

            cmd.append(action)

            # Add action-specific flags
            if action == "up":
                if detach:
                    cmd.append("-d")
                if build:
                    cmd.append("--build")
            elif action == "logs":
                cmd.extend(["--tail", "100"])

            # Add specific services if provided
            if services:
                if isinstance(services, str):
                    services = [services]
                cmd.extend(services)

            # Execute command asynchronously
            logger.info(f"Running: {' '.join(cmd)}")

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            output = stdout.decode('utf-8', errors='replace')
            error = stderr.decode('utf-8', errors='replace')

            # Combine output
            result_text = output if output else error

            # Truncate if too long
            max_length = 3000
            if len(result_text) > max_length:
                result_text = result_text[-max_length:] + "\n\n... (truncated)"

            if process.returncode != 0:
                return self._error_response(
                    f"docker-compose {action} failed (exit {process.returncode}):\n{result_text}"
                )

            return self._success_response(
                result=f"docker-compose {action} completed:\n{result_text}",
                metadata={
                    "action": action,
                    "compose_file": compose_file,
                    "project_name": project_name,
                    "exit_code": process.returncode
                }
            )

        except FileNotFoundError:
            return self._error_response(
                "docker-compose not found. Install it: https://docs.docker.com/compose/install/"
            )
        except Exception as e:
            return self._error_response(f"Compose operation failed: {str(e)}")
