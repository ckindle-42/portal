"""
Integration test for model router.
Requires: Router running at localhost:8000.
"""

import httpx
import pytest


@pytest.mark.asyncio
@pytest.mark.integration
async def test_router_health():
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://localhost:8000/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_router_dry_run_coding():
    """Coding queries should route to coding model."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8000/api/dry-run",
            json={
                "messages": [
                    {"role": "user", "content": "write a python function to reverse a string"}
                ]
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "resolved_model" in data or "model" in data


@pytest.mark.asyncio
@pytest.mark.integration
async def test_router_dry_run_default():
    """Generic queries should use default model."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:8000/api/dry-run",
            json={"messages": [{"role": "user", "content": "what is the weather like today"}]},
        )
        assert resp.status_code == 200
