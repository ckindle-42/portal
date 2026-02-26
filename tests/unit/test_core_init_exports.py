"""Lean contract tests for portal.core public exports."""

from __future__ import annotations

import enum
import inspect

import pytest

import portal.core as core


@pytest.mark.parametrize("name", core.__all__)
def test_all_symbols_in___all___are_importable(name: str) -> None:
    """Every symbol listed in __all__ is actually exported."""
    assert hasattr(core, name), f"Missing export for {name}"


@pytest.mark.parametrize(
    ("name", "predicate"),
    [
        ("AgentCore", inspect.isclass),
        ("EventBus", inspect.isclass),
        ("IncomingMessage", inspect.isclass),
        ("ProcessingResult", inspect.isclass),
        ("create_agent_core", callable),
        ("EventType", lambda value: issubclass(value, enum.Enum)),
        ("InterfaceType", lambda value: issubclass(value, enum.Enum)),
    ],
)
def test_core_exports_have_expected_types(name: str, predicate) -> None:
    """High-value shape checks for the stable public API."""
    assert predicate(getattr(core, name))


@pytest.mark.parametrize(
    "name",
    [
        "AuthorizationError",
        "ModelNotAvailableError",
        "PolicyViolationError",
        "PortalError",
        "RateLimitError",
        "ToolExecutionError",
        "ValidationError",
    ],
)
def test_exported_exceptions_are_exception_types(name: str) -> None:
    """Public exception exports remain usable by callers."""
    assert inspect.isclass(getattr(core, name))
    assert issubclass(getattr(core, name), Exception)


@pytest.mark.parametrize(
    "name",
    [
        "AuthorizationError",
        "ModelNotAvailableError",
        "PolicyViolationError",
        "RateLimitError",
        "ToolExecutionError",
        "ValidationError",
    ],
)
def test_domain_exceptions_inherit_portal_error(name: str) -> None:
    """Domain-specific errors should keep a shared base type."""
    assert issubclass(getattr(core, name), core.PortalError)
