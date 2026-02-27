"""Security Module — rate limiting and input sanitization."""

import asyncio
import atexit
import html
import json
import logging
import os
import re
import shlex
import shutil
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote

logger = logging.getLogger(__name__)


class RateLimiter:
    """Per-user sliding-window rate limiter. Persists state to prevent restart-bypass attacks."""

    def __init__(
        self, max_requests: int = 30, window_seconds: int = 60, persist_path: Path | None = None
    ):
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: dict[str, list[float]] = defaultdict(list)
        self.violations: dict[str, int] = defaultdict(int)
        self.persist_path = (
            persist_path or Path(os.getenv("RATE_LIMIT_DATA_DIR", "data")) / "rate_limits.json"
        )
        self._dirty = False
        self._last_save = time.time()
        self._save_interval = 5.0
        self._load_state()
        atexit.register(self._flush_if_dirty)

    def _check_limit_sync(self, user_id: str) -> tuple[bool, str | None]:
        """Synchronous core of rate limit check (called via asyncio.to_thread)."""
        now = time.time()
        user_requests = [t for t in self.requests[user_id] if now - t < self.window]
        if len(user_requests) >= self.max_requests:
            self.violations[user_id] += 1
            wait_time = int(user_requests[0] + self.window - now)

            logger.warning(
                "Rate limit exceeded for user %s (%d/%d requests)",
                user_id,
                len(user_requests),
                self.max_requests,
            )

            self._dirty = True
            if now - self._last_save >= self._save_interval:
                self._save_state()
                self._last_save = now
                self._dirty = False

            return False, f"⏱️ Rate limit exceeded. Please wait {wait_time} seconds."

        # Add current request
        user_requests.append(now)
        self.requests[user_id] = user_requests[-self.max_requests :]

        # Evict expired users to prevent unbounded memory growth
        self._evict_expired_users()

        self._dirty = True
        if now - self._last_save >= self._save_interval:
            self._save_state()
            self._last_save = now
            self._dirty = False

        return True, None

    async def check_limit(self, user_id: str) -> tuple[bool, str | None]:
        """
        Check if user is within rate limit.

        Args:
            user_id: Telegram user ID

        Returns:
            (is_allowed, error_message)
        """
        return await asyncio.to_thread(self._check_limit_sync, user_id)

    def reset_user(self, user_id: str) -> None:
        """Reset rate limit for specific user"""
        self.requests[user_id] = []
        self.violations[user_id] = 0
        self._flush_if_dirty()
        self._save_state()

    def _flush_if_dirty(self) -> None:
        """Flush state to disk if there are pending changes."""
        if self._dirty:
            self._save_state()
            self._dirty = False

    def get_stats(self, user_id: str) -> dict[str, int]:
        """Get statistics for a user"""
        now = time.time()
        user_requests = self.requests[user_id]

        recent_requests = [req for req in user_requests if now - req < self.window]

        return {
            "total_requests": len(user_requests),
            "recent_requests": len(recent_requests),
            "remaining": self.max_requests - len(recent_requests),
            "violations": self.violations[user_id],
        }

    def _evict_expired_users(self) -> None:
        """Remove users whose last request is older than the window to bound map size."""
        now = time.time()
        for user_id in list(self.requests.keys()):
            self.requests[user_id] = [
                req for req in self.requests[user_id] if now - req < self.window
            ]
            if not self.requests[user_id]:
                del self.requests[user_id]

    def _load_state(self) -> None:
        """
        Load rate limit state from disk.
        Prevents malicious users from bypassing limits via restart.
        """
        if not self.persist_path.exists():
            return

        try:
            with open(self.persist_path, encoding="utf-8") as f:
                data = json.load(f)

            # Keep string keys (user_ids are stored as strings)
            self.requests = defaultdict(list, {k: v for k, v in data.get("requests", {}).items()})
            self.violations = defaultdict(
                int, {k: v for k, v in data.get("violations", {}).items()}
            )

            # Clean up old requests outside the window
            self._evict_expired_users()

            logger.info("Loaded rate limit state for %s users", len(self.requests))

        except json.JSONDecodeError as e:
            logger.error("Failed to decode rate limit state (corrupt file): %s", e)
            bak_path = self.persist_path.with_suffix(".json.bak")
            try:
                self.persist_path.rename(bak_path)
                logger.warning("Renamed corrupt rate_limits.json to %s for inspection", bak_path)
            except OSError as rename_err:
                logger.error("Could not rename corrupt file: %s", rename_err)
        except Exception as e:
            logger.error("Failed to load rate limit state: %s", e)

    def _save_state(self) -> None:
        """
        Save rate limit state to disk with atomic write.
        Prevents data loss and ensures persistence across restarts.
        """
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)

            # Prepare data for serialization
            data = {
                "requests": {str(k): v for k, v in self.requests.items()},
                "violations": {str(k): v for k, v in self.violations.items()},
                "timestamp": time.time(),
            }

            # Atomic write pattern (same as knowledge base)
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.persist_path.parent, prefix=".rate_limits_tmp_", suffix=".json"
            )

            try:
                with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())

                # Atomic rename
                shutil.move(temp_path, self.persist_path)

            except Exception:
                if Path(temp_path).exists():
                    Path(temp_path).unlink()
                raise

        except Exception as e:
            logger.error("Failed to save rate limit state: %s", e)


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
                warnings.append(f"âš ï¸ Dangerous pattern detected: {description}")
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
