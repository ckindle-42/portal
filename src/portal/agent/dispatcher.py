"""
CentralDispatcher — dictionary-based interface registry.

Interfaces self-register with the @CentralDispatcher.register("name")
decorator, eliminating hard-coded switch statements.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class UnknownInterfaceError(Exception):
    """Raised when an unknown interface name is requested."""


class CentralDispatcher:
    """
    Registry-based dispatcher for Portal interfaces.

    Interfaces register themselves at class-definition time:

        @CentralDispatcher.register("web")
        class WebInterface(BaseInterface):
            ...

    Usage:
        iface_cls = CentralDispatcher.get("web")
        interface = iface_cls(agent_core, config)
    """

    _registry: dict[str, type[Any]] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[type[Any]], type[Any]]:
        """Decorator: register *interface_cls* under *name*."""

        def decorator(interface_cls: type[Any]) -> type[Any]:
            cls._registry[name] = interface_cls
            logger.debug("Registered interface %r → %s", name, interface_cls.__qualname__)
            return interface_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> type[Any]:
        """Return the interface class registered under *name*.

        Raises:
            UnknownInterfaceError: if no interface is registered for *name*.
        """
        try:
            return cls._registry[name]
        except KeyError:
            available = ", ".join(sorted(cls._registry)) or "<none>"
            raise UnknownInterfaceError(
                f"No interface registered for {name!r}. "
                f"Available: {available}"
            ) from None

    @classmethod
    def registered_names(cls) -> list[str]:
        """Return a sorted list of all registered interface names."""
        return sorted(cls._registry)
