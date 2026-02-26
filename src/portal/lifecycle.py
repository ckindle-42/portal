"""
Lifecycle Management - Bootstrap and Runtime Orchestration
===========================================================

This module provides lifecycle management for Portal, handling:
- Application bootstrap (loading config, initializing DI container)
- Starting the event bus and core services
- OS signal handling (SIGINT/SIGTERM)
- Graceful shutdown with timeouts and draining

v4.7.0: Enhanced with timeout handling, task draining, and shutdown priorities

This decouples lifecycle concerns from the Engine, which should
purely process input/output.

Architecture:
    CLI/Main → Runtime → Engine
                 ├─ Config Loading
                 ├─ DI Container
                 ├─ Event Bus
                 ├─ Signal Handling
                 ├─ Watchdog (v4.7.0)
                 ├─ Log Rotation (v4.7.0)
                 └─ Shutdown Sequence (Enhanced v4.7.0)
"""

import asyncio
import logging
import signal
import sys
import os
from typing import Optional, Callable, List, Set
from dataclasses import dataclass, field
from enum import Enum

from portal.config.settings import Settings, load_settings
from portal.core import create_agent_core, AgentCore
from portal.core.event_broker import create_event_broker, EventBroker
from portal.security import SecurityMiddleware
from portal.core.structured_logger import get_logger

logger = get_logger('Lifecycle')


class ShutdownPriority(Enum):
    """
    Shutdown priority levels.

    Higher priority items shut down first.
    """
    CRITICAL = 100   # Stop accepting new work
    HIGH = 75        # Stop processing new requests
    NORMAL = 50      # Normal cleanup
    LOW = 25         # Background tasks
    LOWEST = 0       # Final cleanup


@dataclass
class ShutdownCallback:
    """
    Shutdown callback with priority.

    v4.7.0: Added priority-based shutdown
    """
    callback: Callable
    priority: ShutdownPriority
    name: str
    timeout: Optional[float] = None  # Optional per-callback timeout


@dataclass
class RuntimeContext:
    """
    Runtime context containing all initialized components

    This serves as the DI container for the application.

    v4.7.0: Enhanced with watchdog and log rotation support
    """
    settings: Settings
    event_broker: EventBroker
    agent_core: AgentCore
    secure_agent: SecurityMiddleware
    shutdown_callbacks: List[ShutdownCallback] = field(default_factory=list)

    # v4.7.0: New optional components
    watchdog: Optional['Watchdog'] = None
    log_rotator: Optional['LogRotator'] = None

    # v4.7.0: Track in-flight operations
    active_tasks: Set[asyncio.Task] = field(default_factory=set)
    accepting_work: bool = True


