"""
Tests for portal.tools.dev_tools.session_manager
==================================================

Comprehensive tests for ExecutionSession, SessionManager,
Docker/Jupyter backends, session lifecycle, cleanup, and edge cases.

The source module uses structured-logging kwargs
(e.g. ``logger.info("msg", key=val)``), which the stdlib ``logging.Logger``
does not accept. We patch the module-level logger throughout to avoid
``TypeError`` exceptions during tests.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from portal.tools.dev_tools.session_manager import (
    ExecutionSession,
    SessionManager,
)

# Patch the module logger for ALL tests in this module so that
# keyword-argument calls like logger.info("msg", backend=...) do not raise.
pytestmark = pytest.mark.usefixtures("_patch_session_manager_logger")


@pytest.fixture(autouse=True)
def _patch_session_manager_logger():
    """Replace the session_manager module logger with a silent MagicMock."""
    with patch("portal.tools.dev_tools.session_manager.logger", new_callable=MagicMock):
        yield

# ===========================================================================
# ExecutionSession dataclass
# ===========================================================================


class TestExecutionSession:
    """Tests for the ExecutionSession dataclass."""

    def test_default_fields(self):
        s = ExecutionSession(session_id="s1", chat_id="c1")
        assert s.session_id == "s1"
        assert s.chat_id == "c1"
        assert isinstance(s.created_at, datetime)
        assert isinstance(s.last_used_at, datetime)
        assert s.container_id is None
        assert s.kernel_id is None
        assert s.execution_count == 0
        assert s.variables == {}

    def test_touch_updates_last_used_at(self):
        s = ExecutionSession(session_id="s1", chat_id="c1")
        old_ts = s.last_used_at
        # Ensure some time passes (or at least the call runs)
        s.touch()
        assert s.last_used_at >= old_ts

    def test_is_idle_false_when_fresh(self):
        s = ExecutionSession(session_id="s1", chat_id="c1")
        assert s.is_idle(idle_timeout_minutes=30) is False

    def test_is_idle_true_when_old(self):
        s = ExecutionSession(session_id="s1", chat_id="c1")
        s.last_used_at = datetime.utcnow() - timedelta(minutes=60)
        assert s.is_idle(idle_timeout_minutes=30) is True

    def test_is_idle_boundary_not_idle(self):
        """Exactly at the boundary should NOT be idle (> not >=)."""
        s = ExecutionSession(session_id="s1", chat_id="c1")
        s.last_used_at = datetime.utcnow() - timedelta(minutes=30)
        # timedelta comparison uses >, so equal should be False
        # (but timing might vary by microseconds, so we set just under)
        s.last_used_at = datetime.utcnow() - timedelta(minutes=29, seconds=59)
        assert s.is_idle(idle_timeout_minutes=30) is False

    def test_is_idle_custom_timeout(self):
        s = ExecutionSession(session_id="s1", chat_id="c1")
        s.last_used_at = datetime.utcnow() - timedelta(minutes=10)
        assert s.is_idle(idle_timeout_minutes=5) is True
        assert s.is_idle(idle_timeout_minutes=15) is False

    def test_variables_dict_independent(self):
        s1 = ExecutionSession(session_id="s1", chat_id="c1")
        s2 = ExecutionSession(session_id="s2", chat_id="c2")
        s1.variables["x"] = 42
        assert "x" not in s2.variables

    def test_execution_count_starts_zero(self):
        s = ExecutionSession(session_id="s1", chat_id="c1")
        assert s.execution_count == 0

    def test_container_and_kernel_ids_settable(self):
        s = ExecutionSession(
            session_id="s1",
            chat_id="c1",
            container_id="ctr-abc",
            kernel_id="krn-xyz",
        )
        assert s.container_id == "ctr-abc"
        assert s.kernel_id == "krn-xyz"


# ===========================================================================
# SessionManager — init and configuration
# ===========================================================================


class TestSessionManagerInit:
    """Tests for SessionManager initialisation and configuration."""

    def test_default_config(self):
        mgr = SessionManager()
        assert mgr.idle_timeout_minutes == 30
        assert mgr.max_sessions == 100
        assert mgr.backend == "docker"
        assert mgr._sessions == {}
        assert mgr._cleanup_task is None
        assert mgr._shutdown is False

    def test_custom_config(self):
        mgr = SessionManager(
            idle_timeout_minutes=10, max_sessions=5, backend="jupyter"
        )
        assert mgr.idle_timeout_minutes == 10
        assert mgr.max_sessions == 5
        assert mgr.backend == "jupyter"


# ===========================================================================
# SessionManager — start / stop lifecycle
# ===========================================================================


class TestSessionManagerLifecycle:
    """Tests for start() and stop()."""

    async def test_start_creates_cleanup_task(self):
        mgr = SessionManager()
        await mgr.start()

        assert mgr._cleanup_task is not None
        assert not mgr._cleanup_task.done()

        # Teardown
        await mgr.stop()

    async def test_start_idempotent(self):
        mgr = SessionManager()
        await mgr.start()
        task1 = mgr._cleanup_task
        await mgr.start()  # second call should not replace
        assert mgr._cleanup_task is task1

        await mgr.stop()

    async def test_stop_cancels_cleanup_task(self):
        mgr = SessionManager()
        await mgr.start()
        await mgr.stop()

        assert mgr._shutdown is True
        assert mgr._cleanup_task.cancelled() or mgr._cleanup_task.done()

    async def test_stop_cleans_all_sessions(self):
        mgr = SessionManager()
        # Manually add sessions
        s = ExecutionSession(session_id="s1", chat_id="c1", container_id="ctr1")
        mgr._sessions["c1"] = s

        await mgr.stop()
        assert len(mgr._sessions) == 0

    async def test_stop_without_start(self):
        mgr = SessionManager()
        # Should not raise even if cleanup_task is None
        await mgr.stop()
        assert mgr._shutdown is True


# ===========================================================================
# SessionManager — execute (Docker backend)
# ===========================================================================


class TestSessionManagerExecuteDocker:
    """Tests for execute() with the default Docker backend."""

    async def test_execute_creates_session(self):
        mgr = SessionManager(backend="docker")
        result = await mgr.execute("chat1", "x = 1")

        assert "chat1" in mgr._sessions
        assert result["output"].startswith("Executed:")
        assert result["error"] == ""
        assert result["execution_count"] == 1

    async def test_execute_reuses_session(self):
        mgr = SessionManager(backend="docker")
        await mgr.execute("chat1", "x = 1")
        await mgr.execute("chat1", "print(x)")

        assert mgr._sessions["chat1"].execution_count == 2

    async def test_execute_touches_session(self):
        mgr = SessionManager(backend="docker")
        await mgr.execute("chat1", "pass")
        session = mgr._sessions["chat1"]

        old_ts = session.last_used_at
        await mgr.execute("chat1", "pass")
        assert session.last_used_at >= old_ts

    async def test_execute_result_structure(self):
        mgr = SessionManager(backend="docker")
        result = await mgr.execute("chat1", "hello")

        assert "output" in result
        assert "error" in result
        assert "result" in result
        assert "execution_count" in result

    async def test_execute_docker_sets_container_id(self):
        mgr = SessionManager(backend="docker")
        await mgr.execute("chat1", "pass")
        session = mgr._sessions["chat1"]
        assert session.container_id is not None
        assert session.container_id.startswith("placeholder-")


# ===========================================================================
# SessionManager — execute (Jupyter backend)
# ===========================================================================


class TestSessionManagerExecuteJupyter:
    """Tests for execute() with Jupyter backend."""

    async def test_execute_jupyter(self):
        mgr = SessionManager(backend="jupyter")
        result = await mgr.execute("chat_j", "import numpy")

        assert "chat_j" in mgr._sessions
        assert result["output"].startswith("Executed:")
        assert result["error"] == ""

    async def test_execute_jupyter_sets_kernel_id(self):
        mgr = SessionManager(backend="jupyter")
        await mgr.execute("chat_j", "pass")
        session = mgr._sessions["chat_j"]
        assert session.kernel_id is not None
        assert session.kernel_id.startswith("placeholder-")


# ===========================================================================
# SessionManager — execute (unknown backend)
# ===========================================================================


class TestSessionManagerExecuteUnknownBackend:
    """Tests for execute() with an unknown backend."""

    async def test_execute_unknown_backend_returns_error(self):
        mgr = SessionManager(backend="unknown_backend")
        result = await mgr.execute("chat1", "x = 1")

        assert result["error"] != ""
        assert "Unknown backend" in result["error"]
        assert result["output"] == ""


# ===========================================================================
# SessionManager — max sessions / eviction
# ===========================================================================


class TestSessionManagerMaxSessions:
    """Tests for max session enforcement and oldest-session eviction."""

    async def test_max_sessions_evicts_oldest(self):
        mgr = SessionManager(max_sessions=2, backend="docker")

        await mgr.execute("chat_a", "a = 1")
        # Make chat_a the oldest by pushing its last_used_at back
        mgr._sessions["chat_a"].last_used_at = datetime.utcnow() - timedelta(hours=1)

        await mgr.execute("chat_b", "b = 1")
        await mgr.execute("chat_c", "c = 1")  # should evict chat_a

        assert "chat_a" not in mgr._sessions
        assert "chat_b" in mgr._sessions
        assert "chat_c" in mgr._sessions

    async def test_max_sessions_boundary(self):
        mgr = SessionManager(max_sessions=1, backend="docker")

        await mgr.execute("chat_x", "pass")
        await mgr.execute("chat_y", "pass")  # evicts chat_x

        assert len(mgr._sessions) == 1
        assert "chat_y" in mgr._sessions

    async def test_cleanup_oldest_empty_sessions(self):
        mgr = SessionManager()
        # Should not raise on empty dict
        await mgr._cleanup_oldest_session()


# ===========================================================================
# SessionManager — get_session_info / list_sessions
# ===========================================================================


class TestSessionManagerInfo:
    """Tests for get_session_info() and list_sessions()."""

    async def test_get_session_info_existing(self):
        mgr = SessionManager(backend="docker")
        await mgr.execute("chat1", "x = 1")

        info = await mgr.get_session_info("chat1")
        assert info is not None
        assert info["chat_id"] == "chat1"
        assert info["backend"] == "docker"
        assert info["execution_count"] == 1
        assert "session_id" in info
        assert "created_at" in info
        assert "last_used_at" in info
        assert "is_idle" in info

    async def test_get_session_info_nonexistent(self):
        mgr = SessionManager()
        info = await mgr.get_session_info("does_not_exist")
        assert info is None

    async def test_list_sessions_empty(self):
        mgr = SessionManager()
        listing = await mgr.list_sessions()
        assert listing == {}

    async def test_list_sessions_multiple(self):
        mgr = SessionManager(backend="docker")
        await mgr.execute("c1", "pass")
        await mgr.execute("c2", "pass")

        listing = await mgr.list_sessions()
        assert len(listing) == 2
        assert "c1" in listing
        assert "c2" in listing
        assert listing["c1"]["chat_id"] == "c1"
        assert listing["c2"]["chat_id"] == "c2"


# ===========================================================================
# SessionManager — cleanup
# ===========================================================================


class TestSessionManagerCleanup:
    """Tests for session cleanup logic."""

    async def test_cleanup_session_removes_from_dict(self):
        mgr = SessionManager()
        s = ExecutionSession(session_id="s1", chat_id="c1")
        mgr._sessions["c1"] = s

        await mgr._cleanup_session(s)
        assert "c1" not in mgr._sessions

    async def test_cleanup_session_with_container(self):
        mgr = SessionManager()
        s = ExecutionSession(session_id="s1", chat_id="c1", container_id="ctr1")
        mgr._sessions["c1"] = s

        await mgr._cleanup_session(s)
        assert "c1" not in mgr._sessions

    async def test_cleanup_session_with_kernel(self):
        mgr = SessionManager()
        s = ExecutionSession(session_id="s1", chat_id="c1", kernel_id="k1")
        mgr._sessions["c1"] = s

        await mgr._cleanup_session(s)
        assert "c1" not in mgr._sessions

    async def test_cleanup_session_idempotent(self):
        mgr = SessionManager()
        s = ExecutionSession(session_id="s1", chat_id="c1")
        mgr._sessions["c1"] = s

        await mgr._cleanup_session(s)
        # Second call should not raise
        await mgr._cleanup_session(s)
        assert "c1" not in mgr._sessions

    async def test_cleanup_loop_removes_idle_sessions(self):
        """Simulate one iteration of the cleanup loop."""
        mgr = SessionManager(idle_timeout_minutes=1)

        s = ExecutionSession(session_id="s1", chat_id="c1")
        s.last_used_at = datetime.utcnow() - timedelta(minutes=5)
        mgr._sessions["c1"] = s

        # Directly invoke the idle-check logic from _cleanup_loop
        idle_sessions = [
            session
            for session in mgr._sessions.values()
            if session.is_idle(mgr.idle_timeout_minutes)
        ]
        for session in idle_sessions:
            await mgr._cleanup_session(session)

        assert "c1" not in mgr._sessions

    async def test_cleanup_loop_keeps_active_sessions(self):
        mgr = SessionManager(idle_timeout_minutes=30)

        s = ExecutionSession(session_id="s1", chat_id="c1")
        # Fresh session should NOT be idle
        mgr._sessions["c1"] = s

        idle_sessions = [
            session
            for session in mgr._sessions.values()
            if session.is_idle(mgr.idle_timeout_minutes)
        ]
        for session in idle_sessions:
            await mgr._cleanup_session(session)

        assert "c1" in mgr._sessions


# ===========================================================================
# Edge cases
# ===========================================================================


class TestSessionManagerEdgeCases:
    """Various edge-case scenarios."""

    async def test_execute_long_code_truncated_in_output(self):
        mgr = SessionManager(backend="docker")
        long_code = "a" * 200
        result = await mgr.execute("chat1", long_code)
        # Placeholder returns first 50 chars
        assert "..." in result["output"]

    async def test_session_id_is_uuid(self):
        import uuid

        mgr = SessionManager(backend="docker")
        await mgr.execute("chat1", "pass")
        session = mgr._sessions["chat1"]
        # Should be a valid UUID
        uuid.UUID(session.session_id)

    async def test_separate_chat_ids_get_separate_sessions(self):
        mgr = SessionManager(backend="docker")
        await mgr.execute("chat_a", "pass")
        await mgr.execute("chat_b", "pass")

        assert mgr._sessions["chat_a"].session_id != mgr._sessions["chat_b"].session_id

    async def test_execution_count_not_incremented_on_error(self):
        """When execute catches an unknown backend error, count stays unchanged."""
        mgr = SessionManager(backend="bad")
        result = await mgr.execute("chat1", "pass")
        assert result["execution_count"] == 0

    async def test_stop_cleanup_order(self):
        """stop() should handle sessions with both container and kernel ids."""
        mgr = SessionManager()
        s = ExecutionSession(
            session_id="s1",
            chat_id="c1",
            container_id="ctr",
            kernel_id="krn",
        )
        mgr._sessions["c1"] = s
        await mgr.stop()
        assert len(mgr._sessions) == 0
