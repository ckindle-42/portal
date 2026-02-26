"""
End-to-end tests for CLI commands
"""

import subprocess
import sys

import pytest


@pytest.mark.e2e
class TestCLICommands:
    """Test CLI command execution"""

    def run_cli(self, *args):
        """Helper to run CLI commands"""
        cmd = [sys.executable, "-m", "portal"] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result

    def test_cli_help(self):
        """Test --help command"""
        result = self.run_cli("--help")

        assert result.returncode == 0, \
            f"--help should succeed: {result.stderr}"
        assert "portal" in result.stdout.lower() or "usage" in result.stdout.lower(), \
            "Help should contain usage information"

    def test_cli_version(self):
        """Test --version command"""
        result = self.run_cli("--version")

        assert result.returncode == 0, \
            f"--version should succeed: {result.stderr}"
        assert "4.7.4" in result.stdout or "portal" in result.stdout.lower(), \
            "Version should show version number"

    def test_list_tools_command(self):
        """Test list-tools command"""
        result = self.run_cli("list-tools")

        assert result.returncode == 0, \
            f"list-tools should succeed: {result.stderr}"
        assert "33 loaded" in result.stdout or "33" in result.stdout, \
            "Should show 33 loaded tools"
        assert "0 failed" in result.stdout or "failed" not in result.stdout.lower(), \
            "Should show 0 failed tools"

    def test_list_tools_shows_categories(self):
        """Test that list-tools shows tool categories"""
        result = self.run_cli("list-tools")

        assert result.returncode == 0
        # Check for some known categories
        output_lower = result.stdout.lower()
        assert any(cat in output_lower for cat in ['audio', 'data', 'dev', 'automation', 'utility', 'web']), \
            "Should show tool categories"

    def test_validate_config_command(self):
        """Test validate-config command"""
        result = self.run_cli("validate-config")

        # Command should either succeed or fail gracefully
        assert result.returncode in [0, 1], \
            "validate-config should exit with 0 or 1"

    def test_verify_command(self):
        """Test verify command"""
        result = self.run_cli("verify")

        # Should run without crashing
        assert result.returncode in [0, 1], \
            "verify should complete"

    def test_queue_command(self):
        """Test queue management command"""
        result = self.run_cli("queue", "--help")

        assert result.returncode == 0, \
            "queue --help should succeed"
        assert "queue" in result.stdout.lower(), \
            "Should show queue help"

    def test_version_command(self):
        """Test version subcommand"""
        result = self.run_cli("version")

        assert result.returncode == 0, \
            f"version command should succeed: {result.stderr}"
        assert "portal" in result.stdout.lower() or "4.7" in result.stdout, \
            "Should show version information"

    def test_invalid_command(self):
        """Test that invalid commands fail gracefully"""
        result = self.run_cli("nonexistent-command")

        assert result.returncode != 0, \
            "Invalid command should fail"
        assert "error" in result.stderr.lower() or "invalid" in result.stderr.lower() or \
               "error" in result.stdout.lower() or "invalid" in result.stdout.lower(), \
            "Should show error message for invalid command"


@pytest.mark.e2e
class TestCLIOptions:
    """Test CLI global options"""

    def run_cli(self, *args):
        """Helper to run CLI commands"""
        cmd = [sys.executable, "-m", "portal"] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result

    def test_log_level_option(self):
        """Test --log-level option"""
        result = self.run_cli("--log-level", "DEBUG", "list-tools")

        # Should run without crashing
        assert result.returncode == 0 or result.returncode == 1

    def test_log_format_option(self):
        """Test --log-format option"""
        result = self.run_cli("--log-format", "json", "list-tools")

        # Should run without crashing
        assert result.returncode == 0 or result.returncode == 1


@pytest.mark.e2e
class TestCLIToolIntegration:
    """Test CLI integration with tool system"""

    def run_cli(self, *args):
        """Helper to run CLI commands"""
        cmd = [sys.executable, "-m", "portal"] + list(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result

    def test_list_tools_output_format(self):
        """Test that list-tools output is properly formatted"""
        result = self.run_cli("list-tools")

        assert result.returncode == 0
        output = result.stdout

        # Should have category headers
        assert any(cat in output for cat in ["AUDIO", "DATA", "DEV", "AUTOMATION"]), \
            "Should show category headers"

        # Should list tool names
        assert "git_status" in output or "system_stats" in output, \
            "Should list individual tools"

    def test_cli_loads_tools_consistently(self):
        """Test that CLI loads tools consistently across multiple runs"""
        result1 = self.run_cli("list-tools")
        result2 = self.run_cli("list-tools")

        assert result1.returncode == result2.returncode
        # Tool count should be the same
        assert result1.stdout.count("loaded") == result2.stdout.count("loaded")
