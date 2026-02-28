# Portal Architecture

**Version:** 1.3.8
**Last updated:** February 2026

---

## Overview

Portal is a **web-primary, multi-interface, hardware-agnostic** local AI platform.
It exposes an OpenAI-compatible HTTP endpoint that any web UI (Open WebUI, LibreChat)
can point at, while simultaneously bridging Telegram and Slack through the same
AgentCore and model backend.

```
┌─────────────────────────────────────────────────────┐
│                   User Interfaces                    │
│   Open WebUI / LibreChat   Telegram Bot   Slack Bot  │
└───────────────┬─────────────────┬──────────┬────────┘
                │ HTTP /v1        │ polling  │ webhook
                ▼                 ▼          ▼
┌─────────────────────────────────────────────────────┐
│                  Portal Interfaces                   │
│  WebInterface (FastAPI :8081)  TelegramInterface     │
│  SlackInterface (routes on WebInterface app)         │
└──────────────────────────┬──────────────────────────┘
                           │ IncomingMessage / ProcessingResult
                           ▼
┌─────────────────────────────────────────────────────┐
│                     AgentCore                        │
│  process_message()  stream_response()  health_check()│
│  ContextManager   EventBus   PromptManager           │
│  ToolRegistry     MCPRegistry                        │
└──────┬──────────────────────────────────────────────┘
       │ route(query) → ModelDecision
       ▼
┌──────────────────────┐   ┌──────────────────────────┐
│   IntelligentRouter  │   │     ExecutionEngine       │
│   ModelRegistry      │   │  Ollama / LMStudio / MLX  │
│   RoutingStrategy    │   │  circuit-breaker pattern   │
└──────────────────────┘   └──────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│                    MCP Layer                          │
│  MCPRegistry  →  mcpo proxy  →  MCP servers          │
│                               (Filesystem, Time,      │
│                                ComfyUI, Whisper)      │
└──────────────────────────────────────────────────────┘
```

---

## Key Components

### AgentCore (`src/portal/core/agent_core.py`)

The central processing engine.  All interfaces funnel requests through here.

| Method | Purpose |
|--------|---------|
| `process_message(chat_id, message, interface, ...)` | Main entry point; routes to LLM, saves context, emits events |
| `stream_response(incoming: IncomingMessage)` | Async generator used by WebInterface SSE and WebSocket paths |
| `health_check()` | Returns `True` if the execution engine is reachable |
| `execute_tool(tool_name, parameters, ...)` | Direct tool execution with optional human-in-the-loop confirmation |
| `_dispatch_mcp_tools(tool_calls, ...)` | Dispatches LLM-requested tool calls to MCPRegistry |

**Dependencies (all injected via DependencyContainer):**
- `ModelRegistry` — catalogue of available models and their capabilities
- `IntelligentRouter` — selects best model for each query
- `ExecutionEngine` — calls the LLM backend; implements circuit-breaker
- `ContextManager` — per-conversation message history (in-memory + SQLite)
- `EventBus` — publishes progress events (ROUTING_DECISION, MODEL_GENERATING, …)
- `PromptManager` — loads system prompt templates from disk
- `ToolRegistry` — discovers and manages local Python tools
- `MCPRegistry` — registry of connected MCP servers (optional at startup)

---

### Interfaces

All concrete interfaces inherit from `BaseInterface`
(`src/portal/core/interfaces/agent_interface.py`).
`src/portal/interfaces/__init__.py` re-exports `BaseInterface`.

#### WebInterface (`src/portal/interfaces/web/server.py`)

- FastAPI application bound at `:8081`
- **POST `/v1/chat/completions`** — OpenAI-compatible streaming (SSE) and non-streaming
- **GET `/v1/models`** — virtual model list proxied from the Ollama router
- **WS `/ws`** — WebSocket streaming chat
- **GET `/health`** — live health check; calls `AgentCore.health_check()`

