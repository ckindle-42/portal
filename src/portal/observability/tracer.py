"""
Distributed Tracing
===================

OpenTelemetry-based distributed tracing for Portal.

Provides optional tracing instrumentation. If opentelemetry packages are not
installed, tracing is silently disabled.

Example:
--------
from portal.observability.tracer import setup_telemetry

setup_telemetry(service_name="portal", otlp_endpoint="http://localhost:4317")
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    OPENTELEMETRY_AVAILABLE = False
    logger.debug("OpenTelemetry SDK not available; tracing disabled.")


def setup_telemetry(
    service_name: str = "portal",
    otlp_endpoint: str | None = None,
    **kwargs: Any,
) -> Any:
    """Configure OpenTelemetry tracing for Portal.

    Args:
        service_name: The service name reported in traces.
        otlp_endpoint: Optional OTLP gRPC endpoint (e.g. ``http://localhost:4317``).
        **kwargs: Additional keyword arguments (ignored).

    Returns:
        The configured :class:`TracerProvider`, or ``None`` if OpenTelemetry is
        not installed.
    """
    if not OPENTELEMETRY_AVAILABLE:
        logger.warning(
            "OpenTelemetry not installed. Install with: "
            "pip install opentelemetry-sdk opentelemetry-exporter-otlp"
        )
        return None

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OpenTelemetry OTLP exporter configured: %s", otlp_endpoint)
        except ImportError:
            logger.warning(
                "OTLP exporter not installed. Install with: "
                "pip install opentelemetry-exporter-otlp-proto-grpc"
            )

    trace.set_tracer_provider(provider)
    logger.info("OpenTelemetry tracing configured for service: %s", service_name)
    return provider


def get_tracer(name: str = "portal") -> Any:
    """Return an OpenTelemetry tracer, or a no-op object if unavailable."""
    if not OPENTELEMETRY_AVAILABLE:
        return _NoOpTracer()
    from opentelemetry import trace as _trace

    return _trace.get_tracer(name)


class _NoOpTracer:
    """Minimal no-op tracer used when OpenTelemetry is not installed."""

    def start_as_current_span(self, name: str, **kwargs: Any) -> Any:  # noqa: ARG002
        from contextlib import contextmanager

        @contextmanager
        def _noop():  # type: ignore[return]
            yield None

        return _noop()
