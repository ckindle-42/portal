"""Health check system — Kubernetes-style liveness/readiness probes."""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    status: HealthStatus
    message: str
    timestamp: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'status': self.status.value,
            'message': self.message,
            'timestamp': self.timestamp,
            'details': self.details or {},
        }


class HealthCheckProvider:
    """Abstract health check provider — implement check() for custom checks."""

    async def check(self) -> HealthCheckResult:
        raise NotImplementedError


class HealthCheckSystem:
    """Aggregates results from multiple health check providers."""

    def __init__(self) -> None:
        self._providers: dict[str, HealthCheckProvider] = {}
        self._check_functions: dict[str, Callable[[], Awaitable[HealthCheckResult]]] = {}
        logger.info("HealthCheckSystem initialized")

    def add_provider(self, name: str, provider: HealthCheckProvider) -> None:
        self._providers[name] = provider
        logger.info("Added health check provider: %s", name)

    def add_check(self, name: str, check_func: Callable[[], Awaitable[HealthCheckResult]]) -> None:
        self._check_functions[name] = check_func
        logger.info("Added health check function: %s", name)

    async def check_health(self) -> dict[str, Any]:
        checks: dict[str, Any] = {}
        overall = HealthStatus.HEALTHY

        all_checks: dict[str, Any] = {**self._providers, **self._check_functions}
        for name, source in all_checks.items():
            try:
                result = await (source.check() if isinstance(source, HealthCheckProvider) else source())
                checks[name] = result.to_dict()
                if result.status == HealthStatus.UNHEALTHY:
                    overall = HealthStatus.UNHEALTHY
                elif result.status == HealthStatus.DEGRADED and overall == HealthStatus.HEALTHY:
                    overall = HealthStatus.DEGRADED
            except Exception as e:
                logger.exception("Health check failed for %s: %s", name, e)
                checks[name] = {
                    'status': HealthStatus.UNHEALTHY.value,
                    'message': f"Check failed: {e}",
                    'timestamp': datetime.now(tz=UTC).isoformat(),
                }
                overall = HealthStatus.UNHEALTHY

        return {'status': overall.value, 'checks': checks, 'timestamp': datetime.now(tz=UTC).isoformat()}

    async def check_liveness(self) -> dict[str, Any]:
        return {'status': HealthStatus.HEALTHY.value, 'message': 'Service is alive',
                'timestamp': datetime.now(tz=UTC).isoformat()}

    async def check_readiness(self) -> dict[str, Any]:
        result = await self.check_health()
        is_ready = result['status'] in (HealthStatus.HEALTHY.value, HealthStatus.DEGRADED.value)
        return {'status': result['status'], 'ready': is_ready,
                'checks': result['checks'], 'timestamp': result['timestamp']}


class DatabaseHealthCheck(HealthCheckProvider):
    def __init__(self, repository: Any) -> None:
        self.repository = repository

    async def check(self) -> HealthCheckResult:
        try:
            stats = await self.repository.get_stats()
            return HealthCheckResult(HealthStatus.HEALTHY, "Database connection healthy",
                                     datetime.now(tz=UTC).isoformat(), details=stats)
        except Exception as e:
            return HealthCheckResult(HealthStatus.UNHEALTHY, f"Database unhealthy: {e}",
                                     datetime.now(tz=UTC).isoformat())


def register_health_endpoints(app, health_system: HealthCheckSystem) -> None:
    """Register /health, /health/live, /health/ready endpoints with a FastAPI app."""

    @app.get("/health/live")
    async def liveness_probe() -> dict[str, Any]:
        return await health_system.check_liveness()

    @app.get("/health/ready")
    async def readiness_probe() -> dict[str, Any]:
        return await health_system.check_readiness()

    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        return await health_system.check_health()

    logger.info("Health check endpoints registered: /health, /health/live, /health/ready")


async def run_health_check() -> None:
    """CLI health check — prints status of all Portal components."""
    import httpx
    checks = [
        ("Ollama", "http://localhost:11434/api/tags"),
        ("Router", "http://localhost:8000/health"),
        ("Portal API", "http://localhost:8081/health"),
        ("Web UI", "http://localhost:8080"),
    ]
    async with httpx.AsyncClient(timeout=3.0) as client:
        for name, url in checks:
            try:
                resp = await client.get(url)
                status = "OK" if resp.status_code < 500 else "DEGRADED"
            except Exception:
                status = "FAIL"
            print(f"  [{status}] {name}")
