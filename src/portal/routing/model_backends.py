"""
Model Backends - Adapters for Ollama, LM Studio, and MLX
"""

import asyncio
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

    @abstractmethod
    async def generate(self, prompt: str, model_name: str,
                      system_prompt: str | None = None,
                      max_tokens: int = 2048,
                      temperature: float = 0.7,
                      messages: list[dict[str, Any]] | None = None) -> GenerationResult:
        """Generate text from model"""
        pass

    @abstractmethod
    async def generate_stream(self, prompt: str, model_name: str,
                             system_prompt: str | None = None,
                             max_tokens: int = 2048,
                             temperature: float = 0.7,
                             messages: list[dict[str, Any]] | None = None) -> AsyncGenerator[str, None]:
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
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120)
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


class OllamaBackend(BaseHTTPBackend):
    """Ollama backend adapter"""

    def __init__(self, base_url: str = "http://localhost:11434"):
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

    async def generate(self, prompt: str, model_name: str,
                      system_prompt: str | None = None,
                      max_tokens: int = 2048,
                      temperature: float = 0.7,
                      messages: list[dict[str, Any]] | None = None) -> GenerationResult:
        """Generate text using Ollama /api/chat (supports tool calls)."""
        start_time = time.time()

        try:
            session = await self._get_session()

            if messages is not None:
                chat_messages: list[dict[str, Any]] = list(messages)
                if system_prompt and (not chat_messages or chat_messages[0].get("role") != "system"):
                    chat_messages.insert(0, {"role": "system", "content": system_prompt})
            else:
                chat_messages = []
                if system_prompt:
                    chat_messages.append({"role": "system", "content": system_prompt})
                chat_messages.append({"role": "user", "content": prompt})

            payload = {
                "model": model_name,
                "messages": chat_messages,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            }

            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    elapsed = (time.time() - start_time) * 1000
                    msg = data.get("message", {})
                    tool_calls = self._normalize_tool_calls(msg.get("tool_calls"))
                    return GenerationResult(
                        text=msg.get("content", ""),
                        tokens_generated=data.get("eval_count", 0),
                        time_ms=elapsed,
                        model_id=model_name,
                        success=True,
                        tool_calls=tool_calls,
                    )
                else:
                    error_text = await response.text()
                    return GenerationResult(
                        text="",
                        tokens_generated=0,
                        time_ms=(time.time() - start_time) * 1000,
                        model_id=model_name,
                        success=False,
                        error=f"HTTP {response.status}: {error_text}",
                    )

        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            return GenerationResult(
                text="",
                tokens_generated=0,
                time_ms=(time.time() - start_time) * 1000,
                model_id=model_name,
                success=False,
                error=str(e),
            )

    async def generate_stream(self, prompt: str, model_name: str,
                             system_prompt: str | None = None,
                             max_tokens: int = 2048,
                             temperature: float = 0.7,
                             messages: list[dict[str, Any]] | None = None) -> AsyncGenerator[str, None]:
        """Stream generation from Ollama /api/chat."""
        try:
            session = await self._get_session()

            if messages is not None:
                chat_messages: list[dict[str, Any]] = list(messages)
                if system_prompt and (not chat_messages or chat_messages[0].get("role") != "system"):
                    chat_messages.insert(0, {"role": "system", "content": system_prompt})
            else:
                chat_messages = []
                if system_prompt:
                    chat_messages.append({"role": "system", "content": system_prompt})
                chat_messages.append({"role": "user", "content": prompt})

            payload = {
                "model": model_name,
                "messages": chat_messages,
                "stream": True,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature,
                },
            }

            async with session.post(
                f"{self.base_url}/api/chat",
                json=payload,
            ) as response:
                async for line in response.content:
                    if line:
                        try:
                            data = json.loads(line.decode("utf-8"))
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Ollama stream error: {e}")
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
            logger.error(f"Failed to list Ollama models: {e}")
        return []


