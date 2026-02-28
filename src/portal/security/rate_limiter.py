"""Rate Limiter — per-user sliding-window rate limiting with persistence."""

import asyncio
import atexit
import json
import logging
import os
import shutil
import tempfile
import time
from collections import defaultdict
from pathlib import Path

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
