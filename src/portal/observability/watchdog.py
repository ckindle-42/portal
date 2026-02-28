"""Watchdog — process monitoring and auto-recovery for critical components."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import psutil

from .health import HealthCheckResult, HealthCheckSystem, HealthStatus

logger = logging.getLogger(__name__)


class ComponentState(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RESTARTING = "restarting"
    STOPPED = "stopped"


@dataclass
class WatchdogConfig:
    check_interval_seconds: int = 30
    max_consecutive_failures: int = 3
    restart_on_failure: bool = True
    max_restart_attempts: int = 5
    restart_backoff_seconds: int = 10
    memory_threshold_percent: float = 90.0
    cpu_threshold_percent: float = 95.0
    deadlock_timeout_seconds: int = 300
    alert_on_failure: bool = True
    alert_on_restart: bool = True


@dataclass
class ComponentHealth:
    name: str
    state: ComponentState
    last_check_time: float
    consecutive_failures: int = 0
    restart_count: int = 0
    last_restart_time: float | None = None
    last_error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class MonitoredComponent:
    """A component being monitored by the watchdog."""

    def __init__(
        self,
        name: str,
        health_check: Callable[[], Awaitable[HealthCheckResult]],
        restart_func: Callable[[], Awaitable[None]] | None = None,
        critical: bool = True,
    ):
        self.name = name
        self.health_check = health_check
        self.restart_func = restart_func
        self.critical = critical
        self.health = ComponentHealth(
            name=name, state=ComponentState.HEALTHY, last_check_time=time.time()
        )


class Watchdog:
    """Monitors registered components and auto-restarts failed ones."""

    def __init__(
        self,
        config: WatchdogConfig | None = None,
        health_system: HealthCheckSystem | None = None,
        on_component_failed: Callable[[str, str], None] | None = None,
        on_component_restarted: Callable[[str], None] | None = None,
    ):
        self.config = config or WatchdogConfig()
        self.health_system = health_system
        self.on_component_failed = on_component_failed
        self.on_component_restarted = on_component_restarted
        self._components: dict[str, MonitoredComponent] = {}
        self._running = False
        self._task: asyncio.Task | None = None
        self._process = psutil.Process()
        logger.info(
            "Watchdog initialized",
            check_interval=self.config.check_interval_seconds,
            max_failures=self.config.max_consecutive_failures,
            restart_enabled=self.config.restart_on_failure,
        )

    def register_component(
        self,
        name: str,
        health_check: Callable[[], Awaitable[HealthCheckResult]],
        restart_func: Callable[[], Awaitable[None]] | None = None,
        critical: bool = True,
    ) -> None:
        self._components[name] = MonitoredComponent(name, health_check, restart_func, critical)
        logger.info(
            "Registered component for monitoring: %s",
            name,
            critical=critical,
            has_restart_func=restart_func is not None,
        )

    def unregister_component(self, name: str) -> None:
        if name in self._components:
            del self._components[name]
            logger.info("Unregistered component: %s", name)

    async def start(self) -> None:
        if self._running:
            logger.warning("Watchdog already running")
            return
        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info(
            "Watchdog started",
            components_count=len(self._components),
            check_interval=self.config.check_interval_seconds,
        )

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Watchdog stopped")

    async def _monitoring_loop(self) -> None:
        try:
            while self._running:
                await asyncio.sleep(self.config.check_interval_seconds)
                for component in self._components.values():
                    try:
                        await self._check_component(component)
                    except Exception as e:
                        logger.error(
                            "Error checking component %s: %s", component.name, e, exc_info=True
                        )
                await self._check_system_resources()
        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
            raise
        except Exception as e:
            logger.error("Fatal error in monitoring loop: %s", e, exc_info=True)

    async def _check_component(self, component: MonitoredComponent) -> None:
        try:
            result = await component.health_check()
            component.health.last_check_time = time.time()

            if result.status == HealthStatus.HEALTHY:
                if component.health.state != ComponentState.HEALTHY:
                    logger.info("Component %s recovered", component.name)
                component.health.state = ComponentState.HEALTHY
                component.health.consecutive_failures = 0
                component.health.last_error = None

            elif result.status == HealthStatus.DEGRADED:
                component.health.state = ComponentState.DEGRADED
                component.health.consecutive_failures += 1
                logger.warning(
                    "Component %s is degraded",
                    component.name,
                    consecutive_failures=component.health.consecutive_failures,
                    message=result.message,
                )

            elif result.status == HealthStatus.UNHEALTHY:
                component.health.state = ComponentState.FAILED
                component.health.consecutive_failures += 1
                component.health.last_error = result.message
                logger.error(
                    "Component %s failed",
                    component.name,
                    consecutive_failures=component.health.consecutive_failures,
                    error=result.message,
                )
                await self._attempt_recovery(component, result.message)

        except Exception as e:
            component.health.state = ComponentState.FAILED
            component.health.consecutive_failures += 1
            component.health.last_error = str(e)
            logger.error("Health check failed for %s: %s", component.name, e, exc_info=True)

    async def _attempt_recovery(self, component: MonitoredComponent, error_message: str) -> None:
        """Invoke failure callback and restart if thresholds are met."""
        if self.on_component_failed:
            try:
                self.on_component_failed(component.name, error_message)
            except Exception as e:
                logger.error("Error in failure callback: %s", e)
        if (
            component.critical
            and self.config.restart_on_failure
            and component.health.consecutive_failures >= self.config.max_consecutive_failures
        ):
            await self._restart_component(component)

    async def _restart_component(self, component: MonitoredComponent) -> None:
        if not component.restart_func:
            logger.warning("No restart function for component %s", component.name)
            return
        if component.health.restart_count >= self.config.max_restart_attempts:
            logger.error(
                "Component %s has exceeded max restart attempts (%s)",
                component.name,
                self.config.max_restart_attempts,
                restart_count=component.health.restart_count,
            )
            return
        try:
            component.health.state = ComponentState.RESTARTING
            component.health.restart_count += 1
            logger.info(
                "Restarting component %s",
                component.name,
                restart_attempt=component.health.restart_count,
                max_attempts=self.config.max_restart_attempts,
            )
            if component.health.restart_count > 1:
                backoff = self.config.restart_backoff_seconds * (
                    2 ** (component.health.restart_count - 1)
                )
                logger.info("Waiting %ss before restart (exponential backoff)", backoff)
                await asyncio.sleep(backoff)
            await component.restart_func()
            component.health.last_restart_time = time.time()
            component.health.consecutive_failures = 0
            logger.info("Component %s restarted successfully", component.name)
            if self.on_component_restarted:
                try:
                    self.on_component_restarted(component.name)
                except Exception as e:
                    logger.error("Error in restart callback: %s", e)
        except Exception as e:
            logger.error("Failed to restart component %s: %s", component.name, e, exc_info=True)
            component.health.state = ComponentState.FAILED

    async def _check_system_resources(self) -> None:
        try:
            memory_info = self._process.memory_info()
            memory_percent = self._process.memory_percent()
            if memory_percent > self.config.memory_threshold_percent:
                logger.warning(
                    "High memory usage: %.1f%%",
                    memory_percent,
                    memory_mb=memory_info.rss / (1024 * 1024),
                    threshold=self.config.memory_threshold_percent,
                )
            cpu_percent = self._process.cpu_percent(interval=1)
            if cpu_percent > self.config.cpu_threshold_percent:
                logger.warning(
                    "High CPU usage: %.1f%%",
                    cpu_percent,
                    threshold=self.config.cpu_threshold_percent,
                )
        except Exception as e:
            logger.error("Error checking system resources: %s", e)

    def get_component_status(self, name: str) -> dict[str, Any] | None:
        component = self._components.get(name)
        if not component:
            return None
        return {
            "name": component.name,
            "state": component.health.state.value,
            "consecutive_failures": component.health.consecutive_failures,
            "restart_count": component.health.restart_count,
            "last_check_time": component.health.last_check_time,
            "last_restart_time": component.health.last_restart_time,
            "last_error": component.health.last_error,
            "critical": component.critical,
        }

    def get_all_status(self) -> dict[str, Any]:
        try:
            memory_percent = self._process.memory_percent()
            cpu_percent = self._process.cpu_percent()
        except Exception:
            memory_percent = 0.0
            cpu_percent = 0.0
        return {
            "watchdog": {
                "running": self._running,
                "components_count": len(self._components),
                "check_interval_seconds": self.config.check_interval_seconds,
                "system_memory_percent": memory_percent,
                "system_cpu_percent": cpu_percent,
            },
            "components": {name: self.get_component_status(name) for name in self._components},
        }

    async def force_restart(self, component_name: str) -> None:
        component = self._components.get(component_name)
        if not component:
            logger.warning("Component %s not found", component_name)
            return
        logger.info("Forcing restart of component: %s", component_name)
        await self._restart_component(component)

    def reset_restart_count(self, component_name: str) -> None:
        component = self._components.get(component_name)
        if component:
            component.health.restart_count = 0
            component.health.consecutive_failures = 0
            logger.info("Reset restart count for component: %s", component_name)


class WatchdogHealthCheck:
    """Health check provider for the Watchdog system."""

    def __init__(self, watchdog: Watchdog) -> None:
        self.watchdog = watchdog

    async def check(self) -> HealthCheckResult:
        try:
            if not self.watchdog._running:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="Watchdog not running",
                    timestamp=datetime.now(tz=UTC).isoformat(),
                )
            status = self.watchdog.get_all_status()
            failed = [
                name
                for name, s in status["components"].items()
                if s and s["state"] == ComponentState.FAILED.value
            ]
            if failed:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    message=f"Components failed: {', '.join(failed)}",
                    timestamp=datetime.now(tz=UTC).isoformat(),
                    details=status,
                )
            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="All monitored components healthy",
                timestamp=datetime.now(tz=UTC).isoformat(),
                details=status,
            )
        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Watchdog health check failed: {e}",
                timestamp=datetime.now(tz=UTC).isoformat(),
            )
