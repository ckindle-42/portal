"""
Structured Logging with Trace IDs
=================================

Provides JSON-structured logging with request tracing capabilities.
Makes it easy to debug complex failures by following a request through
the entire system.
"""

import json
import logging
import re
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime

# Context variable to store trace_id for current request
_trace_id_var: ContextVar[str | None] = ContextVar('trace_id', default=None)

_SECRET_PATTERNS = re.compile(
    r"(xoxb-[A-Za-z0-9-]+|sk-[A-Za-z0-9]+|bot\d+:[A-Za-z0-9_-]+|"
    r"ghp_[A-Za-z0-9]+|Bearer\s+[A-Za-z0-9._~+/=-]+)",
    re.IGNORECASE,
)


def _redact_secrets(text: str) -> str:
    return _SECRET_PATTERNS.sub("[REDACTED]", text)


class StructuredLogger:
    """
    Structured logger that outputs JSON logs with trace IDs

    Example output:
    {
        "timestamp": "2025-12-17T10:30:45.123Z",
        "level": "INFO",
        "trace_id": "abc123",
        "component": "AgentCore",
        "message": "Processing message",
        "chat_id": "telegram_12345",
        "interface": "telegram",
        "execution_time_ms": 1234.56
    }
    """

    def __init__(self, component: str, logger: logging.Logger | None = None) -> None:
        """
        Initialize structured logger

        Args:
            component: Component name (e.g., 'AgentCore', 'Router', 'Security')
            logger: Optional existing logger (creates new if not provided)
        """
        self.component = component
        self.logger = logger or logging.getLogger(component)

    def _log(self, level: str, message: str, **kwargs) -> None:
        """
        Internal logging method

        Args:
            level: Log level ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
            message: Log message
            **kwargs: Additional structured fields
        """
        # Get current trace_id from context
        trace_id = _trace_id_var.get()

        # Build structured log entry
        log_entry = {
            'timestamp': datetime.now(tz=UTC).isoformat(),
            'level': level,
            'component': self.component,
            'message': _redact_secrets(message),
        }

        # Add trace_id if available
        if trace_id:
            log_entry['trace_id'] = trace_id

        # Add additional fields, redacting string values
        for k, v in kwargs.items():
            log_entry[k] = _redact_secrets(str(v)) if isinstance(v, str) else v

        # Convert to JSON
        json_log = _redact_secrets(json.dumps(log_entry))

        # Log at appropriate level
        log_method = getattr(self.logger, level.lower())
        log_method(json_log)

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message"""
        self._log('DEBUG', message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message"""
        self._log('INFO', message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message"""
        self._log('WARNING', message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message"""
        self._log('ERROR', message, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """Log critical message"""
        self._log('CRITICAL', message, **kwargs)


class TraceContext:
    """
    Context manager for setting trace_id for a request

    Usage:
        with TraceContext() as trace_id:
            # All logs within this context will include this trace_id
            logger.info("Processing request")
    """

    def __init__(self, trace_id: str | None = None) -> None:
        """
        Initialize trace context

        Args:
            trace_id: Optional trace ID (generates new UUID if not provided)
        """
        self.trace_id = trace_id or self._generate_trace_id()
        self.token = None

    def __enter__(self) -> str:
        """Enter trace context"""
        self.token = _trace_id_var.set(self.trace_id)
        return self.trace_id

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit trace context"""
        _trace_id_var.reset(self.token)

    @staticmethod
    def _generate_trace_id() -> str:
        """Generate a unique trace ID"""
        return str(uuid.uuid4())[:8]  # Short UUID



# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_logger(component: str) -> StructuredLogger:
    """
    Get a structured logger for a component

    Args:
        component: Component name

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(component)


