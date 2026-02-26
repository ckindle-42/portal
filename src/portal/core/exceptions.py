"""
Custom Exceptions for Portal 4.0
======================================

Structured error handling allows interfaces to handle errors appropriately
based on type rather than parsing strings.

Error Codes:
- 1xxx: Client errors (user input, validation)
- 2xxx: Security errors (auth, rate limiting, policy)
- 3xxx: Resource errors (model unavailable, quota exceeded)
- 4xxx: Execution errors (tool execution, processing)
- 5xxx: System errors (internal, unexpected)
"""

from enum import IntEnum
from typing import Any


class ErrorCode(IntEnum):
    """Structured error codes for user-friendly messages"""

    # 1xxx: Client Errors
    VALIDATION_ERROR = 1001
    INVALID_PARAMETERS = 1002
    CONTEXT_NOT_FOUND = 1003

    # 2xxx: Security Errors
    UNAUTHORIZED = 2001
    POLICY_VIOLATION = 2002
    RATE_LIMIT_EXCEEDED = 2003
    FORBIDDEN = 2004

    # 3xxx: Resource Errors
    MODEL_NOT_AVAILABLE = 3001
    MODEL_QUOTA_EXCEEDED = 3002
    MODEL_BUSY = 3003
    BACKEND_UNAVAILABLE = 3004

    # 4xxx: Execution Errors
    TOOL_EXECUTION_FAILED = 4001
    PROCESSING_FAILED = 4002
    TIMEOUT = 4003

    # 5xxx: System Errors
    INTERNAL_ERROR = 5001
    DATABASE_ERROR = 5002
    CONFIGURATION_ERROR = 5003


class PortalError(Exception):
    """Base exception for all Portal errors"""

    def __init__(
        self,
        message: str,
        error_code: ErrorCode = ErrorCode.INTERNAL_ERROR,
        details: dict[str, Any] | None = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for structured logging"""
        return {
            'error_type': self.__class__.__name__,
            'error_code': int(self.error_code),
            'message': self.message,
            'details': self.details
        }

    def user_message(self) -> str:
        """Get user-friendly error message based on error code"""
        code_messages = {
            ErrorCode.VALIDATION_ERROR: "Invalid input provided",
            ErrorCode.INVALID_PARAMETERS: "Invalid parameters",
            ErrorCode.CONTEXT_NOT_FOUND: "Conversation not found",
            ErrorCode.UNAUTHORIZED: "Authentication required",
            ErrorCode.POLICY_VIOLATION: "Security policy violation",
            ErrorCode.RATE_LIMIT_EXCEEDED: "Rate limit exceeded. Please try again later",
            ErrorCode.FORBIDDEN: "Access forbidden",
            ErrorCode.MODEL_NOT_AVAILABLE: "AI model not available",
            ErrorCode.MODEL_QUOTA_EXCEEDED: "Model quota exceeded",
            ErrorCode.MODEL_BUSY: "Model is busy. Please try again",
            ErrorCode.BACKEND_UNAVAILABLE: "AI backend unavailable",
            ErrorCode.TOOL_EXECUTION_FAILED: "Tool execution failed",
            ErrorCode.PROCESSING_FAILED: "Processing failed",
            ErrorCode.TIMEOUT: "Request timed out",
            ErrorCode.INTERNAL_ERROR: "Internal server error",
            ErrorCode.DATABASE_ERROR: "Database error",
            ErrorCode.CONFIGURATION_ERROR: "Configuration error",
        }
        return f"Error {self.error_code}: {code_messages.get(self.error_code, self.message)}"


class PolicyViolationError(PortalError):
    """Raised when security policy is violated"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.POLICY_VIOLATION, details)


class ModelQuotaExceededError(PortalError):
    """Raised when model quota or rate limit is exceeded"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.MODEL_QUOTA_EXCEEDED, details)


class ModelNotAvailableError(PortalError):
    """Raised when no models are available"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.MODEL_NOT_AVAILABLE, details)


class ToolExecutionError(PortalError):
    """Raised when tool execution fails"""

    def __init__(self, tool_name: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.TOOL_EXECUTION_FAILED, details)
        self.tool_name = tool_name


class AuthorizationError(PortalError):
    """Raised when user is not authorized"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.UNAUTHORIZED, details)


class RateLimitError(PortalError):
    """Raised when rate limit is exceeded"""

    def __init__(self, message: str, retry_after: int, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.RATE_LIMIT_EXCEEDED, details)
        self.retry_after = retry_after


class ContextNotFoundError(PortalError):
    """Raised when conversation context is not found"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.CONTEXT_NOT_FOUND, details)


class ValidationError(PortalError):
    """Raised when input validation fails"""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, ErrorCode.VALIDATION_ERROR, details)
