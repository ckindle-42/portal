"""
Security Module - Rate limiting and input sanitization
Protects against abuse and malicious inputs
"""

import time
import html
import re
import json
import os
import tempfile
import shutil
import shlex
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# RATE LIMITER
# =============================================================================

class RateLimiter:
    """
    Per-user rate limiting with sliding window algorithm.
    Prevents spam and abuse of the agent.

    SECURITY FIX: Now persists rate limit data to disk to prevent
    malicious users from bypassing limits by forcing restarts.
    """

    def __init__(self, max_requests: int = 30, window_seconds: int = 60,
                 persist_path: Optional[Path] = None):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed per window
            window_seconds: Window duration in seconds
            persist_path: Path to persist rate limit data (prevents bypass via restart)
        """
        self.max_requests = max_requests
        self.window = window_seconds
        self.requests: Dict[int, List[float]] = defaultdict(list)
        self.violations: Dict[int, int] = defaultdict(int)

        # Persistent storage to prevent reset-bypass attacks
        self.persist_path = persist_path or Path(
            os.getenv('RATE_LIMIT_DATA_DIR', 'data')
        ) / 'rate_limits.json'

        # Load existing rate limit data
        self._load_state()
    
    def check_limit(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check if user is within rate limit.
        
        Args:
            user_id: Telegram user ID
            
        Returns:
            (is_allowed, error_message)
        """
        now = time.time()
        user_requests = self.requests[user_id]
        
        # Remove requests outside the window
        user_requests = [
            req_time for req_time in user_requests 
            if now - req_time < self.window
        ]
        
        # Check limit
        if len(user_requests) >= self.max_requests:
            self.violations[user_id] += 1
            wait_time = int(user_requests[0] + self.window - now)

            logger.warning(
                f"Rate limit exceeded for user {user_id} "
                f"({len(user_requests)}/{self.max_requests} requests)"
            )
            
            # Persist violation immediately
            self._save_state()

            return False, f"â±ï¸ Rate limit exceeded. Please wait {wait_time} seconds."
        
        # Add current request
        user_requests.append(now)
        self.requests[user_id] = user_requests[-self.max_requests:]

        # Persist state after each check (prevent bypass via restart)
        self._save_state()

        return True, None
    
    def get_remaining(self, user_id: int) -> int:
        """Get remaining requests for user"""
        now = time.time()
        user_requests = self.requests[user_id]
        
        # Count requests in current window
        recent_requests = [
            req for req in user_requests 
            if now - req < self.window
        ]
        
        return max(0, self.max_requests - len(recent_requests))
    
    def reset_user(self, user_id: int):
        """Reset rate limit for specific user"""
        self.requests[user_id] = []
        self.violations[user_id] = 0
        self._save_state()
    
    def get_stats(self, user_id: int) -> Dict[str, int]:
        """Get statistics for a user"""
        now = time.time()
        user_requests = self.requests[user_id]

        recent_requests = [
            req for req in user_requests
            if now - req < self.window
        ]

        return {
            'total_requests': len(user_requests),
            'recent_requests': len(recent_requests),
            'remaining': self.max_requests - len(recent_requests),
            'violations': self.violations[user_id]
        }

    def _load_state(self):
        """
        Load rate limit state from disk.
        Prevents malicious users from bypassing limits via restart.
        """
        if not self.persist_path.exists():
            return

        try:
            with open(self.persist_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Convert string keys back to integers
            self.requests = defaultdict(list, {
                int(k): v for k, v in data.get('requests', {}).items()
            })
            self.violations = defaultdict(int, {
                int(k): v for k, v in data.get('violations', {}).items()
            })

            # Clean up old requests outside the window
            now = time.time()
            for user_id in list(self.requests.keys()):
                self.requests[user_id] = [
                    req for req in self.requests[user_id]
                    if now - req < self.window
                ]
                if not self.requests[user_id]:
                    del self.requests[user_id]

            logger.info(f"Loaded rate limit state for {len(self.requests)} users")

        except Exception as e:
            logger.error(f"Failed to load rate limit state: {e}")

    def _save_state(self):
        """
        Save rate limit state to disk with atomic write.
        Prevents data loss and ensures persistence across restarts.
        """
        try:
            self.persist_path.parent.mkdir(parents=True, exist_ok=True)

            # Prepare data for serialization
            data = {
                'requests': {str(k): v for k, v in self.requests.items()},
                'violations': {str(k): v for k, v in self.violations.items()},
                'timestamp': time.time()
            }

            # Atomic write pattern (same as knowledge base)
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.persist_path.parent,
                prefix='.rate_limits_tmp_',
                suffix='.json'
            )

            try:
                with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())

                # Atomic rename
                shutil.move(temp_path, self.persist_path)

            except Exception as e:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise

        except Exception as e:
            logger.error(f"Failed to save rate limit state: {e}")


# =============================================================================
# INPUT SANITIZER
# =============================================================================

