"""Tests for portal.observability.health."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from portal.observability.health import (
    DatabaseHealthCheck,
    HealthCheckProvider,
    HealthCheckResult,
    HealthCheckSystem,
    HealthStatus,
)

_HCR = HealthCheckResult


def _result(status, message="ok"):
    return _HCR(status=status, message=message, timestamp="t")


class TestHealthCheckResult:
    def test_to_dict_defaults(self):
        d = _HCR(status=HealthStatus.UNHEALTHY, message="down", timestamp="ts1").to_dict()
        assert d == {"status": "unhealthy", "message": "down", "timestamp": "ts1", "details": {}}

    def test_to_dict_with_details(self):
        r = _HCR(status=HealthStatus.HEALTHY, message="ok", timestamp="ts2", details={"k": 1})
        assert r.to_dict()["details"] == {"k": 1}


class TestHealthCheckProvider:
    async def test_abstract_check_raises(self):
        with pytest.raises(NotImplementedError):
            await HealthCheckProvider().check()


class TestHealthCheckSystem:
    @patch("portal.observability.health.logger")
    def test_add_provider_and_check(self, _):
        system = HealthCheckSystem()
        prov = MagicMock(spec=HealthCheckProvider)
        system.add_provider("db", prov)
        assert system._providers["db"] is prov

        async def fn():
            return _result(HealthStatus.HEALTHY)
        system.add_check("fn", fn)
        assert "fn" in system._check_functions

    @patch("portal.observability.health.logger")
    async def test_check_health_no_providers(self, _):
        result = await HealthCheckSystem().check_health()
        assert result["status"] == "healthy" and result["checks"] == {}

    @patch("portal.observability.health.logger")
    @pytest.mark.parametrize("statuses,expected", [
        ([HealthStatus.HEALTHY], "healthy"),
        ([HealthStatus.HEALTHY, HealthStatus.DEGRADED], "degraded"),
        ([HealthStatus.DEGRADED, HealthStatus.UNHEALTHY], "unhealthy"),
        ([HealthStatus.HEALTHY, HealthStatus.UNHEALTHY], "unhealthy"),
        ([HealthStatus.UNHEALTHY, HealthStatus.UNHEALTHY], "unhealthy"),
    ])
    async def test_status_aggregation(self, _, statuses, expected):
        system = HealthCheckSystem()
        for i, s in enumerate(statuses):
            prov = AsyncMock(spec=HealthCheckProvider)
            prov.check.return_value = _result(s)
            system.add_provider(f"p{i}", prov)
        result = await system.check_health()
        assert result["status"] == expected

    @patch("portal.observability.health.logger")
    async def test_provider_exception_becomes_unhealthy(self, _):
        system = HealthCheckSystem()
        bad = AsyncMock(spec=HealthCheckProvider)
        bad.check.side_effect = RuntimeError("refused")
        system.add_provider("broken", bad)
        result = await system.check_health()
        assert result["status"] == "unhealthy"
        assert "Check failed" in result["checks"]["broken"]["message"]

    @patch("portal.observability.health.logger")
    async def test_function_check_works(self, _):
        system = HealthCheckSystem()
        async def fn():
            return _result(HealthStatus.HEALTHY)
        system.add_check("fn1", fn)
        result = await system.check_health()
        assert result["status"] == "healthy" and "fn1" in result["checks"]

    @patch("portal.observability.health.logger")
    async def test_mixed_providers_and_functions(self, _):
        system = HealthCheckSystem()
        prov = AsyncMock(spec=HealthCheckProvider)
        prov.check.return_value = _result(HealthStatus.HEALTHY)
        system.add_provider("p", prov)
        async def degraded_fn():
            return _result(HealthStatus.DEGRADED, "slow")
        system.add_check("fn", degraded_fn)
        result = await system.check_health()
        assert result["status"] == "degraded"
        assert "p" in result["checks"] and "fn" in result["checks"]

    @patch("portal.observability.health.logger")
    async def test_liveness(self, _):
        result = await HealthCheckSystem().check_liveness()
        assert result["status"] == "healthy" and "alive" in result["message"]

    @patch("portal.observability.health.logger")
    @pytest.mark.parametrize("status,expected_ready", [
        (HealthStatus.HEALTHY, True),
        (HealthStatus.DEGRADED, True),
        (HealthStatus.UNHEALTHY, False),
    ])
    async def test_readiness(self, _, status, expected_ready):
        system = HealthCheckSystem()
        prov = AsyncMock(spec=HealthCheckProvider)
        prov.check.return_value = _result(status)
        system.add_provider("svc", prov)
        result = await system.check_readiness()
        assert result["ready"] is expected_ready and "checks" in result

    @patch("portal.observability.health.logger")
    async def test_overwrite_provider(self, _):
        system = HealthCheckSystem()
        old = AsyncMock(spec=HealthCheckProvider)
        old.check.return_value = _result(HealthStatus.UNHEALTHY, "old")
        system.add_provider("db", old)
        new = AsyncMock(spec=HealthCheckProvider)
        new.check.return_value = _result(HealthStatus.HEALTHY, "new")
        system.add_provider("db", new)
        result = await system.check_health()
        assert result["status"] == "healthy" and result["checks"]["db"]["message"] == "new"


class TestDatabaseHealthCheck:
    async def test_healthy(self):
        repo = AsyncMock()
        repo.get_stats.return_value = {"connections": 5}
        result = await DatabaseHealthCheck(repo).check()
        assert result.status == HealthStatus.HEALTHY
        assert result.details == {"connections": 5}

    async def test_unhealthy_on_exception(self):
        repo = AsyncMock()
        repo.get_stats.side_effect = ConnectionError("refused")
        result = await DatabaseHealthCheck(repo).check()
        assert result.status == HealthStatus.UNHEALTHY and "refused" in result.message


