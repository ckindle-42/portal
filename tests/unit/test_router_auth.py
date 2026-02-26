"""
Tests for router.py ROUTER_TOKEN auth enforcement and resolve_model logic.
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def _no_router_token():
    """Ensure ROUTER_TOKEN is empty so auth is skipped."""
    with patch.dict(os.environ, {"ROUTER_TOKEN": ""}, clear=False):
        # Force reimport so module-level ROUTER_TOKEN picks up the new env
        import importlib

        import portal.routing.router as mod

        importlib.reload(mod)
        yield mod


@pytest.fixture()
def _with_router_token():
    """Set ROUTER_TOKEN so auth is enforced."""
    with patch.dict(os.environ, {"ROUTER_TOKEN": "test-secret-123"}, clear=False):
        import importlib

        import portal.routing.router as mod

        importlib.reload(mod)
        yield mod


class TestResolveModel:
    """Tests for the resolve_model function."""

    def test_manual_override(self, _no_router_token):
        """Manual @model: override selects the correct model."""
        mod = _no_router_token
        model, reason = mod.resolve_model("auto", [{"role": "user", "content": "@model:llama3 hello"}])
        assert model == "llama3"
        assert "manual" in reason

    def test_explicit_model_passthrough(self, _no_router_token):
        """Explicit non-auto model name passes through unchanged."""
        mod = _no_router_token
        model, reason = mod.resolve_model("my-custom-model", [{"role": "user", "content": "hi"}])
        assert model == "my-custom-model"
        assert reason == "explicit model"

    def test_auto_resolves_to_a_model(self, _no_router_token):
        """When model is 'auto', resolve_model returns some valid model."""
        mod = _no_router_token
        model, reason = mod.resolve_model("auto", [{"role": "user", "content": "hi"}])
        assert isinstance(model, str) and model
        assert isinstance(reason, str) and reason


class TestRouterTokenAuth:
    """Tests for ROUTER_TOKEN enforcement on the proxy endpoint."""

    def test_no_token_configured_allows_all(self, _no_router_token):
        """When ROUTER_TOKEN is empty, requests without auth succeed."""
        mod = _no_router_token
        client = TestClient(mod.app, raise_server_exceptions=False)
        # health is before the catch-all, but dry-run is a normal route
        resp = client.post("/api/dry-run", json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]})
        assert resp.status_code == 200

    def test_valid_token_accepted(self, _with_router_token):
        """When ROUTER_TOKEN is set, a matching Bearer token is accepted."""
        mod = _with_router_token
        client = TestClient(mod.app, raise_server_exceptions=False)
        resp = client.post(
            "/api/dry-run",
            json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
            headers={"Authorization": "Bearer test-secret-123"},
        )
        assert resp.status_code == 200

    def test_missing_token_rejected(self, _with_router_token):
        """When ROUTER_TOKEN is set, missing Bearer token returns 401."""
        mod = _with_router_token
        client = TestClient(mod.app, raise_server_exceptions=False)
        resp = client.post(
            "/api/dry-run",
            json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 401

    def test_wrong_token_rejected(self, _with_router_token):
        """When ROUTER_TOKEN is set, a wrong Bearer token returns 401."""
        mod = _with_router_token
        client = TestClient(mod.app, raise_server_exceptions=False)
        resp = client.post(
            "/api/dry-run",
            json={"model": "auto", "messages": [{"role": "user", "content": "hi"}]},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401
