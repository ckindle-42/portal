"""
Unit tests for portal.core canonical public API exports.

Verifies that all symbols declared in __all__ are importable from
``portal.core`` directly (not from sub-modules), and that they resolve
to the expected types.
"""

from __future__ import annotations

import inspect


class TestCoreInitExports:
    """Ensure every symbol in portal.core.__all__ is importable and sane."""

    def test_all_symbols_importable(self):
        """Every name in __all__ must be importable from portal.core."""
        import portal.core as core

        missing = []
        for name in core.__all__:
            if not hasattr(core, name):
                missing.append(name)

        assert missing == [], f"Names in __all__ but not importable: {missing}"

    def test_agent_core_is_class(self):
        """AgentCore must be a class."""
        from portal.core import AgentCore

        assert inspect.isclass(AgentCore)

    def test_create_agent_core_is_callable(self):
        """create_agent_core must be a callable factory."""
        from portal.core import create_agent_core

        assert callable(create_agent_core)

    def test_event_bus_is_class(self):
        """EventBus must be a class."""
        from portal.core import EventBus

        assert inspect.isclass(EventBus)

    def test_event_type_is_enum(self):
        """EventType must be an Enum (or IntEnum)."""
        import enum

        from portal.core import EventType

        assert issubclass(EventType, enum.Enum)

    def test_exception_types_are_exceptions(self):
        """All exported exception types must be Exception subclasses."""
        from portal.core import (
            AuthorizationError,
            ModelNotAvailableError,
            PolicyViolationError,
            PortalError,
            RateLimitError,
            ToolExecutionError,
            ValidationError,
        )

        exc_types = [
            AuthorizationError,
            ModelNotAvailableError,
            PolicyViolationError,
            PortalError,
            RateLimitError,
            ToolExecutionError,
            ValidationError,
        ]
        for exc_type in exc_types:
            assert inspect.isclass(exc_type), f"{exc_type} is not a class"
            assert issubclass(exc_type, Exception), f"{exc_type} is not an Exception subclass"

    def test_portal_error_is_base_for_others(self):
        """Domain-specific exceptions should inherit from PortalError."""
        from portal.core import (
            AuthorizationError,
            ModelNotAvailableError,
            PolicyViolationError,
            PortalError,
            RateLimitError,
            ToolExecutionError,
            ValidationError,
        )

        derived = [
            AuthorizationError,
            ModelNotAvailableError,
            PolicyViolationError,
            RateLimitError,
            ToolExecutionError,
            ValidationError,
        ]
        for exc_type in derived:
            assert issubclass(exc_type, PortalError), (
                f"{exc_type.__name__} should inherit from PortalError"
            )

    def test_message_types_are_classes(self):
        """IncomingMessage and ProcessingResult must be classes."""
        from portal.core import IncomingMessage, ProcessingResult

        assert inspect.isclass(IncomingMessage)
        assert inspect.isclass(ProcessingResult)

    def test_interface_type_is_enum(self):
        """InterfaceType must be an Enum."""
        import enum

        from portal.core import InterfaceType

        assert issubclass(InterfaceType, enum.Enum)

    def test_no_extra_public_names(self):
        """portal.core should not leak private implementation details."""
        import portal.core as core

        public_names = {name for name in dir(core) if not name.startswith("_")}
        undocumented = public_names - set(core.__all__)
        # Python attaches sub-module names when they are imported inside __init__.py;
        # allow those and other harmless builtins that may appear.
        allowed_leak = {"annotations"}
        # Detect and allow sub-module references (ModuleType objects)
        import types
        allowed_leak |= {
            name for name in undocumented if isinstance(getattr(core, name, None), types.ModuleType)
        }
        undocumented -= allowed_leak
        assert undocumented == set(), (
            f"Public names not listed in __all__: {sorted(undocumented)}"
        )
