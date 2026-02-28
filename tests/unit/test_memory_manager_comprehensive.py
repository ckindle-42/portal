"""Comprehensive MemoryManager tests — edge cases, concurrency, context building."""

import asyncio
import sqlite3
from pathlib import Path

import pytest

from portal.memory import MemoryManager
from portal.memory.manager import MemorySnippet

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mm(tmp_path: Path) -> MemoryManager:
    """Fresh MemoryManager backed by a temp SQLite database."""
    return MemoryManager(db_path=tmp_path / "memory.db")


# ---------------------------------------------------------------------------
# Basic CRUD
# ---------------------------------------------------------------------------


class TestBasicCRUD:
    """Verify add/retrieve round-trip for standard inputs."""

    @pytest.mark.asyncio
    async def test_add_and_retrieve(self, mm: MemoryManager) -> None:
        await mm.add_message("u1", "Portal remembers this")
        items = await mm.retrieve("u1", "remembers", limit=3)
        assert len(items) >= 1
        assert "Portal" in items[0].text

    @pytest.mark.asyncio
    async def test_retrieve_returns_memory_snippets(self, mm: MemoryManager) -> None:
        await mm.add_message("u1", "hello world")
        items = await mm.retrieve("u1", "hello")
        assert all(isinstance(s, MemorySnippet) for s in items)
        assert items[0].source == "sqlite"

    @pytest.mark.asyncio
    async def test_multiple_messages_same_user(self, mm: MemoryManager) -> None:
        for i in range(5):
            await mm.add_message("u1", f"message number {i}")
        items = await mm.retrieve("u1", "message", limit=10)
        assert len(items) == 5

    @pytest.mark.asyncio
    async def test_user_isolation(self, mm: MemoryManager) -> None:
        await mm.add_message("u1", "user-one secret")
        await mm.add_message("u2", "user-two secret")
        items_u1 = await mm.retrieve("u1", "secret")
        items_u2 = await mm.retrieve("u2", "secret")
        assert all("user-one" in s.text for s in items_u1)
        assert all("user-two" in s.text for s in items_u2)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Cover boundary / unusual inputs."""

    @pytest.mark.asyncio
    async def test_empty_content_ignored(self, mm: MemoryManager) -> None:
        await mm.add_message("u1", "")
        await mm.add_message("u1", "   ")
        items = await mm.retrieve("u1", "", limit=10)
        assert items == []

    @pytest.mark.asyncio
    async def test_retrieve_no_results(self, mm: MemoryManager) -> None:
        items = await mm.retrieve("nonexistent", "anything")
        assert items == []

    @pytest.mark.asyncio
    async def test_retrieve_respects_limit(self, mm: MemoryManager) -> None:
        for i in range(10):
            await mm.add_message("u1", f"item {i}")
        items = await mm.retrieve("u1", "item", limit=3)
        assert len(items) == 3

    @pytest.mark.asyncio
    async def test_long_query_truncated(self, mm: MemoryManager) -> None:
        """Query strings longer than 200 chars should be safely truncated."""
        await mm.add_message("u1", "short content")
        long_query = "x" * 500
        items = await mm.retrieve("u1", long_query)
        # Should not raise — the manager truncates to 200 chars
        assert isinstance(items, list)

    @pytest.mark.asyncio
    async def test_special_characters_in_content(self, mm: MemoryManager) -> None:
        special = "O'Reilly said: \"100% isn't enough\"; DROP TABLE memories;--"
        await mm.add_message("u1", special)
        items = await mm.retrieve("u1", "O'Reilly")
        assert len(items) == 1
        assert items[0].text == special


# ---------------------------------------------------------------------------
# Context block building
# ---------------------------------------------------------------------------


class TestContextBlock:
    """Verify build_context_block formatting."""

    @pytest.mark.asyncio
    async def test_empty_context_block(self, mm: MemoryManager) -> None:
        block = await mm.build_context_block("u1", "anything")
        assert block == ""

    @pytest.mark.asyncio
    async def test_context_block_format(self, mm: MemoryManager) -> None:
        await mm.add_message("u1", "first memory")
        await mm.add_message("u1", "second memory")
        block = await mm.build_context_block("u1", "memory")
        assert block.startswith("Relevant long-term memory:")
        assert "1." in block
        assert "2." in block

    @pytest.mark.asyncio
    async def test_context_block_contains_content(self, mm: MemoryManager) -> None:
        await mm.add_message("u1", "portal is local-first")
        block = await mm.build_context_block("u1", "local")
        assert "portal is local-first" in block


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


class TestConcurrency:
    """Ensure correctness under concurrent access patterns."""

    @pytest.mark.asyncio
    async def test_concurrent_writes(self, mm: MemoryManager) -> None:
        """Multiple concurrent writes should not lose data."""
        tasks = [mm.add_message("u1", f"concurrent-{i}") for i in range(20)]
        await asyncio.gather(*tasks)
        items = await mm.retrieve("u1", "concurrent", limit=30)
        assert len(items) == 20

    @pytest.mark.asyncio
    async def test_concurrent_reads_and_writes(self, mm: MemoryManager) -> None:
        """Reads and writes running concurrently should not crash."""
        write_tasks = [mm.add_message("u1", f"rw-{i}") for i in range(10)]
        read_tasks = [mm.retrieve("u1", "rw") for _ in range(5)]
        results = await asyncio.gather(*write_tasks, *read_tasks, return_exceptions=True)
        # No exceptions should be raised
        assert not any(isinstance(r, Exception) for r in results)


# ---------------------------------------------------------------------------
# Database integrity
# ---------------------------------------------------------------------------


class TestDatabaseIntegrity:
    """Verify SQLite database structure and WAL mode."""

    def test_wal_mode_enabled(self, mm: MemoryManager) -> None:
        with sqlite3.connect(mm.db_path) as conn:
            journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal == "wal"

    def test_table_exists(self, mm: MemoryManager) -> None:
        with sqlite3.connect(mm.db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='memories'"
            ).fetchall()
        assert len(tables) == 1

    def test_index_exists(self, mm: MemoryManager) -> None:
        with sqlite3.connect(mm.db_path) as conn:
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_memories_user_id'"
            ).fetchall()
        assert len(indexes) == 1

    def test_default_provider_is_sqlite(self, mm: MemoryManager) -> None:
        assert mm.provider == "sqlite"


# ---------------------------------------------------------------------------
# MemorySnippet dataclass
# ---------------------------------------------------------------------------


class TestMemorySnippet:
    """Verify MemorySnippet defaults and fields."""

    def test_defaults(self) -> None:
        s = MemorySnippet(text="hello")
        assert s.text == "hello"
        assert s.score == 0.0
        assert s.source == "sqlite"

    def test_custom_fields(self) -> None:
        s = MemorySnippet(text="data", score=0.95, source="mem0")
        assert s.score == 0.95
        assert s.source == "mem0"


# ---------------------------------------------------------------------------
# R3: TTL-based memory pruning
# ---------------------------------------------------------------------------


class TestMemoryPruning:
    """R3: Old memory entries beyond the retention period must be pruned."""

    @pytest.mark.asyncio
    async def test_prune_removes_old_memories(self, tmp_path: Path) -> None:
        """Memory entries with old created_at timestamps are deleted during prune."""
        import sqlite3

        mm = MemoryManager(db_path=tmp_path / "prune_test.db")

        # Insert a memory directly with an old timestamp (100 days ago)
        old_ts = "2025-10-01 00:00:00"  # definitely older than 90 day default
        with sqlite3.connect(mm.db_path) as conn:
            conn.execute(
                "INSERT INTO memories (user_id, content, created_at) VALUES (?, ?, ?)",
                ("prune_user", "very old memory", old_ts),
            )
            conn.commit()

        import asyncio

        deleted = await asyncio.to_thread(mm._prune_old_memories)
        assert deleted >= 1

        items = await mm.retrieve("prune_user", "old memory")
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_prune_keeps_recent_memories(self, tmp_path: Path) -> None:
        """Recent memories within the retention period are not pruned."""
        mm = MemoryManager(db_path=tmp_path / "recent_test.db")
        await mm.add_message("u1", "recent memory content")

        import asyncio

        deleted = await asyncio.to_thread(mm._prune_old_memories)
        assert deleted == 0

        items = await mm.retrieve("u1", "recent")
        assert len(items) >= 1

    @pytest.mark.asyncio
    async def test_pruning_triggered_after_interval(self, tmp_path: Path) -> None:
        """Pruning is triggered automatically after _PRUNE_INTERVAL inserts."""
        import sqlite3

        mm = MemoryManager(db_path=tmp_path / "auto_prune.db")

        # Insert a very old memory directly
        old_ts = "2025-01-01 00:00:00"
        with sqlite3.connect(mm.db_path) as conn:
            conn.execute(
                "INSERT INTO memories (user_id, content, created_at) VALUES (?, ?, ?)",
                ("prune_auto_user", "stale memory", old_ts),
            )
            conn.commit()

        # Insert exactly _PRUNE_INTERVAL messages to trigger pruning
        for i in range(mm._PRUNE_INTERVAL):
            await mm.add_message("prune_auto_user", f"content {i}")

        # After the interval, the stale memory should have been pruned
        with sqlite3.connect(mm.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE content = 'stale memory'"
            ).fetchone()
        assert row[0] == 0, "Stale memory should have been pruned after _PRUNE_INTERVAL inserts"
