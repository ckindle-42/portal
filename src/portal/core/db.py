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

    def close(self) -> None:
        """Close the thread-local connection if it exists."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None


def get_connection(
    path: Path | str,
    pragmas: tuple[str, ...] = ("PRAGMA journal_mode=WAL",),
) -> sqlite3.Connection:
    """Create a one-off SQLite connection with the given pragmas.

    Use for infrequent operations (schema init, migrations).
    For hot paths, prefer :class:`ConnectionPool`.
    """
    conn = sqlite3.connect(path)
    for pragma in pragmas:
        conn.execute(pragma)
    return conn
