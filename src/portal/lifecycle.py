"""Lifecycle Management — bootstrap, signal handling, and graceful shutdown for Portal."""

from __future__ import annotations

import asyncio
import os
import signal
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from portal.config.settings import Settings, load_settings
from portal.core import AgentCore, create_agent_core
from portal.core.structured_logger import get_logger
from portal.security import SecurityMiddleware

if TYPE_CHECKING:
    from portal.observability.log_rotation import LogRotator
    from portal.observability.watchdog import Watchdog

logger = get_logger("Lifecycle")


class ShutdownPriority(Enum):
    """Shutdown priority levels (higher = shuts down first)."""

    CRITICAL = 100
    HIGH = 75
    NORMAL = 50
    LOW = 25
    LOWEST = 0


@dataclass
class ShutdownCallback:
    """Shutdown callback with priority."""

    callback: Callable
    priority: ShutdownPriority
    name: str
    timeout: float | None = None


@dataclass
class RuntimeContext:
    """DI container holding all initialized Portal components."""

    settings: Settings
    agent_core: AgentCore
    secure_agent: SecurityMiddleware
    shutdown_callbacks: list[ShutdownCallback] = field(default_factory=list)

    # Optional components
    watchdog: Watchdog | None = None
    log_rotator: LogRotator | None = None

    # Track in-flight operations
    active_tasks: set[asyncio.Task] = field(default_factory=set)
    accepting_work: bool = True


