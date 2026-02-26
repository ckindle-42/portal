"""
Tests for portal.observability.health
======================================

Comprehensive tests for HealthStatus, HealthCheckResult,
HealthCheckProvider, HealthCheckSystem, and built-in providers
(DatabaseHealthCheck, JobQueueHealthCheck, WorkerPoolHealthCheck).
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from portal.observability.health import (
    DatabaseHealthCheck,
    HealthCheckProvider,
    HealthCheckResult,
    HealthCheckSystem,
    HealthStatus,
    JobQueueHealthCheck,
    WorkerPoolHealthCheck,
)

# ===========================================================================
# HealthStatus enum
# ===========================================================================


class TestHealthStatus:
    """Tests for the HealthStatus StrEnum."""

    def test_healthy_value(self):
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.HEALTHY.value == "healthy"

    def test_degraded_value(self):
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.DEGRADED.value == "degraded"

    def test_unhealthy_value(self):
        assert HealthStatus.UNHEALTHY == "unhealthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_is_str_subclass(self):
        assert isinstance(HealthStatus.HEALTHY, str)

    def test_all_members(self):
        members = set(HealthStatus)
        assert members == {
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.UNHEALTHY,
        }


# ===========================================================================
# HealthCheckResult dataclass
# ===========================================================================


class TestHealthCheckResult:
    """Tests for the HealthCheckResult dataclass."""

    def test_basic_creation(self):
        ts = datetime.now(tz=UTC).isoformat()
        r = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="All good",
            timestamp=ts,
        )
        assert r.status == HealthStatus.HEALTHY
        assert r.message == "All good"
        assert r.timestamp == ts
        assert r.details is None

    def test_creation_with_details(self):
        r = HealthCheckResult(
            status=HealthStatus.DEGRADED,
            message="slow",
            timestamp="2026-01-01T00:00:00",
            details={"latency_ms": 500},
        )
        assert r.details == {"latency_ms": 500}

    def test_to_dict_without_details(self):
        r = HealthCheckResult(
            status=HealthStatus.UNHEALTHY,
            message="down",
            timestamp="ts1",
        )
        d = r.to_dict()
        assert d == {
            "status": "unhealthy",
            "message": "down",
            "timestamp": "ts1",
            "details": {},
        }

    def test_to_dict_with_details(self):
        r = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="ok",
            timestamp="ts2",
            details={"db_pool": 10},
        )
        d = r.to_dict()
        assert d["details"] == {"db_pool": 10}

    def test_to_dict_status_is_string(self):
        r = HealthCheckResult(
            status=HealthStatus.DEGRADED,
            message="x",
            timestamp="t",
        )
        assert isinstance(r.to_dict()["status"], str)


# ===========================================================================
# HealthCheckProvider (abstract)
# ===========================================================================


class TestHealthCheckProvider:
    """Tests for the abstract HealthCheckProvider base class."""

    async def test_check_raises_not_implemented(self):
        provider = HealthCheckProvider()
        with pytest.raises(NotImplementedError):
            await provider.check()


# ===========================================================================
# HealthCheckSystem
# ===========================================================================


class TestHealthCheckSystem:
    """Tests for the HealthCheckSystem aggregator."""

    @patch("portal.observability.health.logger")
    def test_init(self, mock_logger):
        system = HealthCheckSystem()
        assert system._providers == {}
        assert system._check_functions == {}

    @patch("portal.observability.health.logger")
    def test_add_provider(self, mock_logger):
        system = HealthCheckSystem()
        provider = MagicMock(spec=HealthCheckProvider)
        system.add_provider("db", provider)
        assert "db" in system._providers
        assert system._providers["db"] is provider

    @patch("portal.observability.health.logger")
    def test_add_check(self, mock_logger):
        system = HealthCheckSystem()

        async def my_check():
            return HealthCheckResult(
                status=HealthStatus.HEALTHY, message="ok", timestamp="t"
            )

        system.add_check("custom", my_check)
        assert "custom" in system._check_functions

    @patch("portal.observability.health.logger")
    async def test_check_health_no_providers(self, mock_logger):
        system = HealthCheckSystem()
        result = await system.check_health()
        assert result["status"] == "healthy"
        assert result["checks"] == {}
        assert "timestamp" in result

    @patch("portal.observability.health.logger")
    async def test_check_health_all_healthy(self, mock_logger):
        system = HealthCheckSystem()

        provider = AsyncMock(spec=HealthCheckProvider)
        provider.check.return_value = HealthCheckResult(
            status=HealthStatus.HEALTHY, message="ok", timestamp="t"
        )
        system.add_provider("svc1", provider)

        result = await system.check_health()
        assert result["status"] == "healthy"
        assert "svc1" in result["checks"]
        assert result["checks"]["svc1"]["status"] == "healthy"

    @patch("portal.observability.health.logger")
    async def test_check_health_degraded_overrides_healthy(self, mock_logger):
        system = HealthCheckSystem()

        healthy_prov = AsyncMock(spec=HealthCheckProvider)
        healthy_prov.check.return_value = HealthCheckResult(
            status=HealthStatus.HEALTHY, message="ok", timestamp="t"
        )
        degraded_prov = AsyncMock(spec=HealthCheckProvider)
        degraded_prov.check.return_value = HealthCheckResult(
            status=HealthStatus.DEGRADED, message="slow", timestamp="t"
        )

        system.add_provider("a", healthy_prov)
        system.add_provider("b", degraded_prov)

        result = await system.check_health()
        assert result["status"] == "degraded"

    @patch("portal.observability.health.logger")
    async def test_check_health_unhealthy_overrides_degraded(self, mock_logger):
        system = HealthCheckSystem()

        degraded_prov = AsyncMock(spec=HealthCheckProvider)
        degraded_prov.check.return_value = HealthCheckResult(
            status=HealthStatus.DEGRADED, message="slow", timestamp="t"
        )
        unhealthy_prov = AsyncMock(spec=HealthCheckProvider)
        unhealthy_prov.check.return_value = HealthCheckResult(
            status=HealthStatus.UNHEALTHY, message="down", timestamp="t"
        )

        system.add_provider("x", degraded_prov)
        system.add_provider("y", unhealthy_prov)

        result = await system.check_health()
        assert result["status"] == "unhealthy"

    @patch("portal.observability.health.logger")
    async def test_check_health_unhealthy_overrides_healthy(self, mock_logger):
        system = HealthCheckSystem()

        healthy_prov = AsyncMock(spec=HealthCheckProvider)
        healthy_prov.check.return_value = HealthCheckResult(
            status=HealthStatus.HEALTHY, message="ok", timestamp="t"
        )
        unhealthy_prov = AsyncMock(spec=HealthCheckProvider)
        unhealthy_prov.check.return_value = HealthCheckResult(
            status=HealthStatus.UNHEALTHY, message="down", timestamp="t"
        )

        system.add_provider("h", healthy_prov)
        system.add_provider("u", unhealthy_prov)

        result = await system.check_health()
        assert result["status"] == "unhealthy"

    @patch("portal.observability.health.logger")
    async def test_check_health_provider_exception(self, mock_logger):
        system = HealthCheckSystem()

        bad_provider = AsyncMock(spec=HealthCheckProvider)
        bad_provider.check.side_effect = RuntimeError("connection refused")

        system.add_provider("broken", bad_provider)

        result = await system.check_health()
        assert result["status"] == "unhealthy"
        assert "broken" in result["checks"]
        assert "Check failed" in result["checks"]["broken"]["message"]

    @patch("portal.observability.health.logger")
    async def test_check_health_function_checks_healthy(self, mock_logger):
        system = HealthCheckSystem()

        async def check_fn():
            return HealthCheckResult(
                status=HealthStatus.HEALTHY, message="ok", timestamp="t"
            )

        system.add_check("fn1", check_fn)

        result = await system.check_health()
        assert result["status"] == "healthy"
        assert "fn1" in result["checks"]

    @patch("portal.observability.health.logger")
    async def test_check_health_function_check_exception(self, mock_logger):
        system = HealthCheckSystem()

        async def bad_fn():
            raise ValueError("oops")

        system.add_check("bad_fn", bad_fn)

        result = await system.check_health()
        assert result["status"] == "unhealthy"
        assert "Check failed" in result["checks"]["bad_fn"]["message"]

    @patch("portal.observability.health.logger")
    async def test_check_health_mixed_providers_and_functions(self, mock_logger):
        system = HealthCheckSystem()

        provider = AsyncMock(spec=HealthCheckProvider)
        provider.check.return_value = HealthCheckResult(
            status=HealthStatus.HEALTHY, message="ok", timestamp="t"
        )
        system.add_provider("prov", provider)

        async def degraded_fn():
            return HealthCheckResult(
                status=HealthStatus.DEGRADED, message="slow", timestamp="t"
            )

        system.add_check("fn", degraded_fn)

        result = await system.check_health()
        assert result["status"] == "degraded"
        assert "prov" in result["checks"]
        assert "fn" in result["checks"]

    @patch("portal.observability.health.logger")
    async def test_check_liveness(self, mock_logger):
        system = HealthCheckSystem()
        result = await system.check_liveness()
        assert result["status"] == "healthy"
        assert result["message"] == "Service is alive"
        assert "timestamp" in result

    @patch("portal.observability.health.logger")
    async def test_check_readiness_healthy(self, mock_logger):
        system = HealthCheckSystem()
        result = await system.check_readiness()
        assert result["ready"] is True
        assert result["status"] == "healthy"

    @patch("portal.observability.health.logger")
    async def test_check_readiness_degraded_still_ready(self, mock_logger):
        system = HealthCheckSystem()

        provider = AsyncMock(spec=HealthCheckProvider)
        provider.check.return_value = HealthCheckResult(
            status=HealthStatus.DEGRADED, message="slow", timestamp="t"
        )
        system.add_provider("slow_svc", provider)

        result = await system.check_readiness()
        assert result["ready"] is True
        assert result["status"] == "degraded"

    @patch("portal.observability.health.logger")
    async def test_check_readiness_unhealthy_not_ready(self, mock_logger):
        system = HealthCheckSystem()

        provider = AsyncMock(spec=HealthCheckProvider)
        provider.check.return_value = HealthCheckResult(
            status=HealthStatus.UNHEALTHY, message="down", timestamp="t"
        )
        system.add_provider("dead_svc", provider)

        result = await system.check_readiness()
        assert result["ready"] is False
        assert result["status"] == "unhealthy"

    @patch("portal.observability.health.logger")
    async def test_check_readiness_includes_checks(self, mock_logger):
        system = HealthCheckSystem()

        provider = AsyncMock(spec=HealthCheckProvider)
        provider.check.return_value = HealthCheckResult(
            status=HealthStatus.HEALTHY, message="ok", timestamp="t"
        )
        system.add_provider("p1", provider)

        result = await system.check_readiness()
        assert "checks" in result
        assert "p1" in result["checks"]


# ===========================================================================
# DatabaseHealthCheck
# ===========================================================================


class TestDatabaseHealthCheck:
    """Tests for the DatabaseHealthCheck provider."""

    async def test_healthy_database(self):
        repo = AsyncMock()
        repo.get_stats.return_value = {"connections": 5, "pool_size": 10}

        check = DatabaseHealthCheck(repo)
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY
        assert "healthy" in result.message.lower()
        assert result.details == {"connections": 5, "pool_size": 10}

    async def test_unhealthy_database_exception(self):
        repo = AsyncMock()
        repo.get_stats.side_effect = ConnectionError("refused")

        check = DatabaseHealthCheck(repo)
        result = await check.check()

        assert result.status == HealthStatus.UNHEALTHY
        assert "unhealthy" in result.message.lower()
        assert "refused" in result.message

    async def test_stores_repository(self):
        repo = MagicMock()
        check = DatabaseHealthCheck(repo)
        assert check.repository is repo


# ===========================================================================
# JobQueueHealthCheck
# ===========================================================================


class TestJobQueueHealthCheck:
    """Tests for the JobQueueHealthCheck provider."""

    async def test_healthy_queue(self):
        repo = AsyncMock()
        repo.get_stats.return_value = {
            "status_counts": {"pending": 10, "running": 2}
        }

        check = JobQueueHealthCheck(repo, max_pending=1000)
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY
        assert "healthy" in result.message.lower()

    async def test_degraded_queue_over_max_pending(self):
        repo = AsyncMock()
        repo.get_stats.return_value = {
            "status_counts": {"pending": 1500, "running": 5}
        }

        check = JobQueueHealthCheck(repo, max_pending=1000)
        result = await check.check()

        assert result.status == HealthStatus.DEGRADED
        assert "1500" in result.message

    async def test_degraded_queue_exact_boundary(self):
        """Exactly at max_pending should NOT be degraded (> not >=)."""
        repo = AsyncMock()
        repo.get_stats.return_value = {
            "status_counts": {"pending": 1000}
        }

        check = JobQueueHealthCheck(repo, max_pending=1000)
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY

    async def test_degraded_queue_one_over_boundary(self):
        repo = AsyncMock()
        repo.get_stats.return_value = {
            "status_counts": {"pending": 1001}
        }

        check = JobQueueHealthCheck(repo, max_pending=1000)
        result = await check.check()

        assert result.status == HealthStatus.DEGRADED

    async def test_unhealthy_queue_exception(self):
        repo = AsyncMock()
        repo.get_stats.side_effect = RuntimeError("queue down")

        check = JobQueueHealthCheck(repo)
        result = await check.check()

        assert result.status == HealthStatus.UNHEALTHY
        assert "unhealthy" in result.message.lower()

    async def test_default_max_pending(self):
        check = JobQueueHealthCheck(MagicMock())
        assert check.max_pending == 1000

    async def test_missing_pending_key_defaults_zero(self):
        repo = AsyncMock()
        repo.get_stats.return_value = {"status_counts": {}}

        check = JobQueueHealthCheck(repo, max_pending=100)
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY

    async def test_missing_status_counts_defaults_zero(self):
        repo = AsyncMock()
        repo.get_stats.return_value = {}

        check = JobQueueHealthCheck(repo, max_pending=100)
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY


# ===========================================================================
# WorkerPoolHealthCheck
# ===========================================================================


class TestWorkerPoolHealthCheck:
    """Tests for the WorkerPoolHealthCheck provider."""

    async def test_healthy_pool(self):
        pool = MagicMock()
        pool.is_running.return_value = True
        pool.get_stats.return_value = {"idle_workers": 3, "total_workers": 5}

        check = WorkerPoolHealthCheck(pool)
        result = await check.check()

        assert result.status == HealthStatus.HEALTHY
        assert "healthy" in result.message.lower()
        assert result.details == {"idle_workers": 3, "total_workers": 5}

    async def test_unhealthy_pool_not_running(self):
        pool = MagicMock()
        pool.is_running.return_value = False

        check = WorkerPoolHealthCheck(pool)
        result = await check.check()

        assert result.status == HealthStatus.UNHEALTHY
        assert "not running" in result.message.lower()

    async def test_degraded_pool_all_busy(self):
        pool = MagicMock()
        pool.is_running.return_value = True
        pool.get_stats.return_value = {"idle_workers": 0, "total_workers": 4}

        check = WorkerPoolHealthCheck(pool)
        result = await check.check()

        assert result.status == HealthStatus.DEGRADED
        assert "busy" in result.message.lower()

    async def test_unhealthy_pool_exception(self):
        pool = MagicMock()
        pool.is_running.side_effect = RuntimeError("pool exploded")

        check = WorkerPoolHealthCheck(pool)
        result = await check.check()

        assert result.status == HealthStatus.UNHEALTHY
        assert "unhealthy" in result.message.lower()

    async def test_stores_worker_pool(self):
        pool = MagicMock()
        check = WorkerPoolHealthCheck(pool)
        assert check.worker_pool is pool


# ===========================================================================
# Aggregation edge cases
# ===========================================================================


class TestHealthAggregationEdgeCases:
    """Edge cases for the aggregation logic in check_health."""

    @patch("portal.observability.health.logger")
    async def test_multiple_unhealthy_still_unhealthy(self, mock_logger):
        system = HealthCheckSystem()

        for name in ("a", "b", "c"):
            prov = AsyncMock(spec=HealthCheckProvider)
            prov.check.return_value = HealthCheckResult(
                status=HealthStatus.UNHEALTHY, message="down", timestamp="t"
            )
            system.add_provider(name, prov)

        result = await system.check_health()
        assert result["status"] == "unhealthy"

    @patch("portal.observability.health.logger")
    async def test_provider_and_function_both_fail(self, mock_logger):
        system = HealthCheckSystem()

        prov = AsyncMock(spec=HealthCheckProvider)
        prov.check.side_effect = Exception("prov error")
        system.add_provider("prov", prov)

        async def bad_fn():
            raise Exception("fn error")

        system.add_check("fn", bad_fn)

        result = await system.check_health()
        assert result["status"] == "unhealthy"
        assert len(result["checks"]) == 2

    @patch("portal.observability.health.logger")
    async def test_exception_check_includes_timestamp(self, mock_logger):
        system = HealthCheckSystem()

        prov = AsyncMock(spec=HealthCheckProvider)
        prov.check.side_effect = Exception("fail")
        system.add_provider("prov", prov)

        result = await system.check_health()
        assert "timestamp" in result["checks"]["prov"]

    @patch("portal.observability.health.logger")
    async def test_overwrite_provider(self, mock_logger):
        """Adding a provider with the same name replaces the old one."""
        system = HealthCheckSystem()

        old_prov = AsyncMock(spec=HealthCheckProvider)
        old_prov.check.return_value = HealthCheckResult(
            status=HealthStatus.UNHEALTHY, message="old", timestamp="t"
        )
        system.add_provider("db", old_prov)

        new_prov = AsyncMock(spec=HealthCheckProvider)
        new_prov.check.return_value = HealthCheckResult(
            status=HealthStatus.HEALTHY, message="new", timestamp="t"
        )
        system.add_provider("db", new_prov)

        result = await system.check_health()
        assert result["status"] == "healthy"
        assert result["checks"]["db"]["message"] == "new"
