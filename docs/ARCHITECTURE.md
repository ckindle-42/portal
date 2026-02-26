# Portal Architecture

**Version:** 1.0.3
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
│  ToolRegistry     MCPRegistry (ARCH-3)               │
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
`src/portal/interfaces/base.py` is a convenience re-export of that class.

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
| `ModelRegistry` | Catalogue of local models with capability tags and speed classes |
| `IntelligentRouter` | Classifies query complexity and selects optimal model |
| `RoutingStrategy` | `AUTO` / `QUALITY` / `SPEED` / `BALANCED` |
| `ExecutionEngine` | Calls Ollama / LMStudio / MLX; circuit-breaker per backend |

Routing strategies:
- **AUTO** — automatic complexity-based selection (default)
- **QUALITY** — always use the most capable available model
- **SPEED** — always use the fastest available model
- **BALANCED** — weighted composite of quality and speed scores

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

#### `settings_schema.py` — extended schema for Portal-specific config

Defines `SettingsSchema` with nested objects for hardware profiles, MCP
transport, and observability.  Used as a reference for future migration of
`settings.py` to a fully nested Pydantic v2 model (Phase 2+).

#### Hardware profiles

| Profile | Directory |
|---------|-----------|
| M4 Mac | `hardware/m4-mac/` |
| RTX 5090 Linux | `hardware/linux-rtx5090/` |

Each profile ships an environment file that sets hardware-specific variables
(compute backend, Docker host IP, supervisor type, etc.).

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

**QUAL-3 note:** The `openapi` transport endpoint format
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

MCP dispatch into `AgentCore.process_message()` is wired (ARCH-3) and
ready; full tool-use loop requires `ExecutionEngine` to surface tool-call
entries from the LLM response (Phase 2 work).

---

### Observability (`src/portal/observability/`)

| Component | Purpose |
|-----------|---------|
| `WatchdogMonitor` | Health-checks registered components; auto-restarts on failure |
| `LogRotator` | Time- and size-based log rotation with optional gzip compression |
| `metrics.py` | Prometheus metrics endpoint (`:9090/metrics`) |
| `tracer.py` | OpenTelemetry tracing (optional; configure OTLP endpoint) |
| `config_watcher.py` | File-system watcher for live config reloads |

---

### Security (`src/portal/security/`)

| Component | Purpose |
|-----------|---------|
| `SecurityMiddleware` | Wraps AgentCore; applies rate limiting and input sanitisation |
| `SecurityModule` | Prompt injection detection, PII scrubbing, output sanitisation |
| `RateLimiter` | SQLite-backed per-user request throttling |
| `DockerSandbox` | Runs untrusted code in an isolated container |

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

---

### Persistence (`src/portal/persistence/`)

| Implementation | Notes |
|----------------|-------|
| `SQLiteImpl` | Default; per-conversation history in `data/context.db` |
| `InMemoryImpl` | Testing and ephemeral sessions |

---

### CLI (`src/portal/cli.py`)

Entry point: `portal` (registered in `pyproject.toml`).

| Command | Description |
|---------|-------------|
| `portal up` | Bootstrap and start all configured interfaces |
| `portal down` | Graceful shutdown |
| `portal doctor` | Health-check each component and print structured status |
| `portal status` | Show current runtime stats |
| `portal config` | Display resolved configuration |

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
  2. create_event_broker()       — in-memory event history
  3. create_agent_core(          — DependencyContainer builds all deps
       settings.to_agent_config()  — converts Settings → plain dict
     )
  4. SecurityMiddleware(agent_core)
  5. Watchdog.start()            — optional; controlled by config
  6. LogRotator.start()          — optional; controlled by config
  7. Signal handlers registered  — SIGINT / SIGTERM → graceful shutdown
```

Shutdown is priority-ordered (CRITICAL → HIGH → NORMAL → LOW → LOWEST)
with per-callback timeouts and active-task draining.

---

## Directory Structure

```
portal/
├── src/portal/
│   ├── __init__.py             version = "1.0.x"
│   ├── cli.py
│   ├── lifecycle.py
│   ├── config/
│   │   ├── settings.py         BaseSettings (canonical runtime config)
│   │   └── schemas/
│   │       └── settings_schema.py  SettingsSchema (extended Portal config)
│   ├── core/
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
│   │   ├── web/server.py       WebInterface (FastAPI)
│   │   ├── telegram/interface.py
│   │   └── slack/interface.py
│   ├── routing/
│   │   ├── model_registry.py
│   │   ├── intelligent_router.py
│   │   └── execution_engine.py
│   ├── protocols/mcp/
│   │   ├── mcp_registry.py
│   │   ├── mcp_connector.py
│   │   └── mcp_server.py
│   ├── middleware/
│   │   ├── __init__.py         exports ToolConfirmationMiddleware
│   │   └── tool_confirmation_middleware.py
│   ├── security/
│   ├── observability/
│   ├── persistence/
│   └── tools/
├── tests/
│   ├── unit/
│   │   ├── test_bootstrap.py   startup smoke tests (QUAL-5)
│   │   ├── test_slack_hmac.py  HMAC verification tests (CRIT-5)
│   │   └── ...
│   └── integration/
├── docs/
│   └── ARCHITECTURE.md         this file
├── hardware/
│   ├── m4-mac/
│   └── linux-rtx5090/
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
| mcpo endpoint format verification | Phase 3 — see QUAL-3 note in `mcp_registry.py` |
| Slack E2E test (needs ngrok/Cloudflare) | Phase 3 |
| ComfyUI / Whisper MCP integration tests | Phase 3 |
| LaunchAgent plist for M4 autostart | Phase 3 |
| `portal doctor` structured output | Phase 3 |
