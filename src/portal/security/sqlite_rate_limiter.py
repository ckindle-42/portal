"""
SQLite-based Rate Limiter - Concurrent-safe with proper locking
===============================================================

Replaces JSON-based rate limiting with SQLite for:
- Proper concurrent access handling
- ACID guarantees
- Better performance under load
- No race conditions
"""

import sqlite3
import time
import logging
from typing import Tuple, Optional, Dict
from pathlib import Path
from collections import defaultdict

logger = logging.getLogger(__name__)


class SQLiteRateLimiter:
    """
    SQLite-based rate limiter with proper transaction locking

    Architecture:
    - Uses SQLite WAL mode for concurrent reads
    - Atomic transactions prevent race conditions
    - Automatic cleanup of expired entries
    - Violation tracking for abuse detection
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        max_requests: int = 30,
        window_seconds: int = 60
    ):
        """
        Initialize rate limiter

        Args:
            db_path: Path to SQLite database (default: data/rate_limits.db)
            max_requests: Maximum requests allowed per window
            window_seconds: Window duration in seconds
        """
        self.db_path = db_path or Path("data") / "rate_limits.db"
        self.max_requests = max_requests
        self.window = window_seconds

        # Ensure data directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

        logger.info(
            f"SQLiteRateLimiter initialized: {self.db_path} "
            f"({max_requests} requests per {window_seconds}s)"
        )

    def _init_db(self):
        """Initialize database schema with WAL mode for concurrency"""
        with sqlite3.connect(self.db_path) as conn:
            # Enable WAL mode for better concurrent access
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")

            # Create tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limit_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_timestamp
                ON rate_limit_requests(user_id, timestamp DESC)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS rate_limit_violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    violation_count INTEGER DEFAULT 1,
                    last_violation REAL NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_user_violations
                ON rate_limit_violations(user_id)
            """)

            conn.commit()

    def check_limit(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check if user is within rate limit

        Args:
            user_id: User identifier

        Returns:
            (is_allowed, error_message)
        """
        now = time.time()
        window_start = now - self.window

        with sqlite3.connect(self.db_path) as conn:
            # Use IMMEDIATE transaction to prevent race conditions
            conn.execute("BEGIN IMMEDIATE")

            try:
                # Clean up old requests
                conn.execute("""
                    DELETE FROM rate_limit_requests
                    WHERE user_id = ? AND timestamp < ?
                """, (user_id, window_start))

                # Count recent requests
                cursor = conn.execute("""
                    SELECT COUNT(*) FROM rate_limit_requests
                    WHERE user_id = ? AND timestamp >= ?
                """, (user_id, window_start))

                count = cursor.fetchone()[0]

                # Check limit
                if count >= self.max_requests:
                    # Get oldest request in window to calculate wait time
                    cursor = conn.execute("""
                        SELECT MIN(timestamp) FROM rate_limit_requests
                        WHERE user_id = ?
                    """, (user_id,))

                    oldest_timestamp = cursor.fetchone()[0]
                    wait_time = int(oldest_timestamp + self.window - now) if oldest_timestamp else self.window

                    # Record violation
                    self._record_violation(conn, user_id, now)

                    conn.commit()

                    logger.warning(
                        f"Rate limit exceeded for user {user_id} "
                        f"({count}/{self.max_requests} requests)"
                    )

                    return False, f"⏱️ Rate limit exceeded. Please wait {wait_time} seconds."

                # Add current request
                conn.execute("""
                    INSERT INTO rate_limit_requests (user_id, timestamp)
                    VALUES (?, ?)
                """, (user_id, now))

                conn.commit()

                return True, None

            except Exception as e:
                conn.rollback()
                logger.error(f"Rate limit check failed: {e}")
                # Fail open (allow request) to prevent service disruption
                return True, None

    def _record_violation(self, conn: sqlite3.Connection, user_id: int, timestamp: float):
        """Record a rate limit violation"""
        conn.execute("""
            INSERT INTO rate_limit_violations (user_id, violation_count, last_violation)
            VALUES (?, 1, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                violation_count = violation_count + 1,
                last_violation = ?
        """, (user_id, timestamp, timestamp))

    def get_remaining(self, user_id: int) -> int:
        """Get remaining requests for user"""
        now = time.time()
        window_start = now - self.window

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM rate_limit_requests
                WHERE user_id = ? AND timestamp >= ?
            """, (user_id, window_start))

            count = cursor.fetchone()[0]
            return max(0, self.max_requests - count)

    def reset_user(self, user_id: int):
        """Reset rate limit for specific user"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM rate_limit_requests WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM rate_limit_violations WHERE user_id = ?", (user_id,))
            conn.commit()

        logger.info(f"Reset rate limit for user {user_id}")

    def get_stats(self, user_id: int) -> Dict[str, int]:
        """Get statistics for a user"""
        now = time.time()
        window_start = now - self.window

        with sqlite3.connect(self.db_path) as conn:
            # Get recent requests
            cursor = conn.execute("""
                SELECT COUNT(*) FROM rate_limit_requests
                WHERE user_id = ? AND timestamp >= ?
            """, (user_id, window_start))

            recent_requests = cursor.fetchone()[0]

            # Get total requests
            cursor = conn.execute("""
                SELECT COUNT(*) FROM rate_limit_requests
                WHERE user_id = ?
            """, (user_id,))

            total_requests = cursor.fetchone()[0]

            # Get violations
            cursor = conn.execute("""
                SELECT violation_count FROM rate_limit_violations
                WHERE user_id = ?
            """, (user_id,))

            result = cursor.fetchone()
            violations = result[0] if result else 0

        return {
            'total_requests': total_requests,
            'recent_requests': recent_requests,
            'remaining': max(0, self.max_requests - recent_requests),
            'violations': violations
        }

    def cleanup_old_data(self, days_to_keep: int = 7):
        """Remove data older than specified days"""
        cutoff_time = time.time() - (days_to_keep * 86400)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM rate_limit_requests
                WHERE timestamp < ?
            """, (cutoff_time,))

            deleted_requests = cursor.rowcount

            cursor = conn.execute("""
                DELETE FROM rate_limit_violations
                WHERE last_violation < ?
            """, (cutoff_time,))

            deleted_violations = cursor.rowcount

            conn.commit()

        logger.info(
            f"Cleaned up old data: {deleted_requests} requests, "
            f"{deleted_violations} violations"
        )

        return {'requests_deleted': deleted_requests, 'violations_deleted': deleted_violations}

    def get_top_users(self, limit: int = 10) -> list[Dict[str, any]]:
        """Get top users by request count"""
        now = time.time()
        window_start = now - self.window

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT user_id, COUNT(*) as request_count
                FROM rate_limit_requests
                WHERE timestamp >= ?
                GROUP BY user_id
                ORDER BY request_count DESC
                LIMIT ?
            """, (window_start, limit))

            return [
                {'user_id': row[0], 'request_count': row[1]}
                for row in cursor.fetchall()
            ]
