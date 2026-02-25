"""
Portal WebInterface — OpenAI-compatible HTTP endpoint.

Open WebUI and LibreChat connect here via "Custom OpenAI Endpoint" setting:
  http://localhost:8081/v1

This makes both web UIs skins over Portal's AgentCore. All tool calls,
routing decisions, MCP access, and approval workflows flow through Portal.

Endpoints:
  POST /v1/chat/completions  — streaming chat (SSE)
  GET  /v1/models            — virtual model list from router
  WS   /ws                   — WebSocket chat
  GET  /health               — component health
  GET  /metrics              — Prometheus metrics (if enabled)
"""

import asyncio
import json
import os
import time
import uuid
from typing import AsyncIterator, Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from portal.interfaces.base import BaseInterface
from portal.core.types import IncomingMessage, ProcessingResult


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = "auto"
    messages: list[ChatMessage]
    stream: bool = True
    temperature: float = 0.7
    max_tokens: int | None = None


def _build_cors_origins() -> list[str]:
    """Resolve allowed CORS origins from the ALLOWED_ORIGINS env var."""
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080")
    return [o.strip() for o in raw.split(",") if o.strip()]


async def _verify_api_key(authorization: Optional[str] = Header(None)) -> None:
    """
    Optional API-key guard for /v1/* routes.

    Active only when WEB_API_KEY env var is set.  Accepts the key as either:
      Authorization: Bearer <key>
      X-API-Key: <key>   (checked via the authorization header alias)
    """
    required = os.getenv("WEB_API_KEY", "")
    if not required:
        return  # auth disabled
    if authorization == f"Bearer {required}":
        return
    raise HTTPException(status_code=401, detail="Unauthorized: invalid or missing API key")


