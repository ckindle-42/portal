"""Portal WebInterface — OpenAI-compatible HTTP endpoint."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, AsyncIterator, Optional

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from portal.core.types import IncomingMessage, InterfaceType, ProcessingResult
from portal.interfaces.base import BaseInterface
from portal.observability.runtime_metrics import (
    TOKENS_PER_SECOND,
    TTFT_MS,
    mark_request,
    set_memory_stats,
)
from portal.security.auth import UserStore

logger = logging.getLogger(__name__)

class ChatMessage(BaseModel):
    role: str
    content: Any


class ChatCompletionRequest(BaseModel):
    model: str = "auto"
    messages: list[ChatMessage]
    stream: bool = True
    temperature: float = 0.7
    max_tokens: int | None = None
    tools: list[dict[str, Any]] = Field(default_factory=list)


def _build_cors_origins() -> list[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000,http://127.0.0.1:3000")
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins or ["http://localhost:8080"]


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        csp = os.getenv(
            "PORTAL_CSP",
            "default-src 'self' 'unsafe-inline' 'unsafe-eval'; img-src 'self' data: blob:; frame-ancestors 'none'; base-uri 'self'",
        )
        response.headers["Content-Security-Policy"] = csp
        if _bool_env("PORTAL_HSTS"):
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


class WebInterface(BaseInterface):
    def __init__(self, agent_core, config):
        self.agent_core = agent_core
        self.config = config
        self.user_store = UserStore()
        self._server = None
        self.app = self._build_app()

    def _extract_user_id(self, request: Request) -> str:
        return (
            request.headers.get("x-portal-user-id")
            or request.headers.get("x-user-id")
            or request.headers.get("x-telegram-user-id")
            or request.headers.get("x-slack-user-id")
            or "anonymous"
        )

    async def _auth_context(self, request: Request, authorization: Optional[str] = Header(None)) -> dict[str, str]:
        user_id = self._extract_user_id(request)
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()

        static_web_api_key = os.getenv("WEB_API_KEY", "").strip()
        require_api_key = _bool_env("REQUIRE_API_KEY", default=bool(static_web_api_key))

        if static_web_api_key:
            if token != static_web_api_key:
                raise HTTPException(status_code=401, detail="Invalid API key")
            return {"user_id": user_id, "role": "api_key"}

        if require_api_key and not token:
            raise HTTPException(status_code=401, detail="Missing API key")

        try:
            ctx = await self.user_store.authenticate(token=token, fallback_user=user_id)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        return {"user_id": ctx.user_id, "role": ctx.role}

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="Portal Web Interface", version="1.1.0")
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(CORSMiddleware, allow_origins=_build_cors_origins(), allow_credentials=True, allow_methods=["POST", "GET", "OPTIONS"], allow_headers=["Authorization", "Content-Type", "X-Portal-User-Id", "X-User-Id"])

        @app.post("/v1/chat/completions")
        async def chat_completions(payload: ChatCompletionRequest, request: Request, auth=Depends(self._auth_context)):
            user_id = auth["user_id"]
            mark_request(user_id)

            last_user_msg = next((m.content for m in reversed(payload.messages) if m.role == "user"), "")
            image_present = any(isinstance(m.content, list) for m in payload.messages)
            selected_model = payload.model
            if image_present and payload.model == "auto":
                selected_model = os.getenv("PORTAL_VISION_MODEL", "llava")

            incoming = IncomingMessage(
                id=str(uuid.uuid4()),
                text=str(last_user_msg),
                model=selected_model,
                history=[{"role": m.role, "content": m.content} for m in payload.messages],
                source="web",
                metadata={"tools": payload.tools, "image_present": image_present},
            )

            if payload.stream:
                return StreamingResponse(
                    self._stream_response(incoming, selected_model, user_id),
                    media_type="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
                )

            start = time.perf_counter()
            result = await self.agent_core.process_message(
                chat_id=incoming.id,
                message=incoming.text,
                interface=InterfaceType.WEB,
                user_context={"user_id": user_id},
            )
            elapsed = time.perf_counter() - start
            tokens = (result.completion_tokens or max(len(result.response.split()), 1))
            TOKENS_PER_SECOND.observe(tokens / max(elapsed, 0.001))
            await self.user_store.add_tokens(user_id=user_id, tokens=(result.prompt_tokens or 0) + (result.completion_tokens or 0))
            return JSONResponse(self._format_completion(result, selected_model))


        @app.post("/v1/audio/transcriptions")
        async def audio_transcriptions(file: UploadFile = File(...), auth=Depends(self._auth_context)):
            data = await file.read()
            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {"audio_file": (file.filename or "audio.wav", data, file.content_type or "application/octet-stream")}
                resp = await client.post(os.getenv("WHISPER_URL", "http://localhost:10300/inference"), files=files)
                out = resp.json()
            return {"text": out.get("text", "")}

        @app.get("/v1/models")
        async def list_models(auth=Depends(self._auth_context)):
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(f"{os.getenv('OLLAMA_HOST', 'http://localhost:11434')}/api/tags")
                    data = resp.json()
                return {
                    "object": "list",
                    "data": [
                        {"id": m["name"], "object": "model", "created": int(time.time()), "owned_by": "portal"}
                        for m in data.get("models", [])
                    ],
                }
            except Exception:
                return {"object": "list", "data": [{"id": "auto", "object": "model", "created": int(time.time()), "owned_by": "portal"}]}

        @app.get("/metrics")
        async def metrics():
            set_memory_stats()
            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

        @app.get("/dashboard")
        async def dashboard():
            return Response(
                """
                <html><body><h1>Portal Dashboard</h1>
                <p>Prometheus metrics are available at <code>/metrics</code>.</p>
                </body></html>
                """,
                media_type="text/html",
            )

        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            # Verify API key from query params before accepting connection
            static_key = os.getenv("WEB_API_KEY", "").strip()
            if static_key:
                token = websocket.query_params.get("api_key", "")
                if token != static_key:
                    await websocket.close(code=4001, reason="Unauthorized")
                    return
            await websocket.accept()
            try:
                while True:
                    data = await websocket.receive_json()
                    incoming = IncomingMessage(id=str(uuid.uuid4()), text=data.get("message", ""), model=data.get("model", "auto"))
                    async for token in self.agent_core.stream_response(incoming):
                        await websocket.send_json({"token": token, "done": False})
                    await websocket.send_json({"token": "", "done": True})
            except WebSocketDisconnect:
                return
            except Exception as e:
                logger.error(f"WebSocket error: {e}", exc_info=True)
                try:
                    await websocket.send_json({"error": "Internal error", "done": True})
                except Exception:
                    pass
                return

        @app.get("/health")
        async def health():
            try:
                healthy = await self.agent_core.health_check()
            except Exception:
                healthy = False
            status = "ok" if healthy else "degraded"
            code = 200 if healthy else 503
            return JSONResponse(
                {"status": status, "interface": "web"},
                status_code=code,
            )

        return app

    async def _stream_response(self, incoming: IncomingMessage, model: str, user_id: str) -> AsyncIterator[str]:
        chunk_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created = int(time.time())
        started = time.perf_counter()
        first_token_emitted = False
        token_count = 0

        async for token in self.agent_core.stream_response(incoming):
            if not first_token_emitted:
                TTFT_MS.observe((time.perf_counter() - started) * 1000)
                first_token_emitted = True
            token_count += 1
            chunk = {"id": chunk_id, "object": "chat.completion.chunk", "created": created, "model": model, "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}]}
            yield f"data: {json.dumps(chunk)}\n\n"

        elapsed = time.perf_counter() - started
        TOKENS_PER_SECOND.observe(token_count / max(elapsed, 0.001))
        await self.user_store.add_tokens(user_id=user_id, tokens=token_count)

        final = {"id": chunk_id, "object": "chat.completion.chunk", "created": created, "model": model, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]}
        yield f"data: {json.dumps(final)}\n\n"
        yield "data: [DONE]\n\n"

    def _format_completion(self, result: ProcessingResult, model: str) -> dict:
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": result.response}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": result.prompt_tokens or 0,
                "completion_tokens": result.completion_tokens or 0,
                "total_tokens": (result.prompt_tokens or 0) + (result.completion_tokens or 0),
            },
        }

    async def start(self) -> None:
        import uvicorn

        config = uvicorn.Config(self.app, host="0.0.0.0", port=int(os.getenv("WEB_PORT", "8081")), log_level="info")
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def stop(self) -> None:
        if self._server:
            self._server.should_exit = True

    async def send_message(self, chat_id: str, message: str, **kwargs) -> None:
        return

    async def receive_message(self):
        return

    async def handle_message(self, message):
        return


def create_app(agent_core=None, config: dict | None = None) -> FastAPI:
    if agent_core is None:
        from portal.core.agent_core import create_agent_core as _create

        cfg = config or {
            "routing_strategy": "AUTO",
            "ollama_base_url": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            "max_context_messages": 100,
        }
        agent_core = _create(cfg)
        config = cfg

    return WebInterface(agent_core, config or {}).app


