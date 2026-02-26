"""SQLite RBAC and quota store for Portal API users."""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class AuthContext:
    user_id: str
    role: str
    api_key_id: int | None = None


class UserStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or os.getenv("PORTAL_AUTH_DB", "data/auth.db"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._ensure_bootstrap_api_key()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
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
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO users(id, role, created_at) VALUES (?, ?, ?)",
                (user_id, role, now),
            )
            conn.commit()

    def create_api_key(self, user_id: str, name: str = "default") -> str:
        self.ensure_user(user_id)
        token = f"ptl_{secrets.token_urlsafe(24)}"
        key_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO api_keys(user_id, key_hash, name, created_at) VALUES (?, ?, ?, ?)",
                (user_id, key_hash, name, now),
            )
            conn.commit()
        return token

    def authenticate(self, token: str | None, fallback_user: str) -> AuthContext:
        if not token:
            self.ensure_user(fallback_user, role="guest")
            return AuthContext(user_id=fallback_user, role="guest")

        key_hash = hashlib.sha256(token.encode()).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
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

    def _ensure_bootstrap_api_key(self) -> None:
        """Optionally pre-provision a static API key for local/dev stacks."""
        token = os.getenv("PORTAL_BOOTSTRAP_API_KEY")
        if not token:
            return

        user_id = os.getenv("PORTAL_BOOTSTRAP_USER_ID", "open-webui")
        role = os.getenv("PORTAL_BOOTSTRAP_USER_ROLE", "user")
        self.ensure_user(user_id=user_id, role=role)

        key_hash = hashlib.sha256(token.encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO api_keys(user_id, key_hash, name, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, key_hash, "bootstrap", now),
            )
            conn.commit()

    def add_tokens(self, user_id: str, tokens: int) -> None:
        period = datetime.now(timezone.utc).strftime("%Y-%W")
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
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

    def get_tokens(self, user_id: str) -> int:
        period = datetime.now(timezone.utc).strftime("%Y-%W")
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT token_count FROM quotas WHERE user_id = ? AND period = ?",
                (user_id, period),
            ).fetchone()
        return int(row[0]) if row else 0
