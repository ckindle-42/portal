"""HITL approval middleware with Redis-backed 60s tokens."""

from __future__ import annotations

import os
import secrets
from typing import Awaitable, Callable

import redis

DangerNotifier = Callable[[str, str, str, dict], Awaitable[None]]


class HITLApprovalMiddleware:
    def __init__(self, notifier: DangerNotifier | None = None) -> None:
        self.notifier = notifier
        self.redis = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    async def request(self, user_id: str, channel: str, tool_name: str, args: dict) -> str:
        token = secrets.token_urlsafe(16)
        self.redis.setex(f"portal:approval:{user_id}:{token}", 60, "pending")
        if self.notifier:
            await self.notifier(user_id, channel, token, {"tool": tool_name, "args": args})
        return token

    def check_approved(self, user_id: str, token: str) -> bool:
        value = self.redis.get(f"portal:approval:{user_id}:{token}")
        return value == b"approved"
