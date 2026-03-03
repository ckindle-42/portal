"""
Model Backends - Adapters for Ollama LLM backend
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result from model generation"""

    text: str
    tokens_generated: int
    time_ms: float
    model_id: str
    success: bool
    error: str | None = None
    tool_calls: list | None = None  # Parsed tool-call entries from the LLM response


class ModelBackend(ABC):
    """Abstract base class for model backends"""

    @staticmethod
    def _error_result(model_id: str, start_time: float, error: str) -> "GenerationResult":
        """Return a failed GenerationResult with elapsed time populated."""
        return GenerationResult(
            text="",
            tokens_generated=0,
            time_ms=(time.time() - start_time) * 1000,
            model_id=model_id,
            success=False,
            error=error,
        )

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> GenerationResult:
        """Generate text from model"""
        pass

    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        """Stream text generation"""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if backend is available"""
        pass

    @abstractmethod
    async def list_models(self) -> list:
        """List available models"""
        pass


class BaseHTTPBackend(ModelBackend):
    """Shared HTTP session management for HTTP-based model backends."""

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._session: httpx.AsyncClient | None = None

    async def _get_session(self) -> httpx.AsyncClient:
        if self._session is None or self._session.is_closed:
            self._session = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.is_closed:
            await self._session.aclose()

    async def _post_json(self, endpoint: str, payload: dict) -> tuple[int, Any]:
        """POST JSON payload to an endpoint; return (http_status, parsed_body_or_text).

        On HTTP error returns (status, error_text_string).
        On network/parse error re-raises.
        """
        session = await self._get_session()
        response = await session.post(f"{self.base_url}{endpoint}", json=payload)
        if response.status_code == 200:
            return response.status_code, response.json()
        return response.status_code, response.text

    async def _stream_content(self, endpoint: str, payload: dict) -> AsyncGenerator[str, None]:
        """POST JSON payload and yield NDJSON lines as strings."""
        session = await self._get_session()
        async with session.stream("POST", f"{self.base_url}{endpoint}", json=payload) as response:
            async for line in response.aiter_lines():
                if line:
                    yield line

    @staticmethod
    def _build_chat_messages(
        prompt: str,
        system_prompt: str | None,
        messages: list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        """Build a chat-messages list from prompt, system prompt, and optional history."""
        if messages is not None:
            chat_messages: list[dict[str, Any]] = list(messages)
            if system_prompt and (not chat_messages or chat_messages[0].get("role") != "system"):
                chat_messages.insert(0, {"role": "system", "content": system_prompt})
        else:
            chat_messages = []
            if system_prompt:
                chat_messages.append({"role": "system", "content": system_prompt})
            chat_messages.append({"role": "user", "content": prompt})
        return chat_messages


class OllamaBackend(BaseHTTPBackend):
    """Ollama backend adapter"""

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        super().__init__(base_url)

    @staticmethod
    def _normalize_tool_calls(raw_tool_calls: Any) -> list[dict[str, Any]] | None:
        """Normalize Ollama/OpenAI-style tool call payloads for MCP dispatch."""
        if not isinstance(raw_tool_calls, list):
            return None

        normalized_calls: list[dict[str, Any]] = []
        for call in raw_tool_calls:
            if not isinstance(call, dict):
                continue

            function_payload = call.get("function")
            if isinstance(function_payload, dict):
                normalized_call = {
                    "tool": function_payload.get("name") or call.get("name", ""),
                    "name": function_payload.get("name") or call.get("name", ""),
                    "arguments": function_payload.get("arguments", {}),
                }
                if "server" in call:
                    normalized_call["server"] = call["server"]
                normalized_calls.append(normalized_call)
                continue

            normalized_calls.append(call)

        return normalized_calls or None

    async def generate(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> GenerationResult:
        """Generate text using Ollama /api/chat (supports tool calls)."""
        start_time = time.time()
        try:
            payload = {
                "model": model_name,
                "messages": self._build_chat_messages(prompt, system_prompt, messages),
                "stream": False,
                "options": {"num_predict": max_tokens, "temperature": temperature},
            }
            if tools:
                payload["tools"] = tools
            status, data = await self._post_json("/api/chat", payload)
            if status == 200:
                msg = data.get("message", {})
                return GenerationResult(
                    text=msg.get("content", ""),
                    tokens_generated=data.get("eval_count", 0),
                    time_ms=(time.time() - start_time) * 1000,
                    model_id=model_name,
                    success=True,
                    tool_calls=self._normalize_tool_calls(msg.get("tool_calls")),
                )
            return self._error_result(model_name, start_time, f"HTTP {status}: {data}")
        except Exception as e:
            logger.error("Ollama generation error: %s", e)
            return self._error_result(model_name, start_time, str(e))

    async def generate_stream(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream generation from Ollama /api/chat."""
        try:
            payload = {
                "model": model_name,
                "messages": self._build_chat_messages(prompt, system_prompt, messages),
                "stream": True,
                "options": {"num_predict": max_tokens, "temperature": temperature},
            }
            if tools:
                payload["tools"] = tools
            async for line in self._stream_content("/api/chat", payload):
                try:
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
        except (httpx.HTTPError, json.JSONDecodeError, TimeoutError) as e:
            logger.error("Stream error from Ollama: %s", e, exc_info=True)
            raise

    async def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            session = await self._get_session()
            response = await session.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except (httpx.HTTPError, OSError):
            return False

    async def list_models(self) -> list:
        """List available Ollama models"""
        try:
            session = await self._get_session()
            response = await session.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                data = response.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error("Failed to list Ollama models: %s", e)
        return []


