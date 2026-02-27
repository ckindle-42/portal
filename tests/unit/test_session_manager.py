"""Tests for portal.tools.dev_tools.session_manager."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from portal.tools.dev_tools.session_manager import ExecutionSession, SessionManager

pytestmark = pytest.mark.usefixtures("_patch_session_manager_logger")


@pytest.fixture(autouse=True)
def _patch_session_manager_logger():
    with patch("portal.tools.dev_tools.session_manager.logger", new_callable=MagicMock):
        yield


class TestExecutionSession:
    def test_default_fields(self):
        s = ExecutionSession(session_id="s1", chat_id="c1")
        assert s.session_id == "s1" and s.chat_id == "c1"
        assert isinstance(s.created_at, datetime) and isinstance(s.last_used_at, datetime)
        assert s.container_id is None and s.kernel_id is None
        assert s.execution_count == 0 and s.variables == {}

    def test_touch_updates_timestamp(self):
        s = ExecutionSession(session_id="s1", chat_id="c1")
        old_ts = s.last_used_at
        s.touch()
        assert s.last_used_at >= old_ts

    @pytest.mark.parametrize("age_min,timeout_min,expected_idle", [
        (60, 30, True),    # old enough → idle
        (5, 30, False),    # fresh → not idle
        (10, 5, True),     # over custom timeout → idle
        (10, 15, False),   # under custom timeout → not idle
    ])
    def test_is_idle(self, age_min, timeout_min, expected_idle):
        s = ExecutionSession(session_id="s1", chat_id="c1")
        s.last_used_at = datetime.now(tz=UTC) - timedelta(minutes=age_min)
        assert s.is_idle(idle_timeout_minutes=timeout_min) is expected_idle

    def test_variables_are_independent(self):
        s1, s2 = ExecutionSession("s1", "c1"), ExecutionSession("s2", "c2")
        s1.variables["x"] = 42
        assert "x" not in s2.variables


class TestSessionManagerInit:
    def test_default_config(self):
        mgr = SessionManager()
        assert mgr.idle_timeout_minutes == 30 and mgr.max_sessions == 100
        assert mgr.backend == "docker" and mgr._sessions == {}

    def test_custom_config(self):
        mgr = SessionManager(idle_timeout_minutes=10, max_sessions=5, backend="jupyter")
        assert mgr.idle_timeout_minutes == 10 and mgr.max_sessions == 5 and mgr.backend == "jupyter"


class TestSessionManagerLifecycle:
    async def test_start_creates_task(self):
        mgr = SessionManager()
        await mgr.start()
        assert mgr._cleanup_task is not None and not mgr._cleanup_task.done()
        await mgr.stop()

    async def test_start_idempotent(self):
        mgr = SessionManager()
        await mgr.start()
        t = mgr._cleanup_task
        await mgr.start()
        assert mgr._cleanup_task is t
        await mgr.stop()

    async def test_stop(self):
        mgr = SessionManager()
        s = ExecutionSession(session_id="s1", chat_id="c1", container_id="ctr1")
        mgr._sessions["c1"] = s
        await mgr.stop()
        assert mgr._shutdown is True and len(mgr._sessions) == 0

    async def test_stop_without_start(self):
        mgr = SessionManager()
        await mgr.stop()  # must not raise
        assert mgr._shutdown is True


class TestSessionManagerExecute:
    @pytest.mark.parametrize("backend,id_attr", [
        ("docker", "container_id"),
    ])
    async def test_execute_creates_session(self, backend, id_attr):
        mgr = SessionManager(backend=backend)
        result = await mgr.execute("chat1", "x = 1")
        assert "chat1" in mgr._sessions
        assert result["output"].startswith("Executed:")
        assert result["error"] == "" and result["execution_count"] == 1
        assert getattr(mgr._sessions["chat1"], id_attr).startswith("placeholder-")

    async def test_execute_reuses_session(self):
        mgr = SessionManager(backend="docker")
        await mgr.execute("chat1", "x = 1")
        await mgr.execute("chat1", "print(x)")
        assert mgr._sessions["chat1"].execution_count == 2

    async def test_result_structure(self):
        mgr = SessionManager(backend="docker")
        result = await mgr.execute("chat1", "hello")
        assert {"output", "error", "result", "execution_count"} <= set(result.keys())

    async def test_unknown_backend_error(self):
        mgr = SessionManager(backend="unknown_backend")
        result = await mgr.execute("chat1", "x = 1")
        assert "Unknown backend" in result["error"] and result["output"] == ""
        assert result["execution_count"] == 0

    async def test_long_code_truncated(self):
        mgr = SessionManager(backend="docker")
        result = await mgr.execute("chat1", "a" * 200)
        assert "..." in result["output"]

    async def test_separate_chats_get_separate_sessions(self):
        mgr = SessionManager(backend="docker")
        await mgr.execute("chat_a", "pass")
        await mgr.execute("chat_b", "pass")
        assert mgr._sessions["chat_a"].session_id != mgr._sessions["chat_b"].session_id
        assert uuid.UUID(mgr._sessions["chat_a"].session_id)


class TestSessionManagerMaxSessions:
    async def test_evicts_oldest_on_overflow(self):
        mgr = SessionManager(max_sessions=2, backend="docker")
        await mgr.execute("chat_a", "a = 1")
        mgr._sessions["chat_a"].last_used_at = datetime.now(tz=UTC) - timedelta(hours=1)
        await mgr.execute("chat_b", "b = 1")
        await mgr.execute("chat_c", "c = 1")
        assert "chat_a" not in mgr._sessions
        assert "chat_b" in mgr._sessions and "chat_c" in mgr._sessions

    async def test_cleanup_oldest_on_empty_sessions(self):
        await SessionManager()._cleanup_oldest_session()  # must not raise


class TestSessionManagerInfo:
    async def test_get_session_info_existing(self):
        mgr = SessionManager(backend="docker")
        await mgr.execute("chat1", "x = 1")
        info = await mgr.get_session_info("chat1")
        assert info is not None
        assert info["chat_id"] == "chat1" and info["backend"] == "docker"
        assert {"session_id", "created_at", "last_used_at", "is_idle", "execution_count"} <= set(info)

    async def test_get_session_info_nonexistent(self):
        assert await SessionManager().get_session_info("missing") is None

    async def test_list_sessions(self):
        mgr = SessionManager(backend="docker")
        assert await mgr.list_sessions() == {}
        await mgr.execute("c1", "pass")
        await mgr.execute("c2", "pass")
        listing = await mgr.list_sessions()
        assert len(listing) == 2 and "c1" in listing and "c2" in listing


class TestSessionManagerCleanup:
    async def test_cleanup_removes_session(self):
        mgr = SessionManager()
        s = ExecutionSession(session_id="s1", chat_id="c1", container_id="ctr1", kernel_id="k1")
        mgr._sessions["c1"] = s
        await mgr._cleanup_session(s)
        assert "c1" not in mgr._sessions

    async def test_cleanup_idempotent(self):
        mgr = SessionManager()
        s = ExecutionSession(session_id="s1", chat_id="c1")
        mgr._sessions["c1"] = s
        await mgr._cleanup_session(s)
        await mgr._cleanup_session(s)  # second call must not raise

    @pytest.mark.parametrize("age_min,timeout_min,stays", [
        (5, 30, True),   # active → kept
        (60, 30, False), # idle → removed
    ])
    async def test_cleanup_loop_idle_logic(self, age_min, timeout_min, stays):
        mgr = SessionManager(idle_timeout_minutes=timeout_min)
        s = ExecutionSession(session_id="s1", chat_id="c1")
        s.last_used_at = datetime.now(tz=UTC) - timedelta(minutes=age_min)
        mgr._sessions["c1"] = s
        for session in [sess for sess in mgr._sessions.values() if sess.is_idle(mgr.idle_timeout_minutes)]:
            await mgr._cleanup_session(session)
        assert ("c1" in mgr._sessions) is stays
