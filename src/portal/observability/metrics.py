"""Prometheus-compatible metrics — counters, histograms, and /metrics endpoint."""

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

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
    logger.warning("Prometheus client not installed. Install with: pip install prometheus-client")


class MetricsCollector:
    """Prometheus metrics collector for Portal."""

    def __init__(self, service_name: str = "portal") -> None:
        self.service_name = service_name
        self._metrics: dict[str, Any] = {}
        if not PROMETHEUS_AVAILABLE:
            logger.warning("Prometheus client not available, metrics disabled")
            return
        self._init_standard_metrics()
        logger.info("MetricsCollector initialized")

    def _init_standard_metrics(self) -> None:
        if not PROMETHEUS_AVAILABLE:
            return
        self._metrics["service_info"] = Info("portal_service", "Service information")
        try:
            from importlib.metadata import version as _pkg_version

            _version = _pkg_version("portal")
        except Exception:
            _version = "0.0.0-dev"
        self._metrics["service_info"].info({"service": self.service_name, "version": _version})
        self._metrics["http_requests_total"] = Counter(
            "portal_http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
        )
        self._metrics["http_request_duration_seconds"] = Histogram(
            "portal_http_request_duration_seconds", "HTTP request duration", ["method", "endpoint"]
        )
        self._metrics["jobs_enqueued_total"] = Counter(
            "portal_jobs_enqueued_total", "Total jobs enqueued", ["job_type"]
        )
        self._metrics["jobs_completed_total"] = Counter(
            "portal_jobs_completed_total", "Total jobs completed", ["job_type", "status"]
        )
        self._metrics["jobs_pending"] = Gauge("portal_jobs_pending", "Number of pending jobs")
        self._metrics["jobs_running"] = Gauge("portal_jobs_running", "Number of running jobs")
        self._metrics["job_duration_seconds"] = Histogram(
            "portal_job_duration_seconds", "Job execution duration", ["job_type"]
        )
        self._metrics["workers_total"] = Gauge("portal_workers_total", "Total number of workers")
        self._metrics["workers_busy"] = Gauge("portal_workers_busy", "Number of busy workers")
        self._metrics["llm_requests_total"] = Counter(
            "portal_llm_requests_total", "Total LLM requests", ["model"]
        )
        self._metrics["llm_request_duration_seconds"] = Histogram(
            "portal_llm_request_duration_seconds", "LLM request duration", ["model"]
        )
        self._metrics["llm_tokens_total"] = Counter(
            "portal_llm_tokens_total", "Total LLM tokens used", ["model", "type"]
        )
        self._metrics["errors_total"] = Counter(
            "portal_errors_total", "Total errors", ["type", "component"]
        )
        logger.info("Standard metrics initialized")

    def record_http_request(self, method: str, endpoint: str, status: int, duration: float) -> None:
        if not PROMETHEUS_AVAILABLE:
            return
        self._metrics["http_requests_total"].labels(
            method=method, endpoint=endpoint, status=str(status)
        ).inc()
        self._metrics["http_request_duration_seconds"].labels(
            method=method, endpoint=endpoint
        ).observe(duration)

    def record_job_enqueued(self, job_type: str) -> None:
        if not PROMETHEUS_AVAILABLE:
            return
        self._metrics["jobs_enqueued_total"].labels(job_type=job_type).inc()

    def record_job_completed(self, job_type: str, status: str, duration: float) -> None:
        if not PROMETHEUS_AVAILABLE:
            return
        self._metrics["jobs_completed_total"].labels(job_type=job_type, status=status).inc()
        self._metrics["job_duration_seconds"].labels(job_type=job_type).observe(duration)

    def update_job_queue_stats(self, pending: int, running: int) -> None:
        if not PROMETHEUS_AVAILABLE:
            return
        self._metrics["jobs_pending"].set(pending)
        self._metrics["jobs_running"].set(running)

    def update_worker_stats(self, total: int, busy: int) -> None:
        if not PROMETHEUS_AVAILABLE:
            return
        self._metrics["workers_total"].set(total)
        self._metrics["workers_busy"].set(busy)

    def record_llm_request(
        self, model: str, duration: float, input_tokens: int, output_tokens: int
    ) -> None:
        if not PROMETHEUS_AVAILABLE:
            return
        self._metrics["llm_requests_total"].labels(model=model).inc()
        self._metrics["llm_request_duration_seconds"].labels(model=model).observe(duration)
        self._metrics["llm_tokens_total"].labels(model=model, type="input").inc(input_tokens)
        self._metrics["llm_tokens_total"].labels(model=model, type="output").inc(output_tokens)

    def record_error(self, error_type: str, component: str) -> None:
        if not PROMETHEUS_AVAILABLE:
            return
        self._metrics["errors_total"].labels(type=error_type, component=component).inc()

    def get_metrics_handler(self):
        if not PROMETHEUS_AVAILABLE:

            async def metrics_unavailable() -> dict[str, str]:
                return {"error": "Prometheus client not installed"}

            return metrics_unavailable

        async def metrics():
            from fastapi import Response

            return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)

        return metrics


class MetricsMiddleware:
    """FastAPI middleware for automatic HTTP metrics collection."""

    def __init__(self, app, metrics: MetricsCollector) -> None:
        self.app = app
        self.metrics = metrics

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        start_time = time.time()
        method = scope["method"]
        path = scope["path"]
        status_code = None

        async def send_wrapper(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if status_code is not None:
                self.metrics.record_http_request(
                    method=method,
                    endpoint=path,
                    status=status_code,
                    duration=time.time() - start_time,
                )


def register_metrics_endpoint(app, metrics: MetricsCollector) -> None:
    """Register /metrics endpoint with a FastAPI app."""
    app.add_route("/metrics", metrics.get_metrics_handler(), methods=["GET"])
    logger.info("Metrics endpoint registered: /metrics")
