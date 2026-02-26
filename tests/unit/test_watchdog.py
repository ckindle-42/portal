"""Tests for portal.observability.watchdog"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytest.importorskip("psutil")

from portal.observability.health import HealthCheckResult, HealthStatus
from portal.observability.watchdog import (
    ComponentState,
    MonitoredComponent,
    Watchdog,
    WatchdogConfig,
    WatchdogHealthCheck,
)


class TestMonitoredComponent:
    def test_init(self):
        hc = AsyncMock(return_value=HealthCheckResult(
            status=HealthStatus.HEALTHY, message="ok", timestamp="now"
        ))
        comp = MonitoredComponent(name="worker", health_check=hc, critical=True)
        assert comp.name == "worker"
        assert comp.critical is True
        assert comp.health.state == ComponentState.HEALTHY


# ── Watchdog ─────────────────────────────────────────────────────────────


class TestWatchdog:
    @patch("portal.observability.watchdog.psutil.Process")
    def test_init(self, mock_process):
        wd = Watchdog()
        assert wd._running is False
        assert len(wd._components) == 0

    @patch("portal.observability.watchdog.psutil.Process")
    def test_register_component(self, mock_process):
        wd = Watchdog()
        hc = AsyncMock()
        wd.register_component("test", hc, critical=False)
        assert "test" in wd._components
        assert wd._components["test"].critical is False

    @patch("portal.observability.watchdog.psutil.Process")
    def test_unregister_component(self, mock_process):
        wd = Watchdog()
        hc = AsyncMock()
        wd.register_component("test", hc)
        wd.unregister_component("test")
        assert "test" not in wd._components

    @patch("portal.observability.watchdog.psutil.Process")
    def test_unregister_nonexistent(self, mock_process):
        wd = Watchdog()
        wd.unregister_component("missing")  # Should not raise

    @patch("portal.observability.watchdog.psutil.Process")
    def test_get_component_status_found(self, mock_process):
        wd = Watchdog()
        hc = AsyncMock()
        wd.register_component("worker", hc)
        status = wd.get_component_status("worker")
        assert status is not None
        assert status["name"] == "worker"
        assert status["state"] == "healthy"

    @patch("portal.observability.watchdog.psutil.Process")
    def test_get_component_status_not_found(self, mock_process):
        wd = Watchdog()
        assert wd.get_component_status("missing") is None

    @patch("portal.observability.watchdog.psutil.Process")
    def test_get_all_status(self, mock_process):
        mock_proc = MagicMock()
        mock_proc.memory_percent.return_value = 45.0
        mock_proc.cpu_percent.return_value = 10.0
        mock_process.return_value = mock_proc

        wd = Watchdog()
        hc = AsyncMock()
        wd.register_component("comp1", hc)
        status = wd.get_all_status()
        assert "watchdog" in status
        assert "components" in status
        assert status["watchdog"]["components_count"] == 1

    @patch("portal.observability.watchdog.psutil.Process")
    def test_reset_restart_count(self, mock_process):
        wd = Watchdog()
        hc = AsyncMock()
        wd.register_component("comp", hc)
        wd._components["comp"].health.restart_count = 5
        wd._components["comp"].health.consecutive_failures = 3
        wd.reset_restart_count("comp")
        assert wd._components["comp"].health.restart_count == 0
        assert wd._components["comp"].health.consecutive_failures == 0

    @patch("portal.observability.watchdog.psutil.Process")
    def test_reset_restart_count_missing(self, mock_process):
        wd = Watchdog()
        wd.reset_restart_count("nope")  # Should not raise

    # ── _check_component ─────────────────────────────────────────────

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_check_component_healthy(self, mock_process):
        wd = Watchdog()
        hc = AsyncMock(return_value=HealthCheckResult(
            status=HealthStatus.HEALTHY, message="ok", timestamp="now"
        ))
        wd.register_component("comp", hc)
        comp = wd._components["comp"]
        comp.health.state = ComponentState.DEGRADED  # was degraded
        await wd._check_component(comp)
        assert comp.health.state == ComponentState.HEALTHY
        assert comp.health.consecutive_failures == 0

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.logger")
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_check_component_degraded(self, mock_process, mock_logger):
        wd = Watchdog()
        hc = AsyncMock(return_value=HealthCheckResult(
            status=HealthStatus.DEGRADED, message="slow", timestamp="now"
        ))
        wd.register_component("comp", hc)
        comp = wd._components["comp"]
        await wd._check_component(comp)
        assert comp.health.state == ComponentState.DEGRADED
        assert comp.health.consecutive_failures == 1

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.logger")
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_check_component_unhealthy_triggers_restart(self, mock_process, mock_logger):
        cfg = WatchdogConfig(max_consecutive_failures=1, restart_backoff_seconds=0)
        wd = Watchdog(config=cfg)
        hc = AsyncMock(return_value=HealthCheckResult(
            status=HealthStatus.UNHEALTHY, message="down", timestamp="now"
        ))
        restart_fn = AsyncMock()
        wd.register_component("comp", hc, restart_func=restart_fn, critical=True)
        comp = wd._components["comp"]
        await wd._check_component(comp)
        restart_fn.assert_called_once()

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.logger")
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_check_component_unhealthy_callback(self, mock_process, mock_logger):
        on_fail = MagicMock()
        wd = Watchdog(
            config=WatchdogConfig(max_consecutive_failures=10),
            on_component_failed=on_fail,
        )
        hc = AsyncMock(return_value=HealthCheckResult(
            status=HealthStatus.UNHEALTHY, message="err", timestamp="now"
        ))
        wd.register_component("comp", hc)
        await wd._check_component(wd._components["comp"])
        on_fail.assert_called_once_with("comp", "err")

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_check_component_exception(self, mock_process):
        wd = Watchdog()
        hc = AsyncMock(side_effect=RuntimeError("boom"))
        wd.register_component("comp", hc)
        comp = wd._components["comp"]
        await wd._check_component(comp)
        assert comp.health.state == ComponentState.FAILED
        assert comp.health.last_error == "boom"

    # ── _restart_component ───────────────────────────────────────────

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_restart_no_func(self, mock_process):
        wd = Watchdog()
        hc = AsyncMock()
        wd.register_component("comp", hc, restart_func=None)
        await wd._restart_component(wd._components["comp"])
        # Should not raise

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.logger")
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_restart_exceeds_max_attempts(self, mock_process, mock_logger):
        cfg = WatchdogConfig(max_restart_attempts=2)
        wd = Watchdog(config=cfg)
        hc = AsyncMock()
        restart_fn = AsyncMock()
        wd.register_component("comp", hc, restart_func=restart_fn)
        wd._components["comp"].health.restart_count = 5
        await wd._restart_component(wd._components["comp"])
        restart_fn.assert_not_called()

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.logger")
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_restart_success_callback(self, mock_process, mock_logger):
        on_restart = MagicMock()
        wd = Watchdog(
            config=WatchdogConfig(restart_backoff_seconds=0),
            on_component_restarted=on_restart,
        )
        hc = AsyncMock()
        restart_fn = AsyncMock()
        wd.register_component("comp", hc, restart_func=restart_fn)
        await wd._restart_component(wd._components["comp"])
        on_restart.assert_called_once_with("comp")

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.logger")
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_restart_failure(self, mock_process, mock_logger):
        wd = Watchdog(config=WatchdogConfig(restart_backoff_seconds=0))
        hc = AsyncMock()
        restart_fn = AsyncMock(side_effect=RuntimeError("restart boom"))
        wd.register_component("comp", hc, restart_func=restart_fn)
        await wd._restart_component(wd._components["comp"])
        assert wd._components["comp"].health.state == ComponentState.FAILED

    # ── start / stop ─────────────────────────────────────────────────

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_start_stop(self, mock_process):
        wd = Watchdog()
        await wd.start()
        assert wd._running is True
        await wd.stop()
        assert wd._running is False

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_start_twice_noop(self, mock_process):
        wd = Watchdog()
        await wd.start()
        await wd.start()  # Should not raise
        await wd.stop()

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_stop_when_not_running(self, mock_process):
        wd = Watchdog()
        await wd.stop()  # Should not raise

    # ── force_restart ────────────────────────────────────────────────

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_force_restart_existing(self, mock_process):
        wd = Watchdog(config=WatchdogConfig(restart_backoff_seconds=0))
        hc = AsyncMock()
        restart_fn = AsyncMock()
        wd.register_component("comp", hc, restart_func=restart_fn)
        await wd.force_restart("comp")
        restart_fn.assert_called_once()

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_force_restart_missing(self, mock_process):
        wd = Watchdog()
        await wd.force_restart("missing")  # Should not raise

    # ── _check_system_resources ──────────────────────────────────────

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_check_system_resources_normal(self, mock_process):
        mock_proc = MagicMock()
        mock_proc.memory_info.return_value = MagicMock(rss=100 * 1024 * 1024)
        mock_proc.memory_percent.return_value = 10.0
        mock_proc.cpu_percent.return_value = 5.0
        mock_process.return_value = mock_proc

        wd = Watchdog()
        await wd._check_system_resources()  # Should not raise

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_check_system_resources_high_memory(self, mock_process):
        mock_proc = MagicMock()
        mock_proc.memory_info.return_value = MagicMock(rss=8000 * 1024 * 1024)
        mock_proc.memory_percent.return_value = 95.0
        mock_proc.cpu_percent.return_value = 5.0
        mock_process.return_value = mock_proc

        wd = Watchdog()
        await wd._check_system_resources()  # Should log warning but not raise


# ── WatchdogHealthCheck ──────────────────────────────────────────────────


class TestWatchdogHealthCheck:
    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_check_not_running(self, mock_process):
        wd = Watchdog()
        hc = WatchdogHealthCheck(wd)
        result = await hc.check()
        assert result.status == HealthStatus.UNHEALTHY
        assert "not running" in result.message

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_check_all_healthy(self, mock_process):
        mock_proc = MagicMock()
        mock_proc.memory_percent.return_value = 10.0
        mock_proc.cpu_percent.return_value = 5.0
        mock_process.return_value = mock_proc

        wd = Watchdog()
        wd._running = True
        hc_func = AsyncMock(return_value=HealthCheckResult(
            status=HealthStatus.HEALTHY, message="ok", timestamp="now"
        ))
        wd.register_component("comp", hc_func)
        whc = WatchdogHealthCheck(wd)
        result = await whc.check()
        assert result.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    @patch("portal.observability.watchdog.psutil.Process")
    async def test_check_failed_component(self, mock_process):
        mock_proc = MagicMock()
        mock_proc.memory_percent.return_value = 10.0
        mock_proc.cpu_percent.return_value = 5.0
        mock_process.return_value = mock_proc

        wd = Watchdog()
        wd._running = True
        hc_func = AsyncMock()
        wd.register_component("comp", hc_func)
        wd._components["comp"].health.state = ComponentState.FAILED
        whc = WatchdogHealthCheck(wd)
        result = await whc.check()
        assert result.status == HealthStatus.DEGRADED