Open WebUI and LibreChat connect here via "Custom OpenAI Endpoint":
```
http://localhost:8081/v1
```

#### TelegramInterface (`src/portal/interfaces/telegram/interface.py`)

- Uses python-telegram-bot v20 (polling mode by default, webhook supported)
- Per-user authorisation via `authorized_users` list in config
- Rate limiting via `SecurityModule.RateLimiter`
- Optional human-in-the-loop via `ToolConfirmationMiddleware`
- Inline keyboard buttons for Approve / Deny confirmation requests

#### SlackInterface (`src/portal/interfaces/slack/interface.py`)

- Registers `/slack/events` on the shared WebInterface FastAPI app
- Verifies Slack request signatures (`hmac.new` / SHA-256, CRIT-5 verified)
- Handles `app_mention` and `message` event types
- Channel whitelist support
- Collects streamed tokens and posts full reply via `chat.postMessage`

---

### Routing (`src/portal/routing/`)

| Component | Responsibility |
|-----------|---------------|
| `ModelRegistry` | Catalogue of local models with capability tags and speed classes; `discover_from_ollama()` for dynamic discovery |
| `IntelligentRouter` | Classifies query complexity and selects optimal model |
| `RoutingStrategy` | `AUTO` / `QUALITY` / `SPEED` / `BALANCED` |
| `ExecutionEngine` | Calls Ollama / MLX; circuit-breaker per backend (LMStudio planned - see ROADMAP.md) |
| `BaseHTTPBackend` | Shared aiohttp session management; base class for `OllamaBackend` (MLX and LMStudio planned) |

Routing strategies:
- **AUTO** — automatic complexity-based selection (default)
- **QUALITY** — always use the most capable available model
- **SPEED** — always use the fastest available model
- **BALANCED** — weighted composite of quality and speed scores

#### Dual Router Architecture

Portal uses two separate routers for different client paths:

| Router | Port | Purpose | Client |
|--------|------|---------|--------|
| **Proxy Router** | `:8000` | Ollama proxy with workspace and regex routing | Open WebUI, LibreChat |
| **IntelligentRouter** | `:8081` | Task complexity classification, serves Portal API | Portal interfaces (Web, Telegram, Slack) |

The Proxy Router at `:8000` acts as a transparent pass-through to Ollama with regex-based model selection via `router_rules.json`. It serves external web UIs that expect an Ollama-compatible endpoint.

The IntelligentRouter at `:8081` is Portal's own routing that uses `TaskClassifier` (100+ regex patterns) to classify task complexity and category, then selects the optimal model. It serves the Portal API and chat interfaces.

This separation allows external web UIs to use Ollama directly while Portal's own interfaces get intelligent routing. Future unification is a Track B opportunity (see ROADMAP.md for LLM-based Intelligent Routing).

#### Dynamic Ollama Discovery

`ModelRegistry.discover_from_ollama()` queries the Ollama `/api/tags` endpoint
at startup (and on demand) and auto-registers every locally-pulled model with
inferred capability tags and speed class.  No manual model list is required —
pulling a new model into Ollama makes it immediately available to the router.

#### BaseHTTPBackend

`OllamaBackend` and `LMStudioBackend` both inherit from `BaseHTTPBackend`
(`src/portal/routing/model_backends.py`), which manages a shared `aiohttp`
`ClientSession` with connection pooling, configurable timeouts, and
circuit-breaker state.  `MLXBackend` is a separate in-process backend for
Apple Silicon.

---

### Interface Registry (`src/portal/agent/dispatcher.py`)

Portal uses a dictionary-based `CentralDispatcher` registry instead of
hard-coded `if interface == "web"` dispatch:

```python
from portal.agent.dispatcher import CentralDispatcher

# Interfaces self-register at class-definition time:
@CentralDispatcher.register("web")
class WebInterface(BaseInterface): ...

@CentralDispatcher.register("telegram")
class TelegramInterface: ...

# Lookup at runtime:
iface_cls = CentralDispatcher.get("web")   # → WebInterface
# Raises UnknownInterfaceError for unregistered names
```

