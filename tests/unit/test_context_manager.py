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


class TestConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_writes(self, ctx: ContextManager) -> None:
        tasks = [ctx.add_message("c1", "user", f"concurrent-{i}", "web") for i in range(15)]
        await asyncio.gather(*tasks)
        history = await ctx.get_history("c1", limit=100)
        assert len(history) == 15
