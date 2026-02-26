"""
OpenTelemetry Integration
==========================

Distributed tracing for Portal using OpenTelemetry.

Features:
- Automatic instrumentation for FastAPI, aiohttp
- Manual span creation for custom code
- OTLP export to Jaeger, Grafana Tempo, etc.
- Trace context propagation across services

Usage:
------
# Initialize tracer on startup
setup_telemetry(service_name="portal")

# Automatic tracing for FastAPI/aiohttp
# Manual tracing
with tracer.start_as_current_span("operation_name") as span:
    span.set_attribute("key", "value")
    # Your code here
"""

import logging
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False
    logger.warning(
        "OpenTelemetry not installed. Install with: "
        "pip install opentelemetry-api opentelemetry-sdk "
        "opentelemetry-exporter-otlp opentelemetry-instrumentation-fastapi"
    )


_tracer: Any | None = None
_provider: Any | None = None


def setup_telemetry(
    service_name: str = "portal",
    otlp_endpoint: str | None = None,
    enable_console: bool = False
) -> None:
    """
    Setup OpenTelemetry tracing.

    Args:
        service_name: Name of the service for tracing
        otlp_endpoint: OTLP exporter endpoint (e.g., "http://localhost:4317")
        enable_console: Enable console span exporter for debugging
    """
    global _tracer, _provider

    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available, tracing disabled")
        return

    # Create resource
    resource = Resource(attributes={
        SERVICE_NAME: service_name
    })

    # Create tracer provider
    _provider = TracerProvider(resource=resource)

    # Add OTLP exporter if endpoint provided
    if otlp_endpoint:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
        _provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        logger.info(f"OpenTelemetry OTLP exporter configured: {otlp_endpoint}")

    # Add console exporter for debugging
    if enable_console:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        console_exporter = ConsoleSpanExporter()
        _provider.add_span_processor(BatchSpanProcessor(console_exporter))
        logger.info("OpenTelemetry console exporter enabled")

    # Set as global tracer provider
    trace.set_tracer_provider(_provider)

    # Get tracer
    _tracer = trace.get_tracer(__name__)

    logger.info(f"OpenTelemetry tracing initialized for service: {service_name}")


def get_tracer() -> Any | None:
    """Get the global tracer instance"""
    return _tracer


def instrument_fastapi(app):
    """
    Instrument FastAPI app for automatic tracing.

    Args:
        app: FastAPI application instance
    """
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available, FastAPI instrumentation skipped")
        return

    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented for OpenTelemetry tracing")
    except Exception as e:
        logger.error(f"Failed to instrument FastAPI: {e}")


def instrument_aiohttp():
    """Instrument aiohttp client for automatic tracing"""
    if not OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available, aiohttp instrumentation skipped")
        return

    try:
        AioHttpClientInstrumentor().instrument()
        logger.info("aiohttp instrumented for OpenTelemetry tracing")
    except Exception as e:
        logger.error(f"Failed to instrument aiohttp: {e}")


@contextmanager
def trace_operation(
    operation_name: str,
    attributes: dict | None = None
):
    """
    Context manager for tracing an operation.

    Args:
        operation_name: Name of the operation
        attributes: Optional attributes to add to the span

    Example:
        with trace_operation("process_message", {"chat_id": "123"}):
            # Your code here
            pass
    """
    if _tracer is None:
        # Tracing not enabled, just yield without creating span
        yield None
        return

    with _tracer.start_as_current_span(operation_name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, str(value))

        yield span


def add_trace_event(event_name: str, attributes: dict | None = None):
    """
    Add an event to the current span.

    Args:
        event_name: Name of the event
        attributes: Optional attributes
    """
    if _tracer is None:
        return

    current_span = trace.get_current_span()
    if current_span:
        current_span.add_event(event_name, attributes or {})


def set_trace_attribute(key: str, value):
    """
    Set an attribute on the current span.

    Args:
        key: Attribute key
        value: Attribute value
    """
    if _tracer is None:
        return

    current_span = trace.get_current_span()
    if current_span:
        current_span.set_attribute(key, str(value))


def shutdown_telemetry():
    """Shutdown telemetry and flush spans"""
    global _provider

    if _provider:
        _provider.shutdown()
        logger.info("OpenTelemetry tracing shutdown")