`CentralDispatcher.registered_names()` returns a sorted list of all registered
interface names.

---

### Configuration (`src/portal/config/`)

#### `settings.py` — canonical runtime config (`BaseSettings`)

Loaded at startup by `lifecycle.py` via `load_settings()`.
Environment variables use prefix `PORTAL_` with double-underscore nesting:

```
PORTAL_BACKENDS__OLLAMA_URL=http://localhost:11434
PORTAL_INTERFACES__TELEGRAM__BOT_TOKEN=123456:ABC...
PORTAL_INTERFACES__SLACK__BOT_TOKEN=xoxb-...
PORTAL_INTERFACES__SLACK__SIGNING_SECRET=abc123
PORTAL_SECURITY__SANDBOX_ENABLED=false
```

`Settings.to_agent_config()` converts a `Settings` instance into the plain
dict that `DependencyContainer` and `create_agent_core()` consume.

#### Hardware profiles

| Profile | Directory | COMPUTE_BACKEND |
|---------|-----------|-----------------|
| M4 Mac (Mini Pro / Max) | `hardware/m4-mac/` | `mps` |
| Linux bare-metal (NVIDIA) | `hardware/linux-bare/` | `cuda` |
| CPU-only / WSL2 | — | `cpu` |

Each profile ships an environment file that sets hardware-specific variables
(compute backend, Docker host IP, supervisor type, etc.).

#### Zero-Config Bootstrap

`launch.sh` (repository root) provides a guided first-run experience that
layers on top of the per-platform scripts — those remain fully available for
direct use.

1. **Hardware detection:** `uname -s` for OS, `/proc/version` grep for WSL2
2. **Interactive setup:** Web UI choice (1 question), optional Telegram/Slack
3. **Secret generation:** 6 cryptographic keys via `openssl rand -base64 32`
4. **`.env` written:** All values filled, hardware defaults applied

On subsequent runs, `launch.sh up` sources the existing `.env` and starts
services without any prompts.

| Subcommand | Purpose |
|---|---|
| `launch.sh up [--minimal] [--profile X]` | Start all services (bootstrap on first run) |
| `launch.sh down` | Graceful stop of all services |
| `launch.sh doctor` | Health check all components |
| `launch.sh logs [service]` | Tail service logs from `~/.portal/logs/` |
| `launch.sh status` | One-line service overview |
| `launch.sh reset-secrets` | Rotate all 6 auto-generated keys |

Override hardware detection with `PORTAL_HARDWARE=<profile>` or `--profile`.

---

### MCP Layer (`src/portal/protocols/mcp/`)