class Runtime:
    """
    Runtime orchestrator for Portal

    Responsibilities:
    1. Bootstrap: Load config, initialize services
    2. Signal handling: Graceful shutdown on SIGINT/SIGTERM
    3. Lifecycle management: Start/stop services
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        enable_watchdog: bool = False,
        enable_log_rotation: bool = False,
        shutdown_timeout: float = 30.0
    ):
        """
        Initialize runtime

        Args:
            config_path: Optional path to configuration file
            enable_watchdog: Enable watchdog monitoring (v4.7.0)
            enable_log_rotation: Enable log rotation (v4.7.0)
            shutdown_timeout: Maximum time to wait for graceful shutdown (v4.7.0)
        """
        self.config_path = config_path
        self.enable_watchdog = enable_watchdog
        self.enable_log_rotation = enable_log_rotation
        self.shutdown_timeout = shutdown_timeout
        self.context: Optional[RuntimeContext] = None
        self._shutdown_event = asyncio.Event()
        self._initialized = False
        self._shutdown_in_progress = False

    async def bootstrap(self) -> RuntimeContext:
        """
        Bootstrap the application

        Returns:
            RuntimeContext with all initialized components
        """
        if self._initialized:
            logger.warning("Runtime already initialized")
            return self.context

        logger.info("Bootstrapping Portal runtime")

        # Step 1: Load configuration
        logger.info("Loading configuration")
        if self.config_path:
            settings = load_settings(self.config_path)
        else:
            settings = load_settings()


        # Critical guard: refuse to start with default MCP secret.
        raw_mcp_api_key = (settings.security.mcp_api_key or '').strip()
        env_mcp_api_key = os.getenv("MCP_API_KEY", "").strip()
        effective_mcp_api_key = env_mcp_api_key or raw_mcp_api_key
        if effective_mcp_api_key == "changeme-mcp-secret":
            raise RuntimeError(
                "Refusing to start: MCP_API_KEY is still set to the insecure default "
                "'changeme-mcp-secret'. Set a strong secret before booting Portal."
            )

        bootstrap_api_key = os.getenv("PORTAL_BOOTSTRAP_API_KEY", "").strip()
        if bootstrap_api_key == "portal-dev-key":
            logger.warning(
                "PORTAL_BOOTSTRAP_API_KEY is set to the insecure default 'portal-dev-key'. "
                "Set a strong key before exposing Portal outside localhost."
            )

        # Step 2: Initialize event broker
        logger.info("Initializing event broker")
        event_broker = create_event_broker(
            backend="memory",
            max_history=1000
        )

        # Step 3: Create agent core
        # create_agent_core expects a plain dict; Settings.to_agent_config()
        # extracts the relevant keys so DependencyContainer.create_* functions
        # can call config.get(...) without AttributeError on the Settings object.
        logger.info("Creating agent core")
        agent_core = create_agent_core(settings.to_agent_config())

        # Step 4: Wrap with security middleware
        logger.info("Initializing security middleware")
        secure_agent = SecurityMiddleware(
            agent_core,
            enable_rate_limiting=True,
            enable_input_sanitization=True
        )

        # Step 5: Initialize watchdog (v4.7.0)
        watchdog = None
        if self.enable_watchdog:
            from portal.observability.watchdog import Watchdog, WatchdogConfig
            logger.info("Initializing watchdog")
            watchdog = Watchdog(config=WatchdogConfig())
            # Note: Components will be registered after context creation

        # Step 6: Initialize log rotation (v4.7.0)
        log_rotator = None
        if self.enable_log_rotation:
            from portal.observability.log_rotation import LogRotator, RotationConfig
            from pathlib import Path
            log_file = settings.data_dir / "logs" / "portal.log"
            logger.info(f"Initializing log rotation for {log_file}")
            log_rotator = LogRotator(
                log_file=log_file,
                config=RotationConfig()
            )

        # Step 7: Setup signal handlers
        self._setup_signal_handlers()

        # Create runtime context
        self.context = RuntimeContext(
            settings=settings,
            event_broker=event_broker,
            agent_core=agent_core,
            secure_agent=secure_agent,
            watchdog=watchdog,
            log_rotator=log_rotator
        )

        # Start optional components (v4.7.0)
        if watchdog:
            await watchdog.start()
        if log_rotator:
            await log_rotator.start()

        self._initialized = True
        logger.info(
            "Runtime bootstrap completed",
            watchdog_enabled=self.enable_watchdog,
            log_rotation_enabled=self.enable_log_rotation
        )

        return self.context

    def _setup_signal_handlers(self):
        """Setup OS signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            """Handle shutdown signals"""
            signal_name = signal.Signals(signum).name
            logger.info(f"Received {signal_name}, initiating graceful shutdown")
            self._shutdown_event.set()

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.debug("Signal handlers registered")

    async def wait_for_shutdown(self):
        """Wait for shutdown signal"""
        await self._shutdown_event.wait()

    async def shutdown(self):
        """
        Enhanced graceful shutdown sequence

        v4.7.0: Added timeout handling, task draining, and priority-based shutdown

        Stops all services in priority order with proper timeout handling.
        """
        if not self._initialized:
            logger.warning("Runtime not initialized, nothing to shutdown")
            return

        if self._shutdown_in_progress:
            logger.warning("Shutdown already in progress")
            return

        self._shutdown_in_progress = True
        shutdown_start = asyncio.get_running_loop().time()

        logger.info(
            "Starting graceful shutdown",
            timeout_seconds=self.shutdown_timeout
        )

        try:
            # Phase 1: Stop accepting new work (CRITICAL priority)
            logger.info("Phase 1: Stopping new work acceptance")
            self.context.accepting_work = False

            # Phase 2: Wait for in-flight operations to complete
            logger.info(
                "Phase 2: Draining in-flight operations",
                active_tasks=len(self.context.active_tasks)
            )

            if self.context.active_tasks:
                try:
                    await asyncio.wait_for(
                        self._drain_active_tasks(),
                        timeout=self.shutdown_timeout * 0.5  # Use half timeout for draining
                    )
                    logger.info("All in-flight operations completed")
                except asyncio.TimeoutError:
                    logger.warning(
                        f"Timeout waiting for tasks to drain, {len(self.context.active_tasks)} tasks still active"
                    )

            # Phase 3: Stop optional components (v4.7.0)
            logger.info("Phase 3: Stopping optional components")

            if self.context.watchdog:
                try:
                    logger.info("Stopping watchdog")
                    await asyncio.wait_for(
                        self.context.watchdog.stop(),
                        timeout=5.0
                    )
                except Exception as e:
                    logger.error(f"Error stopping watchdog: {e}", exc_info=True)

            if self.context.log_rotator:
                try:
                    logger.info("Stopping log rotator")
                    await asyncio.wait_for(
                        self.context.log_rotator.stop(),
                        timeout=5.0
                    )
                except Exception as e:
                    logger.error(f"Error stopping log rotator: {e}", exc_info=True)

            # Phase 4: Run custom shutdown callbacks in priority order
            logger.info("Phase 4: Running shutdown callbacks")

            # Sort callbacks by priority (highest first)
            sorted_callbacks = sorted(
                self.context.shutdown_callbacks,
                key=lambda cb: cb.priority.value,
                reverse=True
            )

            for callback in sorted_callbacks:
                try:
                    callback_timeout = callback.timeout or 10.0
                    logger.debug(
                        f"Executing shutdown callback: {callback.name}",
                        priority=callback.priority.value,
                        timeout=callback_timeout
                    )

                    if asyncio.iscoroutinefunction(callback.callback):
                        await asyncio.wait_for(
                            callback.callback(),
                            timeout=callback_timeout
                        )
                    else:
                        # Run sync callback in thread pool
                        loop = asyncio.get_running_loop()
                        await asyncio.wait_for(
                            loop.run_in_executor(None, callback.callback),
                            timeout=callback_timeout
                        )

                except asyncio.TimeoutError:
                    logger.error(
                        f"Shutdown callback timed out: {callback.name}",
                        timeout=callback_timeout
                    )
                except Exception as e:
                    logger.error(
                        f"Error in shutdown callback {callback.name}: {e}",
                        exc_info=True
                    )

            # Phase 5: Cleanup agent core
            logger.info("Phase 5: Cleaning up agent core")
            try:
                await asyncio.wait_for(
                    self.context.secure_agent.cleanup(),
                    timeout=10.0
                )
            except Exception as e:
                logger.error(f"Error cleaning up agent core: {e}", exc_info=True)

            # Phase 6: Clear event history
            logger.info("Phase 6: Clearing event history")
            try:
                await asyncio.wait_for(
                    self.context.event_broker.clear_history(),
                    timeout=5.0
                )
            except Exception as e:
                logger.error(f"Error clearing event history: {e}", exc_info=True)

            # Calculate shutdown duration
            shutdown_duration = asyncio.get_running_loop().time() - shutdown_start

            self._initialized = False
            logger.info(
                "Shutdown completed",
                duration_seconds=shutdown_duration,
                within_timeout=shutdown_duration < self.shutdown_timeout
            )

        except Exception as e:
            logger.error(f"Critical error during shutdown: {e}", exc_info=True)
        finally:
            self._shutdown_in_progress = False

    async def _drain_active_tasks(self):
        """
        Wait for all active tasks to complete.

        v4.7.0: New method for draining in-flight operations
        """
        while self.context.active_tasks:
            # Cancel any tasks that are still running
            done, pending = await asyncio.wait(
                self.context.active_tasks,
                timeout=1.0,
                return_when=asyncio.FIRST_COMPLETED
            )

            # Remove completed tasks
            for task in done:
                self.context.active_tasks.discard(task)

            logger.debug(
                "Draining tasks",
                completed=len(done),
                remaining=len(self.context.active_tasks)
            )

    def register_shutdown_callback(
        self,
        callback: Callable,
        priority: ShutdownPriority = ShutdownPriority.NORMAL,
        name: Optional[str] = None,
        timeout: Optional[float] = None
    ):
        """
        Register a callback to be executed during shutdown

        v4.7.0: Enhanced with priority and timeout support

        Args:
            callback: Function or coroutine to execute
            priority: Shutdown priority (higher runs first)
            name: Optional callback name for logging
            timeout: Optional per-callback timeout
        """
        if not self.context:
            logger.warning("Cannot register shutdown callback: Runtime not initialized")
            return

        callback_name = name or getattr(callback, '__name__', 'unknown')

        shutdown_callback = ShutdownCallback(
            callback=callback,
            priority=priority,
            name=callback_name,
            timeout=timeout
        )

        self.context.shutdown_callbacks.append(shutdown_callback)

        logger.debug(
            f"Registered shutdown callback: {callback_name}",
            priority=priority.value
        )

    def track_task(self, task: asyncio.Task):
        """
        Track an active task for graceful shutdown draining.

        v4.7.0: New method for tracking in-flight operations

        Args:
            task: Task to track
        """
        if self.context:
            self.context.active_tasks.add(task)
            task.add_done_callback(lambda t: self.context.active_tasks.discard(t))

    def is_accepting_work(self) -> bool:
        """
        Check if runtime is accepting new work.

        v4.7.0: New method to check shutdown state

        Returns:
            True if accepting work, False if shutting down
        """
        return self.context and self.context.accepting_work and not self._shutdown_in_progress


async def run_with_lifecycle(
    main_task: Callable[[RuntimeContext], None],
    config_path: Optional[str] = None
):
    """
    Helper function to run an application with proper lifecycle management

    Args:
        main_task: Async function that runs the main application logic
        config_path: Optional path to configuration file

    Example:
        async def main(ctx: RuntimeContext):
            # Your application logic here
            await my_interface.start()

        asyncio.run(run_with_lifecycle(main))
    """
    runtime = Runtime(config_path)

    try:
        # Bootstrap
        context = await runtime.bootstrap()

        # Run main task
        await main_task(context)

        # Wait for shutdown signal
        await runtime.wait_for_shutdown()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Graceful shutdown
        await runtime.shutdown()
