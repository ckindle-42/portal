"""Portal WebInterface — OpenAI-compatible HTTP endpoint."""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import uvicorn

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
from starlette.responses import FileResponse, Response

from portal import __version__
from portal.agent.dispatcher import CentralDispatcher
from portal.core.exceptions import (
    ModelNotAvailableError,
    PortalError,
    RateLimitError,
    ValidationError,
)
from portal.core.interfaces.agent_interface import BaseInterface
from portal.core.types import IncomingMessage, InterfaceType, ProcessingResult
from portal.observability.metrics import (
    TOKENS_PER_SECOND,
    TTFT_MS,
    mark_request,
    set_memory_stats,
)
from portal.security.auth import UserStore
from portal.security.middleware import SecurityMiddleware

logger = logging.getLogger(__name__)

_DEFAULT_CSP = "default-src 'self' 'unsafe-inline' 'unsafe-eval'; img-src 'self' data: blob:; frame-ancestors 'none'; base-uri 'self'"


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


def _is_valid_origin(origin: str) -> bool:
    """Return True if origin is a valid http/https URL with a netloc."""
    from urllib.parse import urlparse

    try:
        p = urlparse(origin)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except ValueError:
        return False


def _build_cors_origins(origins: list[str]) -> list[str]:
    """Return validated CORS origins, falling back to localhost:8080 if none valid."""
    valid = [o for o in origins if _is_valid_origin(o)]
    if not valid:
        logger.warning("No valid CORS origins found; defaulting to http://localhost:8080")
        return ["http://localhost:8080"]
    return valid


def _cfg_str(obj: Any, attr: str, default: str) -> str:
    """Safely read a string attribute from config, returning default if missing or wrong type."""
    v = getattr(obj, attr, default) if obj is not None else default
    return v if isinstance(v, str) else default


def _cfg_int(obj: Any, attr: str, default: int) -> int:
    """Safely read an int attribute from config, returning default if missing or wrong type."""
    v = getattr(obj, attr, default) if obj is not None else default
    return v if type(v) is int else default


def _cfg_float(obj: Any, attr: str, default: float) -> float:
    """Safely read a float/int attribute from config as float."""
    v = getattr(obj, attr, default) if obj is not None else default
    return float(v) if isinstance(v, (int, float)) and type(v) is not bool else default


def _cfg_bool(obj: Any, attr: str, default: bool) -> bool:
    """Safely read a bool attribute from config, returning default if missing or wrong type."""
    v = getattr(obj, attr, default) if obj is not None else default
    return v if type(v) is bool else default


def _cfg_list(obj: Any, attr: str, default: list) -> list:
    """Safely read a list attribute from config, returning default if missing or wrong type."""
    v = getattr(obj, attr, default) if obj is not None else default
    return v if isinstance(v, list) else default


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, csp_policy: str = _DEFAULT_CSP, hsts_enabled: bool = False) -> None:
        super().__init__(app)
        self._csp_policy = csp_policy
        self._hsts_enabled = hsts_enabled

    async def dispatch(self, request: Request, call_next) -> Response:
        # Echo or generate a request ID for distributed tracing
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4())[:8])
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = self._csp_policy
        if self._hsts_enabled:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