class LMStudioBackend(BaseHTTPBackend):
    """LM Studio backend adapter (OpenAI-compatible API)"""

    def __init__(self, base_url: str = "http://localhost:1234/v1"):
        super().__init__(base_url)

    async def generate(self, prompt: str, model_name: str,
                      system_prompt: str | None = None,
                      max_tokens: int = 2048,
                      temperature: float = 0.7,
                      messages: list[dict[str, Any]] | None = None) -> GenerationResult:
        """Generate using OpenAI-compatible API"""
        start_time = time.time()

        try:
            session = await self._get_session()

            if messages is not None:
                chat_messages: list[dict[str, Any]] = list(messages)
                if system_prompt and (not chat_messages or chat_messages[0].get("role") != "system"):
                    chat_messages.insert(0, {"role": "system", "content": system_prompt})
            else:
                chat_messages = []
                if system_prompt:
                    chat_messages.append({"role": "system", "content": system_prompt})
                chat_messages.append({"role": "user", "content": prompt})

            payload = {
                "model": model_name,
                "messages": chat_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False
            }

            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    elapsed = (time.time() - start_time) * 1000

                    content = data["choices"][0]["message"]["content"]
                    tokens = data.get("usage", {}).get("completion_tokens", 0)

                    return GenerationResult(
                        text=content,
                        tokens_generated=tokens,
                        time_ms=elapsed,
                        model_id=model_name,
                        success=True
                    )
                else:
                    error_text = await response.text()
                    return GenerationResult(
                        text="",
                        tokens_generated=0,
                        time_ms=(time.time() - start_time) * 1000,
                        model_id=model_name,
                        success=False,
                        error=f"HTTP {response.status}: {error_text}"
                    )

        except Exception as e:
            logger.error(f"LM Studio generation error: {e}")
            return GenerationResult(
                text="",
                tokens_generated=0,
                time_ms=(time.time() - start_time) * 1000,
                model_id=model_name,
                success=False,
                error=str(e)
            )

    async def generate_stream(self, prompt: str, model_name: str,
                             system_prompt: str | None = None,
                             max_tokens: int = 2048,
                             temperature: float = 0.7,
                             messages: list[dict[str, Any]] | None = None) -> AsyncGenerator[str, None]:
        """Stream generation from LM Studio"""
        try:
            session = await self._get_session()

            if messages is not None:
                chat_messages: list[dict[str, Any]] = list(messages)
                if system_prompt and (not chat_messages or chat_messages[0].get("role") != "system"):
                    chat_messages.insert(0, {"role": "system", "content": system_prompt})
            else:
                chat_messages = []
                if system_prompt:
                    chat_messages.append({"role": "system", "content": system_prompt})
                chat_messages.append({"role": "user", "content": prompt})

            payload = {
                "model": model_name,
                "messages": chat_messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True
            }

            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload
            ) as response:
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: ') and line != 'data: [DONE]':
                        try:
                            data = json.loads(line[6:])
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except Exception:
                            continue

        except Exception as e:
            logger.error(f"LM Studio stream error: {e}")
            return

    async def is_available(self) -> bool:
        """Check if LM Studio is available"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/models") as response:
                return response.status == 200
        except Exception:
            return False

    async def list_models(self) -> list:
        """List available LM Studio models"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/models") as response:
                if response.status == 200:
                    data = await response.json()
                    return [m["id"] for m in data.get("data", [])]
        except Exception as e:
            logger.error(f"Failed to list LM Studio models: {e}")
        return []


class MLXBackend(ModelBackend):
    """MLX backend adapter for Apple Silicon"""

    def __init__(self, model_path: str | None = None):
        self.model_path = model_path
        self._model = None
        self._tokenizer = None
        self._available = None

    async def _load_model(self, model_path: str):
        """Load MLX model"""
        try:
            from mlx_lm import load
            self._model, self._tokenizer = load(model_path)
            self._available = True
            logger.info(f"Loaded MLX model: {model_path}")
        except ImportError:
            logger.warning("MLX not available (not on Apple Silicon?)")
            self._available = False
        except Exception as e:
            logger.error(f"Failed to load MLX model: {e}")
            self._available = False

    async def generate(self, prompt: str, model_name: str,
                      system_prompt: str | None = None,
                      max_tokens: int = 2048,
                      temperature: float = 0.7,
                      messages: list[dict[str, Any]] | None = None) -> GenerationResult:
        """Generate using MLX"""
        start_time = time.time()

        try:
            if self._model is None:
                await self._load_model(model_name)

            if not self._available:
                return GenerationResult(
                    text="",
                    tokens_generated=0,
                    time_ms=0,
                    model_id=model_name,
                    success=False,
                    error="MLX not available"
                )

            from mlx_lm import generate

            # Format prompt with system prompt if provided
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"System: {system_prompt}\n\nUser: {prompt}\n\nAssistant:"

            # Run generation in thread pool (MLX is CPU/GPU bound)
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(
                None,
                lambda: generate(
                    self._model,
                    self._tokenizer,
                    prompt=full_prompt,
                    max_tokens=max_tokens,
                    temp=temperature
                )
            )

            elapsed = (time.time() - start_time) * 1000

            return GenerationResult(
                text=response,
                tokens_generated=len(self._tokenizer.encode(response)),
                time_ms=elapsed,
                model_id=model_name,
                success=True
            )

        except Exception as e:
            logger.error(f"MLX generation error: {e}")
            return GenerationResult(
                text="",
                tokens_generated=0,
                time_ms=(time.time() - start_time) * 1000,
                model_id=model_name,
                success=False,
                error=str(e)
            )

    async def generate_stream(self, prompt: str, model_name: str,
                             system_prompt: str | None = None,
                             max_tokens: int = 2048,
                             temperature: float = 0.7,
                             messages: list[dict[str, Any]] | None = None) -> AsyncGenerator[str, None]:
        """Stream generation from MLX"""
        # MLX doesn't have native streaming, so we generate and yield
        result = await self.generate(prompt, model_name, system_prompt, max_tokens, temperature)
        if result.success:
            # Yield in chunks
            chunk_size = 50
            for i in range(0, len(result.text), chunk_size):
                yield result.text[i:i+chunk_size]
                await asyncio.sleep(0.01)  # Small delay for effect
        else:
            logger.error(f"MLX stream error: {result.error}")
            return

    async def is_available(self) -> bool:
        """Check if MLX is available"""
        if self._available is not None:
            return self._available

        try:
            import mlx_lm  # noqa: F401
            self._available = True
        except ImportError:
            self._available = False

        return self._available

    async def list_models(self) -> list:
        """List available MLX models"""
        # MLX models are loaded from HuggingFace paths
        return ["mlx-community/Qwen2.5-7B-Instruct-4bit"]
