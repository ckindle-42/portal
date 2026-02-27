"""ContextManager tests — history persistence, formatting, limits."""

import asyncio

import pytest

from portal.core.context_manager import ContextManager


@pytest.fixture()
def ctx(tmp_path) -> ContextManager:
    """ContextManager backed by a temp SQLite file."""
    return ContextManager(max_context_messages=10, db_path=tmp_path / "ctx.db")


class TestBasicHistory:
    @pytest.mark.asyncio
    async def test_add_and_get_history(self, ctx: ContextManager) -> None:
        await ctx.add_message("c1", "user", "Hello", "web")
        await ctx.add_message("c1", "assistant", "Hi there", "web")
        history = await ctx.get_history("c1")
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_empty_history(self, ctx: ContextManager) -> None:
        history = await ctx.get_history("nonexistent")
        assert history == []

    @pytest.mark.asyncio
    async def test_chat_isolation(self, ctx: ContextManager) -> None:
        await ctx.add_message("c1", "user", "Chat 1", "web")
        await ctx.add_message("c2", "user", "Chat 2", "web")
        h1 = await ctx.get_history("c1")
        h2 = await ctx.get_history("c2")
        assert len(h1) == 1
        assert len(h2) == 1
        assert "Chat 1" in h1[0].content
        assert "Chat 2" in h2[0].content


class TestLimits:
    @pytest.mark.asyncio
    async def test_history_respects_limit(self, ctx: ContextManager) -> None:
        for i in range(20):
            await ctx.add_message("c1", "user", f"msg {i}", "web")
        history = await ctx.get_history("c1")
        # Default limit is 10
        assert len(history) <= 10

    @pytest.mark.asyncio
    async def test_custom_limit(self, ctx: ContextManager) -> None:
        for i in range(10):
            await ctx.add_message("c1", "user", f"msg {i}", "web")
        history = await ctx.get_history("c1", limit=3)
        assert len(history) == 3


class TestClearHistory:
    @pytest.mark.asyncio
    async def test_clear_removes_messages(self, ctx: ContextManager) -> None:
        await ctx.add_message("c1", "user", "to be deleted", "web")
        await ctx.clear_history("c1")
        history = await ctx.get_history("c1")
        assert history == []

    @pytest.mark.asyncio
    async def test_clear_only_affects_target_chat(self, ctx: ContextManager) -> None:
        await ctx.add_message("c1", "user", "Chat 1", "web")
        await ctx.add_message("c2", "user", "Chat 2", "web")
        await ctx.clear_history("c1")
        assert await ctx.get_history("c1") == []
        assert len(await ctx.get_history("c2")) == 1


class TestFormattedHistory:
    @pytest.mark.asyncio
    async def test_openai_format(self, ctx: ContextManager) -> None:
        await ctx.add_message("c1", "user", "Hello", "web")
        await ctx.add_message("c1", "assistant", "Hi", "web")
        formatted = await ctx.get_formatted_history("c1", format="openai")
        assert isinstance(formatted, list)
        assert formatted[0]["role"] == "user"
        assert formatted[0]["content"] == "Hello"

    @pytest.mark.asyncio
    async def test_anthropic_format(self, ctx: ContextManager) -> None:
        await ctx.add_message("c1", "user", "Hello", "web")
        formatted = await ctx.get_formatted_history("c1", format="anthropic")
        assert isinstance(formatted, list)
        assert formatted[0]["role"] == "user"


class TestExcludeSystem:
    @pytest.mark.asyncio
    async def test_exclude_system_messages(self, ctx: ContextManager) -> None:
        await ctx.add_message("c1", "system", "init", "web")
        await ctx.add_message("c1", "user", "hello", "web")
        history = await ctx.get_history("c1", include_system=False)
        assert len(history) == 1
        assert history[0].role == "user"

    @pytest.mark.asyncio
    async def test_include_system_messages(self, ctx: ContextManager) -> None:
        await ctx.add_message("c1", "system", "init", "web")
        await ctx.add_message("c1", "user", "hello", "web")
        history = await ctx.get_history("c1", include_system=True)
        assert len(history) == 2


