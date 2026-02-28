"""Input Sanitizer — validation and sanitization against malicious patterns."""

import html
import logging
import re
import shlex
from pathlib import Path
from urllib.parse import unquote

logger = logging.getLogger(__name__)


class InputSanitizer:
    """Input validation and sanitization against malicious patterns."""

    # Dangerous command patterns
    DANGEROUS_PATTERNS = [
        # Destructive commands
        (r"\brm\s+(-rf|-fr)\s+/", "Recursive delete from root"),
        (r"\brm\s+(-rf|-fr)\s+\*", "Recursive delete all"),
        (r"\bdd\s+.*of=/dev/", "Direct disk write"),
        (r":\(\)\{.*:\|:&\};:", "Fork bomb"),
        (r"\bmkfs\.", "Filesystem format"),
        (r"\bshred\b", "Secure file deletion"),
        # Privilege escalation
        (r"\bsudo\s+rm\s+-rf\s+/", "Sudo destructive delete"),
        (r"\bsudo\s+chmod\s+777\s+/", "Sudo permission change"),
        # Network dangerous
        (r"\bcurl.*\|\s*(bash|sh)", "Curl to shell execution"),
        (r"\bwget.*\|\s*(bash|sh)", "Wget to shell execution"),
        (r"\bnc\s+-[el]", "Netcat backdoor"),
        # Data exfiltration
        (r">\s*/dev/tcp/", "Network redirect"),
        (r"\bscp\s+.*@", "Remote copy"),
        # System modification
        (r">\s*/etc/", "System config modification"),
        (r">\s*/boot/", "Boot config modification"),
    ]

    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"';\s*DROP\s+TABLE",
        r"'\s*OR\s+'1'\s*=\s*'1",
        r"--\s*$",
        r"/\*.*\*/",
        r"xp_cmdshell",
    ]

    # Path traversal patterns
    PATH_TRAVERSAL_PATTERNS = [
        r"\.\./+",
        r"\.\.\\+",
        r"%2e%2e/",
        r"%2e%2e\\",
    ]

    @staticmethod
    def sanitize_command(command: str) -> tuple[str, list[str]]:
        """
        Sanitize shell command and detect dangerous patterns.

        Args:
            command: Shell command to sanitize

        Returns:
            (sanitized_command, list_of_warnings)
        """
        warnings = []

        # Check for dangerous patterns
        for pattern, description in InputSanitizer.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                warnings.append(f"âš ï¸ Dangerous pattern detected: {description}")
                logger.warning("Dangerous command detected: %s", command[:100])

        # Basic sanitization (without breaking legitimate use)
        sanitized = command.strip()

        return sanitized, warnings

    @staticmethod
    def validate_file_path(path: str) -> tuple[bool, str | None]:
        """
        Validate file path to prevent path traversal attacks.

        Args:
            path: File path to validate

        Returns:
            (is_valid, error_message)
        """
        # Decode URL-encoded input first so encoded traversal sequences such as
        # "%2e%2e%2f" are detected by the regex patterns below.
        decoded_path = unquote(path)

        # Check for path traversal
        for pattern in InputSanitizer.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, decoded_path, re.IGNORECASE):
                return False, "Path traversal detected"

        # Check for absolute paths to sensitive directories
        path_obj = Path(decoded_path).resolve()
        sensitive_dirs = [Path("/etc"), Path("/boot"), Path("/sys"), Path("/proc"), Path("/dev")]

        for sensitive_dir in sensitive_dirs:
            try:
                path_obj.relative_to(sensitive_dir)
                return False, f"Access to {sensitive_dir} is restricted"
            except ValueError:
                continue

        return True, None

    @staticmethod
    def sanitize_sql_query(query: str) -> tuple[bool, str | None]:
        """
        Check SQL query for injection attempts.

        Args:
            query: SQL query to check

        Returns:
            (is_safe, error_message)
        """
        for pattern in InputSanitizer.SQL_INJECTION_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                logger.warning("SQL injection attempt detected: %s", query[:100])
                return False, "Potential SQL injection detected"

        return True, None

    @staticmethod
    def sanitize_html(text: str) -> str:
        """
        Sanitize HTML to prevent XSS attacks.

        Args:
            text: Text potentially containing HTML

        Returns:
            Sanitized text
        """
        # Escape HTML special characters
        return html.escape(text)

    @staticmethod
    def validate_url(url: str) -> tuple[bool, str | None]:
        """
        Validate URL format and safety.

        Args:
            url: URL to validate

        Returns:
            (is_valid, error_message)
        """
        # Basic URL validation
        url_pattern = re.compile(
            r"^https?://"  # http:// or https://
            r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"  # domain
            r"localhost|"  # localhost
            r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # IP
            r"(?::\d+)?"  # optional port
            r"(?:/?|[/?]\S+)$",
            re.IGNORECASE,
        )

        if not url_pattern.match(url):
            return False, "Invalid URL format"

        # Check for suspicious URLs
        suspicious_domains = ["bit.ly", "tinyurl.com"]  # Can be expanded
        for domain in suspicious_domains:
            if domain in url.lower():
                return False, f"Suspicious URL shortener detected: {domain}"

        return True, None

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent directory traversal and special chars.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove path separators
        filename = filename.replace("/", "_").replace("\\", "_")

        # Remove parent directory references
        filename = filename.replace("..", "")

        # Remove special characters
        filename = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)

        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
            filename = name[:250] + ("." + ext if ext else "")

        return filename

    @staticmethod
    def quote_shell_arg(arg: str) -> str:
        """
        Safely quote a shell argument using shlex.quote().

        This prevents shell injection attacks by properly escaping special characters.
        Use this for ALL arguments passed to subprocess calls.

        Args:
            arg: Shell argument to quote

        Returns:
            Safely quoted argument

        Example:
            >>> InputSanitizer.quote_shell_arg("file name.txt")
            "'file name.txt'"
            >>> InputSanitizer.quote_shell_arg("'; rm -rf /")
            "''\\'''; rm -rf /'"
        """
        return shlex.quote(arg)

    @staticmethod
    def quote_shell_args(args: list[str]) -> list[str]:
        """
        Safely quote multiple shell arguments.

        Args:
            args: List of shell arguments to quote

        Returns:
            List of safely quoted arguments

        Example:
            >>> InputSanitizer.quote_shell_args(["ls", "-la", "my file.txt"])
            ['ls', '-la', "'my file.txt'"]
        """
        return [shlex.quote(arg) for arg in args]
