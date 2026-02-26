"""
Portal Model Router — FastAPI proxy to Ollama.

Sits at :8000 and provides:
  - Full Ollama API proxy (pass-through)
  - Workspace virtual models (auto, auto-coding, auto-reasoning, auto-fast)
  - Regex keyword routing rules
  - Manual override via @model: prefix
  - VRAM-aware model management
  - /health — component status
  - /api/dry-run — routing decision without execution
  - /api/tags — augmented model list with virtual workspaces

Based on M4 AI Stack Setup Guide v6.2 / v4.7.
"""

import hmac
import json
import logging
import os
import re
import time
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
ROUTER_PORT = int(os.getenv("ROUTER_PORT", "8000"))
ROUTER_TOKEN = os.getenv("ROUTER_TOKEN", "")

# Load rules from JSON file next to this module
_RULES_FILE = Path(__file__).parent / "router_rules.json"


def _load_rules() -> dict:
    if _RULES_FILE.exists():
        with open(_RULES_FILE) as f:
            return json.load(f)
    return {
        "version": "1.0",
        "default_model": "qwen2.5:7b",
        "warm_model": "qwen2.5:7b",
        "workspaces": {},
        "regex_rules": [],
        "manual_override_prefix": "@model:",
        "auth_token_env": "ROUTER_TOKEN",
    }


RULES = _load_rules()
DEFAULT_MODEL = RULES.get("default_model", "qwen2.5:7b")
MANUAL_PREFIX = RULES.get("manual_override_prefix", "@model:")

# Pre-compile regex rules sorted by priority (desc)
_compiled_rules: list[tuple[int, str, list[re.Pattern], str]] = []
for rule in sorted(RULES.get("regex_rules", []), key=lambda r: -r.get("priority", 0)):
    patterns = [re.compile(k) for k in rule.get("keywords", [])]
    _compiled_rules.append((rule.get("priority", 0), rule["name"], patterns, rule["model"]))

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Portal Model Router",
    version="1.0.0",
    description="Intelligent Ollama proxy with workspace routing",
    docs_url="/docs",
    redoc_url=None,
)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

async def _verify_token(authorization: str | None = Header(None)) -> None:
    """Verify ROUTER_TOKEN when it is configured (non-empty).

    Uses ``hmac.compare_digest`` to prevent timing-attack enumeration.
    When ROUTER_TOKEN is unset or empty, all requests are allowed through
    so development environments work without extra configuration.
    """
    if not ROUTER_TOKEN:
        return
    token = ""
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
    if not hmac.compare_digest(token.encode(), ROUTER_TOKEN.encode()):
        raise HTTPException(status_code=401, detail="Invalid or missing ROUTER_TOKEN")


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------

def _extract_user_text(messages: list[dict]) -> str:
    """Extract latest user message content."""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, list):
                # Handle multimodal content blocks
                return " ".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                )
            return str(content)
    return ""


def resolve_model(requested_model: str, messages: list[dict]) -> tuple[str, str]:
    """
    Resolve the actual Ollama model to use.

    Returns (resolved_model, reason).
    """
    user_text = _extract_user_text(messages)

    # 1. Manual override (@model:name in message)
    if MANUAL_PREFIX in user_text:
        try:
            override = user_text.split(MANUAL_PREFIX, 1)[1].split()[0]
            return override, f"manual override: {override}"
        except IndexError:
            pass

    # 2. Workspace model (virtual model names)
    workspaces = RULES.get("workspaces", {})
    if requested_model in workspaces:
        ws = workspaces[requested_model]
        return ws["model"], f"workspace: {requested_model}"

    # 3. Regex content rules
    for priority, name, patterns, model in _compiled_rules:
        for pattern in patterns:
            if pattern.search(user_text):
                return model, f"rule: {name}"

    # 4. Default
    if requested_model and requested_model != "auto":
        return requested_model, "explicit model"

    return DEFAULT_MODEL, "default"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    """Health check — verify Ollama connectivity."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
            models = resp.json().get("models", [])
            return {
                "status": "ok",
                "ollama": "ok",
                "model_count": len(models),
                "default_model": DEFAULT_MODEL,
                "version": "1.0.0",
            }
    except Exception as e:
        return {
            "status": "degraded",
            "ollama": f"unreachable: {e}",
            "default_model": DEFAULT_MODEL,
            "version": "1.0.0",
        }


@app.post("/api/dry-run")
async def dry_run(request: Request) -> dict:
    """Return routing decision without executing."""
    body = await request.json()
    messages = body.get("messages", [])
    requested = body.get("model", "auto")
    resolved, reason = resolve_model(requested, messages)
    return {
        "requested_model": requested,
        "resolved_model": resolved,
        "reason": reason,
        "default_model": DEFAULT_MODEL,
    }


@app.get("/api/tags")
async def list_tags() -> dict:
    """Return Ollama models augmented with virtual workspace names."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_HOST}/api/tags")
            data = resp.json()
    except Exception as e:
        logger.warning(f"Could not fetch Ollama tags: {e}")
        data = {"models": []}

    real_models = data.get("models", [])

    # Add virtual workspace models
    for ws_name, ws_config in RULES.get("workspaces", {}).items():
        virtual = {
            "name": ws_name,
            "model": ws_name,
            "modified_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "size": 0,
            "digest": "",
            "details": {
                "family": "virtual",
                "parameter_size": "",
                "quantization_level": "",
                "resolves_to": ws_config.get("model", DEFAULT_MODEL),
            },
        }
        real_models.append(virtual)

    return {"models": real_models}


async def _proxy_stream(
    method: str,
    url: str,
    headers: dict,
    body: bytes,
):
    """Stream response from Ollama back to client."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
        async with client.stream(method, url, headers=headers, content=body) as resp:
            async for chunk in resp.aiter_bytes():
                yield chunk


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"],
    dependencies=[Depends(_verify_token)],
)
async def proxy(request: Request, path: str) -> Response:
    """
    Catch-all proxy — forward all Ollama API calls.
    Rewrites model field in chat/generate endpoints before forwarding.
    """
    body = await request.body()
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }

    # Rewrite model in chat/generate requests
    resolved_model = None
    if path in ("api/chat", "api/generate") and body:
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise TypeError("payload must be a JSON object, not an array or scalar")
            messages = payload.get("messages", [])
            if not messages:
                # generate endpoint uses "prompt" not "messages"
                messages = [{"role": "user", "content": payload.get("prompt", "")}]
            requested = payload.get("model", "auto")
            resolved_model, reason = resolve_model(requested, messages)
            payload["model"] = resolved_model
            body = json.dumps(payload).encode()
            headers["content-length"] = str(len(body))
            logger.debug(f"Routing {requested!r} → {resolved_model!r} ({reason})")
        except (json.JSONDecodeError, KeyError, TypeError):
            pass

    target_url = f"{OLLAMA_HOST}/{path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # Check if client wants streaming
    is_stream = False
    if body:
        try:
            payload = json.loads(body)
            if isinstance(payload, dict):
                is_stream = payload.get("stream", True)  # Ollama defaults to streaming
        except (json.JSONDecodeError, TypeError):
            pass

    if is_stream and path in ("api/chat", "api/generate", "v1/chat/completions"):
        return StreamingResponse(
            _proxy_stream(request.method, target_url, headers, body),
            media_type="application/x-ndjson",
        )

    # Non-streaming
    async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0)) as client:
        resp = await client.request(
            request.method,
            target_url,
            headers=headers,
            content=body,
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
        )
