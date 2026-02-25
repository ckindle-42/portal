"""
Model Backends - Adapters for Ollama, LM Studio, and MLX
"""

import asyncio
import aiohttp
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, AsyncGenerator
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result from model generation"""
    text: str
    tokens_generated: int
    time_ms: float
    model_id: str
    success: bool
    error: Optional[str] = None


class ModelBackend(ABC):
    """Abstract base class for model backends"""
    
    @abstractmethod
    async def generate(self, prompt: str, model_name: str, 
                      system_prompt: Optional[str] = None,
                      max_tokens: int = 2048,
                      temperature: float = 0.7) -> GenerationResult:
        """Generate text from model"""
        pass
    
    @abstractmethod
    async def generate_stream(self, prompt: str, model_name: str,
                             system_prompt: Optional[str] = None,
                             max_tokens: int = 2048,
                             temperature: float = 0.7) -> AsyncGenerator[str, None]:
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


class OllamaBackend(ModelBackend):
    """Ollama backend adapter"""
    
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip('/')
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120)
            )
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def generate(self, prompt: str, model_name: str,
                      system_prompt: Optional[str] = None,
                      max_tokens: int = 2048,
                      temperature: float = 0.7) -> GenerationResult:
        """Generate text using Ollama API"""
        import time
        start_time = time.time()
        
        try:
            session = await self._get_session()
            
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature
                }
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    elapsed = (time.time() - start_time) * 1000
                    
                    return GenerationResult(
                        text=data.get("response", ""),
                        tokens_generated=data.get("eval_count", 0),
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
            logger.error(f"Ollama generation error: {e}")
            return GenerationResult(
                text="",
                tokens_generated=0,
                time_ms=(time.time() - start_time) * 1000,
                model_id=model_name,
                success=False,
                error=str(e)
            )
    
    async def generate_stream(self, prompt: str, model_name: str,
                             system_prompt: Optional[str] = None,
                             max_tokens: int = 2048,
                             temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """Stream generation from Ollama"""
        try:
            session = await self._get_session()
            
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": temperature
                }
            }
            
            if system_prompt:
                payload["system"] = system_prompt
            
            async with session.post(
                f"{self.base_url}/api/generate",
                json=payload
            ) as response:
                async for line in response.content:
                    if line:
                        try:
                            import json
                            data = json.loads(line.decode('utf-8'))
                            if "response" in data:
                                yield data["response"]
                        except json.JSONDecodeError:
                            continue
        
        except Exception as e:
            logger.error(f"Ollama stream error: {e}")
            yield f"[Error: {str(e)}]"
    
    async def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/api/tags") as response:
                return response.status == 200
        except:
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


class LMStudioBackend(ModelBackend):
    """LM Studio backend adapter (OpenAI-compatible API)"""
    
    def __init__(self, base_url: str = "http://localhost:1234/v1"):
        self.base_url = base_url.rstrip('/')
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120)
            )
        return self._session
    
    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def generate(self, prompt: str, model_name: str,
                      system_prompt: Optional[str] = None,
                      max_tokens: int = 2048,
                      temperature: float = 0.7) -> GenerationResult:
        """Generate using OpenAI-compatible API"""
        import time
        start_time = time.time()
        
        try:
            session = await self._get_session()
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": model_name,
                "messages": messages,
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
                             system_prompt: Optional[str] = None,
                             max_tokens: int = 2048,
                             temperature: float = 0.7) -> AsyncGenerator[str, None]:
        """Stream generation from LM Studio"""
        try:
            session = await self._get_session()
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": model_name,
                "messages": messages,
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
                            import json
                            data = json.loads(line[6:])
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except:
                            continue
        
        except Exception as e:
            logger.error(f"LM Studio stream error: {e}")
            yield f"[Error: {str(e)}]"
    
    async def is_available(self) -> bool:
        """Check if LM Studio is available"""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/models") as response:
                return response.status == 200
        except:
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
    
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self._model = None
        self._tokenizer = None
        self._available = None
    
    async def _load_model(self, model_path: str):
        """Load MLX model"""
        try:
            from mlx_lm import load, generate
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
                      system_prompt: Optional[str] = None,
                      max_tokens: int = 2048,
                      temperature: float = 0.7) -> GenerationResult:
        """Generate using MLX"""
        import time
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
            loop = asyncio.get_event_loop()
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
                             system_prompt: Optional[str] = None,
                             max_tokens: int = 2048,
                             temperature: float = 0.7) -> AsyncGenerator[str, None]:
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
            yield f"[Error: {result.error}]"
    
    async def is_available(self) -> bool:
        """Check if MLX is available"""
        if self._available is not None:
            return self._available
        
        try:
            import mlx_lm
            self._available = True
        except ImportError:
            self._available = False
        
        return self._available
    
    async def list_models(self) -> list:
        """List available MLX models"""
        # MLX models are loaded from HuggingFace paths
        return ["mlx-community/Qwen2.5-7B-Instruct-4bit"]
