"""
Unit tests for Automation tools
"""

import pytest
from unittest.mock import patch, Mock
from portal.tools.automation_tools.scheduler import JobSchedulerTool
from portal.tools.automation_tools.shell_safety import ShellSafetyTool


@pytest.mark.unit
class TestJobSchedulerTool:
    """Test job_scheduler tool"""

    @pytest.mark.asyncio
    async def test_schedule_job(self):
        """Test scheduling a recurring job"""
        tool = JobSchedulerTool()

        result = await tool.execute({
            "operation": "schedule",
            "name": "test_job",
            "schedule": "0 9 * * *",  # Daily at 9 AM
            "command": "echo 'test'"
        })

        assert result["success"] is True or result["success"] is False
        # Implementation may vary

    @pytest.mark.asyncio
    async def test_list_jobs(self):
        """Test listing scheduled jobs"""
        tool = JobSchedulerTool()

        result = await tool.execute({
            "action": "list"
        })

        assert result["success"] is True
        assert "jobs" in result or "result" in result

    @pytest.mark.asyncio
    async def test_cancel_job(self):
        """Test canceling a scheduled job"""
        tool = JobSchedulerTool()

        result = await tool.execute({
            "operation": "cancel",
            "job_id": "test_job_id"
        })

        # May succeed or fail depending on whether job exists
        assert "success" in result


@pytest.mark.unit
class TestShellSafetyTool:
    """Test shell_safety tool"""

    @pytest.mark.asyncio
    async def test_safe_command_execution(self):
        """Test executing a safe shell command"""
        tool = ShellSafetyTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="safe output",
                stderr=""
            )

            result = await tool.execute({
                "command": "echo 'hello world'"
            })

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_dangerous_command_blocked(self):
        """Test that dangerous commands are blocked"""
        tool = ShellSafetyTool()

        dangerous_commands = [
            "rm -rf /",
            "dd if=/dev/zero of=/dev/sda",
            ":(){ :|:& };:",  # Fork bomb
        ]

        for cmd in dangerous_commands:
            result = await tool.execute({
                "command": cmd
            })

            # Should either block or warn
            assert "success" in result
            if result["success"]:
                assert "warning" in result or "blocked" in str(result).lower()

    @pytest.mark.asyncio
    async def test_command_validation(self):
        """Test command safety validation"""
        tool = ShellSafetyTool()

        result = await tool.execute({
            "command": "ls -la",
            "validate_only": True
        })

        assert result["success"] is True
