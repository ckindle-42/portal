"""
Base Interface Abstract Class
==============================

Defines the contract that all PocketPortal interfaces must implement.
This enables the AgentCore to work with any interface uniformly.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable, Awaitable
from dataclasses import dataclass
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """
    Standardized message format across all interfaces.

    This abstraction allows the core agent to process messages
    without knowing which interface they came from.
    """
    user_id: str
    content: str
    interface_type: str  # "telegram", "web", "slack", etc.
    metadata: Dict[str, Any] = None  # Interface-specific metadata
    chat_id: Optional[str] = None
    message_id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Response:
    """
    Standardized response format from the agent.

    Interfaces translate this into their native format.
    """
    content: str
    message_type: str = "text"  # "text", "image", "file", "code", etc.
    metadata: Dict[str, Any] = None
    reply_to_message_id: Optional[str] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseInterface(ABC):
    """
    Abstract base class for all PocketPortal interfaces.

    All interfaces (Telegram, Web, Slack, Discord, etc.) must implement
    this contract to ensure uniform interaction with the agent core.

    Design Principles:
    1. **Dependency Injection**: AgentCore is injected, not created internally
    2. **Async First**: All methods are async for non-blocking I/O
    3. **Message Abstraction**: Uses standardized Message/Response objects
    4. **Lifecycle Management**: Clear start/stop methods for resource management
    """

    def __init__(self, agent_core: Any, config: Dict[str, Any]):
        """
        Initialize the interface.

        Args:
            agent_core: The agent core instance (AgentCore or SecurityMiddleware wrapper)
            config: Interface-specific configuration
        """
        self.agent_core = agent_core
        self.config = config
        self.is_running = False
        self._shutdown_event = asyncio.Event()
        logger.info(f"Initialized {self.__class__.__name__}")

    @abstractmethod
    async def start(self) -> None:
        """
        Start the interface and begin listening for messages.

        This method should:
        1. Initialize connections (websockets, bot API, etc.)
        2. Register message handlers
        3. Start the event loop
        4. Set self.is_running = True

        Should be idempotent - calling multiple times should be safe.
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the interface and cleanup resources.

        This method should:
        1. Stop accepting new messages
        2. Complete in-flight requests
        3. Close connections gracefully
        4. Release resources
        5. Set self.is_running = False

        Should be idempotent - calling multiple times should be safe.
        """
        pass

    @abstractmethod
    async def handle_message(self, message: Message) -> Response:
        """
        Process an incoming message and return a response.

        This is the core message processing method. It should:
        1. Validate the message
        2. Call agent_core.process_message(message.content, message.user_id)
        3. Translate the agent response into a Response object
        4. Handle errors gracefully

        Args:
            message: Standardized message object

        Returns:
            Response object to send back to the user

        Raises:
            May raise interface-specific exceptions
        """
        pass

    @abstractmethod
    async def send_message(self, user_id: str, response: Response) -> bool:
        """
        Send a message to a specific user.

        This enables proactive messaging (notifications, alerts, etc.)

        Args:
            user_id: The user to send to (interface-specific ID)
            response: The response to send

        Returns:
            True if sent successfully, False otherwise
        """
        pass

    # Optional methods with default implementations

    async def on_error(self, error: Exception, message: Optional[Message] = None) -> None:
        """
        Handle errors that occur during message processing.

        Default implementation logs the error. Override for custom behavior.

        Args:
            error: The exception that occurred
            message: The message being processed (if any)
        """
        logger.error(
            f"Error in {self.__class__.__name__}: {error}",
            exc_info=error,
            extra={"message": message}
        )

    async def health_check(self) -> bool:
        """
        Check if the interface is healthy and operational.

        Returns:
            True if healthy, False otherwise
        """
        return self.is_running

    async def get_status(self) -> Dict[str, Any]:
        """
        Get current status information about the interface.

        Returns:
            Dictionary with status information
        """
        return {
            "interface": self.__class__.__name__,
            "is_running": self.is_running,
            "config_keys": list(self.config.keys()) if self.config else []
        }

    def register_event_handler(self, event_type: str, handler: Callable[[Any], Awaitable[None]]) -> None:
        """
        Register a handler for interface-specific events.

        This allows the core to subscribe to events like:
        - User joined
        - User left
        - Typing indicator
        - File uploaded

        Args:
            event_type: Type of event to handle
            handler: Async function to call when event occurs
        """
        # Default implementation does nothing
        # Override in subclasses that support events
        pass

    async def wait_until_stopped(self) -> None:
        """
        Wait until the interface is stopped.

        Useful for keeping the main process alive.
        """
        await self._shutdown_event.wait()

    def _signal_shutdown(self) -> None:
        """
        Signal that the interface has been stopped.

        Call this from your stop() implementation.
        """
        self._shutdown_event.set()


class InterfaceManager:
    """
    Manages multiple interfaces simultaneously.

    Allows running Telegram, Web, and other interfaces concurrently
    with a single agent core instance.
    """

    def __init__(self, agent_core: Any):
        """
        Initialize the interface manager.

        Args:
            agent_core: The agent core to share across interfaces
        """
        self.agent_core = agent_core
        self.interfaces: Dict[str, BaseInterface] = {}
        logger.info("InterfaceManager initialized")

    def register(self, name: str, interface: BaseInterface) -> None:
        """
        Register an interface.

        Args:
            name: Unique name for the interface
            interface: The interface instance
        """
        self.interfaces[name] = interface
        logger.info(f"Registered interface: {name}")

    async def start_all(self) -> None:
        """Start all registered interfaces concurrently."""
        logger.info(f"Starting {len(self.interfaces)} interfaces...")
        tasks = [interface.start() for interface in self.interfaces.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("All interfaces started")

    async def stop_all(self) -> None:
        """Stop all registered interfaces gracefully."""
        logger.info(f"Stopping {len(self.interfaces)} interfaces...")
        tasks = [interface.stop() for interface in self.interfaces.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("All interfaces stopped")

    async def health_check_all(self) -> Dict[str, bool]:
        """
        Check health of all interfaces.

        Returns:
            Dictionary mapping interface names to health status
        """
        results = {}
        for name, interface in self.interfaces.items():
            try:
                results[name] = await interface.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {name}: {e}")
                results[name] = False
        return results


__all__ = [
    'BaseInterface',
    'InterfaceManager',
    'Message',
    'Response',
]
