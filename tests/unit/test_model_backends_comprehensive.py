"""
Comprehensive tests for portal.routing.model_backends

Covers:
- GenerationResult dataclass
- BaseHTTPBackend: _build_chat_messages, _get_session, close
- OllamaBackend: generate, generate_stream, is_available, list_models, _normalize_tool_calls
- LMStudioBackend: generate, generate_stream, is_available, list_models
- MLXBackend: generate, is_available, list_models, generate_stream
"""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from portal.routing.model_backends import (
    BaseHTTPBackend,
    GenerationResult,
    LMStudioBackend,
    MLXBackend,
    OllamaBackend,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _FakeResponse:
    """Minimal mock for an aiohttp response context manager."""

    def __init__(self, status: int = 200, json_data: dict | None = None,
                 text_data: str = "", lines: list[bytes] | None = None):
        self.status = status
        self._json_data = json_data or {}
        self._text_data = text_data
        self._lines = lines or []

    async def json(self):
        return self._json_data

    async def text(self):
        return self._text_data

    @property
    def content(self):
        return _FakeContent(self._lines)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class _FakeContent:
    """Async iterable over raw bytes (simulates aiohttp StreamReader)."""

    def __init__(self, lines: list[bytes]):
        self._lines = lines

    def __aiter__(self):
        return _FakeContentIter(self._lines)


class _FakeContentIter:
    def __init__(self, lines: list[bytes]):
        self._iter = iter(lines)

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class _FakeSession:
    """Minimal mock of aiohttp.ClientSession."""

    def __init__(self, response: _FakeResponse | None = None):
        self._response = response or _FakeResponse()
        self.closed = False

    def post(self, url, **kwargs):
        return self._response

    def get(self, url, **kwargs):
        return self._response

    async def close(self):
        self.closed = True


# ---------------------------------------------------------------------------
# GenerationResult
# ---------------------------------------------------------------------------

class TestGenerationResult:
    def test_success_result(self):
        r = GenerationResult(
            text="hello", tokens_generated=5, time_ms=100.0,
            model_id="test", success=True,
        )
        assert r.success
        assert r.error is None
        assert r.tool_calls is None

    def test_failure_result(self):
        r = GenerationResult(
            text="", tokens_generated=0, time_ms=50.0,
            model_id="test", success=False, error="timeout",
        )
        assert not r.success
        assert r.error == "timeout"

    def test_with_tool_calls(self):
        calls = [{"tool": "clock", "arguments": {}}]
        r = GenerationResult(
            text="", tokens_generated=0, time_ms=10.0,
            model_id="test", success=True, tool_calls=calls,
        )
        assert r.tool_calls == calls


# ---------------------------------------------------------------------------
# BaseHTTPBackend._build_chat_messages
# ---------------------------------------------------------------------------

class TestBuildChatMessages:
    def test_prompt_only(self):
        msgs = BaseHTTPBackend._build_chat_messages("hello", None, None)
        assert msgs == [{"role": "user", "content": "hello"}]

    def test_prompt_with_system(self):
        msgs = BaseHTTPBackend._build_chat_messages("hello", "Be helpful", None)
        assert msgs[0] == {"role": "system", "content": "Be helpful"}
        assert msgs[1] == {"role": "user", "content": "hello"}

    def test_messages_passthrough(self):
        history = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        msgs = BaseHTTPBackend._build_chat_messages("ignored", None, history)
        assert msgs == history

    def test_messages_with_system_prepended(self):
        history = [{"role": "user", "content": "q1"}]
        msgs = BaseHTTPBackend._build_chat_messages("ignored", "sys", history)
        assert msgs[0] == {"role": "system", "content": "sys"}
        assert msgs[1] == {"role": "user", "content": "q1"}

    def test_messages_with_system_already_present(self):
        history = [
            {"role": "system", "content": "existing"},
            {"role": "user", "content": "q1"},
        ]
        msgs = BaseHTTPBackend._build_chat_messages("ignored", "new sys", history)
        # Should NOT prepend another system message
        assert msgs[0] == {"role": "system", "content": "existing"}
        assert len(msgs) == 2

    def test_empty_messages_list_gets_system_prepended(self):
        msgs = BaseHTTPBackend._build_chat_messages("ignored", "sys", [])
        assert msgs == [{"role": "system", "content": "sys"}]


# ---------------------------------------------------------------------------
# OllamaBackend._normalize_tool_calls
# ---------------------------------------------------------------------------

class TestNormalizeToolCalls:
    def test_openai_function_shape(self):
        raw = [{"function": {"name": "f1", "arguments": {"a": 1}}}]
        result = OllamaBackend._normalize_tool_calls(raw)
        assert result == [{"tool": "f1", "name": "f1", "arguments": {"a": 1}}]

    def test_openai_function_with_server(self):
        raw = [{"function": {"name": "f1", "arguments": {}}, "server": "s1"}]
        result = OllamaBackend._normalize_tool_calls(raw)
        assert result[0]["server"] == "s1"

    def test_passthrough_already_normalized(self):
        raw = [{"tool": "t1", "arguments": {}}]
        result = OllamaBackend._normalize_tool_calls(raw)
        assert result == raw

    def test_non_list_returns_none(self):
        assert OllamaBackend._normalize_tool_calls("bad") is None
        assert OllamaBackend._normalize_tool_calls(42) is None
        assert OllamaBackend._normalize_tool_calls(None) is None

    def test_empty_list_returns_none(self):
        assert OllamaBackend._normalize_tool_calls([]) is None

    def test_non_dict_entries_skipped(self):
        raw = ["not_a_dict", {"tool": "t1", "arguments": {}}]
        result = OllamaBackend._normalize_tool_calls(raw)
        assert len(result) == 1
        assert result[0]["tool"] == "t1"

    def test_function_with_fallback_name(self):
        raw = [{"function": {"arguments": {}}, "name": "fallback_name"}]
        result = OllamaBackend._normalize_tool_calls(raw)
        assert result[0]["name"] == "fallback_name"
        assert result[0]["tool"] == "fallback_name"

    def test_list_of_all_non_dicts_returns_none(self):
        assert OllamaBackend._normalize_tool_calls([1, 2, "three"]) is None


# ---------------------------------------------------------------------------
# OllamaBackend: generate
# ---------------------------------------------------------------------------

class TestOllamaGenerate:
    @pytest.mark.asyncio
    async def test_successful_generation(self):
        backend = OllamaBackend()
        response_data = {
            "message": {"content": "Hello!", "tool_calls": None},
            "eval_count": 10,
        }
        fake_resp = _FakeResponse(status=200, json_data=response_data)
        fake_session = _FakeSession(fake_resp)
        backend._session = fake_session

        with patch.object(backend, "_get_session", return_value=fake_session):
            result = await backend.generate("hi", "test-model")

        assert result.success
        assert result.text == "Hello!"
        assert result.tokens_generated == 10

    @pytest.mark.asyncio
    async def test_http_error(self):
        backend = OllamaBackend()
        fake_resp = _FakeResponse(status=500, text_data="Internal Server Error")
        fake_session = _FakeSession(fake_resp)

        with patch.object(backend, "_get_session", return_value=fake_session):
            result = await backend.generate("hi", "test-model")

        assert not result.success
        assert "500" in result.error

    @pytest.mark.asyncio
    async def test_exception_during_generate(self):
        backend = OllamaBackend()
        with patch.object(backend, "_get_session", side_effect=ConnectionError("refused")):
            result = await backend.generate("hi", "test-model")
        assert not result.success
        assert "refused" in result.error

    @pytest.mark.asyncio
    async def test_generate_with_tool_calls(self):
        backend = OllamaBackend()
        tool_calls_raw = [{"function": {"name": "calc", "arguments": {"x": 1}}}]
        response_data = {
            "message": {"content": "", "tool_calls": tool_calls_raw},
            "eval_count": 0,
        }
        fake_resp = _FakeResponse(status=200, json_data=response_data)
        fake_session = _FakeSession(fake_resp)

        with patch.object(backend, "_get_session", return_value=fake_session):
            result = await backend.generate("calc 1+1", "test-model")

        assert result.success
        assert result.tool_calls is not None
        assert result.tool_calls[0]["tool"] == "calc"


# ---------------------------------------------------------------------------
# OllamaBackend: generate_stream
# ---------------------------------------------------------------------------

class TestOllamaGenerateStream:
    @pytest.mark.asyncio
    async def test_successful_stream(self):
        backend = OllamaBackend()
        lines = [
            json.dumps({"message": {"content": "Hello"}}).encode(),
            json.dumps({"message": {"content": " world"}}).encode(),
        ]
        fake_resp = _FakeResponse(status=200, lines=lines)
        fake_session = _FakeSession(fake_resp)

        with patch.object(backend, "_get_session", return_value=fake_session):
            tokens = []
            async for token in backend.generate_stream("hi", "test-model"):
                tokens.append(token)

        assert tokens == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_stream_skips_invalid_json(self):
        backend = OllamaBackend()
        lines = [
            b"not valid json",
            json.dumps({"message": {"content": "ok"}}).encode(),
        ]
        fake_resp = _FakeResponse(status=200, lines=lines)
        fake_session = _FakeSession(fake_resp)

        with patch.object(backend, "_get_session", return_value=fake_session):
            tokens = []
            async for token in backend.generate_stream("hi", "test-model"):
                tokens.append(token)

        assert tokens == ["ok"]

    @pytest.mark.asyncio
    async def test_stream_exception_yields_nothing(self):
        backend = OllamaBackend()
        with patch.object(backend, "_get_session", side_effect=ConnectionError("fail")):
            tokens = []
            async for token in backend.generate_stream("hi", "test-model"):
                tokens.append(token)
        assert tokens == []


# ---------------------------------------------------------------------------
# OllamaBackend: is_available, list_models
# ---------------------------------------------------------------------------

class TestOllamaAvailability:
    @pytest.mark.asyncio
    async def test_is_available_true(self):
        backend = OllamaBackend()
        fake_resp = _FakeResponse(status=200)
        fake_session = _FakeSession(fake_resp)
        with patch.object(backend, "_get_session", return_value=fake_session):
            assert await backend.is_available()

    @pytest.mark.asyncio
    async def test_is_available_false_on_error(self):
        backend = OllamaBackend()
        with patch.object(backend, "_get_session", side_effect=ConnectionError):
            assert not await backend.is_available()

    @pytest.mark.asyncio
    async def test_list_models_success(self):
        backend = OllamaBackend()
        data = {"models": [{"name": "m1"}, {"name": "m2"}]}
        fake_resp = _FakeResponse(status=200, json_data=data)
        fake_session = _FakeSession(fake_resp)
        with patch.object(backend, "_get_session", return_value=fake_session):
            models = await backend.list_models()
        assert models == ["m1", "m2"]

    @pytest.mark.asyncio
    async def test_list_models_empty_on_error(self):
        backend = OllamaBackend()
        with patch.object(backend, "_get_session", side_effect=ConnectionError):
            models = await backend.list_models()
        assert models == []

    @pytest.mark.asyncio
    async def test_list_models_empty_on_non_200(self):
        backend = OllamaBackend()
        fake_resp = _FakeResponse(status=500)
        fake_session = _FakeSession(fake_resp)
        with patch.object(backend, "_get_session", return_value=fake_session):
            models = await backend.list_models()
        assert models == []


# ---------------------------------------------------------------------------
# LMStudioBackend: generate
# ---------------------------------------------------------------------------

class TestLMStudioGenerate:
    @pytest.mark.asyncio
    async def test_successful_generation(self):
        backend = LMStudioBackend()
        data = {
            "choices": [{"message": {"content": "Hi there!"}}],
            "usage": {"completion_tokens": 5},
        }
        fake_resp = _FakeResponse(status=200, json_data=data)
        fake_session = _FakeSession(fake_resp)

        with patch.object(backend, "_get_session", return_value=fake_session):
            result = await backend.generate("hello", "lm-model")

        assert result.success
        assert result.text == "Hi there!"
        assert result.tokens_generated == 5

    @pytest.mark.asyncio
    async def test_http_error(self):
        backend = LMStudioBackend()
        fake_resp = _FakeResponse(status=503, text_data="Overloaded")
        fake_session = _FakeSession(fake_resp)

        with patch.object(backend, "_get_session", return_value=fake_session):
            result = await backend.generate("hello", "lm-model")

        assert not result.success
        assert "503" in result.error

    @pytest.mark.asyncio
    async def test_exception_during_generate(self):
        backend = LMStudioBackend()
        with patch.object(backend, "_get_session", side_effect=TimeoutError("timeout")):
            result = await backend.generate("hello", "lm-model")
        assert not result.success
        assert "timeout" in result.error


# ---------------------------------------------------------------------------
# LMStudioBackend: generate_stream
# ---------------------------------------------------------------------------

class TestLMStudioGenerateStream:
    @pytest.mark.asyncio
    async def test_successful_stream(self):
        backend = LMStudioBackend()
        lines = [
            b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n',
            b'data: {"choices": [{"delta": {"content": " world"}}]}\n',
            b'data: [DONE]\n',
        ]
        fake_resp = _FakeResponse(status=200, lines=lines)
        fake_session = _FakeSession(fake_resp)

        with patch.object(backend, "_get_session", return_value=fake_session):
            tokens = []
            async for token in backend.generate_stream("hi", "lm-model"):
                tokens.append(token)

        assert tokens == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_stream_exception_yields_nothing(self):
        backend = LMStudioBackend()
        with patch.object(backend, "_get_session", side_effect=ConnectionError("fail")):
            tokens = []
            async for token in backend.generate_stream("hi", "lm-model"):
                tokens.append(token)
        assert tokens == []


# ---------------------------------------------------------------------------
# LMStudioBackend: is_available, list_models
# ---------------------------------------------------------------------------

class TestLMStudioAvailability:
    @pytest.mark.asyncio
    async def test_is_available_true(self):
        backend = LMStudioBackend()
        fake_resp = _FakeResponse(status=200)
        fake_session = _FakeSession(fake_resp)
        with patch.object(backend, "_get_session", return_value=fake_session):
            assert await backend.is_available()

    @pytest.mark.asyncio
    async def test_is_available_false_on_error(self):
        backend = LMStudioBackend()
        with patch.object(backend, "_get_session", side_effect=ConnectionError):
            assert not await backend.is_available()

    @pytest.mark.asyncio
    async def test_list_models_success(self):
        backend = LMStudioBackend()
        data = {"data": [{"id": "model-a"}, {"id": "model-b"}]}
        fake_resp = _FakeResponse(status=200, json_data=data)
        fake_session = _FakeSession(fake_resp)
        with patch.object(backend, "_get_session", return_value=fake_session):
            models = await backend.list_models()
        assert models == ["model-a", "model-b"]

    @pytest.mark.asyncio
    async def test_list_models_empty_on_error(self):
        backend = LMStudioBackend()
        with patch.object(backend, "_get_session", side_effect=ConnectionError):
            models = await backend.list_models()
        assert models == []


# ---------------------------------------------------------------------------
# MLXBackend: generate, is_available, list_models, generate_stream
# ---------------------------------------------------------------------------

class TestMLXBackendGenerate:
    @pytest.mark.asyncio
    async def test_generate_when_mlx_unavailable(self):
        backend = MLXBackend()
        backend._available = False
        result = await backend.generate("hello", "some-model")
        assert not result.success
        assert "not available" in result.error.lower()

    @pytest.mark.asyncio
    async def test_generate_loads_model_on_first_call(self):
        backend = MLXBackend()
        # Simulate ImportError for mlx_lm
        with patch.object(backend, "_load_model", new_callable=AsyncMock) as mock_load:
            # After _load_model is called, _available will still be None (not set by mock)
            # So we need to set it to False to trigger the "not available" path
            async def set_unavailable(model_name):
                backend._available = False
            mock_load.side_effect = set_unavailable

            result = await backend.generate("hello", "test-model")
            mock_load.assert_called_once_with("test-model")
            assert not result.success

    @pytest.mark.asyncio
    async def test_generate_exception_returns_failure(self):
        backend = MLXBackend()
        backend._available = True
        backend._model = MagicMock()
        # The import of mlx_lm.generate will fail
        with patch.dict("sys.modules", {"mlx_lm": None}):
            result = await backend.generate("hello", "test-model")
        assert not result.success


class TestMLXBackendAvailability:
    @pytest.mark.asyncio
    async def test_is_available_cached_true(self):
        backend = MLXBackend()
        backend._available = True
        assert await backend.is_available()

    @pytest.mark.asyncio
    async def test_is_available_cached_false(self):
        backend = MLXBackend()
        backend._available = False
        assert not await backend.is_available()

    @pytest.mark.asyncio
    async def test_is_available_import_check(self):
        backend = MLXBackend()
        # _available is None initially; the import check will likely fail
        # in CI, so we expect False
        result = await backend.is_available()
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_list_models_returns_hardcoded(self):
        backend = MLXBackend()
        models = await backend.list_models()
        assert isinstance(models, list)
        assert len(models) >= 1


class TestMLXBackendStream:
    @pytest.mark.asyncio
    async def test_stream_yields_chunks_on_success(self):
        backend = MLXBackend()
        fake_result = GenerationResult(
            text="A" * 120,  # 120 chars -> should yield 3 chunks (50+50+20)
            tokens_generated=10,
            time_ms=100.0,
            model_id="test",
            success=True,
        )
        with patch.object(backend, "generate", new_callable=AsyncMock, return_value=fake_result):
            chunks = []
            async for chunk in backend.generate_stream("hi", "test-model"):
                chunks.append(chunk)
        assert len(chunks) == 3
        assert "".join(chunks) == "A" * 120

    @pytest.mark.asyncio
    async def test_stream_yields_nothing_on_failure(self):
        backend = MLXBackend()
        fake_result = GenerationResult(
            text="", tokens_generated=0, time_ms=50.0,
            model_id="test", success=False, error="mlx error",
        )
        with patch.object(backend, "generate", new_callable=AsyncMock, return_value=fake_result):
            chunks = []
            async for chunk in backend.generate_stream("hi", "test-model"):
                chunks.append(chunk)
        assert chunks == []


# ---------------------------------------------------------------------------
# BaseHTTPBackend: _get_session, close
# ---------------------------------------------------------------------------

class TestBaseHTTPBackendSession:
    @pytest.mark.asyncio
    async def test_get_session_creates_session(self):
        backend = OllamaBackend()
        with patch("portal.routing.model_backends.aiohttp.ClientSession") as MockSession:
            mock_instance = MagicMock()
            mock_instance.closed = False
            MockSession.return_value = mock_instance
            session = await backend._get_session()
            assert session is mock_instance
            MockSession.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_reuses_existing(self):
        backend = OllamaBackend()
        mock_session = MagicMock()
        mock_session.closed = False
        backend._session = mock_session
        session = await backend._get_session()
        assert session is mock_session

    @pytest.mark.asyncio
    async def test_get_session_recreates_if_closed(self):
        backend = OllamaBackend()
        old_session = MagicMock()
        old_session.closed = True
        backend._session = old_session
        with patch("portal.routing.model_backends.aiohttp.ClientSession") as MockSession:
            new_session = MagicMock()
            new_session.closed = False
            MockSession.return_value = new_session
            session = await backend._get_session()
            assert session is new_session

    @pytest.mark.asyncio
    async def test_close_closes_session(self):
        backend = OllamaBackend()
        mock_session = AsyncMock()
        mock_session.closed = False
        backend._session = mock_session
        await backend.close()
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_session(self):
        backend = OllamaBackend()
        backend._session = None
        await backend.close()  # should not raise

    @pytest.mark.asyncio
    async def test_close_noop_when_already_closed(self):
        backend = OllamaBackend()
        mock_session = MagicMock()
        mock_session.closed = True
        backend._session = mock_session
        await backend.close()  # should not raise or call close


# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------

class TestURLConstruction:
    def test_ollama_strips_trailing_slash(self):
        backend = OllamaBackend(base_url="http://host:11434/")
        assert backend.base_url == "http://host:11434"

    def test_lmstudio_strips_trailing_slash(self):
        backend = LMStudioBackend(base_url="http://host:1234/v1/")
        assert backend.base_url == "http://host:1234/v1"
