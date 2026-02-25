"""
Watchdog - Process Monitoring and Auto-Recovery
================================================

Monitors critical components and automatically restarts failed processes.

Features:
- Component health monitoring
- Automatic restart on failure
- Deadlock detection
- Resource monitoring (memory, CPU)
- Configurable thresholds
- Integration with health check system

v4.7.0: Initial implementation for production reliability
"""

import asyncio
import logging
import psutil
import time
from typing import Dict, Any, Optional, Callable, List, Awaitable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from .health import HealthCheckSystem, HealthStatus, HealthCheckResult

logger = logging.getLogger(__name__)


class ComponentState(Enum):
    """Component states"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RESTARTING = "restarting"
    STOPPED = "stopped"


@dataclass
class WatchdogConfig:
    """Configuration for watchdog monitoring"""

    # Health check interval
    check_interval_seconds: int = 30

    # Failure thresholds
    max_consecutive_failures: int = 3
    restart_on_failure: bool = True
    max_restart_attempts: int = 5
    restart_backoff_seconds: int = 10

    # Resource thresholds
    memory_threshold_percent: float = 90.0
    cpu_threshold_percent: float = 95.0

    # Deadlock detection
    deadlock_timeout_seconds: int = 300  # 5 minutes

    # Alerting
    alert_on_failure: bool = True
    alert_on_restart: bool = True


@dataclass
class ComponentHealth:
    """Health status of a monitored component"""

    name: str
    state: ComponentState
    last_check_time: float
    consecutive_failures: int = 0
    restart_count: int = 0
    last_restart_time: Optional[float] = None
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MonitoredComponent:
    """
    Represents a component being monitored by the watchdog.

    Components must provide:
    - health_check(): Returns health status
    - restart(): Restarts the component
    """

    def __init__(
        self,
        name: str,
        health_check: Callable[[], Awaitable[HealthCheckResult]],
        restart_func: Optional[Callable[[], Awaitable[None]]] = None,
        critical: bool = True
    ):
        """
        Initialize monitored component.

        Args:
            name: Component name
            health_check: Async function that returns HealthCheckResult
            restart_func: Optional async function to restart component
            critical: Whether component is critical (restart on failure)
        """
        self.name = name
        self.health_check = health_check
        self.restart_func = restart_func
        self.critical = critical

        self.health = ComponentHealth(
            name=name,
            state=ComponentState.HEALTHY,
            last_check_time=time.time()
        )


class Watchdog:
    """
    Watchdog system for monitoring and auto-recovery.

    Monitors registered components and automatically restarts failed ones.

    Example:
        >>> watchdog = Watchdog(config=WatchdogConfig(check_interval_seconds=30))
        >>>
        >>> # Register components
        >>> watchdog.register_component(
        ...     name="worker_pool",
        ...     health_check=worker_pool.health_check,
        ...     restart_func=worker_pool.restart
        ... )
        >>>
        >>> # Start monitoring
        >>> await watchdog.start()
    """

    def __init__(
        self,
        config: Optional[WatchdogConfig] = None,
        health_system: Optional[HealthCheckSystem] = None,
        on_component_failed: Optional[Callable[[str, str], None]] = None,
        on_component_restarted: Optional[Callable[[str], None]] = None
    ):
        """
        Initialize watchdog.

        Args:
            config: Watchdog configuration
            health_system: Optional HealthCheckSystem for integration
            on_component_failed: Callback when component fails (name, error)
            on_component_restarted: Callback when component is restarted (name)
        """
        self.config = config or WatchdogConfig()
        self.health_system = health_system
        self.on_component_failed = on_component_failed
        self.on_component_restarted = on_component_restarted

        self._components: Dict[str, MonitoredComponent] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._process = psutil.Process()

        logger.info(
            "Watchdog initialized",
            check_interval=self.config.check_interval_seconds,
            max_failures=self.config.max_consecutive_failures,
            restart_enabled=self.config.restart_on_failure
        )

    def register_component(
        self,
        name: str,
        health_check: Callable[[], Awaitable[HealthCheckResult]],
        restart_func: Optional[Callable[[], Awaitable[None]]] = None,
        critical: bool = True
    ):
        """
        Register a component for monitoring.

        Args:
            name: Unique component name
            health_check: Async function returning HealthCheckResult
            restart_func: Optional async restart function
            critical: Whether to restart on failure
        """
        component = MonitoredComponent(
            name=name,
            health_check=health_check,
            restart_func=restart_func,
            critical=critical
        )

        self._components[name] = component

        logger.info(
            f"Registered component for monitoring: {name}",
            critical=critical,
            has_restart_func=restart_func is not None
        )

    def unregister_component(self, name: str):
        """
        Unregister a component.

        Args:
            name: Component name
        """
        if name in self._components:
            del self._components[name]
            logger.info(f"Unregistered component: {name}")

    async def start(self):
        """Start watchdog monitoring"""
        if self._running:
            logger.warning("Watchdog already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())

        logger.info(
            f"Watchdog started",
            components_count=len(self._components),
            check_interval=self.config.check_interval_seconds
        )

    async def stop(self):
        """Stop watchdog monitoring"""
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

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        try:
            while self._running:
                await asyncio.sleep(self.config.check_interval_seconds)

                # Check all components
                for component in self._components.values():
                    try:
                        await self._check_component(component)
                    except Exception as e:
                        logger.error(
                            f"Error checking component {component.name}: {e}",
                            exc_info=True
                        )

                # Monitor system resources
                await self._check_system_resources()

        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Fatal error in monitoring loop: {e}", exc_info=True)

    async def _check_component(self, component: MonitoredComponent):
        """
        Check health of a single component.

        Args:
            component: Component to check
        """
        try:
            # Run health check
            result = await component.health_check()

            component.health.last_check_time = time.time()

            # Update component state based on health check
            if result.status == HealthStatus.HEALTHY:
                # Component is healthy
                if component.health.state != ComponentState.HEALTHY:
                    logger.info(f"Component {component.name} recovered")

                component.health.state = ComponentState.HEALTHY
                component.health.consecutive_failures = 0
                component.health.last_error = None

            elif result.status == HealthStatus.DEGRADED:
                # Component is degraded
                component.health.state = ComponentState.DEGRADED
                component.health.consecutive_failures += 1

                logger.warning(
                    f"Component {component.name} is degraded",
                    consecutive_failures=component.health.consecutive_failures,
                    message=result.message
                )

            elif result.status == HealthStatus.UNHEALTHY:
                # Component failed
                component.health.state = ComponentState.FAILED
                component.health.consecutive_failures += 1
                component.health.last_error = result.message

                logger.error(
                    f"Component {component.name} failed",
                    consecutive_failures=component.health.consecutive_failures,
                    error=result.message
                )

                # Trigger failure callback
                if self.on_component_failed:
                    try:
                        self.on_component_failed(component.name, result.message)
                    except Exception as e:
                        logger.error(f"Error in failure callback: {e}")

                # Check if we should restart
                if (component.critical and
                    self.config.restart_on_failure and
                    component.health.consecutive_failures >= self.config.max_consecutive_failures):

                    await self._restart_component(component)

        except Exception as e:
            # Health check itself failed
            component.health.state = ComponentState.FAILED
            component.health.consecutive_failures += 1
            component.health.last_error = str(e)

            logger.error(
                f"Health check failed for {component.name}: {e}",
                exc_info=True
            )

    async def _restart_component(self, component: MonitoredComponent):
        """
        Restart a failed component.

        Args:
            component: Component to restart
        """
        if not component.restart_func:
            logger.warning(f"No restart function for component {component.name}")
            return

        if component.health.restart_count >= self.config.max_restart_attempts:
            logger.error(
                f"Component {component.name} has exceeded max restart attempts ({self.config.max_restart_attempts})",
                restart_count=component.health.restart_count
            )
            return

        try:
            component.health.state = ComponentState.RESTARTING
            component.health.restart_count += 1

            logger.info(
                f"Restarting component {component.name}",
                restart_attempt=component.health.restart_count,
                max_attempts=self.config.max_restart_attempts
            )

            # Apply backoff delay
            if component.health.restart_count > 1:
                backoff = self.config.restart_backoff_seconds * (2 ** (component.health.restart_count - 1))
                logger.info(f"Waiting {backoff}s before restart (exponential backoff)")
                await asyncio.sleep(backoff)

            # Execute restart
            await component.restart_func()

            component.health.last_restart_time = time.time()
            component.health.consecutive_failures = 0

            logger.info(f"Component {component.name} restarted successfully")

            # Trigger restart callback
            if self.on_component_restarted:
                try:
                    self.on_component_restarted(component.name)
                except Exception as e:
                    logger.error(f"Error in restart callback: {e}")

        except Exception as e:
            logger.error(f"Failed to restart component {component.name}: {e}", exc_info=True)
            component.health.state = ComponentState.FAILED

    async def _check_system_resources(self):
        """Monitor system-level resources"""
        try:
            # Memory usage
            memory_info = self._process.memory_info()
            memory_percent = self._process.memory_percent()

            if memory_percent > self.config.memory_threshold_percent:
                logger.warning(
                    f"High memory usage: {memory_percent:.1f}%",
                    memory_mb=memory_info.rss / (1024 * 1024),
                    threshold=self.config.memory_threshold_percent
                )

            # CPU usage
            cpu_percent = self._process.cpu_percent(interval=1)

            if cpu_percent > self.config.cpu_threshold_percent:
                logger.warning(
                    f"High CPU usage: {cpu_percent:.1f}%",
                    threshold=self.config.cpu_threshold_percent
                )

        except Exception as e:
            logger.error(f"Error checking system resources: {e}")

    def get_component_status(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a specific component.

        Args:
            name: Component name

        Returns:
            Status dictionary or None if not found
        """
        component = self._components.get(name)
        if not component:
            return None

        return {
            'name': component.name,
            'state': component.health.state.value,
            'consecutive_failures': component.health.consecutive_failures,
            'restart_count': component.health.restart_count,
            'last_check_time': component.health.last_check_time,
            'last_restart_time': component.health.last_restart_time,
            'last_error': component.health.last_error,
            'critical': component.critical
        }

    def get_all_status(self) -> Dict[str, Any]:
        """
        Get status of all monitored components.

        Returns:
            Dictionary with watchdog and component status
        """
        components_status = {
            name: self.get_component_status(name)
            for name in self._components.keys()
        }

        # System resource usage
        try:
            memory_percent = self._process.memory_percent()
            cpu_percent = self._process.cpu_percent()
        except:
            memory_percent = 0.0
            cpu_percent = 0.0

        return {
            'watchdog': {
                'running': self._running,
                'components_count': len(self._components),
                'check_interval_seconds': self.config.check_interval_seconds,
                'system_memory_percent': memory_percent,
                'system_cpu_percent': cpu_percent
            },
            'components': components_status
        }

    async def force_restart(self, component_name: str):
        """
        Manually force restart of a component.

        Args:
            component_name: Name of component to restart
        """
        component = self._components.get(component_name)
        if not component:
            logger.warning(f"Component {component_name} not found")
            return

        logger.info(f"Forcing restart of component: {component_name}")
        await self._restart_component(component)

    def reset_restart_count(self, component_name: str):
        """
        Reset restart count for a component.

        Args:
            component_name: Name of component
        """
        component = self._components.get(component_name)
        if component:
            component.health.restart_count = 0
            component.health.consecutive_failures = 0
            logger.info(f"Reset restart count for component: {component_name}")


# =============================================================================
# HEALTH CHECK INTEGRATION
# =============================================================================

class WatchdogHealthCheck:
    """Health check provider for Watchdog system"""

    def __init__(self, watchdog: Watchdog):
        """
        Initialize watchdog health check.

        Args:
            watchdog: Watchdog instance
        """
        self.watchdog = watchdog

    async def check(self) -> HealthCheckResult:
        """Check watchdog health"""
        try:
            if not self.watchdog._running:
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="Watchdog not running",
                    timestamp=datetime.now().isoformat()
                )

            status = self.watchdog.get_all_status()

            # Check if any critical components are failed
            failed_components = [
                name for name, comp_status in status['components'].items()
                if comp_status and comp_status['state'] == ComponentState.FAILED.value
            ]

            if failed_components:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    message=f"Components failed: {', '.join(failed_components)}",
                    timestamp=datetime.now().isoformat(),
                    details=status
                )

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="All monitored components healthy",
                timestamp=datetime.now().isoformat(),
                details=status
            )

        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Watchdog health check failed: {e}",
                timestamp=datetime.now().isoformat()
            )
