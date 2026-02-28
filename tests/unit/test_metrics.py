"""Tests for portal.observability.metrics."""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _fresh_collector(service_name="test-portal"):
    """Build a MetricsCollector with its own private registry to avoid collisions."""
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, Info

    from portal.observability.metrics import MetricsCollector

    registry = CollectorRegistry()
    collector = MetricsCollector.__new__(MetricsCollector)
    collector.service_name = service_name
    collector._metrics = {}
    uid = id(collector)

    collector._metrics["service_info"] = Info(f"portal_service_{uid}", "Info", registry=registry)
    collector._metrics["service_info"].info({"service": service_name, "version": "0.0.0-test"})
    collector._metrics["http_requests_total"] = Counter(
        f"portal_http_req_{uid}", "HTTP req", ["method", "endpoint", "status"], registry=registry
    )
    collector._metrics["http_request_duration_seconds"] = Histogram(
        f"portal_http_dur_{uid}", "HTTP dur", ["method", "endpoint"], registry=registry
    )
    collector._metrics["jobs_enqueued_total"] = Counter(
        f"portal_jobs_enq_{uid}", "Jobs enqueued", ["job_type"], registry=registry
    )
    collector._metrics["jobs_completed_total"] = Counter(
        f"portal_jobs_comp_{uid}", "Jobs completed", ["job_type", "status"], registry=registry
    )
    collector._metrics["jobs_pending"] = Gauge(
        f"portal_jobs_pend_{uid}", "Pending", registry=registry
    )
    collector._metrics["jobs_running"] = Gauge(
        f"portal_jobs_run_{uid}", "Running", registry=registry
    )
    collector._metrics["job_duration_seconds"] = Histogram(
        f"portal_job_dur_{uid}", "Job dur", ["job_type"], registry=registry
    )
    collector._metrics["workers_total"] = Gauge(
        f"portal_workers_t_{uid}", "Total W", registry=registry
    )
    collector._metrics["workers_busy"] = Gauge(
        f"portal_workers_b_{uid}", "Busy W", registry=registry
    )
    collector._metrics["llm_requests_total"] = Counter(
        f"portal_llm_req_{uid}", "LLM req", ["model"], registry=registry
    )
    collector._metrics["llm_request_duration_seconds"] = Histogram(
        f"portal_llm_dur_{uid}", "LLM dur", ["model"], registry=registry
    )
    collector._metrics["llm_tokens_total"] = Counter(
        f"portal_llm_tok_{uid}", "LLM tok", ["model", "type"], registry=registry
    )
    collector._metrics["errors_total"] = Counter(
        f"portal_err_{uid}", "Errors", ["type", "component"], registry=registry
    )
    collector._registry = registry
    return collector


class TestMetricsCollectorWithPrometheus:
    def test_http_request_increments_counter(self):
        mc = _fresh_collector()
        mc.record_http_request("GET", "/api/v1/chat", 200, 0.05)
        val = (
            mc._metrics["http_requests_total"]
            .labels(method="GET", endpoint="/api/v1/chat", status="200")
            ._value.get()
        )
        assert val == 1.0

    def test_http_request_records_duration(self):
        mc = _fresh_collector()
        mc.record_http_request("POST", "/run", 201, 1.234)
        hist_sum = (
            mc._metrics["http_request_duration_seconds"]
            .labels(method="POST", endpoint="/run")
            ._sum.get()
        )
        assert hist_sum == pytest.approx(1.234)

    def test_record_job_enqueued_multiple(self):
        mc = _fresh_collector()
        mc.record_job_enqueued("inference")
        mc.record_job_enqueued("inference")
        mc.record_job_enqueued("embedding")
        assert mc._metrics["jobs_enqueued_total"].labels(job_type="inference")._value.get() == 2.0
        assert mc._metrics["jobs_enqueued_total"].labels(job_type="embedding")._value.get() == 1.0

    def test_record_job_completed(self):
        mc = _fresh_collector()
        mc.record_job_completed("inference", "completed", 5.5)
        assert (
            mc._metrics["jobs_completed_total"]
            .labels(job_type="inference", status="completed")
            ._value.get()
            == 1.0
        )
        assert mc._metrics["job_duration_seconds"].labels(
            job_type="inference"
        )._sum.get() == pytest.approx(5.5)

    def test_update_job_queue_stats(self):
        mc = _fresh_collector()
        mc.update_job_queue_stats(pending=10, running=3)
        assert mc._metrics["jobs_pending"]._value.get() == 10
        assert mc._metrics["jobs_running"]._value.get() == 3
        mc.update_job_queue_stats(pending=0, running=0)
        assert mc._metrics["jobs_pending"]._value.get() == 0

    def test_update_worker_stats(self):
        mc = _fresh_collector()
        mc.update_worker_stats(total=8, busy=5)
        assert mc._metrics["workers_total"]._value.get() == 8
        mc.update_worker_stats(total=4, busy=2)
        assert mc._metrics["workers_busy"]._value.get() == 2

    def test_record_llm_request(self):
        mc = _fresh_collector()
        mc.record_llm_request("llama3", 2.5, 100, 50)
        mc.record_llm_request("llama3", 0.5, 30, 15)
        assert mc._metrics["llm_requests_total"].labels(model="llama3")._value.get() == 2.0
        assert (
            mc._metrics["llm_tokens_total"].labels(model="llama3", type="input")._value.get()
            == 130.0
        )
        assert (
            mc._metrics["llm_tokens_total"].labels(model="llama3", type="output")._value.get()
            == 65.0
        )

    def test_record_error(self):
        mc = _fresh_collector()
        mc.record_error("TimeoutError", "llm")
        mc.record_error("TimeoutError", "llm")
        mc.record_error("RuntimeError", "worker")
        assert (
            mc._metrics["errors_total"].labels(type="TimeoutError", component="llm")._value.get()
            == 2.0
        )
        assert (
            mc._metrics["errors_total"].labels(type="RuntimeError", component="worker")._value.get()
            == 1.0
        )


