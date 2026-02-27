"""
Observability Package
=====================

Production-grade observability for Portal.

Modules:
--------
- health: Kubernetes-style health/readiness probes
- config_watcher: Hot-reloading configuration
- metrics: Prometheus-compatible metrics

Example Usage:
--------------
# Setup health checks
from portal.observability import HealthCheckSystem, register_health_endpoints
health = HealthCheckSystem()
health.add_provider("database", database_health_check)
register_health_endpoints(app, health)

# Setup metrics
from portal.observability import MetricsCollector, register_metrics_endpoint
metrics = MetricsCollector()
register_metrics_endpoint(app, metrics)

# Setup config watching
from portal.observability import watch_config
watcher = await watch_config("config.yaml", on_config_change)
"""

# Config watching
from .config_watcher import (
    ConfigWatcher,
    watch_config,
)

# Health checks
from .health import (
    DatabaseHealthCheck,
    HealthCheckProvider,
    HealthCheckResult,
    HealthCheckSystem,
    HealthStatus,
    register_health_endpoints,
)

# Metrics
from .metrics import (
    MetricsCollector,
    MetricsMiddleware,
    register_metrics_endpoint,
)

__all__ = [
    # Health checks
    'HealthCheckSystem',
    'HealthCheckProvider',
    'HealthCheckResult',
    'HealthStatus',
    'DatabaseHealthCheck',
    'register_health_endpoints',

    # Config watching
    'ConfigWatcher',
    'watch_config',

    # Metrics
    'MetricsCollector',
    'MetricsMiddleware',
    'register_metrics_endpoint',
]
