"""
Tests for the guarded redis import in HITLApprovalMiddleware.

Verifies that portal.middleware.hitl_approval can be imported and
instantiated even when the redis package is absent, and that a clear
RuntimeError is raised only when the .redis property is accessed.
"""

import importlib
import sys

import pytest


class TestHITLImportGuard:
    """Guard tests for the optional redis import."""

    def test_module_imports_without_redis(self):
        """hitl_approval must import cleanly even when redis is unavailable."""
        # Temporarily hide the redis package
        real_redis = sys.modules.get("redis")
        sys.modules["redis"] = None  # type: ignore[assignment]
        try:
            # Force reimport of the module
            module_name = "portal.middleware.hitl_approval"
            if module_name in sys.modules:
                del sys.modules[module_name]
            mod = importlib.import_module(module_name)
            assert hasattr(mod, "HITLApprovalMiddleware")
        finally:
            if real_redis is None:
                del sys.modules["redis"]
            else:
                sys.modules["redis"] = real_redis
            # Clean up reimported module so other tests get the real one
            sys.modules.pop("portal.middleware.hitl_approval", None)

    def test_redis_property_raises_when_package_missing(self):
        """Accessing .redis raises RuntimeError when redis is not installed."""
        real_redis = sys.modules.get("redis")
        sys.modules["redis"] = None  # type: ignore[assignment]
        try:
            module_name = "portal.middleware.hitl_approval"
            if module_name in sys.modules:
                del sys.modules[module_name]
            mod = importlib.import_module(module_name)
            middleware = mod.HITLApprovalMiddleware()
            with pytest.raises(RuntimeError, match="redis package is required"):
                _ = middleware.redis
        finally:
            if real_redis is None:
                sys.modules.pop("redis", None)
            else:
                sys.modules["redis"] = real_redis
            sys.modules.pop("portal.middleware.hitl_approval", None)

    def test_middleware_instantiation_does_not_require_redis(self):
        """HITLApprovalMiddleware() must not touch Redis at __init__ time."""
        from portal.middleware.hitl_approval import HITLApprovalMiddleware

        middleware = HITLApprovalMiddleware()
        assert middleware is not None
        assert middleware._redis is None
