"""
Unit tests for lifecycle management — Runtime, RuntimeContext, and shutdown.

Tests bootstrap guards, shutdown sequencing, and task tracking without
requiring external services.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from portal.lifecycle import (
    Runtime,
    RuntimeContext,
    ShutdownCallback,
    ShutdownPriority,
)

# ---------------------------------------------------------------------------
# RuntimeContext tests
# ---------------------------------------------------------------------------


class TestRuntimeContext:
    def test_runtime_context_defaults(self):
        """RuntimeContext initializes with sensible defaults."""
        ctx = RuntimeContext(
            settings=MagicMock(),
            agent_core=MagicMock(),
            secure_agent=MagicMock(),
        )
        assert ctx.accepting_work is True
        assert ctx.shutdown_callbacks == []
        assert ctx.active_tasks == set()
        assert ctx.watchdog is None
        assert ctx.log_rotator is None

    def test_runtime_context_no_event_broker(self):
        """RuntimeContext should not have an event_broker field (removed debt)."""
        ctx = RuntimeContext(
            settings=MagicMock(),
            agent_core=MagicMock(),
            secure_agent=MagicMock(),
        )
        assert not hasattr(ctx, "event_broker")


# ---------------------------------------------------------------------------
# ShutdownPriority ordering
# ---------------------------------------------------------------------------


class TestShutdownPriority:
    def test_priority_ordering(self):
        """CRITICAL > HIGH > NORMAL > LOW > LOWEST."""
        assert ShutdownPriority.CRITICAL.value > ShutdownPriority.HIGH.value
        assert ShutdownPriority.HIGH.value > ShutdownPriority.NORMAL.value
        assert ShutdownPriority.NORMAL.value > ShutdownPriority.LOW.value
        assert ShutdownPriority.LOW.value > ShutdownPriority.LOWEST.value

    def test_callbacks_sort_by_priority(self):
        """Shutdown callbacks should sort by priority descending."""
        cb_low = ShutdownCallback(callback=lambda: None, priority=ShutdownPriority.LOW, name="low")
        cb_high = ShutdownCallback(
            callback=lambda: None, priority=ShutdownPriority.HIGH, name="high"
        )
        cb_crit = ShutdownCallback(
            callback=lambda: None, priority=ShutdownPriority.CRITICAL, name="crit"
        )

        sorted_cbs = sorted(
            [cb_low, cb_high, cb_crit], key=lambda c: c.priority.value, reverse=True
        )
        assert [c.name for c in sorted_cbs] == ["crit", "high", "low"]


# ---------------------------------------------------------------------------
# Runtime initialization tests
# ---------------------------------------------------------------------------


class TestRuntime:
    def test_runtime_initial_state(self):
        """Runtime starts uninitialized."""
        rt = Runtime()
        assert rt.context is None
        assert rt._initialized is False
        assert rt._shutdown_in_progress is False

    def test_is_accepting_work_before_bootstrap(self):
        """is_accepting_work returns False before bootstrap."""
        rt = Runtime()
        assert rt.is_accepting_work() is False

    def test_track_task_before_bootstrap(self):
        """track_task is a no-op before bootstrap (no crash)."""
        rt = Runtime()
        rt.track_task(MagicMock())  # Should not raise

    def test_register_callback_before_bootstrap(self):
        """register_shutdown_callback is a no-op before bootstrap."""
        rt = Runtime()
        rt.register_shutdown_callback(lambda: None, name="noop")
        # No crash, no context to append to


# ---------------------------------------------------------------------------
# Bootstrap security guards
# ---------------------------------------------------------------------------


class TestBootstrapGuards:
    @pytest.mark.asyncio
    async def test_mcp_api_key_guard(self):
        """Bootstrap refuses to start with default MCP secret."""
        rt = Runtime()
        mock_settings = MagicMock()
        mock_settings.security.mcp_api_key = "changeme-mcp-secret"

        with (
            patch("portal.lifecycle.load_settings", return_value=mock_settings),
            patch.dict("os.environ", {"MCP_API_KEY": "", "PORTAL_ENV": "development"}),
        ):
            with pytest.raises(RuntimeError, match="changeme-mcp-secret"):
                await rt.bootstrap()

    @pytest.mark.asyncio
    async def test_bootstrap_key_guard(self):
        """Bootstrap refuses to start with default bootstrap key in production."""
        rt = Runtime()
        mock_settings = MagicMock()
        mock_settings.security.mcp_api_key = "real-secret"

        with (
            patch("portal.lifecycle.load_settings", return_value=mock_settings),
            patch.dict(
                "os.environ",
                {
                    "MCP_API_KEY": "real-secret",
                    "PORTAL_BOOTSTRAP_API_KEY": "portal-dev-key",
                    "PORTAL_ENV": "production",
                },
            ),
        ):
            with pytest.raises(RuntimeError, match="PORTAL_BOOTSTRAP_API_KEY"):
                await rt.bootstrap()


# ---------------------------------------------------------------------------
# Shutdown sequencing
# ---------------------------------------------------------------------------


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_without_init(self):
        """shutdown() is safe to call before bootstrap."""
        rt = Runtime()
        await rt.shutdown()  # Should not raise

    @pytest.mark.asyncio
    async def test_double_shutdown(self):
        """Calling shutdown() twice does not crash."""
        rt = Runtime()
        rt._initialized = True
        rt._shutdown_in_progress = True
        await rt.shutdown()  # Second call returns early

    @pytest.mark.asyncio
    async def test_shutdown_runs_callbacks_in_priority_order(self):
        """Shutdown callbacks execute in priority order (highest first)."""
        execution_order = []

        async def cb_high():
            execution_order.append("high")

        async def cb_low():
            execution_order.append("low")

        rt = Runtime()
        mock_secure = AsyncMock()
        rt.context = RuntimeContext(
            settings=MagicMock(),
            agent_core=MagicMock(),
            secure_agent=mock_secure,
        )
        rt.context.shutdown_callbacks = [
            ShutdownCallback(callback=cb_low, priority=ShutdownPriority.LOW, name="low"),
            ShutdownCallback(callback=cb_high, priority=ShutdownPriority.HIGH, name="high"),
        ]
        rt._initialized = True

        await rt.shutdown()

        assert execution_order == ["high", "low"]

    @pytest.mark.asyncio
    async def test_shutdown_stops_accepting_work(self):
        """After shutdown, accepting_work is False."""
        rt = Runtime()
        mock_secure = AsyncMock()
        rt.context = RuntimeContext(
            settings=MagicMock(),
            agent_core=MagicMock(),
            secure_agent=mock_secure,
        )
        rt._initialized = True

        await rt.shutdown()
        assert rt.context.accepting_work is False
