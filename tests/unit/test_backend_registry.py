"""Unit tests for BackendRegistry (TASK-17)."""

import pytest

from portal.routing.backend_registry import BackendRegistry


class TestBackendRegistry:
    def test_register_and_get(self):
        registry = BackendRegistry()
        backend = object()
        registry.register("test", backend)  # type: ignore[arg-type]
        assert registry.get("test") is backend

    def test_get_unknown_raises_key_error(self):
        registry = BackendRegistry()
        with pytest.raises(KeyError, match="'missing' not registered"):
            registry.get("missing")

    def test_available_returns_registered_names(self):
        registry = BackendRegistry()
        assert registry.available() == []
        registry.register("a", object())  # type: ignore[arg-type]
        registry.register("b", object())  # type: ignore[arg-type]
        assert set(registry.available()) == {"a", "b"}

    def test_register_overwrites_existing(self):
        registry = BackendRegistry()
        backend1 = object()
        backend2 = object()
        registry.register("x", backend1)  # type: ignore[arg-type]
        registry.register("x", backend2)  # type: ignore[arg-type]
        assert registry.get("x") is backend2
