"""
Observability Package
=====================

Production-grade observability for Portal.

Modules:
--------
- tracer: OpenTelemetry distributed tracing
- health: Kubernetes-style health/readiness probes
- config_watcher: Hot-reloading configuration
- metrics: Prometheus-compatible metrics

Example Usage:
--------------
# Setup tracing
from portal.observability import setup_telemetry, instrument_fastapi
setup_telemetry(service_name="portal")
instrument_fastapi(app)

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

# Tracing
from .tracer import (
    setup_telemetry,
    get_tracer,
    instrument_fastapi,
    instrument_aiohttp,
    trace_operation,
    add_trace_event,
    set_trace_attribute,
    shutdown_telemetry,
)

# Health checks
from .health import (
    HealthCheckSystem,
    HealthCheckProvider,
    HealthCheckResult,
    HealthStatus,
    DatabaseHealthCheck,
    JobQueueHealthCheck,
    WorkerPoolHealthCheck,
    register_health_endpoints,
)

# Config watching
from .config_watcher import (
    ConfigWatcher,
    watch_config,
)

# Metrics
from .metrics import (
    MetricsCollector,
    MetricsMiddleware,
    register_metrics_endpoint,
)

__all__ = [
    # Tracing
    'setup_telemetry',
    'get_tracer',
    'instrument_fastapi',
    'instrument_aiohttp',
    'trace_operation',
    'add_trace_event',
    'set_trace_attribute',
    'shutdown_telemetry',

    # Health checks
    'HealthCheckSystem',
    'HealthCheckProvider',
    'HealthCheckResult',
    'HealthStatus',
    'DatabaseHealthCheck',
    'JobQueueHealthCheck',
    'WorkerPoolHealthCheck',
    'register_health_endpoints',

    # Config watching
    'ConfigWatcher',
    'watch_config',

    # Metrics
    'MetricsCollector',
    'MetricsMiddleware',
    'register_metrics_endpoint',
]
