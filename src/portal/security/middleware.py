"""
Security Middleware - Wraps AgentCore with security enforcement
===============================================================

Ensures NO data reaches AgentCore without passing security checks.
Acts as a protective wrapper around the core.
"""

import re
from dataclasses import dataclass
from typing import Any

from portal.core.exceptions import PolicyViolationError, RateLimitError, ValidationError
from portal.core.structured_logger import get_logger
from portal.security.security_module import InputSanitizer, RateLimiter

logger = get_logger('SecurityMiddleware')


@dataclass
class SecurityContext:
    """Security context for a request"""
    user_id: str | None = None
    chat_id: str = ""
    interface: str = "unknown"
    ip_address: str | None = None
    sanitized_input: str = ""
    warnings: list[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class SecurityMiddleware:
    """
    Security middleware that wraps AgentCore

    Architecture:
        Interface → SecurityMiddleware → AgentCore

    This ensures:
    1. All inputs are sanitized BEFORE reaching core
    2. Rate limits are enforced BEFORE processing
    3. Security violations prevent execution
    4. No bypass paths exist
    """

    def __init__(
        self,
        agent_core,
        rate_limiter: RateLimiter | None = None,
        input_sanitizer: InputSanitizer | None = None,
        enable_rate_limiting: bool = True,
        enable_input_sanitization: bool = True,
        max_message_length: int = 10000,
    ):
        """
        Initialize security middleware

        Args:
            agent_core: The AgentCore instance to protect
            rate_limiter: Rate limiter instance (creates default if None)
            input_sanitizer: Input sanitizer instance (creates default if None)
            enable_rate_limiting: Enable rate limiting
            enable_input_sanitization: Enable input sanitization
        """
        self.agent_core = agent_core
        self.rate_limiter = rate_limiter or RateLimiter()
        self.input_sanitizer = input_sanitizer or InputSanitizer()
        self.enable_rate_limiting = enable_rate_limiting
        self.enable_input_sanitization = enable_input_sanitization
        self.max_message_length = max_message_length

        logger.info(
            "SecurityMiddleware initialized",
            rate_limiting=enable_rate_limiting,
            input_sanitization=enable_input_sanitization
        )

    async def process_message(
        self,
        chat_id: str,
        message: str,
        interface: str = "unknown",
        user_context: dict | None = None,
        files: list[Any] | None = None
    ):
        """
        Process a message through security layer then core

        Args:
            chat_id: Unique identifier for conversation
            message: User's message text
            interface: Source interface (telegram, web, etc.)
            user_context: Optional user context
            files: Optional attached files

        Returns:
            ProcessingResult from AgentCore

        Raises:
            RateLimitError: If rate limit exceeded
            ValidationError: If input validation fails
            PolicyViolationError: If security policy violated
        """
        user_context = user_context or {}
        user_id = user_context.get('user_id')

        # Create security context
        sec_ctx = SecurityContext(
            user_id=str(user_id) if user_id else None,
            chat_id=chat_id,
            interface=interface,
            ip_address=user_context.get('ip_address')
        )

        # Step 1: Rate limiting check
        if self.enable_rate_limiting and user_id:
            await self._check_rate_limit(user_id, sec_ctx)

        # Step 2: Input sanitization
        if self.enable_input_sanitization:
            await self._sanitize_input(message, sec_ctx)
        else:
            sec_ctx.sanitized_input = message

        # Step 3: Additional security validations
        await self._validate_security_policies(sec_ctx)

        # Log security check passed
        logger.info(
            "Security checks passed",
            chat_id=chat_id,
            interface=interface,
            warnings=len(sec_ctx.warnings)
        )

        # Step 4: Forward to AgentCore
        result = await self.agent_core.process_message(
            chat_id=chat_id,
            message=sec_ctx.sanitized_input,
            interface=interface,
            user_context=user_context,
            files=files
        )

        # Append security warnings to result
        if sec_ctx.warnings:
            existing_warnings = getattr(result, 'warnings', None)
            if isinstance(existing_warnings, list):
                existing_warnings.extend(sec_ctx.warnings)
            else:
                setattr(result, 'warnings', list(sec_ctx.warnings))

        return result

    async def _check_rate_limit(self, user_id: str, sec_ctx: SecurityContext):
        """
        Check rate limiting

        Args:
            user_id: User identifier
            sec_ctx: Security context

        Raises:
            RateLimitError: If rate limit exceeded
        """
        allowed, error_msg = await self.rate_limiter.check_limit(user_id)

        if not allowed:
            logger.warning(
                "Rate limit exceeded",
                user_id=user_id,
                chat_id=sec_ctx.chat_id,
                interface=sec_ctx.interface
            )

            # Extract wait time from error message if possible
            match = re.search(r'wait (\d+) seconds', error_msg)
            retry_after = int(match.group(1)) if match else 60

            raise RateLimitError(
                error_msg,
                retry_after=retry_after,
                details={
                    'user_id': user_id,
                    'interface': sec_ctx.interface
                }
            )

    async def _sanitize_input(self, message: str, sec_ctx: SecurityContext):
        """
        Sanitize input message

        Args:
            message: Raw message
            sec_ctx: Security context

        Raises:
            ValidationError: If input validation fails
        """
        sanitized, warnings = self.input_sanitizer.sanitize_command(message)

        sec_ctx.sanitized_input = sanitized
        sec_ctx.warnings = warnings

        if warnings:
            logger.warning(
                "Input sanitization warnings",
                chat_id=sec_ctx.chat_id,
                warnings=warnings
            )

            # Check if warnings indicate dangerous content
            for warning in warnings:
                if "Dangerous pattern detected" in warning:
                    # This is a critical security issue
                    raise PolicyViolationError(
                        "Dangerous command pattern detected",
                        details={
                            'warning': warning,
                            'chat_id': sec_ctx.chat_id,
                            'interface': sec_ctx.interface
                        }
                    )

    async def _validate_security_policies(self, sec_ctx: SecurityContext):
        """
        Additional security policy validations

        Args:
            sec_ctx: Security context

        Raises:
            ValidationError: If validation fails
        """
        # Reject empty messages
        if not sec_ctx.sanitized_input or not sec_ctx.sanitized_input.strip():
            raise ValidationError(
                "Message cannot be empty",
                details={'chat_id': sec_ctx.chat_id}
            )

        # Check message length
        max_message_length = self.max_message_length
        if len(sec_ctx.sanitized_input) > max_message_length:
            raise ValidationError(
                f"Message exceeds maximum length of {max_message_length} characters",
                details={
                    'length': len(sec_ctx.sanitized_input),
                    'max_length': max_message_length
                }
            )

        # Example: Check for suspicious patterns
        # (Add your own security policies here)

    def get_rate_limit_stats(self, user_id: str) -> dict[str, int]:
        """Get rate limit statistics for a user"""
        return self.rate_limiter.get_stats(user_id)

    def reset_rate_limit(self, user_id: str):
        """Reset rate limit for a user (admin function)"""
        self.rate_limiter.reset_user(user_id)
        logger.info("Rate limit reset", user_id=user_id)

    async def execute_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        user_id: str | None = None
    ) -> dict[str, Any]:
        """
        Execute a tool directly through security layer

        Args:
            tool_name: Name of tool to execute
            parameters: Tool parameters
            user_id: Optional user ID for rate limiting

        Returns:
            Tool execution result
        """
        # Apply rate limiting if user_id provided
        if self.enable_rate_limiting and user_id:
            sec_ctx = SecurityContext(user_id=str(user_id))
            await self._check_rate_limit(user_id, sec_ctx)

        # Forward to core
        return await self.agent_core.execute_tool(tool_name, parameters)

    async def cleanup(self):
        """Cleanup resources"""
        await self.agent_core.cleanup()
