"""
Health Check System
===================

Kubernetes-style health and readiness probes.

Endpoints:
- /health/live: Liveness probe (is the service running?)
- /health/ready: Readiness probe (is the service ready to accept traffic?)

Each check can have multiple providers that contribute to overall health.

Example:
--------
health_system = HealthCheckSystem()

# Add health check providers
health_system.add_provider("database", database_health_check)
health_system.add_provider("llm", llm_health_check)

# Check health
status = await health_system.check_health()
# Returns: {"status": "healthy", "checks": {...}, "timestamp": "..."}
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class HealthStatus(StrEnum):
    """Health status values"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check"""
    status: HealthStatus
    message: str
    timestamp: str
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            'status': self.status.value,
            'message': self.message,
            'timestamp': self.timestamp,
            'details': self.details or {}
        }


class HealthCheckProvider:
    """
    Health check provider interface.

    Implement this to add custom health checks.
    """

    async def check(self) -> HealthCheckResult:
        """Perform health check"""
        raise NotImplementedError


class HealthCheckSystem:
    """
    System for managing health checks.

    Aggregates results from multiple providers.
    """

    def __init__(self) -> None:
        """Initialize health check system"""
        self._providers: dict[str, HealthCheckProvider] = {}
        self._check_functions: dict[str, Callable[[], Awaitable[HealthCheckResult]]] = {}

        logger.info("HealthCheckSystem initialized")

    def add_provider(self, name: str, provider: HealthCheckProvider) -> None:
        """
        Add a health check provider.

        Args:
            name: Name of the check
            provider: Provider instance
        """
        self._providers[name] = provider
        logger.info("Added health check provider: %s", name)

    def add_check(
        self,
        name: str,
        check_func: Callable[[], Awaitable[HealthCheckResult]]
    ) -> None:
        """
        Add a health check function.

        Args:
            name: Name of the check
            check_func: Async function that returns HealthCheckResult
        """
        self._check_functions[name] = check_func
        logger.info("Added health check function: %s", name)

    async def check_health(self) -> dict[str, Any]:
        """
        Check overall system health.

        Returns:
            Dict with overall status and individual check results
        """
        checks = {}
        overall_status = HealthStatus.HEALTHY

        # Run all provider checks
        for name, provider in self._providers.items():
            try:
                result = await provider.check()
                checks[name] = result.to_dict()

                # Update overall status
                if result.status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif result.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED

            except Exception as e:
                logger.exception("Health check failed for %s: %s", name, e)
                checks[name] = {
                    'status': HealthStatus.UNHEALTHY.value,
                    'message': f"Check failed: {e}",
                    'timestamp': datetime.now(tz=UTC).isoformat()
                }
                overall_status = HealthStatus.UNHEALTHY

        # Run all function checks
        for name, func in self._check_functions.items():
            try:
                result = await func()
                checks[name] = result.to_dict()

                # Update overall status
                if result.status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif result.status == HealthStatus.DEGRADED and overall_status == HealthStatus.HEALTHY:
                    overall_status = HealthStatus.DEGRADED

            except Exception as e:
                logger.exception("Health check failed for %s: %s", name, e)
                checks[name] = {
                    'status': HealthStatus.UNHEALTHY.value,
                    'message': f"Check failed: {e}",
                    'timestamp': datetime.now(tz=UTC).isoformat()
                }
                overall_status = HealthStatus.UNHEALTHY

        return {
            'status': overall_status.value,
            'checks': checks,
            'timestamp': datetime.now(tz=UTC).isoformat()
        }

    async def check_liveness(self) -> dict[str, Any]:
        """
        Liveness check - is the service running?

        This should be a lightweight check that only fails if
        the service is completely dead.

        Returns:
            Dict with liveness status
        """
        return {
            'status': HealthStatus.HEALTHY.value,
            'message': 'Service is alive',
            'timestamp': datetime.now(tz=UTC).isoformat()
        }

    async def check_readiness(self) -> dict[str, Any]:
        """
        Readiness check - is the service ready to accept traffic?

        This runs all health checks and returns the aggregated result.

        Returns:
            Dict with readiness status
        """
        result = await self.check_health()

        # Service is ready if status is healthy or degraded
        # (degraded means some non-critical components are down)
        is_ready = result['status'] in [HealthStatus.HEALTHY.value, HealthStatus.DEGRADED.value]

        return {
            'status': result['status'],
            'ready': is_ready,
            'checks': result['checks'],
            'timestamp': result['timestamp']
        }


