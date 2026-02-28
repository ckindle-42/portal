"""Shell Safety Tool - Secure command execution"""

import asyncio
import re
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter


class ShellSafetyTool(BaseTool):
    """Execute shell commands with safety checks"""

    # Dangerous patterns that require extra confirmation
    DANGEROUS_PATTERNS = [
        (r"\brm\s+(-rf|-fr)\s+[/~]", "Recursive delete from important directory"),
        (r"\brm\s+(-rf|-fr)\s+\*", "Recursive delete all"),
        (r"\bsudo\b", "Elevated privileges"),
        (r"\bdd\s+.*of=", "Direct disk write"),
        (r">\s*/dev/", "Device write"),
        (r"\bmkfs\b", "Filesystem format"),
        (r"\bshutdown\b", "System shutdown"),
        (r"\breboot\b", "System reboot"),
        (r"curl.*\|\s*(bash|sh)", "Pipe to shell"),
        (r"wget.*\|\s*(bash|sh)", "Pipe to shell"),
        (r":\(\)\{", "Fork bomb pattern"),
    ]

    # Blocked commands (never execute)
    BLOCKED_COMMANDS = [
        r"rm\s+-rf\s+/",
        r"rm\s+-rf\s+~",
        r"dd\s+if=/dev/zero\s+of=/dev/",
        r"mkfs\.",
        r":(){ :|:& };:",
    ]

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="shell_safety",
            description="Execute shell commands with safety validation",
            category=ToolCategory.AUTOMATION,
            version="1.0.0",
            requires_confirmation=True,  # Always requires confirmation
            parameters=[
                ToolParameter(
                    name="command",
                    param_type="string",
                    description="Shell command to execute",
                    required=True,
                ),
                ToolParameter(
                    name="timeout",
                    param_type="int",
                    description="Command timeout in seconds",
                    required=False,
                    default=30,
                ),
                ToolParameter(
                    name="working_dir",
                    param_type="string",
                    description="Working directory",
                    required=False,
                ),
            ],
            examples=["ls -la", "df -h"],
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute shell command with safety checks"""
        try:
            command = parameters.get("command", "")
            timeout = parameters.get("timeout", 30)
            working_dir = parameters.get("working_dir")

            if not command:
                return self._error_response("No command provided")

            # Safety analysis
            safety_result = self._analyze_command(command)

            if safety_result["blocked"]:
                return self._error_response(
                    f"â›” BLOCKED: {safety_result['reason']}\n"
                    f"This command pattern is never allowed."
                )

            if safety_result["dangerous"]:
                return self._error_response(
                    f"âš ï¸ DANGEROUS: {safety_result['warnings']}\n"
                    f"Command requires additional confirmation. "
                    f"Please confirm you understand the risks."
                )

            # Execute command
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except TimeoutError:
                process.kill()
                return self._error_response(f"Command timed out after {timeout}s")

            return self._success_response(
                {
                    "return_code": process.returncode,
                    "stdout": stdout.decode("utf-8", errors="replace")[:5000],
                    "stderr": stderr.decode("utf-8", errors="replace")[:1000],
                    "command": command,
                }
            )

        except Exception as e:
            return self._error_response(str(e))

    def _analyze_command(self, command: str) -> dict[str, Any]:
        """Analyze command for safety"""
        result = {"blocked": False, "dangerous": False, "warnings": [], "reason": None}

        # Check blocked patterns
        for pattern in self.BLOCKED_COMMANDS:
            if re.search(pattern, command, re.IGNORECASE):
                result["blocked"] = True
                result["reason"] = "Matches blocked dangerous pattern"
                return result

        # Check dangerous patterns
        for pattern, description in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                result["dangerous"] = True
                result["warnings"].append(description)

        return result