class InputSanitizer:
    """
    Input validation and sanitization.
    Prevents malicious inputs and dangerous operations.
    """
    
    # Dangerous command patterns
    DANGEROUS_PATTERNS = [
        # Destructive commands
        (r'\brm\s+(-rf|-fr)\s+/', 'Recursive delete from root'),
        (r'\brm\s+(-rf|-fr)\s+\*', 'Recursive delete all'),
        (r'\bdd\s+.*of=/dev/', 'Direct disk write'),
        (r':\(\)\{.*:\|:&\};:', 'Fork bomb'),
        (r'\bmkfs\.', 'Filesystem format'),
        (r'\bshred\b', 'Secure file deletion'),
        
        # Privilege escalation
        (r'\bsudo\s+rm\s+-rf\s+/', 'Sudo destructive delete'),
        (r'\bsudo\s+chmod\s+777\s+/', 'Sudo permission change'),
        
        # Network dangerous
        (r'\bcurl.*\|\s*(bash|sh)', 'Curl to shell execution'),
        (r'\bwget.*\|\s*(bash|sh)', 'Wget to shell execution'),
        (r'\bnc\s+-[el]', 'Netcat backdoor'),
        
        # Data exfiltration
        (r'>\s*/dev/tcp/', 'Network redirect'),
        (r'\bscp\s+.*@', 'Remote copy'),
        
        # System modification
        (r'>\s*/etc/', 'System config modification'),
        (r'>\s*/boot/', 'Boot config modification'),
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
        r'\.\./+',
        r'\.\.\\+',
        r'%2e%2e/',
        r'%2e%2e\\',
    ]
    
    @staticmethod
    def sanitize_command(command: str) -> Tuple[str, List[str]]:
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
                logger.warning(f"Dangerous command detected: {command[:100]}")
        
        # Basic sanitization (without breaking legitimate use)
        sanitized = command.strip()
        
        return sanitized, warnings
    
    @staticmethod
    def validate_file_path(path: str) -> Tuple[bool, Optional[str]]:
        """
        Validate file path to prevent path traversal attacks.
        
        Args:
            path: File path to validate
            
        Returns:
            (is_valid, error_message)
        """
        # Check for path traversal
        for pattern in InputSanitizer.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                return False, "Path traversal detected"
        
        # Check for absolute paths to sensitive directories
        path_obj = Path(path).resolve()
        sensitive_dirs = ['/etc', '/boot', '/sys', '/proc', '/dev']
        
        for sensitive_dir in sensitive_dirs:
            if str(path_obj).startswith(sensitive_dir):
                return False, f"Access to {sensitive_dir} is restricted"
        
        return True, None
    
    @staticmethod
    def sanitize_sql_query(query: str) -> Tuple[bool, Optional[str]]:
        """
        Check SQL query for injection attempts.
        
        Args:
            query: SQL query to check
            
        Returns:
            (is_safe, error_message)
        """
        for pattern in InputSanitizer.SQL_INJECTION_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                logger.warning(f"SQL injection attempt detected: {query[:100]}")
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
    def validate_url(url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate URL format and safety.
        
        Args:
            url: URL to validate
            
        Returns:
            (is_valid, error_message)
        """
        # Basic URL validation
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        if not url_pattern.match(url):
            return False, "Invalid URL format"
        
        # Check for suspicious URLs
        suspicious_domains = ['bit.ly', 'tinyurl.com']  # Can be expanded
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
        filename = filename.replace('/', '_').replace('\\', '_')

        # Remove parent directory references
        filename = filename.replace('..', '')

        # Remove special characters
        filename = re.sub(r'[^a-zA-Z0-9._-]', '_', filename)

        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:250] + ('.' + ext if ext else '')

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
    def quote_shell_args(args: List[str]) -> List[str]:
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


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

def test_rate_limiter():
    """Test rate limiter functionality"""
    limiter = RateLimiter(max_requests=5, window_seconds=10)
    
    user_id = 12345
    
    # Should allow first 5 requests
    for i in range(5):
        allowed, msg = limiter.check_limit(user_id)
        assert allowed, f"Request {i+1} should be allowed"
    
    # 6th request should be blocked
    allowed, msg = limiter.check_limit(user_id)
    assert not allowed, "6th request should be blocked"
    assert msg is not None
    
    print("âœ… Rate limiter test passed")


def test_input_sanitizer():
    """Test input sanitizer functionality"""
    
    # Test dangerous command detection
    dangerous_cmd = "rm -rf /"
    sanitized, warnings = InputSanitizer.sanitize_command(dangerous_cmd)
    assert warnings, "Dangerous command should trigger warnings"
    
    # Test path validation
    valid, msg = InputSanitizer.validate_file_path("../../etc/passwd")
    assert not valid, "Path traversal should be detected"
    
    # Test SQL injection detection
    safe, msg = InputSanitizer.sanitize_sql_query("SELECT * FROM users WHERE id = 1")
    assert safe, "Safe query should pass"
    
    unsafe, msg = InputSanitizer.sanitize_sql_query("SELECT * FROM users WHERE id = 1' OR '1'='1")
    assert not unsafe, "SQL injection should be detected"
    
    # Test filename sanitization
    filename = "../../etc/passwd.txt"
    safe_filename = InputSanitizer.sanitize_filename(filename)
    assert '..' not in safe_filename, "Parent refs should be removed"
    assert '/' not in safe_filename, "Path separators should be removed"
    
    print("âœ… Input sanitizer test passed")


if __name__ == "__main__":
    """Run tests"""
    test_rate_limiter()
    test_input_sanitizer()
    print("\nâœ… All security tests passed!")