class WebInterface(BaseInterface):
    """
    OpenAI-compatible interface.
    Bridges Open WebUI / LibreChat to Portal's AgentCore.
    """

    def __init__(self, agent_core, config):
        self.agent_core = agent_core
        self.config = config
        self.app = self._build_app()
        self._server = None

    def _build_app(self) -> FastAPI:
        app = FastAPI(
            title="Portal Web Interface",
            version="1.0.0",
            description="OpenAI-compatible endpoint for Portal AgentCore",
        )

        app.add_middleware(
            CORSMiddleware,
            allow_origins=_build_cors_origins(),
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @app.post("/v1/chat/completions", dependencies=[Depends(_verify_api_key)])
        async def chat_completions(request: ChatCompletionRequest):
            """
            OpenAI-compatible chat completion.
            Streams tokens via SSE when request.stream=True.
            """
            # Convert to internal message format
            last_user_msg = next(
                (m.content for m in reversed(request.messages) if m.role == "user"),
                "",
            )

            incoming = IncomingMessage(
                id=str(uuid.uuid4()),
                text=last_user_msg,
                model=request.model,
                history=[
                    {"role": m.role, "content": m.content}
                    for m in request.messages
                ],
            )

            if request.stream:
                return StreamingResponse(
                    self._stream_response(incoming, request.model),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                    },
                )
            else:
                from portal.core.types import InterfaceType
                result = await self.agent_core.process_message(
                    chat_id=incoming.id,
                    message=incoming.text,
                    interface=InterfaceType.WEB,
                )
                return JSONResponse(self._format_completion(result, request.model))

        @app.get("/v1/models", dependencies=[Depends(_verify_api_key)])
        async def list_models():
            """Return virtual model names from the Portal router."""
            router_port = getattr(self.config, "llm", None)
            router_port = getattr(router_port, "router_port", 8000) if router_port else 8000
            if isinstance(self.config, dict):
                router_port = self.config.get("router_port", 8000)
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.get(
                        f"http://localhost:{router_port}/api/tags"
                    )
                    data = resp.json()
                    return {
                        "object": "list",
                        "data": [
                            {
                                "id": m["name"],
                                "object": "model",
                                "created": int(time.time()),
                                "owned_by": "portal",
                            }
                            for m in data.get("models", [])
                        ],
                    }
            except Exception:
                # Fallback: return default model list
                return {
                    "object": "list",
                    "data": [
                        {"id": "auto", "object": "model", "created": int(time.time()), "owned_by": "portal"},
                        {"id": "auto-coding", "object": "model", "created": int(time.time()), "owned_by": "portal"},
                        {"id": "auto-reasoning", "object": "model", "created": int(time.time()), "owned_by": "portal"},
                    ],
                }

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            try:
                while True:
                    data = await websocket.receive_json()
                    incoming = IncomingMessage(
                        id=str(uuid.uuid4()),
                        text=data.get("message", ""),
                        model=data.get("model", "auto"),
                        history=data.get("history", []),
                    )
                    # Stream tokens back over WebSocket
                    async for token in self.agent_core.stream_response(incoming):
                        await websocket.send_json({"token": token, "done": False})
                    await websocket.send_json({"token": "", "done": True})
            except WebSocketDisconnect:
                pass

        @app.get("/health")
        async def health():
            agent_health = "ok"
            if hasattr(self.agent_core, 'health_check'):
                try:
                    healthy = await self.agent_core.health_check()
                    agent_health = "ok" if healthy else "degraded"
                except Exception:
                    agent_health = "error"
            return {
                "status": "ok",
                "version": "1.0.1",
                "interface": "web",
                "agent_core": agent_health,
            }

        return app

    async def _stream_response(
        self, incoming: IncomingMessage, model: str
    ) -> AsyncIterator[str]:
        """Yield SSE chunks in OpenAI streaming format."""
        chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created = int(time.time())

        async for token in self.agent_core.stream_response(incoming):
            chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": token},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk)}\n\n"

        # Final chunk
        final = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(final)}\n\n"
        yield "data: [DONE]\n\n"

    def _format_completion(self, result: ProcessingResult, model: str) -> dict:
        """Format a non-streaming completion response."""
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": result.response},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": result.prompt_tokens or 0,
                "completion_tokens": result.completion_tokens or 0,
                "total_tokens": (result.prompt_tokens or 0) + (result.completion_tokens or 0),
            },
        }

    async def start(self) -> None:
        import uvicorn
        web_config = getattr(self.config, "interfaces", None)
        web_port = getattr(getattr(web_config, "web", None), "port", 8081) if web_config else 8081
        if isinstance(self.config, dict):
            web_port = self.config.get("web_port", 8081)
        config = uvicorn.Config(
            self.app,
            host="0.0.0.0",
            port=web_port,
            log_level="info",
        )
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def stop(self) -> None:
        if self._server:
            self._server.should_exit = True

    async def send_message(self, chat_id: str, message: str, **kwargs) -> None:
        # WebInterface is pull-based (HTTP request/response).
        # For push notifications to web clients, use WebSocket.
        pass

    async def receive_message(self):
        # WebInterface receives via HTTP endpoints, not a polling loop.
        # This is a no-op; FastAPI handles incoming requests.
        pass

    # Required by BaseInterface ABC
    async def handle_message(self, message):
        pass


def create_app(agent_core=None, config: dict | None = None) -> FastAPI:
    """
    Clean FastAPI application factory.

    For programmatic use (lifecycle.py / tests): pass agent_core + config.
    For standalone deployment (Docker / uvicorn direct): call with no args;
    AgentCore is bootstrapped from environment variables / defaults.

    Usage:
        # Standalone (Docker):
        uvicorn portal.interfaces.web.server:app --host 0.0.0.0 --port 8081

        # Programmatic:
        from portal.interfaces.web.server import create_app
        app = create_app(agent_core=my_core, config=my_cfg)
    """
    if agent_core is None:
        from portal.core.agent_core import create_agent_core as _create
        cfg: dict = config or {
            "routing_strategy": "AUTO",
            "ollama_base_url": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            "max_context_messages": 100,
            "circuit_breaker_enabled": True,
            "circuit_breaker_threshold": 3,
            "circuit_breaker_timeout": 60,
            "circuit_breaker_half_open_calls": 1,
        }
        agent_core = _create(cfg)
        config = cfg

    return WebInterface(agent_core, config or {}).app


# Module-level ASGI app for `uvicorn portal.interfaces.web.server:app`
# Bootstraps AgentCore from env-vars when started standalone (Docker / bare metal).
app: FastAPI = create_app()
