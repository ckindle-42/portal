"""Unit tests for WebInterface — audio size limit, security headers, request IDs."""

import io
from unittest.mock import AsyncMock, MagicMock, patch


async def aiter(items):
    for item in items:
        yield item


def _make_interface(stream_tokens=None):
    """Build a WebInterface backed by fully mocked AgentCore + SecurityMiddleware."""
    from portal.interfaces.web.server import WebInterface

    _tokens = stream_tokens or ["Hello", " world"]

    agent = MagicMock()
    agent.stream_response = MagicMock(side_effect=lambda _: aiter(_tokens))
    agent.health_check = AsyncMock(return_value=True)

    secure = MagicMock()
    secure.process_message = AsyncMock(
        return_value=MagicMock(
            response="ok",
            model_used="auto",
            prompt_tokens=0,
            completion_tokens=1,
        )
    )
    # No rate_limiter on the mock — tests that need it set it explicitly
    del secure.rate_limiter

    return WebInterface(agent_core=agent, config={}, secure_agent=secure)


class TestAudioSizeLimit:
    """S4: /v1/audio/transcriptions must reject oversized uploads."""

    def test_oversized_audio_returns_413(self, monkeypatch) -> None:
        """Uploading a file larger than PORTAL_MAX_AUDIO_MB returns 413."""
        from fastapi.testclient import TestClient

        monkeypatch.setenv("PORTAL_MAX_AUDIO_MB", "1")
        monkeypatch.delenv("WEB_API_KEY", raising=False)

        # Rebuild the module-level constant for this test
        import importlib

        import portal.interfaces.web.server as srv

        importlib.reload(srv)

        from portal.interfaces.web.server import WebInterface

        agent = MagicMock()
        agent.health_check = AsyncMock(return_value=True)
        iface = WebInterface(agent_core=agent, config={}, secure_agent=None)

        # Create a file bigger than 1MB
        big_content = b"x" * (1 * 1024 * 1024 + 1)
        with TestClient(iface.app, raise_server_exceptions=False) as client:
            resp = client.post(
                "/v1/audio/transcriptions",
                files={"file": ("big.wav", io.BytesIO(big_content), "audio/wav")},
            )
        assert resp.status_code == 413

    def test_small_audio_is_forwarded(self, monkeypatch) -> None:
        """Uploading a file within the limit is forwarded to the whisper endpoint."""
        from fastapi.testclient import TestClient

        monkeypatch.setenv("PORTAL_MAX_AUDIO_MB", "25")
        monkeypatch.delenv("WEB_API_KEY", raising=False)

        import importlib

        import portal.interfaces.web.server as srv

        importlib.reload(srv)

        from portal.interfaces.web.server import WebInterface

        agent = MagicMock()
        agent.health_check = AsyncMock(return_value=True)
        iface = WebInterface(agent_core=agent, config={}, secure_agent=None)

        small_content = b"x" * 1024  # 1 KB

        # Patch the httpx client to return a fake transcription result
        fake_resp = MagicMock()
        fake_resp.json.return_value = {"text": "hello"}

        with patch("portal.interfaces.web.server.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=fake_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_class.return_value = mock_client

            with TestClient(iface.app, raise_server_exceptions=False) as client:
                resp = client.post(
                    "/v1/audio/transcriptions",
                    files={"file": ("test.wav", io.BytesIO(small_content), "audio/wav")},
                )
        # Should not be 413
        assert resp.status_code != 413


class TestRequestIdHeader:
    """E3: Every response must include an X-Request-Id header."""

    def test_response_includes_request_id(self, monkeypatch) -> None:
        """GET /health includes X-Request-Id in the response."""
        from fastapi.testclient import TestClient

        monkeypatch.delenv("WEB_API_KEY", raising=False)
        iface = _make_interface()
        with TestClient(iface.app) as client:
            resp = client.get("/health")
        assert "x-request-id" in resp.headers

    def test_client_supplied_request_id_is_echoed(self, monkeypatch) -> None:
        """If the client supplies X-Request-Id it is echoed back unchanged."""
        from fastapi.testclient import TestClient

        monkeypatch.delenv("WEB_API_KEY", raising=False)
        iface = _make_interface()
        custom_id = "my-trace-id-42"
        with TestClient(iface.app) as client:
            resp = client.get("/health", headers={"X-Request-Id": custom_id})
        assert resp.headers.get("x-request-id") == custom_id


class TestVersionNotHardcoded:
    """R4: FastAPI app version must come from portal.__version__, not be hardcoded."""

    def test_app_version_matches_package_version(self) -> None:
        import portal
        from portal.interfaces.web.server import WebInterface

        agent = MagicMock()
        agent.health_check = AsyncMock(return_value=True)
        iface = WebInterface(agent_core=agent, config={}, secure_agent=None)
        assert iface.app.version == portal.__version__
