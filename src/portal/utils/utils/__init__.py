"""
Utility Functions Module
========================

Shared utility functions used across the application.
"""

from typing import Any, Dict
import asyncio
import functools
from datetime import datetime


def format_timestamp(dt: datetime = None) -> str:
    """Format timestamp for logging"""
    if dt is None:
        dt = datetime.now()
    return dt.isoformat()


def truncate_string(s: str, max_length: int = 100) -> str:
    """Truncate string with ellipsis"""
    if len(s) <= max_length:
        return s
    return s[:max_length-3] + "..."


def retry_async(max_attempts: int = 3, delay: float = 1.0):
    """Decorator for retrying async functions"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(delay * (attempt + 1))
            raise last_exception
        return wrapper
    return decorator


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal"""
    import re
    # Remove any path components
    filename = filename.split('/')[-1].split('\\')[-1]
    # Remove potentially dangerous characters
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    return filename


def parse_size_string(size_str: str) -> int:
    """Parse size string like '10MB' to bytes"""
    units = {
        'B': 1,
        'KB': 1024,
        'MB': 1024**2,
        'GB': 1024**3,
    }
    size_str = size_str.upper().strip()
    for unit, multiplier in units.items():
        if size_str.endswith(unit):
            value = float(size_str[:-len(unit)])
            return int(value * multiplier)
    return int(size_str)


__all__ = [
    'format_timestamp',
    'truncate_string',
    'retry_async',
    'sanitize_filename',
    'parse_size_string',
]
