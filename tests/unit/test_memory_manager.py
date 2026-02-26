import asyncio

from portal.memory import MemoryManager


def test_memory_manager_sqlite_roundtrip(tmp_path):
    async def _run():
        mm = MemoryManager(db_path=tmp_path / "memory.db")
        await mm.add_message("u1", "portal remembers this")
        items = await mm.retrieve("u1", "remembers", limit=3)
        assert items
        assert "portal" in items[0].text

    asyncio.run(_run())