Portal integrates with the [Model Context Protocol](https://modelcontextprotocol.io)
to give the AI access to external tools and data sources.

```
AgentCore._dispatch_mcp_tools()
    └─► MCPRegistry.call_tool(server, tool, arguments)
            └─► HTTP POST {server_url}/{tool_name}   [openapi transport]
            └─► HTTP POST {server_url}/call           [streamable-http]
```

#### `MCPRegistry` (`src/portal/protocols/mcp/mcp_registry.py`)

- Registers MCP servers by name and transport type
- `health_check(name)` — probes the server's OpenAPI or root endpoint
- `list_tools(server_name)` — discovers tools from OpenAPI spec
- `call_tool(server_name, tool_name, arguments)` — executes a tool

**Retry transport (v1.1):** All HTTP calls in `MCPRegistry` route through the
private `_request()` helper which adds up to 3 automatic retries with
exponential backoff (1 s → 2 s → 4 s) for transient
`ConnectError / TimeoutException / RemoteProtocolError`.  The underlying
`httpx.AsyncClient` also uses `AsyncHTTPTransport(retries=3)` at the TCP level.

**Note:** The `openapi` transport endpoint format
`{server_url}/{tool_name}` needs verification against a live mcpo instance.
If mcpo mounts servers under a prefix, register the server at the prefixed
sub-URL (e.g. `http://localhost:9000/filesystem`) so the path resolves to
`http://localhost:9000/filesystem/read_file`.

#### MCP servers shipped with Portal

| Server | Transport | Purpose |
|--------|-----------|---------|
| `core` | mcpo/openapi | Filesystem, Time (via mcpo proxy at :9000) |
| `scrapling` | streamable-http | Web scraping via Scrapling at :8900 |
| ComfyUI | openapi | Image generation at :8188 |
| Whisper | openapi | Audio transcription at :5002 |

MCP dispatch into `AgentCore.process_message()` is fully wired: `OllamaBackend.generate()`
surfaces `tool_calls` from the LLM response and `AgentCore._dispatch_mcp_tools()` routes
them to `MCPRegistry`.

---

### Observability (`src/portal/observability/`)

| Component | Purpose |
|-----------|---------|
| `Watchdog` | Health-checks registered components; auto-restarts on failure |
| `LogRotator` | Time- and size-based log rotation with optional gzip compression |
| `metrics.py` | Prometheus metrics endpoint (`:9090/metrics`) |
| `config_watcher.py` | File-system watcher for live config reloads |

---

### Security (`src/portal/security/`)

| Component | Purpose |
|-----------|---------|
| `SecurityMiddleware` | Wraps AgentCore; applies rate limiting and input sanitisation |
| `SecurityModule` | Prompt injection detection, PII scrubbing, output sanitisation |
| `RateLimiter` | SQLite-backed per-user request throttling |
| `DockerPythonSandbox` | Runs untrusted code in an isolated container |

#### Security Hardening

##### Content Security Policy

The default CSP includes `'unsafe-inline' 'unsafe-eval'` for Open WebUI
compatibility. For deployments without a web UI frontend (API-only), set a
strict CSP via environment variable:

```bash
PORTAL_CSP="default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'"
```

##### Bootstrap API Key

`PORTAL_BOOTSTRAP_API_KEY` is **required** in production. The application
refuses to start when this is unset or left at the default `portal-dev-key`
value (unless `PORTAL_ENV=development` is set, which is automatically applied
by `docker-compose.override.yml`).

Generate a strong key before first deployment:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

### Middleware (`src/portal/middleware/`)

#### `ToolConfirmationMiddleware`

Human-in-the-loop gate for high-risk tool executions.

```
Tool request → middleware.request_confirmation()
    → sends Approve/Deny keyboard to Telegram admin
    → waits (async, up to timeout) for admin response
    → returns True (approved) or False (denied/timeout)
```

Exported from `portal.middleware` alongside `ConfirmationRequest` and
`ConfirmationStatus`.

#### `HITLApprovalMiddleware` (`src/portal/middleware/hitl_approval.py`)

Redis-backed approval tokens for blocking tool calls that require explicit
human approval (e.g. `bash`, `filesystem_write`, `web_fetch`).

```
AgentCore._dispatch_mcp_tools()
    └─► hitl_middleware.request(user_id, channel, tool_name, args)
            → stores "pending" token in Redis (60 s TTL)
            → notifies operator via DangerNotifier callback
    └─► hitl_middleware.check_approved(user_id, token)
            → returns True only if operator set token to "approved"
```

The `redis` package is a soft dependency; Portal boots cleanly without it.
When Redis is unavailable, `HITLApprovalMiddleware.redis` raises a
`RuntimeError` with install instructions rather than an `ImportError` at
module load time.

---

### CLI (`src/portal/cli.py`)

Entry point: `portal` (registered in `pyproject.toml`).

| Command | Description |
|---------|-------------|
| `portal up [--minimal] [--skip-port-check]` | Bootstrap and start all configured interfaces |
| `portal down` | Graceful shutdown |
| `portal doctor` | Health-check each component and print structured status |
| `portal logs [SERVICE]` | Tail Portal logs; optionally specify a service name (follows `~/.portal/logs/{service}.log`) |

---

## Data Flow — Single Request

```
1. User sends message via Open WebUI
       ↓
2. WebInterface receives POST /v1/chat/completions
   Builds IncomingMessage(id=uuid, text=..., model=..., source="web")
       ↓
3. AgentCore.process_message(chat_id, message, InterfaceType.WEB)
   a. Loads context history (ContextManager)
   b. Saves user message immediately (crash-safety)
   c. Builds system prompt (PromptManager)
   d. Routes query → ModelDecision (IntelligentRouter)
   e. Calls LLM (ExecutionEngine → Ollama /api/chat)
   f. If LLM returns tool calls → _dispatch_mcp_tools() → MCPRegistry
   g. Saves assistant response
   h. Returns ProcessingResult(response=..., model_used=..., ...)
       ↓
4. WebInterface streams ProcessingResult.response as SSE chunks
   (real per-token streaming via ExecutionEngine.generate_stream())
       ↓
5. Open WebUI renders the response
```

---

## Startup Sequence (`lifecycle.py`)

```
Runtime.bootstrap()
  1. load_settings()             — YAML + PORTAL_* env vars
  2. Guard: MCP_API_KEY ≠ "changeme-mcp-secret"
  3. Guard: PORTAL_BOOTSTRAP_API_KEY set in production
  4. create_event_broker()       — in-memory event history
  5. create_agent_core(          — DependencyContainer builds all deps
       settings.to_agent_config()  — converts Settings → plain dict
     )
  6. SecurityMiddleware(agent_core)
  7. Watchdog.start()            — optional; controlled by config
  8. LogRotator.start()          — optional; controlled by config
  9. ConfigWatcher.start()       — asyncio task if portal.yaml exists
 10. Signal handlers registered  — SIGINT / SIGTERM → graceful shutdown
```

Shutdown is priority-ordered (CRITICAL → HIGH → NORMAL → LOW → LOWEST)
with per-callback timeouts and active-task draining.

---

## Directory Structure

```
portal/
├── src/portal/
│   ├── __init__.py             version = "1.3.4"
│   ├── cli.py
│   ├── lifecycle.py
│   ├── agent/
│   │   ├── __init__.py         re-exports CentralDispatcher, UnknownInterfaceError
│   │   └── dispatcher.py       CentralDispatcher registry + @register decorator
│   ├── config/
│   │   └── settings.py         BaseSettings (canonical runtime config)
│   ├── core/
│   │   ├── __init__.py         canonical public API (AgentCore, exceptions, types)
│   │   ├── agent_core.py       AgentCore + module-level create_agent_core()
│   │   ├── factories.py        DependencyContainer
│   │   ├── types.py            IncomingMessage, ProcessingResult, InterfaceType
│   │   ├── context_manager.py
│   │   ├── event_bus.py
│   │   ├── prompt_manager.py
│   │   └── interfaces/
│   │       └── agent_interface.py   BaseInterface (canonical)
│   ├── interfaces/
│   │   ├── base.py             re-export of agent_interface.BaseInterface
│   │   ├── web/server.py       WebInterface (FastAPI, @CentralDispatcher.register("web"))
│   │   ├── telegram/interface.py  (@CentralDispatcher.register("telegram"))
│   │   └── slack/interface.py     (@CentralDispatcher.register("slack"))
│   ├── memory/
│   │   └── manager.py          MemoryManager
│   ├── routing/
│   │   ├── model_registry.py   ModelRegistry + discover_from_ollama()
│   │   ├── intelligent_router.py
│   │   ├── model_backends.py   BaseHTTPBackend, OllamaBackend (MLX/LMStudio planned)
│   │   └── execution_engine.py
│   ├── protocols/mcp/
│   │   └── mcp_registry.py     MCPRegistry with retry transport
│   ├── middleware/
│   │   ├── __init__.py         exports ToolConfirmationMiddleware
│   │   ├── hitl_approval.py    HITLApprovalMiddleware (Redis-backed)
│   │   └── tool_confirmation_middleware.py
│   ├── security/
│   ├── observability/
│   └── tools/
├── tests/
│   ├── conftest.py             shared fixtures + pytest configuration
│   ├── unit/
│   │   ├── test_bootstrap.py   startup smoke tests
│   │   ├── test_slack_hmac.py  HMAC verification tests
│   │   ├── tools/              per-tool unit tests
│   │   └── ...
│   ├── integration/
│   └── e2e/
├── docs/
│   └── ARCHITECTURE.md         this file
├── hardware/
│   └── m4-mac/
├── mcp/                        MCP server definitions
├── deploy/                     docker-compose stacks
├── Dockerfile
└── pyproject.toml
```

---

## Status & Remaining Work

| Issue | Status |
|-------|--------|
| Token streaming (true per-token from Ollama) | **Done** — `ExecutionEngine.generate_stream()` calls Ollama `/api/chat` with `stream: true` and yields tokens as they arrive |
| MCP tool-use loop in AgentCore | **Done** — `OllamaBackend.generate()` uses `/api/chat`; `tool_calls` surface via `ExecutionResult`; `AgentCore._dispatch_mcp_tools()` dispatches them to `MCPRegistry` |
| Security headers on WebInterface | **Done** — `SecurityHeadersMiddleware` adds CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy; HSTS opt-in via `PORTAL_HSTS=1`. **Note:** The default CSP includes `'unsafe-inline' 'unsafe-eval'` for compatibility with Open WebUI's JavaScript. Production deployments that do not use a web UI frontend should override via `PORTAL_CSP` env var with a stricter policy. |
| API-key guard on /v1/* routes | **Done** — `WEB_API_KEY` env var enables `_verify_api_key` dependency; must be set before any non-localhost exposure |
| mcpo endpoint format verification | Phase 3 — see note in `mcp_registry.py` |
| Slack E2E test (needs ngrok/Cloudflare) | Phase 3 |
| ComfyUI / Whisper MCP integration tests | Phase 3 |
| LaunchAgent plist for M4 autostart | Phase 3 |
| `portal doctor` structured output | Phase 3 |

### v1.3.3 Code Health Drive (Feb 2026)
- Test coverage expansion: 49% → 70%+ (372 → 828 tests after shrink rationalization)
- Refactored agent_core.py: extracted 7 helpers from 3 oversized methods
- Added return type hints to 230+ functions across entire codebase
- Converted 171 f-string logging calls to lazy % formatting
- Removed dead code: `__name__` blocks, backward-compat wrappers, example functions
- Documentation version sync (ARCHITECTURE.md, CHANGELOG.md)

### v1.2.2 Code Quality Pass (Feb 2026)
- Python 3.11+ modernization: removed `importlib_metadata` fallback
- Replaced `os.path` → `pathlib` in security module
- Fixed `TelegramInterface._check_rate_limit()` async/sync mismatch
- Hardened `InputSanitizer.validate_file_path()` — uses `Path.relative_to()` instead of `str.startswith()`
- Fixed log rotation crash in sync context (missing event loop)
- Fixed hardcoded version in Prometheus metrics
- Added missing `ToolMetadata.async_capable` field
- Aligned `ToolCategory` constants across registry and config

### v1.2.1 Modernization (Feb 2026)
- Removed ~3,200 lines dead/stale code across 11+ files and directories
- Security hardened: bash sidecar (`shell=True` → allowlist), `eval()` → AST, pickle gating, secret redaction in logger, Docker sandbox resource limits + network isolation
- Flattened `media_tools/audio/` unnecessary nesting
- Removed half-integrated tracer module (rewire when OTLP endpoint is configured)
- Fixed 4 confirmed bugs: `TelegramInterface` broken entrypoint, `lifecycle.py` Path coercion, `docker_sandbox.py` broken import, `ToolRegistry` dict/list parameter crash
