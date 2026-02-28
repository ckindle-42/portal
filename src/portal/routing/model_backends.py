"""
Model Backends - Adapters for Ollama LLM backend
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import aiohttp

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
    ) -> GenerationResult:
        """Generate text from model"""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
        messages: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream text generation"""
        pass

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
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120))
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _post_json(self, endpoint: str, payload: dict) -> tuple[int, Any]:
        """POST JSON payload to an endpoint; return (http_status, parsed_body_or_text).

        On HTTP error returns (status, error_text_string).
        On network/parse error re-raises.
        """
        session = await self._get_session()
        async with session.post(f"{self.base_url}{endpoint}", json=payload) as response:
            if response.status == 200:
                return response.status, await response.json()
            return response.status, await response.text()

    async def _stream_content(
        self, endpoint: str, payload: dict
    ) -> AsyncGenerator[bytes, None]:
        """POST JSON payload and yield raw content bytes line-by-line."""
        session = await self._get_session()
        async with session.post(f"{self.base_url}{endpoint}", json=payload) as response:
            async for line in response.content:
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


# TODO(Track B): Migrate from aiohttp to httpx for consistency with rest of Portal.
# The rest of the codebase uses httpx; consolidating would remove a dual-dependency.
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
    ) -> AsyncGenerator[str, None]:
        """Stream generation from Ollama /api/chat."""
        try:
            payload = {
                "model": model_name,
                "messages": self._build_chat_messages(prompt, system_prompt, messages),
                "stream": True,
                "options": {"num_predict": max_tokens, "temperature": temperature},
            }
            async for line in self._stream_content("/api/chat", payload):
                try:
                    data = json.loads(line.decode("utf-8"))
                    content = data.get("message", {}).get("content", "")
                    if content:
                        yield content
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            logger.error("Ollama stream error: %s", e)
            return

    async def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/tags") as response:
                return response.status == 200
        except Exception:
            return False

    async def list_models(self) -> list:
        """List available Ollama models"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/tags") as response:
                if response.status == 200:
                    data = await response.json()
                    return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error("Failed to list Ollama models: %s", e)
        return []
