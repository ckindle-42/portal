"""
Prometheus Metrics
==================

Prometheus-compatible metrics for production monitoring.

Metrics:
- Request counters (by endpoint, status)
- Request duration histograms
- Job queue metrics
- Worker pool metrics
- LLM request metrics
- Error rates

Endpoints:
- /metrics - Prometheus scrape endpoint

Example:
--------
# Initialize metrics
metrics = MetricsCollector()

# Record metrics
metrics.increment_counter("requests_total", {"endpoint": "/chat", "status": "200"})
metrics.observe_histogram("request_duration_seconds", 0.5, {"endpoint": "/chat"})

# Expose metrics endpoint (FastAPI)
app.add_route("/metrics", metrics.get_metrics_handler())
"""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Try to import Prometheus client
try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        REGISTRY,
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning(
        "Prometheus client not installed. Install with: "
        "pip install prometheus-client"
    )


class MetricsCollector:
    """
    Prometheus metrics collector for Portal.

    Provides common metrics out of the box and allows
    custom metric registration.
    """

    def __init__(self, service_name: str = "portal"):
        """
        Initialize metrics collector.

        Args:
            service_name: Name of the service
        """
        self.service_name = service_name
        self._metrics: dict[str, Any] = {}

        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus client not available, metrics disabled")
            return

        # Initialize standard metrics
        self._init_standard_metrics()

        logger.info("MetricsCollector initialized")

    def _init_standard_metrics(self):
        """Initialize standard metrics"""
        if not PROMETHEUS_AVAILABLE:
            return

        # Service info
        self._metrics['service_info'] = Info(
            'portal_service',
            'Service information'
        )
        try:
            from importlib.metadata import version as _pkg_version
            _version = _pkg_version("portal")
        except Exception:
            _version = "0.0.0-dev"
        self._metrics['service_info'].info({
            'service': self.service_name,
            'version': _version,
        })

        # HTTP request metrics
        self._metrics['http_requests_total'] = Counter(
            'portal_http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status']
        )

        self._metrics['http_request_duration_seconds'] = Histogram(
            'portal_http_request_duration_seconds',
            'HTTP request duration',
            ['method', 'endpoint']
        )

        # Job queue metrics
        self._metrics['jobs_enqueued_total'] = Counter(
            'portal_jobs_enqueued_total',
            'Total jobs enqueued',
            ['job_type']
        )

        self._metrics['jobs_completed_total'] = Counter(
            'portal_jobs_completed_total',
            'Total jobs completed',
            ['job_type', 'status']
        )

        self._metrics['jobs_pending'] = Gauge(
            'portal_jobs_pending',
            'Number of pending jobs'
        )

        self._metrics['jobs_running'] = Gauge(
            'portal_jobs_running',
            'Number of running jobs'
        )

        self._metrics['job_duration_seconds'] = Histogram(
            'portal_job_duration_seconds',
            'Job execution duration',
            ['job_type']
        )

        # Worker pool metrics
        self._metrics['workers_total'] = Gauge(
            'portal_workers_total',
            'Total number of workers'
        )

        self._metrics['workers_busy'] = Gauge(
            'portal_workers_busy',
            'Number of busy workers'
        )

        # LLM request metrics
        self._metrics['llm_requests_total'] = Counter(
            'portal_llm_requests_total',
            'Total LLM requests',
            ['model']
        )

        self._metrics['llm_request_duration_seconds'] = Histogram(
            'portal_llm_request_duration_seconds',
            'LLM request duration',
            ['model']
        )

        self._metrics['llm_tokens_total'] = Counter(
            'portal_llm_tokens_total',
            'Total LLM tokens used',
            ['model', 'type']  # type: input/output
        )

        # Error metrics
        self._metrics['errors_total'] = Counter(
            'portal_errors_total',
            'Total errors',
            ['type', 'component']
        )

        logger.info("Standard metrics initialized")

    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration: float
    ):
        """
        Record HTTP request metrics.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: Endpoint path
            status: HTTP status code
            duration: Request duration in seconds
        """
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics['http_requests_total'].labels(
            method=method,
            endpoint=endpoint,
            status=str(status)
        ).inc()

        self._metrics['http_request_duration_seconds'].labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)

    def record_job_enqueued(self, job_type: str):
        """Record job enqueued"""
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics['jobs_enqueued_total'].labels(
            job_type=job_type
        ).inc()

    def record_job_completed(
        self,
        job_type: str,
        status: str,
        duration: float
    ):
        """
        Record job completion.

        Args:
            job_type: Type of job
            status: Completion status (completed, failed, etc.)
            duration: Job duration in seconds
        """
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics['jobs_completed_total'].labels(
            job_type=job_type,
            status=status
        ).inc()

        self._metrics['job_duration_seconds'].labels(
            job_type=job_type
        ).observe(duration)

    def update_job_queue_stats(self, pending: int, running: int):
        """
        Update job queue gauges.

        Args:
            pending: Number of pending jobs
            running: Number of running jobs
        """
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics['jobs_pending'].set(pending)
        self._metrics['jobs_running'].set(running)

    def update_worker_stats(self, total: int, busy: int):
        """
        Update worker pool gauges.

        Args:
            total: Total number of workers
            busy: Number of busy workers
        """
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics['workers_total'].set(total)
        self._metrics['workers_busy'].set(busy)

    def record_llm_request(
        self,
        model: str,
        duration: float,
        input_tokens: int,
        output_tokens: int
    ):
        """
        Record LLM request metrics.

        Args:
            model: Model name
            duration: Request duration in seconds
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics['llm_requests_total'].labels(
            model=model
        ).inc()

        self._metrics['llm_request_duration_seconds'].labels(
            model=model
        ).observe(duration)

        self._metrics['llm_tokens_total'].labels(
            model=model,
            type='input'
        ).inc(input_tokens)

        self._metrics['llm_tokens_total'].labels(
            model=model,
            type='output'
        ).inc(output_tokens)

    def record_error(self, error_type: str, component: str):
        """
        Record error.

        Args:
            error_type: Type of error
            component: Component where error occurred
        """
        if not PROMETHEUS_AVAILABLE:
            return

        self._metrics['errors_total'].labels(
            type=error_type,
            component=component
        ).inc()

    def get_metrics_handler(self):
        """
        Get FastAPI handler for /metrics endpoint.

        Returns:
            FastAPI route handler
        """
        if not PROMETHEUS_AVAILABLE:
            async def metrics_unavailable():
                return {"error": "Prometheus client not installed"}

            return metrics_unavailable

        async def metrics():
            """Prometheus metrics endpoint"""
            from fastapi import Response

            metrics_output = generate_latest(REGISTRY)
            return Response(
                content=metrics_output,
                media_type=CONTENT_TYPE_LATEST
            )

        return metrics


# =============================================================================
# FASTAPI MIDDLEWARE
# =============================================================================


class MetricsMiddleware:
    """
    FastAPI middleware for automatic metrics collection.

    Automatically records:
    - Request count
    - Request duration
    - Response status
    """

    def __init__(self, app, metrics: MetricsCollector):
        """
        Initialize middleware.

        Args:
            app: FastAPI application
            metrics: MetricsCollector instance
        """
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope, receive, send):
        """Process request"""
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        # Record start time
        start_time = time.time()

        # Extract request info
        method = scope['method']
        path = scope['path']

        # Process request
        status_code = None

        async def send_wrapper(message):
            nonlocal status_code

            if message['type'] == 'http.response.start':
                status_code = message['status']

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)

        finally:
            # Record metrics
            duration = time.time() - start_time

            if status_code is not None:
                self.metrics.record_http_request(
                    method=method,
                    endpoint=path,
                    status=status_code,
                    duration=duration
                )


def register_metrics_endpoint(app, metrics: MetricsCollector):
    """
    Register /metrics endpoint with FastAPI app.

    Args:
        app: FastAPI application
        metrics: MetricsCollector instance
    """
    app.add_route("/metrics", metrics.get_metrics_handler(), methods=["GET"])
    logger.info("Metrics endpoint registered: /metrics")