class TestFormattedHistoryExtended:
    @pytest.mark.asyncio
    async def test_anthropic_excludes_system(self, ctx: ContextManager) -> None:
        await ctx.add_message("c1", "system", "sys prompt", "web")
        await ctx.add_message("c1", "user", "hello", "web")
        await ctx.add_message("c1", "assistant", "hi", "web")
        formatted = await ctx.get_formatted_history("c1", format="anthropic")
        roles = [m["role"] for m in formatted]
        assert "system" not in roles
        assert len(formatted) == 2

    @pytest.mark.asyncio
    async def test_unsupported_format_raises(self, ctx: ContextManager) -> None:
        await ctx.add_message("c1", "user", "hi", "web")
        with pytest.raises(ValueError, match="Unsupported format"):
            await ctx.get_formatted_history("c1", format="invalid")


class TestMessageMetadata:
    @pytest.mark.asyncio
    async def test_add_with_metadata(self, ctx: ContextManager) -> None:
        await ctx.add_message("c1", "user", "hello", "web", metadata={"lang": "en"})
        history = await ctx.get_history("c1")
        assert history[0].metadata == {"lang": "en"}

    @pytest.mark.asyncio
    async def test_default_metadata_is_empty_dict(self, ctx: ContextManager) -> None:
        await ctx.add_message("c1", "user", "hello", "web")
        history = await ctx.get_history("c1")
        assert history[0].metadata == {}


class TestMessageDataclass:
    def test_to_dict(self) -> None:
        from portal.core.context_manager import Message

        msg = Message(role="user", content="hi", timestamp="t", interface="web", metadata={})
        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "hi"


class TestConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_writes(self, ctx: ContextManager) -> None:
        tasks = [ctx.add_message("c1", "user", f"concurrent-{i}", "web") for i in range(15)]
        await asyncio.gather(*tasks)
        history = await ctx.get_history("c1", limit=100)
        assert len(history) == 15


# ---------------------------------------------------------------------------
# R2: TTL-based message pruning
# ---------------------------------------------------------------------------


class TestMessagePruning:
    """R2: Old messages beyond the retention period must be pruned."""

    @pytest.mark.asyncio
    async def test_prune_removes_old_messages(self, tmp_path) -> None:
        """Messages with old timestamps are deleted during a prune run."""
        import sqlite3
        from datetime import UTC, datetime, timedelta

        ctx = ContextManager(db_path=tmp_path / "prune_test.db", max_context_messages=100)

        # Insert a message directly with an old timestamp (40 days ago)
        old_ts = (datetime.now(tz=UTC) - timedelta(days=40)).isoformat()
        with sqlite3.connect(ctx.db_path) as conn:
            conn.execute(
                "INSERT INTO conversations (chat_id, role, content, timestamp, interface, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("prune_chat", "user", "old message", old_ts, "web", "{}"),
            )
            conn.commit()

        # Trigger pruning directly
        deleted = await asyncio.to_thread(ctx._sync_prune_old_messages)
        assert deleted >= 1

        # The message should be gone
        history = await ctx.get_history("prune_chat", limit=100)
        assert len(history) == 0

    @pytest.mark.asyncio
    async def test_prune_keeps_recent_messages(self, tmp_path) -> None:
        """Messages within the retention period must not be pruned."""
        ctx = ContextManager(db_path=tmp_path / "keep_test.db", max_context_messages=100)
        await ctx.add_message("keep_chat", "user", "recent message", "web")

        deleted = await asyncio.to_thread(ctx._sync_prune_old_messages)
        assert deleted == 0  # nothing old to remove

        history = await ctx.get_history("keep_chat", limit=100)
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_pruning_triggered_after_interval(self, tmp_path) -> None:
        """Pruning is triggered automatically after _PRUNE_INTERVAL inserts."""
        import sqlite3
        from datetime import UTC, datetime, timedelta

        ctx = ContextManager(db_path=tmp_path / "auto_prune.db", max_context_messages=1000)

        # Insert a very old message directly into the DB
        old_ts = (datetime.now(tz=UTC) - timedelta(days=40)).isoformat()
        with sqlite3.connect(ctx.db_path) as conn:
            conn.execute(
                "INSERT INTO conversations (chat_id, role, content, timestamp, interface, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("auto_chat", "user", "stale", old_ts, "web", "{}"),
            )
            conn.commit()

        # Insert exactly _PRUNE_INTERVAL messages to trigger pruning
        for i in range(ctx._PRUNE_INTERVAL):
            await ctx.add_message("auto_chat", "user", f"msg-{i}", "web")

        # After the interval, the stale message should have been pruned
        import sqlite3 as _sqlite3

        with _sqlite3.connect(ctx.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM conversations WHERE content = 'stale'"
            ).fetchone()
        assert row[0] == 0, "Stale message should have been pruned after _PRUNE_INTERVAL inserts"
