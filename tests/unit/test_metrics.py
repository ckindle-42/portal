"""
Tests for portal.observability.metrics
=======================================

Comprehensive tests for MetricsCollector, MetricsMiddleware,
and register_metrics_endpoint covering both Prometheus-available
and Prometheus-unavailable code paths.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_collector(service_name: str = "test-portal"):
    """
    Build a MetricsCollector that uses its own private registry so tests
    never collide with the global Prometheus REGISTRY.
    """
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, Info

    registry = CollectorRegistry()
    from portal.observability.metrics import MetricsCollector

    collector = MetricsCollector.__new__(MetricsCollector)
    collector.service_name = service_name
    collector._metrics = {}

    # service info
    collector._metrics["service_info"] = Info(
        f"portal_service_{id(collector)}",
        "Service information",
        registry=registry,
    )
    collector._metrics["service_info"].info(
        {"service": service_name, "version": "0.0.0-test"}
    )

    # HTTP
    collector._metrics["http_requests_total"] = Counter(
        f"portal_http_requests_total_{id(collector)}",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
        registry=registry,
    )
    collector._metrics["http_request_duration_seconds"] = Histogram(
        f"portal_http_request_duration_seconds_{id(collector)}",
        "HTTP request duration",
        ["method", "endpoint"],
        registry=registry,
    )

    # Jobs
    collector._metrics["jobs_enqueued_total"] = Counter(
        f"portal_jobs_enqueued_total_{id(collector)}",
        "Total jobs enqueued",
        ["job_type"],
        registry=registry,
    )
    collector._metrics["jobs_completed_total"] = Counter(
        f"portal_jobs_completed_total_{id(collector)}",
        "Total jobs completed",
        ["job_type", "status"],
        registry=registry,
    )
    collector._metrics["jobs_pending"] = Gauge(
        f"portal_jobs_pending_{id(collector)}",
        "Pending jobs",
        registry=registry,
    )
    collector._metrics["jobs_running"] = Gauge(
        f"portal_jobs_running_{id(collector)}",
        "Running jobs",
        registry=registry,
    )
    collector._metrics["job_duration_seconds"] = Histogram(
        f"portal_job_duration_seconds_{id(collector)}",
        "Job execution duration",
        ["job_type"],
        registry=registry,
    )

    # Workers
    collector._metrics["workers_total"] = Gauge(
        f"portal_workers_total_{id(collector)}",
        "Total workers",
        registry=registry,
    )
    collector._metrics["workers_busy"] = Gauge(
        f"portal_workers_busy_{id(collector)}",
        "Busy workers",
        registry=registry,
    )

    # LLM
    collector._metrics["llm_requests_total"] = Counter(
        f"portal_llm_requests_total_{id(collector)}",
        "Total LLM requests",
        ["model"],
        registry=registry,
    )
    collector._metrics["llm_request_duration_seconds"] = Histogram(
        f"portal_llm_request_duration_seconds_{id(collector)}",
        "LLM request duration",
        ["model"],
        registry=registry,
    )
    collector._metrics["llm_tokens_total"] = Counter(
        f"portal_llm_tokens_total_{id(collector)}",
        "Total LLM tokens used",
        ["model", "type"],
        registry=registry,
    )

    # Errors
    collector._metrics["errors_total"] = Counter(
        f"portal_errors_total_{id(collector)}",
        "Total errors",
        ["type", "component"],
        registry=registry,
    )

    collector._registry = registry  # stash for assertions
    return collector


# ===========================================================================
# MetricsCollector — Prometheus available
# ===========================================================================


class TestMetricsCollectorPrometheusAvailable:
    """Tests that exercise real Prometheus metric objects via a private registry."""

    def test_record_http_request_increments_counter(self):
        mc = _fresh_collector()
        mc.record_http_request("GET", "/api/v1/chat", 200, 0.05)

        val = mc._metrics["http_requests_total"].labels(
            method="GET", endpoint="/api/v1/chat", status="200"
        )._value.get()
        assert val == 1.0

    def test_record_http_request_records_duration(self):
        mc = _fresh_collector()
        mc.record_http_request("POST", "/run", 201, 1.234)

        hist = mc._metrics["http_request_duration_seconds"].labels(
            method="POST", endpoint="/run"
        )
        # Histogram sum should include the observed value
        assert hist._sum.get() == pytest.approx(1.234)

    def test_record_http_request_multiple_statuses(self):
        mc = _fresh_collector()
        mc.record_http_request("GET", "/", 200, 0.01)
        mc.record_http_request("GET", "/", 404, 0.02)
        mc.record_http_request("GET", "/", 500, 0.03)

        for status in ("200", "404", "500"):
            val = mc._metrics["http_requests_total"].labels(
                method="GET", endpoint="/", status=status
            )._value.get()
            assert val == 1.0

    def test_record_job_enqueued(self):
        mc = _fresh_collector()
        mc.record_job_enqueued("inference")
        mc.record_job_enqueued("inference")
        mc.record_job_enqueued("embedding")

        assert (
            mc._metrics["jobs_enqueued_total"]
            .labels(job_type="inference")
            ._value.get()
            == 2.0
        )
        assert (
            mc._metrics["jobs_enqueued_total"]
            .labels(job_type="embedding")
            ._value.get()
            == 1.0
        )

    def test_record_job_completed_increments_and_observes(self):
        mc = _fresh_collector()
        mc.record_job_completed("inference", "completed", 5.5)

        val = mc._metrics["jobs_completed_total"].labels(
            job_type="inference", status="completed"
        )._value.get()
        assert val == 1.0

        hist_sum = mc._metrics["job_duration_seconds"].labels(
            job_type="inference"
        )._sum.get()
        assert hist_sum == pytest.approx(5.5)

    def test_record_job_completed_failed_status(self):
        mc = _fresh_collector()
        mc.record_job_completed("training", "failed", 12.0)

        val = mc._metrics["jobs_completed_total"].labels(
            job_type="training", status="failed"
        )._value.get()
        assert val == 1.0

    def test_update_job_queue_stats(self):
        mc = _fresh_collector()
        mc.update_job_queue_stats(pending=10, running=3)

        assert mc._metrics["jobs_pending"]._value.get() == 10
        assert mc._metrics["jobs_running"]._value.get() == 3

    def test_update_job_queue_stats_overwrites(self):
        mc = _fresh_collector()
        mc.update_job_queue_stats(pending=5, running=1)
        mc.update_job_queue_stats(pending=0, running=0)

        assert mc._metrics["jobs_pending"]._value.get() == 0
        assert mc._metrics["jobs_running"]._value.get() == 0

    def test_update_worker_stats(self):
        mc = _fresh_collector()
        mc.update_worker_stats(total=8, busy=5)

        assert mc._metrics["workers_total"]._value.get() == 8
        assert mc._metrics["workers_busy"]._value.get() == 5

    def test_update_worker_stats_overwrites(self):
        mc = _fresh_collector()
        mc.update_worker_stats(total=4, busy=4)
        mc.update_worker_stats(total=4, busy=2)

        assert mc._metrics["workers_busy"]._value.get() == 2

    def test_record_llm_request(self):
        mc = _fresh_collector()
        mc.record_llm_request(
            model="llama3", duration=2.5, input_tokens=100, output_tokens=50
        )

        assert (
            mc._metrics["llm_requests_total"]
            .labels(model="llama3")
            ._value.get()
            == 1.0
        )
        assert mc._metrics["llm_request_duration_seconds"].labels(
            model="llama3"
        )._sum.get() == pytest.approx(2.5)
        assert (
            mc._metrics["llm_tokens_total"]
            .labels(model="llama3", type="input")
            ._value.get()
            == 100.0
        )
        assert (
            mc._metrics["llm_tokens_total"]
            .labels(model="llama3", type="output")
            ._value.get()
            == 50.0
        )

    def test_record_llm_request_accumulates_tokens(self):
        mc = _fresh_collector()
        mc.record_llm_request("gpt4", 1.0, 50, 25)
        mc.record_llm_request("gpt4", 0.5, 30, 15)

        assert (
            mc._metrics["llm_tokens_total"]
            .labels(model="gpt4", type="input")
            ._value.get()
            == 80.0
        )
        assert (
            mc._metrics["llm_tokens_total"]
            .labels(model="gpt4", type="output")
            ._value.get()
            == 40.0
        )

    def test_record_error(self):
        mc = _fresh_collector()
        mc.record_error("ValueError", "parser")

        val = mc._metrics["errors_total"].labels(
            type="ValueError", component="parser"
        )._value.get()
        assert val == 1.0

    def test_record_error_multiple(self):
        mc = _fresh_collector()
        mc.record_error("TimeoutError", "llm")
        mc.record_error("TimeoutError", "llm")
        mc.record_error("RuntimeError", "worker")

        assert (
            mc._metrics["errors_total"]
            .labels(type="TimeoutError", component="llm")
            ._value.get()
            == 2.0
        )
        assert (
            mc._metrics["errors_total"]
            .labels(type="RuntimeError", component="worker")
            ._value.get()
            == 1.0
        )

    def test_service_name_stored(self):
        mc = _fresh_collector("my-service")
        assert mc.service_name == "my-service"


# ===========================================================================
# MetricsCollector — Prometheus NOT available
# ===========================================================================


class TestMetricsCollectorPrometheusUnavailable:
    """Patch PROMETHEUS_AVAILABLE=False to verify graceful no-op behaviour."""

    @patch("portal.observability.metrics.PROMETHEUS_AVAILABLE", False)
    def test_init_no_metrics(self):
        from portal.observability.metrics import MetricsCollector

        mc = MetricsCollector("fallback")
        assert mc._metrics == {}

    @patch("portal.observability.metrics.PROMETHEUS_AVAILABLE", False)
    def test_record_http_request_noop(self):
        from portal.observability.metrics import MetricsCollector

        mc = MetricsCollector()
        # Should not raise
        mc.record_http_request("GET", "/", 200, 0.1)

    @patch("portal.observability.metrics.PROMETHEUS_AVAILABLE", False)
    def test_record_job_enqueued_noop(self):
        from portal.observability.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.record_job_enqueued("test")

    @patch("portal.observability.metrics.PROMETHEUS_AVAILABLE", False)
    def test_record_job_completed_noop(self):
        from portal.observability.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.record_job_completed("test", "ok", 1.0)

    @patch("portal.observability.metrics.PROMETHEUS_AVAILABLE", False)
    def test_update_job_queue_stats_noop(self):
        from portal.observability.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.update_job_queue_stats(0, 0)

    @patch("portal.observability.metrics.PROMETHEUS_AVAILABLE", False)
    def test_update_worker_stats_noop(self):
        from portal.observability.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.update_worker_stats(1, 0)

    @patch("portal.observability.metrics.PROMETHEUS_AVAILABLE", False)
    def test_record_llm_request_noop(self):
        from portal.observability.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.record_llm_request("model", 1.0, 10, 5)

    @patch("portal.observability.metrics.PROMETHEUS_AVAILABLE", False)
    def test_record_error_noop(self):
        from portal.observability.metrics import MetricsCollector

        mc = MetricsCollector()
        mc.record_error("Err", "comp")

    @patch("portal.observability.metrics.PROMETHEUS_AVAILABLE", False)
    async def test_get_metrics_handler_unavailable(self):
        from portal.observability.metrics import MetricsCollector

        mc = MetricsCollector()
        handler = mc.get_metrics_handler()
        result = await handler()
        assert result == {"error": "Prometheus client not installed"}

    @patch("portal.observability.metrics.PROMETHEUS_AVAILABLE", False)
    def test_init_standard_metrics_noop(self):
        """_init_standard_metrics returns early when Prometheus is missing."""
        from portal.observability.metrics import MetricsCollector

        mc = MetricsCollector()
        mc._init_standard_metrics()
        assert mc._metrics == {}


# ===========================================================================
# get_metrics_handler — Prometheus available
# ===========================================================================


class TestGetMetricsHandlerAvailable:
    """Test the /metrics handler when Prometheus IS available."""

    async def test_returns_coroutine_function(self):
        mc = _fresh_collector()
        handler = mc.get_metrics_handler()
        import asyncio

        assert asyncio.iscoroutinefunction(handler)

    @patch("portal.observability.metrics.generate_latest")
    @patch("portal.observability.metrics.CONTENT_TYPE_LATEST", "text/plain")
    async def test_handler_returns_response(self, mock_gen_latest):
        """Handler should call generate_latest and wrap in a Response."""
        mock_gen_latest.return_value = b"# HELP test\n"

        from portal.observability.metrics import MetricsCollector

        mc = _fresh_collector()
        # The handler produced by get_metrics_handler uses the module-level
        # generate_latest / REGISTRY, so we patch those.
        handler = mc.get_metrics_handler()
        resp = await handler()

        # Should be a FastAPI Response
        assert resp.body == b"# HELP test\n"


# ===========================================================================
# MetricsMiddleware
# ===========================================================================


class TestMetricsMiddleware:
    """Tests for the ASGI MetricsMiddleware."""

    async def test_non_http_scope_passes_through(self):
        from portal.observability.metrics import MetricsMiddleware

        mc = _fresh_collector()
        inner_app = AsyncMock()
        mw = MetricsMiddleware(inner_app, mc)

        scope = {"type": "websocket", "path": "/ws"}
        receive = AsyncMock()
        send = AsyncMock()

        await mw(scope, receive, send)
        inner_app.assert_awaited_once_with(scope, receive, send)

    async def test_http_scope_records_metrics(self):
        from portal.observability.metrics import MetricsMiddleware

        mc = _fresh_collector()
        mc.record_http_request = MagicMock()

        async def inner_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})
            await send({"type": "http.response.body", "body": b"ok"})

        mw = MetricsMiddleware(inner_app, mc)
        scope = {"type": "http", "method": "GET", "path": "/test"}
        receive = AsyncMock()
        send = AsyncMock()

        await mw(scope, receive, send)

        mc.record_http_request.assert_called_once()
        call_kwargs = mc.record_http_request.call_args
        assert call_kwargs.kwargs["method"] == "GET"
        assert call_kwargs.kwargs["endpoint"] == "/test"
        assert call_kwargs.kwargs["status"] == 200
        assert call_kwargs.kwargs["duration"] >= 0

    async def test_http_scope_no_status_code_skips_record(self):
        """If the inner app never sends http.response.start, no metric recorded."""
        from portal.observability.metrics import MetricsMiddleware

        mc = _fresh_collector()
        mc.record_http_request = MagicMock()

        async def inner_app(scope, receive, send):
            pass  # never sends a response start

        mw = MetricsMiddleware(inner_app, mc)
        scope = {"type": "http", "method": "GET", "path": "/noresp"}
        await mw(scope, AsyncMock(), AsyncMock())

        mc.record_http_request.assert_not_called()

    async def test_http_scope_app_raises_still_records(self):
        """Even when the inner app raises, finally block should run."""
        from portal.observability.metrics import MetricsMiddleware

        mc = _fresh_collector()
        mc.record_http_request = MagicMock()

        async def inner_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 500})
            raise RuntimeError("boom")

        mw = MetricsMiddleware(inner_app, mc)
        scope = {"type": "http", "method": "POST", "path": "/err"}

        with pytest.raises(RuntimeError, match="boom"):
            await mw(scope, AsyncMock(), AsyncMock())

        mc.record_http_request.assert_called_once()
        assert mc.record_http_request.call_args.kwargs["status"] == 500

    async def test_middleware_stores_app_and_metrics(self):
        from portal.observability.metrics import MetricsMiddleware

        mc = _fresh_collector()
        app = AsyncMock()
        mw = MetricsMiddleware(app, mc)

        assert mw.app is app
        assert mw.metrics is mc

    async def test_duration_is_positive(self):
        from portal.observability.metrics import MetricsMiddleware

        mc = _fresh_collector()
        mc.record_http_request = MagicMock()

        async def inner_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 204})

        mw = MetricsMiddleware(inner_app, mc)
        scope = {"type": "http", "method": "DELETE", "path": "/item"}
        await mw(scope, AsyncMock(), AsyncMock())

        duration = mc.record_http_request.call_args.kwargs["duration"]
        assert duration >= 0


# ===========================================================================
# register_metrics_endpoint
# ===========================================================================


class TestRegisterMetricsEndpoint:
    """Tests for the register_metrics_endpoint helper."""

    def test_registers_route_on_app(self):
        from portal.observability.metrics import register_metrics_endpoint

        mc = _fresh_collector()
        mock_app = MagicMock()

        register_metrics_endpoint(mock_app, mc)

        mock_app.add_route.assert_called_once()
        args, kwargs = mock_app.add_route.call_args
        assert args[0] == "/metrics"
        assert kwargs.get("methods") == ["GET"] or args[2] == ["GET"]

    def test_handler_is_callable(self):
        from portal.observability.metrics import register_metrics_endpoint

        mc = _fresh_collector()
        mock_app = MagicMock()

        register_metrics_endpoint(mock_app, mc)

        handler = mock_app.add_route.call_args[0][1]
        assert callable(handler)


# ===========================================================================
# Edge cases
# ===========================================================================


class TestMetricsEdgeCases:
    """Edge-case and boundary tests."""

    def test_zero_duration_http_request(self):
        mc = _fresh_collector()
        mc.record_http_request("GET", "/", 200, 0.0)

        hist = mc._metrics["http_request_duration_seconds"].labels(
            method="GET", endpoint="/"
        )
        assert hist._sum.get() == 0.0

    def test_large_token_counts(self):
        mc = _fresh_collector()
        mc.record_llm_request("big-model", 100.0, 1_000_000, 500_000)

        assert (
            mc._metrics["llm_tokens_total"]
            .labels(model="big-model", type="input")
            ._value.get()
            == 1_000_000.0
        )

    def test_empty_strings_as_labels(self):
        mc = _fresh_collector()
        mc.record_http_request("", "", 0, 0.0)
        mc.record_error("", "")
        mc.record_job_enqueued("")
        # Should not raise

    def test_special_characters_in_endpoint(self):
        mc = _fresh_collector()
        mc.record_http_request("GET", "/api/v1/users?q=hello&limit=10", 200, 0.01)
        val = mc._metrics["http_requests_total"].labels(
            method="GET", endpoint="/api/v1/users?q=hello&limit=10", status="200"
        )._value.get()
        assert val == 1.0

    def test_negative_duration_accepted(self):
        """Prometheus doesn't reject negative observations."""
        mc = _fresh_collector()
        mc.record_http_request("GET", "/", 200, -1.0)
        # No exception raised

    def test_status_code_stored_as_string(self):
        mc = _fresh_collector()
        mc.record_http_request("GET", "/x", 418, 0.0)
        val = mc._metrics["http_requests_total"].labels(
            method="GET", endpoint="/x", status="418"
        )._value.get()
        assert val == 1.0