@CentralDispatcher.register("web")
class WebInterface(BaseInterface):
    def __init__(self, agent_core, config, secure_agent=None) -> None:
        self.agent_core = agent_core
        self.secure_agent = secure_agent  # SecurityMiddleware wrapping agent_core
        self.config = config
        self.user_store = UserStore()
        self._server: uvicorn.Server | None = None
        # Shared HTTP client for Ollama/Whisper calls (avoids per-request connection overhead)
        self._ollama_client: httpx.AsyncClient | None = None
        # Reuse sanitizer from SecurityMiddleware to share state; fall back to new instance
        from portal.security.input_sanitizer import InputSanitizer as _InputSanitizer

        self._input_sanitizer = (
            secure_agent.input_sanitizer
            if isinstance(secure_agent, SecurityMiddleware)
            else _InputSanitizer()
        )

        # Extract typed settings from config with safe fallbacks for dicts/mocks
        _sec = getattr(config, "security", None)
        _ifaces = getattr(config, "interfaces", None)
        _web = getattr(_ifaces, "web", None) if _ifaces is not None else None
        _be = getattr(config, "backends", None)

        self._web_api_key: str = _cfg_str(_sec, "web_api_key", "")
        self._require_api_key: bool = _cfg_bool(_sec, "require_api_key", False)
        self._max_audio_bytes: int = _cfg_int(_web, "max_audio_mb", 25) * 1024 * 1024
        self._whisper_url: str = _cfg_str(_web, "whisper_url", "http://localhost:10300/inference")
        self._vision_model: str = _cfg_str(_web, "vision_model", "llava")
        self._ollama_host: str = _cfg_str(_be, "ollama_url", "http://localhost:11434")
        self._ws_rate_limit: int = _cfg_int(_web, "ws_rate_limit", 10)
        self._ws_rate_window: float = _cfg_float(_web, "ws_rate_window", 60.0)
        _cors = _cfg_list(_web, "cors_origins", [])
        self._cors_origins: list[str] = (
            _cors
            if _cors
            else [
                "http://localhost:8080",
                "http://127.0.0.1:8080",
            ]
        )
        self._csp_policy: str = _cfg_str(_web, "csp_policy", _DEFAULT_CSP)
        self._hsts_enabled: bool = _cfg_bool(_web, "hsts_enabled", False)
        self._web_port: int = _cfg_int(_web, "port", 8081)

        self.app = self._build_app()

    def _extract_user_id(self, request: Request) -> str:
        return (
            request.headers.get("x-portal-user-id")
            or request.headers.get("x-user-id")
            or request.headers.get("x-telegram-user-id")
            or request.headers.get("x-slack-user-id")
            or "anonymous"
        )

    async def _auth_context(
        self, request: Request, authorization: str | None = Header(None)
    ) -> dict[str, str]:
        user_id = self._extract_user_id(request)
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()

        static_web_api_key = self._web_api_key
        require_api_key = self._require_api_key or bool(static_web_api_key)

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

    async def _validate_request(self, user_id: str, message: str) -> tuple[str, list[str]]:
        """
        Shared security validation for all request paths (HTTP streaming, WebSocket).

        Performs input sanitization, rate limiting, and message length checks.
        Returns (sanitized_message, warnings) or raises appropriate exceptions.

        This consolidates security enforcement to prevent code divergence.
        """
        if not isinstance(self.secure_agent, SecurityMiddleware):
            # No security middleware - return message as-is
            return message, []

        # Input sanitization
        sanitized, warnings = self._input_sanitizer.sanitize_command(message)
        if any("Dangerous pattern detected" in w for w in warnings):
            raise ValidationError("Message blocked by security policy")

        # Rate limiting
        allowed, error_msg = await self.secure_agent.rate_limiter.check_limit(user_id)
        if not allowed:
            raise RateLimitError(error_msg or "Rate limit exceeded", retry_after=60)

        # Message length check using configured max_message_length
        if len(sanitized) > self.secure_agent.max_message_length:
            raise ValidationError(
                f"Message exceeds maximum length of {self.secure_agent.max_message_length} characters"
            )

        return sanitized, warnings

    def _build_app(self) -> FastAPI:
        _agent_ready: asyncio.Event = asyncio.Event()

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            """Async lifespan: warm up AgentCore in the background so startup is non-blocking."""
            # Initialize shared HTTP client
            self._ollama_client = httpx.AsyncClient(timeout=60.0)

            async def _warmup() -> None:
                try:
                    if hasattr(self.agent_core, "health_check"):
                        await self.agent_core.health_check()
                except Exception as e:
                    logger.warning("Agent warmup health check failed: %s", e, exc_info=True)
                finally:
                    _agent_ready.set()

            warmup_task = asyncio.create_task(_warmup(), name="agent-warmup")
            try:
                yield
            finally:
                warmup_task.cancel()
                if self._ollama_client is not None:
                    await self._ollama_client.aclose()

        app = FastAPI(title="Portal Web Interface", version=__version__, lifespan=lifespan)
        self._register_exception_handlers(app)
        self._register_middleware(app)
        self._register_routes(app, _agent_ready)
        return app

    def _register_exception_handlers(self, app: FastAPI) -> None:
        @app.exception_handler(RateLimitError)
        async def rate_limit_handler(request: Request, exc: RateLimitError):
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "message": str(exc),
                        "type": "rate_limit_error",
                        "code": "rate_limit_exceeded",
                    }
                },
                headers={"Retry-After": str(getattr(exc, "retry_after", 60))},
            )

        @app.exception_handler(ValidationError)
        async def validation_handler(request: Request, exc: ValidationError):
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": str(exc),
                        "type": "invalid_request_error",
                        "code": "validation_error",
                    }
                },
            )

        @app.exception_handler(ModelNotAvailableError)
        async def model_unavailable_handler(request: Request, exc: ModelNotAvailableError):
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "message": str(exc),
                        "type": "server_error",
                        "code": "model_not_available",
                    }
                },
            )

        @app.exception_handler(PortalError)
        async def portal_error_handler(request: Request, exc: PortalError):
            return JSONResponse(
                status_code=500,
                content={
                    "error": {"message": str(exc), "type": "server_error", "code": "internal_error"}
                },
            )

    def _register_middleware(self, app: FastAPI) -> None:
        app.add_middleware(
            SecurityHeadersMiddleware,
            csp_policy=self._csp_policy,
            hsts_enabled=self._hsts_enabled,
        )
        app.add_middleware(
            CORSMiddleware,
            allow_origins=_build_cors_origins(self._cors_origins),
            allow_credentials=True,
            allow_methods=["POST", "GET", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Portal-User-Id", "X-User-Id"],
        )

    def _register_routes(self, app: FastAPI, _agent_ready: asyncio.Event) -> None:
        self._register_chat_routes(app, _agent_ready)
        self._register_utility_routes(app, _agent_ready)
        self._register_websocket_route(app)

    def _register_chat_routes(self, app: FastAPI, _agent_ready: asyncio.Event) -> None:
        @app.post("/v1/chat/completions")
        async def chat_completions(
            payload: ChatCompletionRequest, request: Request, auth=Depends(self._auth_context)
        ):
            return await self._handle_chat_completions(payload, request, auth, _agent_ready)

        @app.post("/v1/audio/transcriptions")
        async def audio_transcriptions(
            file: UploadFile = File(...), auth=Depends(self._auth_context)
        ):
            return await self._handle_audio_transcriptions(file, auth)

        @app.get("/v1/models")
        async def list_models(auth=Depends(self._auth_context)):
            return await self._handle_list_models(auth)

    async def _handle_chat_completions(
        self,
        payload: ChatCompletionRequest,
        request: Request,
        auth: dict,
        _agent_ready: asyncio.Event,
    ) -> Any:
        """Handle /v1/chat/completions — both streaming and non-streaming paths."""
        if not _agent_ready.is_set():
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "message": "Portal is starting up. Please retry in a few seconds.",
                        "type": "server_error",
                    }
                },
                headers={"Retry-After": "5"},
            )

        user_id = auth["user_id"]
        mark_request(user_id)

        last_user_msg = next(
            (m.content for m in reversed(payload.messages) if m.role == "user"), ""
        )
        image_present = any(isinstance(m.content, list) for m in payload.messages)
        selected_model = payload.model
        if image_present and payload.model == "auto":
            selected_model = self._vision_model

        incoming = IncomingMessage(
            id=str(uuid.uuid4()),
            text=str(last_user_msg),
            model=selected_model,
            history=[{"role": m.role, "content": m.content} for m in payload.messages],
            source="web",
            metadata={"tools": payload.tools, "image_present": image_present},
        )

        if payload.stream:
            # Use shared validation method for security checks
            await self._validate_request(user_id, str(last_user_msg))
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
            workspace_id=selected_model,
        )
        elapsed = time.perf_counter() - start
        tokens = result.completion_tokens or max(len(result.response.split()), 1)
        TOKENS_PER_SECOND.observe(tokens / max(elapsed, 0.001))
        await self.user_store.add_tokens(
            user_id=user_id,
            tokens=(result.prompt_tokens or 0) + (result.completion_tokens or 0),
        )
        return JSONResponse(self._format_completion(result, selected_model))

    async def _handle_audio_transcriptions(self, file: UploadFile, auth: dict) -> dict:
        """Handle /v1/audio/transcriptions — proxy to Whisper with size guard."""
        data = await file.read(self._max_audio_bytes + 1)
        if len(data) > self._max_audio_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Audio file exceeds {self._max_audio_bytes // (1024 * 1024)}MB limit",
            )
        client = self._ollama_client or httpx.AsyncClient(timeout=60.0)
        files = {
            "audio_file": (
                file.filename or "audio.wav",
                data,
                file.content_type or "application/octet-stream",
            )
        }
        resp = await client.post(self._whisper_url, files=files)
        out = resp.json()
        return {"text": out.get("text", "")}

    async def _handle_list_models(self, auth: dict) -> dict:
        """Handle /v1/models — workspace virtual models prepended, then live Ollama models."""
        created = int(time.time())
        models: list[dict] = []

        # 1. Add virtual workspace models (these trigger intelligent routing)
        try:
            rules_path = Path(__file__).parents[2] / "routing" / "router_rules.json"
            if rules_path.exists():
                rules = json.loads(rules_path.read_text())
                for ws_name in rules.get("workspaces", {}):
                    models.append(
                        {
                            "id": ws_name,
                            "object": "model",
                            "created": created,
                            "owned_by": "portal-workspace",
                        }
                    )
        except Exception as e:
            logger.warning("Failed to load workspace models: %s", e)

        # 2. Add real Ollama models
        try:
            client = self._ollama_client or httpx.AsyncClient(timeout=3.0)
            resp = await client.get(f"{self._ollama_host}/api/tags")
            data = resp.json()
            for m in data.get("models", []):
                models.append(
                    {
                        "id": m["name"],
                        "object": "model",
                        "created": created,
                        "owned_by": "portal",
                    }
                )
        except (httpx.HTTPError, json.JSONDecodeError):
            pass

        # Fallback: always have at least "auto"
        if not models:
            models.append(
                {"id": "auto", "object": "model", "created": created, "owned_by": "portal"}
            )

        return {"object": "list", "data": models}

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
            except (TimeoutError, RuntimeError):
                healthy = False
            body["agent_core"] = "ok" if healthy else "degraded"
            mcp_status = {}
            if hasattr(self.agent_core, "mcp_registry") and self.agent_core.mcp_registry:
                try:
                    mcp_status = await self.agent_core.mcp_registry.health_check_all()
                except (TimeoutError, RuntimeError):
                    mcp_status = {"error": "health check failed"}
            body["mcp"] = mcp_status
            return JSONResponse(body, status_code=200)

        @app.get("/health/live")
        async def liveness():
            """Liveness probe - returns OK if the service is running."""
            return {"status": "ok"}

        @app.get("/health/ready")
        async def readiness():
            """Readiness probe - returns OK if the agent is ready to serve requests."""
            if not _agent_ready.is_set():
                return JSONResponse(
                    {"status": "not_ready", "reason": "agent_warming_up"},
                    status_code=503,
                )
            try:
                healthy = await self.agent_core.health_check()
            except (TimeoutError, RuntimeError):
                healthy = False
            if healthy:
                return {"status": "ready"}
            return JSONResponse(
                {"status": "not_ready", "reason": "agent_not_healthy"},
                status_code=503,
            )

        # File delivery endpoints
        @app.get("/v1/files")
        async def list_files():
            """List recently generated files."""

            generated_dir = Path("data/generated")
            if not generated_dir.exists():
                return {"files": []}

            files = []
            try:
                for f in sorted(
                    generated_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True
                ):
                    if f.is_file():
                        files.append(
                            {
                                "name": f.name,
                                "size": f.stat().st_size,
                                "modified": f.stat().st_mtime,
                            }
                        )
            except OSError:
                pass

            return {"files": files[:50]}  # Limit to 50 most recent

        @app.get("/v1/files/{filename}")
        async def get_file(filename: str):
            """Serve a generated file with proper MIME type and download headers."""

            # Security: reject path traversal attempts
            if ".." in filename or "/" in filename or "\\" in filename:
                return JSONResponse({"error": "Invalid filename"}, status_code=400)

            generated_dir = Path("data/generated")
            file_path = generated_dir / filename

            # Only serve files from the generated directory
            if not file_path.exists() or not file_path.is_file():
                return JSONResponse({"error": "File not found"}, status_code=404)

            # Determine MIME type
            import mimetypes

            content_type, _ = mimetypes.guess_type(str(file_path))
            content_type = content_type or "application/octet-stream"

            # Add Content-Disposition for document types
            document_types = {".docx", ".pptx", ".xlsx", ".pdf", ".txt", ".md"}
            disposition = "attachment" if file_path.suffix.lower() in document_types else "inline"

            return FileResponse(
                file_path,
                media_type=content_type,
                headers={"Content-Disposition": f'{disposition}; filename="{filename}"'},
            )

    def _register_websocket_route(self, app: FastAPI) -> None:
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket) -> None:
            await self._handle_websocket(websocket)

    async def _handle_websocket(self, websocket: WebSocket) -> None:
        """Handle /ws — authenticated, rate-limited, streaming WebSocket chat."""
        if self._web_api_key:
            token = websocket.query_params.get("api_key", "")
            if not hmac.compare_digest(token.encode(), self._web_api_key.encode()):
                await websocket.close(code=4001, reason="Unauthorized")
                return
        await websocket.accept()

        # Use shared rate limiter if available (S2: share state with HTTP rate limiter)
        shared_rate_limiter = (
            self.secure_agent.rate_limiter
            if isinstance(self.secure_agent, SecurityMiddleware)
            else None
        )
        ws_user_id = websocket.query_params.get("user_id", "ws-anonymous")

        # Fallback per-connection rate limiter (used only when no shared limiter is present)
        ws_rate_limit = self._ws_rate_limit
        ws_rate_window = self._ws_rate_window
        message_timestamps: list[float] = []

        try:
            while True:
                data = await websocket.receive_json()

                # Rate limiting: prefer shared limiter to prevent bypass via reconnect
                if shared_rate_limiter is not None:
                    allowed, error_msg = await shared_rate_limiter.check_limit(ws_user_id)
                    if not allowed:
                        await websocket.send_json({"error": error_msg, "done": True})
                        continue
                else:
                    now = time.time()
                    message_timestamps = [
                        ts for ts in message_timestamps if now - ts < ws_rate_window
                    ]
                    if len(message_timestamps) >= ws_rate_limit:
                        await websocket.send_json(
                            {
                                "error": f"Rate limit exceeded ({ws_rate_limit} messages per {int(ws_rate_window)}s). Please wait.",
                                "done": True,
                            }
                        )
                        continue
                    message_timestamps.append(now)

                raw_text = data.get("message", "")
                sanitized_text, warnings = self._input_sanitizer.sanitize_command(raw_text)
                if any("Dangerous pattern detected" in w for w in warnings):
                    await websocket.send_json(
                        {"error": "Message blocked by security policy", "done": True}
                    )
                    continue
                # Use configured max_message_length from SecurityMiddleware if available
                max_len = (
                    self.secure_agent.max_message_length
                    if isinstance(self.secure_agent, SecurityMiddleware)
                    else 10000
                )
                if len(sanitized_text) > max_len:
                    await websocket.send_json(
                        {
                            "error": f"Message exceeds maximum length of {max_len} characters",
                            "done": True,
                        }
                    )
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
            logger.error("WebSocket error: %s", e, exc_info=True)
            try:
                await websocket.send_json({"error": "Internal error", "done": True})
            except (RuntimeError, OSError):
                pass
            return

    async def _stream_response(
        self, incoming: IncomingMessage, model: str, user_id: str
    ) -> AsyncIterator[str]:
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
            chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {"content": token}, "finish_reason": None}],
            }
            yield f"data: {json.dumps(chunk)}\n\n"

        elapsed = time.perf_counter() - started
        TOKENS_PER_SECOND.observe(token_count / max(elapsed, 0.001))
        await self.user_store.add_tokens(user_id=user_id, tokens=token_count)

        if not first_token_emitted:
            error_chunk = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {
                            "content": "I'm sorry, I wasn't able to generate a response. Please try again."
                        },
                        "finish_reason": "stop",
                    }
                ],
            }
            yield f"data: {json.dumps(error_chunk)}\n\n"

        # Final chunk includes usage data for token accounting in clients (E1)
        final = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            "usage": {
                "prompt_tokens": 0,  # not available during streaming
                "completion_tokens": token_count,
                "total_tokens": token_count,
            },
        }
        yield f"data: {json.dumps(final)}\n\n"
        yield "data: [DONE]\n\n"

    def _format_completion(self, result: ProcessingResult, model: str) -> dict:
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

    async def handle_message(self, message):  # type: ignore[override]
        """Not used by WebInterface; HTTP handlers process messages via FastAPI routes."""
        raise NotImplementedError(
            "WebInterface processes messages via HTTP — call the FastAPI app directly."
        )

    async def send_message(self, user_id: str, response) -> bool:  # type: ignore[override]
        """Not used by WebInterface; responses are delivered via HTTP streaming."""
        return False

    async def start(self) -> None:
        import uvicorn

        config = uvicorn.Config(self.app, host="0.0.0.0", port=self._web_port, log_level="info")
        self._server = uvicorn.Server(config)
        await self._server.serve()

    async def stop(self) -> None:
        if self._server:
            self._server.should_exit = True


def create_app(agent_core=None, config: dict | None = None, secure_agent=None) -> FastAPI:
    if agent_core is None:
        from portal.config.settings import Settings
        from portal.core.agent_core import create_agent_core as _create

        # Use Settings to properly load env vars (e.g., PORTAL_BACKENDS__OLLAMA_URL)
        settings = Settings()
        cfg = config or settings.to_agent_config()
        agent_core = _create(cfg)
        # Pass Settings object to WebInterface so it reads backends.ollama_url correctly
        config = settings  # type: ignore[assignment]

    if secure_agent is None:
        secure_agent = SecurityMiddleware(
            agent_core,
            enable_rate_limiting=True,
            enable_input_sanitization=True,
        )

    return WebInterface(agent_core, config, secure_agent=secure_agent).app
