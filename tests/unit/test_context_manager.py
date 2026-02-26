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

    def test_from_dict(self) -> None:
        from portal.core.context_manager import Message
        d = {"role": "assistant", "content": "hey", "timestamp": "t", "interface": "api", "metadata": {}}
        msg = Message.from_dict(d)
        assert msg.role == "assistant"
        assert msg.interface == "api"

    def test_roundtrip(self) -> None:
        from portal.core.context_manager import Message
        msg = Message(role="system", content="init", timestamp="ts", interface="telegram", metadata={"k": "v"})
        msg2 = Message.from_dict(msg.to_dict())
        assert msg == msg2


class TestConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_writes(self, ctx: ContextManager) -> None:
        tasks = [ctx.add_message("c1", "user", f"concurrent-{i}", "web") for i in range(15)]
        await asyncio.gather(*tasks)
        history = await ctx.get_history("c1", limit=100)
        assert len(history) == 15
