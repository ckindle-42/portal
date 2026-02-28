"""Shared SQLite connection pool for Portal modules."""
import sqlite3
import threading
from pathlib import Path


class ConnectionPool:
    """Thread-local SQLite connection cache with configurable PRAGMAs."""

    def __init__(self, db_path: Path, pragmas: tuple[str, ...] = ("PRAGMA journal_mode=WAL",)) -> None:
        self._db_path = db_path
        self._local = threading.local()
        self._pragmas = pragmas

    def get(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self._db_path)
            for pragma in self._pragmas:
                conn.execute(pragma)
            self._local.conn = conn
        return conn