class MLXServerBackend(BaseHTTPBackend):
    """MLX-LM server backend adapter for Apple Silicon."""

    def __init__(self, base_url: str = "http://localhost:8800") -> None:
        super().__init__(base_url)

    async def generate(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> GenerationResult:
        """Generate text using MLX-LM server /v1/chat/completions."""
        start_time = time.time()
        try:
            payload = {
                "model": model_name,
                "messages": self._build_chat_messages(prompt, system_prompt, messages),
                "stream": False,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            status, data = await self._post_json("/v1/chat/completions", payload)
            if status == 200:
                msg = data.get("choices", [{}])[0].get("message", {})
                return GenerationResult(
                    text=msg.get("content", ""),
                    tokens_generated=data.get("usage", {}).get("completion_tokens", 0),
                    time_ms=(time.time() - start_time) * 1000,
                    model_id=model_name,
                    success=True,
                    tool_calls=None,
                )
            return self._error_result(model_name, start_time, f"HTTP {status}: {data}")
        except Exception as e:
            logger.error("MLX generation error: %s", e)
            return self._error_result(model_name, start_time, str(e))

    async def generate_stream(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        messages: list[dict[str, Any]] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream generation from MLX-LM server /v1/chat/completions."""
        try:
            payload = {
                "model": model_name,
                "messages": self._build_chat_messages(prompt, system_prompt, messages),
                "stream": True,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            async for line in self._stream_content("/v1/chat/completions", payload):
                try:
                    data = json.loads(line)
                    if data.get("choices"):
                        content = data["choices"][0].get("delta", {}).get("content", "")
                        if content:
                            yield content
                except json.JSONDecodeError:
                    continue
        except (httpx.HTTPError, json.JSONDecodeError, TimeoutError) as e:
            logger.error("Stream error from MLX: %s", e, exc_info=True)
            raise

    async def is_available(self) -> bool:
        """Check if MLX-LM server is available."""
        try:
            session = await self._get_session()
            response = await session.get(f"{self.base_url}/v1/models")
            return response.status_code == 200
        except (httpx.HTTPError, OSError):
            return False

    async def list_models(self) -> list:
        """List available MLX models."""
        try:
            session = await self._get_session()
            response = await session.get(f"{self.base_url}/v1/models")
            if response.status_code == 200:
                data = response.json()
                return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            logger.error("Failed to list MLX models: %s", e)
        return []