# =============================================================================
# BUILT-IN HEALTH CHECK PROVIDERS
# =============================================================================


class DatabaseHealthCheck(HealthCheckProvider):
    """Health check for database connection"""

    def __init__(self, repository: Any) -> None:
        """
        Initialize database health check.

        Args:
            repository: Repository instance with get_stats() method
        """
        self.repository = repository

    async def check(self) -> HealthCheckResult:
        """Check database health"""
        try:
            # Try to get stats (lightweight DB operation)
            stats = await self.repository.get_stats()

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Database connection healthy",
                timestamp=datetime.now(tz=UTC).isoformat(),
                details=stats
            )

        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Database unhealthy: {e}",
                timestamp=datetime.now(tz=UTC).isoformat()
            )


class JobQueueHealthCheck(HealthCheckProvider):
    """Health check for job queue"""

    def __init__(self, job_repository: Any, max_pending: int = 1000) -> None:
        """
        Initialize job queue health check.

        Args:
            job_repository: Job repository instance
            max_pending: Maximum pending jobs before degraded status
        """
        self.job_repository = job_repository
        self.max_pending = max_pending

    async def check(self) -> HealthCheckResult:
        """Check job queue health"""
        try:
            stats = await self.job_repository.get_stats()
            pending_count = stats.get('status_counts', {}).get('pending', 0)

            if pending_count > self.max_pending:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    message=f"Job queue degraded: {pending_count} pending jobs",
                    timestamp=datetime.now(tz=UTC).isoformat(),
                    details=stats
                )

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Job queue healthy",
                timestamp=datetime.now(tz=UTC).isoformat(),
                details=stats
            )

        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Job queue unhealthy: {e}",
                timestamp=datetime.now(tz=UTC).isoformat()
            )


class WorkerPoolHealthCheck(HealthCheckProvider):
    """Health check for worker pool"""

    def __init__(self, worker_pool: Any) -> None:
        """
        Initialize worker pool health check.

        Args:
            worker_pool: Worker pool instance
        """
        self.worker_pool = worker_pool

    async def check(self) -> HealthCheckResult:
        """Check worker pool health"""
        try:
            if not self.worker_pool.is_running():
                return HealthCheckResult(
                    status=HealthStatus.UNHEALTHY,
                    message="Worker pool not running",
                    timestamp=datetime.now(tz=UTC).isoformat()
                )

            stats = self.worker_pool.get_stats()

            # Check if we have idle workers
            idle_workers = stats.get('idle_workers', 0)
            if idle_workers == 0:
                return HealthCheckResult(
                    status=HealthStatus.DEGRADED,
                    message="All workers busy",
                    timestamp=datetime.now(tz=UTC).isoformat(),
                    details=stats
                )

            return HealthCheckResult(
                status=HealthStatus.HEALTHY,
                message="Worker pool healthy",
                timestamp=datetime.now(tz=UTC).isoformat(),
                details=stats
            )

        except Exception as e:
            return HealthCheckResult(
                status=HealthStatus.UNHEALTHY,
                message=f"Worker pool unhealthy: {e}",
                timestamp=datetime.now(tz=UTC).isoformat()
            )


# =============================================================================
# FASTAPI INTEGRATION
# =============================================================================


def register_health_endpoints(app, health_system: HealthCheckSystem) -> None:
    """
    Register health check endpoints with FastAPI app.

    Args:
        app: FastAPI application
        health_system: HealthCheckSystem instance

    Endpoints:
        GET /health/live - Liveness probe
        GET /health/ready - Readiness probe
        GET /health - Full health check
    """

    @app.get("/health/live")
    async def liveness_probe() -> dict[str, Any]:
        """Liveness probe - is the service running?"""
        return await health_system.check_liveness()

    @app.get("/health/ready")
    async def readiness_probe() -> dict[str, Any]:
        """Readiness probe - is the service ready to accept traffic?"""
        return await health_system.check_readiness()

    @app.get("/health")
    async def health_check() -> dict[str, Any]:
        """Full health check with all providers"""
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
