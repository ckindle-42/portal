"""Portal WebInterface — OpenAI-compatible HTTP endpoint."""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import (
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from portal.agent.dispatcher import CentralDispatcher
from portal.core.exceptions import (
    ModelNotAvailableError,
    PortalError,
    RateLimitError,
    ValidationError,
)
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


@CentralDispatcher.register("web")
class WebInterface(BaseInterface):
    def __init__(self, agent_core, config, secure_agent=None):
        self.agent_core = agent_core
        self.secure_agent = secure_agent  # SecurityMiddleware wrapping agent_core
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

    async def _auth_context(self, request: Request, authorization: str | None = Header(None)) -> dict[str, str]:
        user_id = self._extract_user_id(request)
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()

        static_web_api_key = os.getenv("WEB_API_KEY", "").strip()
        require_api_key = _bool_env("REQUIRE_API_KEY", default=bool(static_web_api_key))

        if static_web_api_key:
            # Use hmac.compare_digest to prevent timing-attack enumeration of the key
            if not hmac.compare_digest((token or "").encode(), static_web_api_key.encode()):
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
        _agent_ready: asyncio.Event = asyncio.Event()

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Async lifespan: warm up AgentCore in the background so startup is non-blocking."""
            async def _warmup():
                try:
                    if hasattr(self.agent_core, "health_check"):
                        await self.agent_core.health_check()
                except Exception:
                    pass
                finally:
                    _agent_ready.set()

            warmup_task = asyncio.create_task(_warmup(), name="agent-warmup")
            try:
                yield
            finally:
                warmup_task.cancel()

        app = FastAPI(title="Portal Web Interface", version="1.3.0", lifespan=lifespan)
        self._register_exception_handlers(app)
        self._register_middleware(app)
        self._register_routes(app, _agent_ready)
        return app

    def _register_exception_handlers(self, app: FastAPI) -> None:
        @app.exception_handler(RateLimitError)
        async def rate_limit_handler(request: Request, exc: RateLimitError):
            return JSONResponse(
                status_code=429,
                content={"error": {"message": str(exc), "type": "rate_limit_error", "code": "rate_limit_exceeded"}},
                headers={"Retry-After": str(getattr(exc, 'retry_after', 60))},
            )

        @app.exception_handler(ValidationError)
        async def validation_handler(request: Request, exc: ValidationError):
            return JSONResponse(
                status_code=400,
                content={"error": {"message": str(exc), "type": "invalid_request_error", "code": "validation_error"}},
            )

        @app.exception_handler(ModelNotAvailableError)
        async def model_unavailable_handler(request: Request, exc: ModelNotAvailableError):
            return JSONResponse(
                status_code=503,
                content={"error": {"message": str(exc), "type": "server_error", "code": "model_not_available"}},
            )

        @app.exception_handler(PortalError)
        async def portal_error_handler(request: Request, exc: PortalError):
            return JSONResponse(
                status_code=500,
                content={"error": {"message": str(exc), "type": "server_error", "code": "internal_error"}},
            )

    def _register_middleware(self, app: FastAPI) -> None:
        app.add_middleware(SecurityHeadersMiddleware)
        app.add_middleware(
            CORSMiddleware,
            allow_origins=_build_cors_origins(),
            allow_credentials=True,
            allow_methods=["POST", "GET", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Portal-User-Id", "X-User-Id"],
        )

    def _register_routes(self, app: FastAPI, _agent_ready: asyncio.Event) -> None:
        self._register_chat_routes(app)
        self._register_utility_routes(app, _agent_ready)
        self._register_websocket_route(app)

    def _register_chat_routes(self, app: FastAPI) -> None:
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
            processor = self.secure_agent if self.secure_agent is not None else self.agent_core
            result = await processor.process_message(
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

    def _register_utility_routes(self, app: FastAPI, _agent_ready: asyncio.Event) -> None:
        @app.get("/metrics")
        async def metrics():
            set_memory_stats()
            return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

        @app.get("/dashboard")
        async def dashboard():
            return Response(
                "<html><body><h1>Portal Dashboard</h1>"
                "<p>Prometheus metrics are available at <code>/metrics</code>.</p>"
                "</body></html>",
                media_type="text/html",
            )

        @app.get("/health")
        async def health():
            import sys

            import portal as _portal

            body: dict = {
                "status": "ok",
                "version": getattr(_portal, "__version__", "unknown"),
                "build": {
                    "python_version": sys.version.split()[0],
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
                "interface": "web",
            }
            if not _agent_ready.is_set():
                body["status"] = "warming_up"
                body["agent_core"] = "warming_up"
                return JSONResponse(body, status_code=200)
            try:
                healthy = await self.agent_core.health_check()
            except Exception:
                healthy = False
            body["agent_core"] = "ok" if healthy else "degraded"
            mcp_status = {}
            if hasattr(self.agent_core, 'mcp_registry') and self.agent_core.mcp_registry:
                try:
                    mcp_status = await self.agent_core.mcp_registry.health_check_all()
                except Exception:
                    mcp_status = {"error": "health check failed"}
            body["mcp"] = mcp_status
            return JSONResponse(body, status_code=200)

    def _register_websocket_route(self, app: FastAPI) -> None:
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            from portal.security.security_module import InputSanitizer
            sanitizer = InputSanitizer()

            static_key = os.getenv("WEB_API_KEY", "").strip()
            if static_key:
                token = websocket.query_params.get("api_key", "")
                if not hmac.compare_digest(token.encode(), static_key.encode()):
                    await websocket.close(code=4001, reason="Unauthorized")
                    return
            await websocket.accept()

            ws_rate_limit = int(os.getenv("WS_RATE_LIMIT", "10"))
            ws_rate_window = float(os.getenv("WS_RATE_WINDOW", "60"))
            message_timestamps: list[float] = []

            try:
                while True:
                    data = await websocket.receive_json()
                    now = time.time()
                    message_timestamps = [ts for ts in message_timestamps if now - ts < ws_rate_window]
                    if len(message_timestamps) >= ws_rate_limit:
                        await websocket.send_json({
                            "error": f"Rate limit exceeded ({ws_rate_limit} messages per {int(ws_rate_window)}s). Please wait.",
                            "done": True,
                        })
                        continue
                    message_timestamps.append(now)

                    raw_text = data.get("message", "")
                    sanitized_text, warnings = sanitizer.sanitize_command(raw_text)
                    if any("Dangerous pattern detected" in w for w in warnings):
                        await websocket.send_json({"error": "Message blocked by security policy", "done": True})
                        continue
                    if len(sanitized_text) > 10000:
                        await websocket.send_json({"error": "Message exceeds maximum length", "done": True})
                        continue

                    incoming = IncomingMessage(
                        id=str(uuid.uuid4()),
                        text=sanitized_text,
                        model=data.get("model", "auto"),
                    )
                    async for tok in self.agent_core.stream_response(incoming):
                        await websocket.send_json({"token": tok, "done": False})
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

        if not first_token_emitted:
            error_chunk = {
                "id": chunk_id, "object": "chat.completion.chunk", "created": created,
                "model": model, "choices": [{"index": 0, "delta": {"content": "I'm sorry, I wasn't able to generate a response. Please try again."}, "finish_reason": "stop"}]
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"

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

    async def handle_message(self, message):  # type: ignore[override]
        """Not used by WebInterface; HTTP handlers process messages via FastAPI routes."""
        raise NotImplementedError("WebInterface processes messages via HTTP — call the FastAPI app directly.")

    async def send_message(self, user_id: str, response) -> bool:  # type: ignore[override]
        """Not used by WebInterface; responses are delivered via HTTP streaming."""
        return False

    async def start(self) -> None:
        import uvicorn

        config = uvicorn.Config(self.app, host="0.0.0.0", port=int(os.getenv("WEB_PORT", "8081")), log_level="info")
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def stop(self) -> None:
        if self._server:
            self._server.should_exit = True


def create_app(agent_core=None, config: dict | None = None, secure_agent=None) -> FastAPI:
    if agent_core is None:
        from portal.core.agent_core import create_agent_core as _create

        cfg = config or {
            "routing_strategy": "AUTO",
            "ollama_base_url": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            "max_context_messages": 100,
        }
        agent_core = _create(cfg)
        config = cfg

    if secure_agent is None:
        from portal.security import SecurityMiddleware
        secure_agent = SecurityMiddleware(
            agent_core,
            enable_rate_limiting=True,
            enable_input_sanitization=True,
        )

    return WebInterface(agent_core, config or {}, secure_agent=secure_agent).app
