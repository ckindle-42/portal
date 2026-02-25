"""
Structured Logging with Trace IDs
=================================

Provides JSON-structured logging with request tracing capabilities.
Makes it easy to debug complex failures by following a request through
the entire system.
"""

import logging
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from contextvars import ContextVar

# Context variable to store trace_id for current request
_trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)


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

    def __init__(self, component: str, logger: Optional[logging.Logger] = None):
        """
        Initialize structured logger

        Args:
            component: Component name (e.g., 'AgentCore', 'Router', 'Security')
            logger: Optional existing logger (creates new if not provided)
        """
        self.component = component
        self.logger = logger or logging.getLogger(component)

    def _log(self, level: str, message: str, **kwargs):
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
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'component': self.component,
            'message': message,
        }

        # Add trace_id if available
        if trace_id:
            log_entry['trace_id'] = trace_id

        # Add additional fields
        log_entry.update(kwargs)

        # Convert to JSON
        json_log = json.dumps(log_entry)

        # Log at appropriate level
        log_method = getattr(self.logger, level.lower())
        log_method(json_log)

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self._log('DEBUG', message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message"""
        self._log('INFO', message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self._log('WARNING', message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message"""
        self._log('ERROR', message, **kwargs)

    def critical(self, message: str, **kwargs):
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

    def __init__(self, trace_id: Optional[str] = None):
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

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit trace context"""
        _trace_id_var.reset(self.token)

    @staticmethod
    def _generate_trace_id() -> str:
        """Generate a unique trace ID"""
        return str(uuid.uuid4())[:8]  # Short UUID

    @staticmethod
    def get_current_trace_id() -> Optional[str]:
        """Get current trace ID from context"""
        return _trace_id_var.get()


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


def set_trace_id(trace_id: str):
    """
    Manually set trace_id for current context

    Args:
        trace_id: Trace ID to set
    """
    _trace_id_var.set(trace_id)


def get_trace_id() -> Optional[str]:
    """Get current trace ID"""
    return _trace_id_var.get()


# =============================================================================
# LOG PARSER UTILITY
# =============================================================================

class LogParser:
    """
    Utility for parsing and querying structured logs

    Useful for debugging and analysis
    """

    @staticmethod
    def parse_log_file(file_path: str) -> list[Dict[str, Any]]:
        """
        Parse a log file containing JSON logs

        Args:
            file_path: Path to log file

        Returns:
            List of parsed log entries
        """
        entries = []

        with open(file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    # Try to parse as JSON
                    entry = json.loads(line)
                    entries.append(entry)
                except json.JSONDecodeError:
                    # Skip non-JSON lines
                    continue

        return entries

    @staticmethod
    def filter_by_trace_id(entries: list[Dict[str, Any]], trace_id: str) -> list[Dict[str, Any]]:
        """
        Filter log entries by trace_id

        Args:
            entries: List of log entries
            trace_id: Trace ID to filter by

        Returns:
            Filtered log entries
        """
        return [e for e in entries if e.get('trace_id') == trace_id]

    @staticmethod
    def filter_by_component(entries: list[Dict[str, Any]], component: str) -> list[Dict[str, Any]]:
        """
        Filter log entries by component

        Args:
            entries: List of log entries
            component: Component name to filter by

        Returns:
            Filtered log entries
        """
        return [e for e in entries if e.get('component') == component]

    @staticmethod
    def get_trace_timeline(entries: list[Dict[str, Any]], trace_id: str) -> str:
        """
        Generate a timeline view for a trace_id

        Args:
            entries: List of log entries
            trace_id: Trace ID to trace

        Returns:
            Human-readable timeline string
        """
        trace_entries = LogParser.filter_by_trace_id(entries, trace_id)

        if not trace_entries:
            return f"No logs found for trace_id: {trace_id}"

        # Sort by timestamp
        trace_entries.sort(key=lambda e: e.get('timestamp', ''))

        # Build timeline
        lines = [f"Trace Timeline: {trace_id}", "=" * 60]

        for entry in trace_entries:
            timestamp = entry.get('timestamp', 'N/A')
            component = entry.get('component', 'Unknown')
            level = entry.get('level', 'INFO')
            message = entry.get('message', '')

            line = f"[{timestamp}] {component:15s} {level:8s} {message}"
            lines.append(line)

        return '\n'.join(lines)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    # Configure root logger for JSON output
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(message)s'  # Just output the message (which is JSON)
    )

    # Create component loggers
    core_logger = get_logger('AgentCore')
    router_logger = get_logger('Router')

    # Example: Processing a request with trace context
    with TraceContext() as trace_id:
        core_logger.info(
            "Processing message",
            chat_id="telegram_123",
            interface="telegram",
            message_length=42
        )

        router_logger.info(
            "Selected model",
            model="qwen2.5-7b",
            complexity="moderate",
            reasoning="balanced_quality_speed"
        )

        core_logger.info(
            "Processing completed",
            execution_time_ms=1234.56,
            tokens_generated=150
        )

    # All three logs will have the same trace_id!
