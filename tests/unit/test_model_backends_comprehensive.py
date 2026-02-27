"""Tests for portal.routing.model_backends."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from portal.routing.model_backends import (
    BaseHTTPBackend,
    GenerationResult,
    LMStudioBackend,
    MLXBackend,
    OllamaBackend,
)


class _FakeResponse:
    def __init__(self, status=200, json_data=None, text_data="", lines=None):
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
    def __init__(self, lines):
        self._lines = lines

    def __aiter__(self):
        return _FakeContentIter(self._lines)


class _FakeContentIter:
    def __init__(self, lines):
        self._iter = iter(lines)

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class _FakeSession:
    def __init__(self, response=None):
        self._response = response or _FakeResponse()
        self.closed = False

    def post(self, url, **kwargs):
        return self._response

    def get(self, url, **kwargs):
        return self._response

    async def close(self):
        self.closed = True


class TestGenerationResult:
    def test_defaults(self):
        r = GenerationResult(text="hi", tokens_generated=5, time_ms=100.0, model_id="m", success=True)
        assert r.error is None and r.tool_calls is None

    def test_failure_with_error(self):
        r = GenerationResult(text="", tokens_generated=0, time_ms=50.0, model_id="m",
                             success=False, error="timeout")
        assert not r.success and r.error == "timeout"

    def test_with_tool_calls(self):
        calls = [{"tool": "clock", "arguments": {}}]
        r = GenerationResult(text="", tokens_generated=0, time_ms=10.0, model_id="m",
                             success=True, tool_calls=calls)
        assert r.tool_calls == calls


class TestBuildChatMessages:
    @pytest.mark.parametrize("prompt,system,messages,expected_start,expected_len", [
        ("hello", None, None, [{"role": "user", "content": "hello"}], 1),
        ("hello", "Be helpful", None, {"role": "system", "content": "Be helpful"}, 2),
        ("ignored", None, [{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"}],
         [{"role": "user", "content": "q1"}, {"role": "assistant", "content": "a1"}], 2),
    ])
    def test_build_messages(self, prompt, system, messages, expected_start, expected_len):
        result = BaseHTTPBackend._build_chat_messages(prompt, system, messages)
        assert len(result) == expected_len
        if isinstance(expected_start, list):
            assert result == expected_start
        else:
            assert result[0] == expected_start

    def test_system_not_duplicated(self):
        history = [{"role": "system", "content": "existing"}, {"role": "user", "content": "q1"}]
        result = BaseHTTPBackend._build_chat_messages("ignored", "new sys", history)
        assert result[0] == {"role": "system", "content": "existing"} and len(result) == 2


class TestNormalizeToolCalls:
    @pytest.mark.parametrize("raw,expected_tool", [
        ([{"function": {"name": "f1", "arguments": {"a": 1}}}], "f1"),
        ([{"function": {"name": "f1", "arguments": {}}, "server": "s1"}], "f1"),
        ([{"tool": "t1", "arguments": {}}], "t1"),
        ([{"function": {"arguments": {}}, "name": "fallback"}], "fallback"),
    ])
    def test_normalize_variants(self, raw, expected_tool):
        result = OllamaBackend._normalize_tool_calls(raw)
        assert result[0]["tool"] == expected_tool

    @pytest.mark.parametrize("raw", ["bad", 42, None, [], [1, 2, "three"]])
    def test_invalid_returns_none(self, raw):
        assert OllamaBackend._normalize_tool_calls(raw) is None

    def test_non_dict_entries_skipped(self):
        raw = ["not_a_dict", {"tool": "t1", "arguments": {}}]
        result = OllamaBackend._normalize_tool_calls(raw)
        assert len(result) == 1 and result[0]["tool"] == "t1"


class TestOllamaGenerate:
    @pytest.mark.asyncio
    async def test_successful_generation(self):
        backend = OllamaBackend()
        fake_resp = _FakeResponse(200, {"message": {"content": "Hello!", "tool_calls": None}, "eval_count": 10})
        with patch.object(backend, "_get_session", return_value=_FakeSession(fake_resp)):
            result = await backend.generate("hi", "test-model")
        assert result.success and result.text == "Hello!" and result.tokens_generated == 10

    @pytest.mark.asyncio
    async def test_http_error(self):
        backend = OllamaBackend()
        fake_resp = _FakeResponse(500, text_data="Error")
        with patch.object(backend, "_get_session", return_value=_FakeSession(fake_resp)):
            result = await backend.generate("hi", "test-model")
        assert not result.success and "500" in result.error

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self):
        backend = OllamaBackend()
        with patch.object(backend, "_get_session", side_effect=ConnectionError("refused")):
            result = await backend.generate("hi", "test-model")
        assert not result.success and "refused" in result.error

    @pytest.mark.asyncio
    async def test_tool_calls_normalized(self):
        backend = OllamaBackend()
        tool_calls_raw = [{"function": {"name": "calc", "arguments": {"x": 1}}}]
        fake_resp = _FakeResponse(200, {"message": {"content": "", "tool_calls": tool_calls_raw}, "eval_count": 0})
        with patch.object(backend, "_get_session", return_value=_FakeSession(fake_resp)):
            result = await backend.generate("calc 1+1", "test-model")
        assert result.success and result.tool_calls[0]["tool"] == "calc"


class TestOllamaStream:
    @pytest.mark.asyncio
    async def test_successful_stream(self):
        backend = OllamaBackend()
        lines = [json.dumps({"message": {"content": t}}).encode() for t in ["Hello", " world"]]
        with patch.object(backend, "_get_session", return_value=_FakeSession(_FakeResponse(200, lines=lines))):
            tokens = [t async for t in backend.generate_stream("hi", "test-model")]
        assert tokens == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_invalid_json_skipped(self):
        backend = OllamaBackend()
        lines = [b"bad json", json.dumps({"message": {"content": "ok"}}).encode()]
        with patch.object(backend, "_get_session", return_value=_FakeSession(_FakeResponse(200, lines=lines))):
            tokens = [t async for t in backend.generate_stream("hi", "test-model")]
        assert tokens == ["ok"]

    @pytest.mark.asyncio
    async def test_exception_yields_nothing(self):
        backend = OllamaBackend()
        with patch.object(backend, "_get_session", side_effect=ConnectionError):
            tokens = [t async for t in backend.generate_stream("hi", "test-model")]
        assert tokens == []


class TestOllamaAvailability:
    @pytest.mark.asyncio
    async def test_available_on_200(self):
        backend = OllamaBackend()
        with patch.object(backend, "_get_session", return_value=_FakeSession(_FakeResponse(200))):
            assert await backend.is_available()

    @pytest.mark.asyncio
    async def test_unavailable_on_error(self):
        backend = OllamaBackend()
        with patch.object(backend, "_get_session", side_effect=ConnectionError):
            assert not await backend.is_available()

    @pytest.mark.asyncio
    async def test_list_models(self):
        backend = OllamaBackend()
        fake_resp = _FakeResponse(200, {"models": [{"name": "m1"}, {"name": "m2"}]})
        with patch.object(backend, "_get_session", return_value=_FakeSession(fake_resp)):
            models = await backend.list_models()
        assert models == ["m1", "m2"]

    @pytest.mark.asyncio
    async def test_list_models_empty_on_error(self):
        backend = OllamaBackend()
        with patch.object(backend, "_get_session", side_effect=ConnectionError):
            assert await backend.list_models() == []


class TestLMStudioGenerate:
    @pytest.mark.asyncio
    async def test_successful_generation(self):
        backend = LMStudioBackend()
        data = {"choices": [{"message": {"content": "Hi!"}}], "usage": {"completion_tokens": 5}}
        with patch.object(backend, "_get_session", return_value=_FakeSession(_FakeResponse(200, data))):
            result = await backend.generate("hello", "lm-model")
        assert result.success and result.text == "Hi!" and result.tokens_generated == 5

    @pytest.mark.asyncio
    async def test_http_error(self):
        backend = LMStudioBackend()
        with patch.object(backend, "_get_session", return_value=_FakeSession(_FakeResponse(503, text_data="OL"))):
            result = await backend.generate("hello", "lm-model")
        assert not result.success and "503" in result.error

    @pytest.mark.asyncio
    async def test_exception_returns_failure(self):
        backend = LMStudioBackend()
        with patch.object(backend, "_get_session", side_effect=TimeoutError("timeout")):
            result = await backend.generate("hello", "lm-model")
        assert not result.success and "timeout" in result.error


class TestLMStudioStream:
    @pytest.mark.asyncio
    async def test_successful_stream(self):
        backend = LMStudioBackend()
        lines = [
            b'data: {"choices": [{"delta": {"content": "Hello"}}]}\n',
            b'data: {"choices": [{"delta": {"content": " world"}}]}\n',
            b'data: [DONE]\n',
        ]
        with patch.object(backend, "_get_session", return_value=_FakeSession(_FakeResponse(200, lines=lines))):
            tokens = [t async for t in backend.generate_stream("hi", "lm-model")]
        assert tokens == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_exception_yields_nothing(self):
        backend = LMStudioBackend()
        with patch.object(backend, "_get_session", side_effect=ConnectionError):
            assert [t async for t in backend.generate_stream("hi", "lm-model")] == []


class TestLMStudioAvailability:
    @pytest.mark.asyncio
    async def test_available_and_list_models(self):
        backend = LMStudioBackend()
        data = {"data": [{"id": "model-a"}, {"id": "model-b"}]}
        with patch.object(backend, "_get_session", return_value=_FakeSession(_FakeResponse(200, data))):
            assert await backend.is_available()
            models = await backend.list_models()
        assert models == ["model-a", "model-b"]

    @pytest.mark.asyncio
    async def test_unavailable_and_empty_on_error(self):
        backend = LMStudioBackend()
        with patch.object(backend, "_get_session", side_effect=ConnectionError):
            assert not await backend.is_available()
            assert await backend.list_models() == []


class TestMLXBackend:
    @pytest.mark.asyncio
    async def test_generate_when_unavailable(self):
        backend = MLXBackend()
        backend._available = False
        result = await backend.generate("hello", "some-model")
        assert not result.success and "not available" in result.error.lower()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cached", [True, False])
    async def test_is_available_cached(self, cached):
        backend = MLXBackend()
        backend._available = cached
        assert await backend.is_available() == cached

    @pytest.mark.asyncio
    async def test_list_models_returns_list(self):
        backend = MLXBackend()
        models = await backend.list_models()
        assert isinstance(models, list) and len(models) >= 1

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        backend = MLXBackend()
        fake = GenerationResult(text="A" * 120, tokens_generated=10, time_ms=100.0,
                                model_id="test", success=True)
        with patch.object(backend, "generate", new_callable=AsyncMock, return_value=fake):
            chunks = [c async for c in backend.generate_stream("hi", "test-model")]
        assert len(chunks) == 3 and "".join(chunks) == "A" * 120

    @pytest.mark.asyncio
    async def test_stream_yields_nothing_on_failure(self):
        backend = MLXBackend()
        fake = GenerationResult(text="", tokens_generated=0, time_ms=50.0,
                                model_id="test", success=False, error="mlx error")
        with patch.object(backend, "generate", new_callable=AsyncMock, return_value=fake):
            assert [c async for c in backend.generate_stream("hi", "test-model")] == []


class TestBaseHTTPBackendSession:
    @pytest.mark.asyncio
    async def test_creates_session(self):
        backend = OllamaBackend()
        with patch("portal.routing.model_backends.aiohttp.ClientSession") as MockSession:
            mock = MagicMock(closed=False)
            MockSession.return_value = mock
            session = await backend._get_session()
        assert session is mock and MockSession.call_count == 1

    @pytest.mark.asyncio
    async def test_reuses_existing_session(self):
        backend = OllamaBackend()
        mock = MagicMock(closed=False)
        backend._session = mock
        assert await backend._get_session() is mock

    @pytest.mark.asyncio
    async def test_recreates_closed_session(self):
        backend = OllamaBackend()
        backend._session = MagicMock(closed=True)
        with patch("portal.routing.model_backends.aiohttp.ClientSession") as MockSession:
            new = MagicMock(closed=False)
            MockSession.return_value = new
            session = await backend._get_session()
        assert session is new

    @pytest.mark.asyncio
    async def test_close_closes_open_session(self):
        backend = OllamaBackend()
        mock = AsyncMock(closed=False)
        backend._session = mock
        await backend.close()
        mock.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_noop_when_no_session(self):
        backend = OllamaBackend()
        backend._session = None
        await backend.close()  # must not raise


class TestURLConstruction:
    @pytest.mark.parametrize("backend_cls,url,expected", [
        (OllamaBackend, "http://host:11434/", "http://host:11434"),
        (LMStudioBackend, "http://host:1234/v1/", "http://host:1234/v1"),
    ])
    def test_strips_trailing_slash(self, backend_cls, url, expected):
        assert backend_cls(base_url=url).base_url == expected
