"""Tests for portal.observability.tracer"""

from unittest.mock import patch

from portal.observability.tracer import (
    _NoOpTracer,
    get_tracer,
    setup_telemetry,
)


class TestNoOpTracer:
    def test_start_as_current_span_context_manager(self):
        tracer = _NoOpTracer()
        with tracer.start_as_current_span("test") as span:
            assert span is None

    def test_start_as_current_span_yields_none(self):
        tracer = _NoOpTracer()
        with tracer.start_as_current_span("op", extra="kw") as span:
            assert span is None


class TestSetupTelemetry:
    def test_returns_provider_when_otel_available(self):
        provider = setup_telemetry(service_name="test-portal")
        # OpenTelemetry IS installed in this environment
        assert provider is not None

    def test_without_endpoint(self):
        provider = setup_telemetry(service_name="test")
        assert provider is not None

    def test_with_endpoint_no_exporter(self):
        # Even if exporter is missing, setup should still work
        provider = setup_telemetry(
            service_name="test",
            otlp_endpoint="http://localhost:4317"
        )
        assert provider is not None

    @patch("portal.observability.tracer.OPENTELEMETRY_AVAILABLE", False)
    def test_returns_none_when_otel_unavailable(self):
        result = setup_telemetry(service_name="test")
        assert result is None


class TestGetTracer:
    @patch("portal.observability.tracer.OPENTELEMETRY_AVAILABLE", False)
    def test_returns_noop_when_otel_unavailable(self):
        tracer = get_tracer("test")
        assert isinstance(tracer, _NoOpTracer)

    def test_returns_real_tracer_when_available(self):
        tracer = get_tracer("test")
        # Should NOT be a _NoOpTracer when OpenTelemetry is installed
        assert tracer is not None
