"""SQLite RBAC and quota store for Portal API users."""

from __future__ import annotations

import asyncio
import hashlib
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from portal.core.db import ConnectionPool


@dataclass(slots=True)
class AuthContext:
    user_id: str
    role: str
    api_key_id: int | None = None


class UserStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or os.getenv("PORTAL_AUTH_DB", "data/auth.db"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._pool = ConnectionPool(self.db_path, pragmas=("PRAGMA journal_mode=WAL", "PRAGMA foreign_keys=ON"))
        self._init_db()
        self._ensure_bootstrap_api_key()

    def _init_db(self) -> None:
        conn = self._pool.get()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                name TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS quotas (
                user_id TEXT NOT NULL,
                period TEXT NOT NULL,
                token_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY(user_id, period),
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            """
        )
        conn.commit()

    def ensure_user(self, user_id: str, role: str = "user") -> None:
        now = datetime.now(UTC).isoformat()
        conn = self._pool.get()
        conn.execute(
            "INSERT OR IGNORE INTO users(id, role, created_at) VALUES (?, ?, ?)",
            (user_id, role, now),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Private sync helpers (called via asyncio.to_thread)
    # ------------------------------------------------------------------

    def _sync_authenticate(self, token: str | None, fallback_user: str) -> AuthContext:
        if not token:
            self.ensure_user(fallback_user, role="guest")
            return AuthContext(user_id=fallback_user, role="guest")

        key_hash = hashlib.sha256(token.encode()).hexdigest()
        conn = self._pool.get()
        row = conn.execute(
            """
            SELECT api_keys.id, users.id, users.role
            FROM api_keys JOIN users ON users.id = api_keys.user_id
            WHERE api_keys.key_hash = ?
            """,
            (key_hash,),
        ).fetchone()
        if not row:
            raise ValueError("Invalid API key")
        return AuthContext(api_key_id=row[0], user_id=row[1], role=row[2])

    def _sync_add_tokens(self, user_id: str, tokens: int) -> None:
        period = datetime.now(UTC).strftime("%Y-%W")
        now = datetime.now(UTC).isoformat()
        conn = self._pool.get()
        conn.execute(
            """
            INSERT INTO quotas(user_id, period, token_count, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, period)
            DO UPDATE SET token_count = token_count + excluded.token_count, updated_at = excluded.updated_at
            """,
            (user_id, period, tokens, now),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Public async API
    # ------------------------------------------------------------------

    async def authenticate(self, token: str | None, fallback_user: str) -> AuthContext:
        return await asyncio.to_thread(self._sync_authenticate, token, fallback_user)

    async def add_tokens(self, user_id: str, tokens: int) -> None:
        await asyncio.to_thread(self._sync_add_tokens, user_id, tokens)

    def _ensure_bootstrap_api_key(self) -> None:
        """Optionally pre-provision a static API key for local/dev stacks."""
        token = os.getenv("PORTAL_BOOTSTRAP_API_KEY")
        if not token:
            return

        user_id = os.getenv("PORTAL_BOOTSTRAP_USER_ID", "open-webui")
        role = os.getenv("PORTAL_BOOTSTRAP_USER_ROLE", "user")
        self.ensure_user(user_id=user_id, role=role)

        key_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.now(UTC).isoformat()
        conn = self._pool.get()
        conn.execute(
            """
            INSERT OR IGNORE INTO api_keys(user_id, key_hash, name, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, key_hash, "bootstrap", now),
        )
        conn.commit()