class TestMetricsCollectorPrometheusUnavailable:
    @patch("portal.observability.metrics.PROMETHEUS_AVAILABLE", False)
    def test_all_methods_are_noops(self):
        from portal.observability.metrics import MetricsCollector

        mc = MetricsCollector("fallback")
        assert mc._metrics == {}
        mc.record_http_request("GET", "/", 200, 0.1)
        mc.record_job_enqueued("test")
        mc.record_job_completed("test", "ok", 1.0)
        mc.update_job_queue_stats(0, 0)
        mc.update_worker_stats(1, 0)
        mc.record_llm_request("model", 1.0, 10, 5)
        mc.record_error("Err", "comp")
        assert mc._metrics == {}  # still empty

    @patch("portal.observability.metrics.PROMETHEUS_AVAILABLE", False)
    async def test_handler_returns_error(self):
        from portal.observability.metrics import MetricsCollector

        mc = MetricsCollector()
        result = await mc.get_metrics_handler()()
        assert result == {"error": "Prometheus client not installed"}


class TestGetMetricsHandler:
    async def test_handler_is_coroutine(self):
        mc = _fresh_collector()
        assert inspect.iscoroutinefunction(mc.get_metrics_handler())

    @patch("portal.observability.metrics.generate_latest", return_value=b"# HELP test\n")
    @patch("portal.observability.metrics.CONTENT_TYPE_LATEST", "text/plain")
    async def test_handler_returns_response(self, _):
        mc = _fresh_collector()
        resp = await mc.get_metrics_handler()()
        assert resp.body == b"# HELP test\n"


class TestMetricsMiddleware:
    async def test_non_http_passthrough(self):
        from portal.observability.metrics import MetricsMiddleware

        mc = _fresh_collector()
        inner = AsyncMock()
        mw = MetricsMiddleware(inner, mc)
        scope = {"type": "websocket", "path": "/ws"}
        await mw(scope, AsyncMock(), AsyncMock())
        inner.assert_awaited_once_with(scope, inner.call_args[0][1], inner.call_args[0][2])

    async def test_http_scope_records_metrics(self):
        from portal.observability.metrics import MetricsMiddleware

        mc = _fresh_collector()
        mc.record_http_request = MagicMock()

        async def inner(scope, receive, send):
            await send({"type": "http.response.start", "status": 200})

        mw = MetricsMiddleware(inner, mc)
        await mw({"type": "http", "method": "GET", "path": "/test"}, AsyncMock(), AsyncMock())
        mc.record_http_request.assert_called_once()
        kw = mc.record_http_request.call_args.kwargs
        assert kw["method"] == "GET" and kw["endpoint"] == "/test" and kw["status"] == 200
        assert kw["duration"] >= 0

    async def test_no_response_start_skips_record(self):
        from portal.observability.metrics import MetricsMiddleware

        mc = _fresh_collector()
        mc.record_http_request = MagicMock()
        mw = MetricsMiddleware(AsyncMock(), mc)
        await mw({"type": "http", "method": "GET", "path": "/x"}, AsyncMock(), AsyncMock())
        mc.record_http_request.assert_not_called()

    async def test_app_raises_still_records(self):
        from portal.observability.metrics import MetricsMiddleware

        mc = _fresh_collector()
        mc.record_http_request = MagicMock()

        async def inner(scope, receive, send):
            await send({"type": "http.response.start", "status": 500})
            raise RuntimeError("boom")

        mw = MetricsMiddleware(inner, mc)
        with pytest.raises(RuntimeError):
            await mw({"type": "http", "method": "POST", "path": "/err"}, AsyncMock(), AsyncMock())
        assert mc.record_http_request.call_args.kwargs["status"] == 500


class TestRegisterMetricsEndpoint:
    def test_registers_metrics_route(self):
        from portal.observability.metrics import register_metrics_endpoint

        mc = _fresh_collector()
        app = MagicMock()
        register_metrics_endpoint(app, mc)
        app.add_route.assert_called_once()
        args = app.add_route.call_args[0]
        assert args[0] == "/metrics" and callable(args[1])
