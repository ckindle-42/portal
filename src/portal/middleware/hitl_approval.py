"""HITL approval middleware with Redis-backed 60s tokens."""

from __future__ import annotations

import logging
import os
import secrets
from collections.abc import Awaitable, Callable

try:
    import redis as _redis
except ImportError:  # pragma: no cover
    _redis = None  # type: ignore[assignment]

from portal.core.exceptions import ToolExecutionError

DangerNotifier = Callable[[str, str, str, dict], Awaitable[None]]

logger = logging.getLogger(__name__)


class HITLApprovalMiddleware:
    def __init__(self, notifier: DangerNotifier | None = None) -> None:
        self.notifier = notifier
        self._redis = None

    @property
    def redis(self):
        if _redis is None:
            raise RuntimeError(
                "redis package is required for HITL approval. "
                "Install it with: pip install redis"
            )
        if self._redis is None:
            self._redis = _redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        return self._redis

    async def request(self, user_id: str, channel: str, tool_name: str, args: dict) -> str:
        try:
            token = secrets.token_urlsafe(16)
            self.redis.setex(f"portal:approval:{user_id}:{token}", 60, "pending")
            if self.notifier:
                await self.notifier(user_id, channel, token, {"tool": tool_name, "args": args})
            return token
        except _redis.ConnectionError:
            logger.warning("Redis unavailable for HITL approval — denying tool execution")
            raise ToolExecutionError(tool_name, "HITL approval requires Redis but Redis is unavailable")

    def check_approved(self, user_id: str, token: str) -> bool:
        try:
            value = self.redis.get(f"portal:approval:{user_id}:{token}")
            return value == b"approved"
        except _redis.ConnectionError:
            logger.warning("Redis unavailable when checking HITL approval token")
            return False