class Runtime:
    """Runtime orchestrator — bootstrap, signal handling, graceful shutdown."""

    def __init__(
        self,
        config_path: str | None = None,
        enable_watchdog: bool = False,
        enable_log_rotation: bool = False,
        shutdown_timeout: float = 30.0,
    ):
        self.config_path = config_path
        self.enable_watchdog = enable_watchdog
        self.enable_log_rotation = enable_log_rotation
        self.shutdown_timeout = shutdown_timeout
        self.context: RuntimeContext | None = None
        self._shutdown_event = asyncio.Event()
        self._initialized = False
        self._shutdown_in_progress = False

    async def bootstrap(self) -> RuntimeContext:
        """Bootstrap the application and return RuntimeContext."""
        if self._initialized:
            logger.warning("Runtime already initialized")
            return self.context

        logger.info("Bootstrapping Portal runtime")
        settings = load_settings(self.config_path) if self.config_path else load_settings()

        # Refuse to start with insecure default MCP secret
        raw_mcp_api_key = (settings.security.mcp_api_key or "").strip()
        env_mcp_api_key = os.getenv("MCP_API_KEY", "").strip()
        effective_mcp_api_key = env_mcp_api_key or raw_mcp_api_key
        if effective_mcp_api_key == "changeme-mcp-secret":
            raise RuntimeError(
                "Refusing to start: MCP_API_KEY is still set to the insecure default "
                "'changeme-mcp-secret'. Set a strong secret before booting Portal."
            )

        effective_bootstrap_key = os.getenv("PORTAL_BOOTSTRAP_API_KEY", "").strip()
        portal_env = os.getenv("PORTAL_ENV", "production")
        if portal_env != "development" and effective_bootstrap_key in ("portal-dev-key", ""):
            raise RuntimeError(
                "Refusing to start: PORTAL_BOOTSTRAP_API_KEY is not set or uses the insecure "
                "default 'portal-dev-key'. Generate a strong key: "
                'python -c "import secrets; print(secrets.token_urlsafe(32))"'
            )

        agent_core = create_agent_core(settings.to_agent_config())
        secure_agent = SecurityMiddleware(
            agent_core, enable_rate_limiting=True, enable_input_sanitization=True
        )

        # Auto-discover live Ollama models and add them to the registry (R1)
        try:
            ollama_url = getattr(
                getattr(settings, "backends", None), "ollama_url", "http://localhost:11434"
            )
            newly_registered = await agent_core.model_registry.discover_from_ollama(
                base_url=ollama_url,
                mark_others_unavailable=False,
            )
            if newly_registered:
                logger.info("Discovered %d Ollama model(s) at startup", len(newly_registered))
        except Exception as _disc_err:
            logger.warning(
                "Ollama model discovery failed (will use static registry): %s", _disc_err
            )

        watchdog = None
        if self.enable_watchdog:
            from portal.observability.watchdog import Watchdog, WatchdogConfig

            logger.info("Initializing watchdog")
            watchdog = Watchdog(config=WatchdogConfig())

        log_rotator = None
        if self.enable_log_rotation:
            from portal.observability.log_rotation import LogRotator, RotationConfig

            log_file = settings.data_dir / "logs" / "portal.log"
            logger.info("Initializing log rotation for %s", log_file)
            log_rotator = LogRotator(log_file=log_file, config=RotationConfig())

        self._setup_signal_handlers()
        self.context = RuntimeContext(
            settings=settings,
            agent_core=agent_core,
            secure_agent=secure_agent,
            watchdog=watchdog,
            log_rotator=log_rotator,
        )

        if watchdog:
            await watchdog.start()
        if log_rotator:
            await log_rotator.start()

        config_watch_path = Path(self.config_path) if self.config_path else Path("portal.yaml")
        if config_watch_path.exists():
            from portal.observability.config_watcher import ConfigWatcher

            config_watcher = ConfigWatcher(config_file=config_watch_path)
            asyncio.create_task(config_watcher.start(), name="config-watcher")
            logger.info("Config watcher started for %s", config_watch_path)

        self._initialized = True
        logger.info(
            "Runtime bootstrap completed",
            watchdog_enabled=self.enable_watchdog,
            log_rotation_enabled=self.enable_log_rotation,
        )

        return self.context

    def _setup_signal_handlers(self):
        """Setup OS signal handlers for graceful shutdown."""

        def signal_handler(signum, _frame):
            signal_name = signal.Signals(signum).name
            logger.info("Received %s, initiating graceful shutdown", signal_name)
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.debug("Signal handlers registered")

    async def wait_for_shutdown(self):
        """Wait for shutdown signal."""
        await self._shutdown_event.wait()

    async def shutdown(self):
        """Graceful shutdown: drain tasks, stop components, run callbacks, cleanup."""
        if not self._initialized:
            logger.warning("Runtime not initialized, nothing to shutdown")
            return
        if self._shutdown_in_progress:
            logger.warning("Shutdown already in progress")
            return

        self._shutdown_in_progress = True
        shutdown_start = asyncio.get_running_loop().time()
        logger.info("Starting graceful shutdown", timeout_seconds=self.shutdown_timeout)

        try:
            self.context.accepting_work = False
            await self._drain_tasks()
            await self._stop_optional_components()
            await self._run_shutdown_callbacks()
            await self._cleanup_agent_core()

            shutdown_duration = asyncio.get_running_loop().time() - shutdown_start
            self._initialized = False
            logger.info(
                "Shutdown completed",
                duration_seconds=shutdown_duration,
                within_timeout=shutdown_duration < self.shutdown_timeout,
            )
        except Exception as e:
            logger.error("Critical error during shutdown: %s", e, exc_info=True)
        finally:
            self._shutdown_in_progress = False

    async def _drain_tasks(self):
        """Wait for in-flight tasks to complete within half the shutdown timeout."""
        if not self.context.active_tasks:
            return
        logger.info("Draining in-flight operations", active_tasks=len(self.context.active_tasks))
        try:
            await asyncio.wait_for(self._drain_active_tasks(), timeout=self.shutdown_timeout * 0.5)
            logger.info("All in-flight operations completed")
        except TimeoutError:
            logger.warning(
                "Timeout waiting for tasks to drain, %d tasks still active",
                len(self.context.active_tasks),
            )

    async def _stop_optional_components(self):
        """Stop watchdog and log rotator."""
        for name, component in [
            ("watchdog", self.context.watchdog),
            ("log_rotator", self.context.log_rotator),
        ]:
            if component is None:
                continue
            try:
                logger.info("Stopping %s", name)
                await asyncio.wait_for(component.stop(), timeout=5.0)
            except Exception as e:
                logger.error("Error stopping %s: %s", name, e, exc_info=True)

    async def _run_shutdown_callbacks(self):
        """Run registered shutdown callbacks in priority order."""
        sorted_callbacks = sorted(
            self.context.shutdown_callbacks, key=lambda cb: cb.priority.value, reverse=True
        )
        for cb in sorted_callbacks:
            cb_timeout = cb.timeout or 10.0
            try:
                if asyncio.iscoroutinefunction(cb.callback):
                    await asyncio.wait_for(cb.callback(), timeout=cb_timeout)
                else:
                    loop = asyncio.get_running_loop()
                    await asyncio.wait_for(
                        loop.run_in_executor(None, cb.callback), timeout=cb_timeout
                    )
            except TimeoutError:
                logger.error("Shutdown callback timed out: %s", cb.name)
            except Exception as e:
                logger.error("Error in shutdown callback %s: %s", cb.name, e, exc_info=True)

    async def _cleanup_agent_core(self):
        """Cleanup the agent core via security middleware."""
        try:
            await asyncio.wait_for(self.context.secure_agent.cleanup(), timeout=10.0)
        except Exception as e:
            logger.error("Error cleaning up agent core: %s", e, exc_info=True)

    async def _drain_active_tasks(self):
        """Wait for all active tasks to complete."""
        while self.context.active_tasks:
            done, _pending = await asyncio.wait(
                self.context.active_tasks, timeout=1.0, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                self.context.active_tasks.discard(task)
            logger.debug(
                "Draining tasks", completed=len(done), remaining=len(self.context.active_tasks)
            )

    def register_shutdown_callback(
        self,
        callback: Callable,
        priority: ShutdownPriority = ShutdownPriority.NORMAL,
        name: str | None = None,
        timeout: float | None = None,
    ):
        """Register a callback to be executed during shutdown."""
        if not self.context:
            logger.warning("Cannot register shutdown callback: Runtime not initialized")
            return

        callback_name = name or getattr(callback, "__name__", "unknown")
        self.context.shutdown_callbacks.append(
            ShutdownCallback(
                callback=callback, priority=priority, name=callback_name, timeout=timeout
            )
        )
        logger.debug("Registered shutdown callback: %s", callback_name, priority=priority.value)

    def track_task(self, task: asyncio.Task):
        """Track an active task for graceful shutdown draining."""
        if self.context:
            self.context.active_tasks.add(task)
            task.add_done_callback(lambda t: self.context.active_tasks.discard(t))

    def is_accepting_work(self) -> bool:
        """Check if runtime is accepting new work."""
        return bool(self.context and self.context.accepting_work and not self._shutdown_in_progress)
