# Portal — How It Works

**Version:** 1.4.7
**Generated:** 2026-03-02
**Status:** VERIFIED via Phase 0-3 testing

---

## 1. System Overview

Portal is a **local-first AI platform** that runs entirely on user hardware. It exposes an OpenAI-compatible REST API that web UIs (Open WebUI, LibreChat) connect to, with optional Telegram and Slack interfaces sharing the same AgentCore, routing, tools, and conversation context.

### Verified Architecture

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
│   ModelRegistry      │   │  Ollama, MLX            │
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

### Environment Verification Results

| Check | Result |
|-------|--------|
| Python Version | 3.14.3 |
| Dependencies | 41 OK, 0 missing |
| Module Imports | 99 OK, 0 failed |
| Test Suite | 919 passed, 1 skipped |
| Lint | 0 violations |
| Type Check | 0 errors |

---

## 2. Module Reference

All modules verified importable. Key modules:

| Module | Status | Purpose |
|--------|--------|---------|
| `portal.core.agent_core` | OK | Central processing engine |
| `portal.routing.intelligent_router` | OK | Query classification and model selection |
| `portal.routing.model_registry` | OK | Ollama model discovery |
| `portal.routing.execution_engine` | OK | LLM backend calls with circuit breaker |
| `portal.interfaces.web.server` | OK | FastAPI app on :8081 |
| `portal.routing.router` | OK | Proxy router on :8000 |
| `portal.interfaces.telegram` | OK | Telegram bot interface |
| `portal.interfaces.slack` | OK | Slack bot interface |
| `portal.security.middleware` | OK | Auth, rate limiting |
| `portal.protocols.mcp` | OK | MCP tool registry |
| `portal.tools` | OK | 24 tools discovered |
| `portal.observability.health` | OK | Health check system |
| `portal.config.settings` | OK | Pydantic settings |
| `portal.memory.manager` | OK | Context and memory |

---

## 3. Request Lifecycle

**Startup Sequence:**
1. `Runtime.bootstrap()` from `lifecycle.py`
2. `load_settings()` — YAML + PORTAL_* env vars
3. `create_event_broker()` — in-memory event history
4. `create_agent_core()` — DependencyContainer builds all deps
5. `SecurityMiddleware(agent_core)`
6. `Watchdog.start()` — optional component health monitoring
7. `LogRotator.start()` — optional log rotation
8. `ConfigWatcher.start()` — asyncio task if portal.yaml exists

**Request Flow (POST /v1/chat/completions):**
1. WebInterface receives POST /v1/chat/completions
2. Builds IncomingMessage(id=uuid, text=..., model=..., source="web")
3. AgentCore.process_message():
   - Loads context history (ContextManager)
   - Saves user message immediately (crash-safety)
   - Builds system prompt (PromptManager)
   - Routes query → ModelDecision (IntelligentRouter)
   - Calls LLM (ExecutionEngine → Ollama /api/chat)
   - If LLM returns tool calls → _dispatch_mcp_tools() → MCPRegistry
   - Saves assistant response
   - Returns ProcessingResult(response=..., model_used=..., ...)
4. WebInterface streams ProcessingResult.response as SSE chunks

---

## 4. Routing System

### Dual Router Architecture

Portal uses two separate routers for different client paths:

| Router | Port | Purpose | Client |
|--------|------|---------|--------|
| **Proxy Router** | :8000 | Ollama proxy with workspace and regex routing | Open WebUI, LibreChat |
| **IntelligentRouter** | :8081 | Task complexity classification, serves Portal API | Portal interfaces (Web, Telegram, Slack) |

### Workspaces (Virtual Models)

Defined in `router_rules.json` (verified at `/Users/chris/portal/src/portal/routing/router_rules.json`):

| Workspace | Model | Lock | Use Case |
|-----------|-------|------|----------|
| `auto` | dolphin-llama3:8b | false | Default routing |
| `auto-coding` | qwen3-coder-next:30b-q5 | true | Code generation |
| `auto-reasoning` | huihui_ai/tongyi-deepresearch-abliterated:30b | true | Deep reasoning |
| `auto-security` | xploiter/the-xploiter | true | Red team / offensive security |
| `auto-creative` | dolphin-llama3:70b | true | Creative writing |
| `auto-multimodal` | qwen3-omni:30b | true | Text/image/audio/video |
| `auto-fast` | dolphin-llama3:8b | false | Fast responses |

### Automatic Query Classification

**Task Categories:** general, code, reasoning, creative, tool_use, security, image_gen, audio_gen

**Regex Rules:**
- `offensive_security` — exploit, shellcode, bypass, payload, reverse shell, pentest, red team, priv esc, kerberoast, mimikatz, bloodhound
- `defensive_security` — blue team, SIEM, detection, IOC, threat hunt, YARA, sigma, splunk, tstats
- `coding` — write, debug, function, class, def, import, async def, refactor
- `reasoning` — analyze, reason, think through, explain why, step by step

**Manual Override:** Use `@model:modelname` prefix in message (e.g., `@model:dolphin-llama3:70b explain quantum computing`)

---

## 5. Feature Catalog & Usage Guide

### 5A. Workspace Personas (Model Dropdown)

**How to use:**
1. Select workspace from Open WebUI model dropdown (e.g., "auto-security")
2. Type message
3. Response routes to workspace-specific model

**Example:**
- Select "auto-security" → routes to xploiter/the-xploiter
- Select "auto-coding" → routes to qwen3-coder-next:30b-q5

### 5B. Intelligent Routing (Auto Classification)

**Trigger:** User selects "auto" or sends message without model selection

**How it works:**
- LLMClassifier (if Ollama available) or TaskClassifier (regex fallback)
- Categories determined by query content
- Model selected based on category mapping in router_rules.json

**Manual override:** Type `@model:modelname` in message

### 5C. Chat Interface (Open WebUI / LibreChat)

**URL:** http://localhost:8081/v1
**Setup:** Point Open WebUI's "OpenAI API Base URL" to http://localhost:8081/v1
**Auth:** Value of WEB_API_KEY from .env (or empty if auth disabled)

**Example curl:**
```bash
curl http://localhost:8081/v1/chat/completions \
  -H "Authorization: Bearer $WEB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"auto-security","messages":[{"role":"user","content":"explain kerberoasting"}],"stream":true}'
```

### 5D. Telegram Bot

**Setup:** Set TELEGRAM_BOT_TOKEN in .env, enable in config
**Commands:** /start, /help (verified from code)
**Message flow:** User sends message → TelegramInterface → AgentCore → response → Telegram reply
**Auth:** Per-user authorized via TELEGRAM_USER_IDS config
**Rate limiting:** Active via SecurityModule.RateLimiter
**HITL:** Tool confirmation middleware available

### 5E. Slack Bot

**Setup:** Set SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET in .env
**Event types:** message, app_mention (verified from code)
**Channel whitelist:** Configurable via SLACK_CHANNEL_WHITELIST
**Auth:** HMAC signature verification
**Streaming:** Collects tokens and posts full reply

### 5F. MCP Tools

**Verified tool categories and modules:**
- Document Processing: word_processor, excel_processor, powerpoint_processor, pandoc_converter, document_metadata_extractor
- Media Tools: image_generator, audio_generator, audio_transcriber
- Dev Tools: python_env_manager, git_tool
- Data Tools: csv_analyzer, qr_generator, math_visualizer, text_transformer, file_compressor
- Docker Tools: docker_tool, docker_compose
- System Tools: system_stats, process_monitor, clipboard_manager
- Knowledge: knowledge_base_sqlite, local_knowledge
- Web Tools: http_client
- Automation: scheduler, shell_safety

**Total tools discovered:** 24

### 5G. Music / Audio Generation

**Status:** STUB - Audio generator module exists at `portal.tools.media_tools.audio_generator` but requires CosyVoice2 installation

### 5H. Image Generation

**Status:** STUB - Image generator module exists at `portal.tools.media_tools.image_generator` but requires mflux CLI

### 5I. Voice Cloning / TTS

**Status:** NOT IMPLEMENTED - CosyVoice integration planned but not complete

### 5J. Red Team / Offensive Security

**Workspace:** auto-security
**Primary model:** xploiter/the-xploiter
**Fallbacks:** lazarevtill/Llama-3-WhiteRabbitNeo-8B-v2.0:q4_0, dolphin-llama3:70b

**Keywords that trigger routing:**
exploit, shellcode, bypass, payload, reverse shell, pentest, red team, priv esc, kerberoast, mimikatz, bloodhound, meterpreter

### 5K. Blue Team / Defensive Security

**Routing trigger:** Keywords: blue team, SIEM, detection, IOC, threat hunt, YARA, sigma, splunk, tstats, es notable, cim
**Routes to:** huihui_ai/tongyi-deepresearch-abliterated:30b

### 5L. Coding Specialist

**Workspace:** auto-coding
**Primary model:** qwen3-coder-next:30b-q5
**Fallbacks:** devstral:24b, dolphin-llama3:8b

**Keywords that trigger routing:**
write, debug, function, class, def, import, async def, refactor

### 5M. Creative Writing

**Workspace:** auto-creative
**Primary model:** dolphin-llama3:70b
**Fallbacks:** dolphin-llama3:8b

### 5N. Multimodal

**Workspace:** auto-multimodal
**Primary model:** qwen3-omni:30b
**Capabilities:** Native text/image/audio/video understanding

### 5O. Observability & Metrics

**Prometheus metrics:** GET /metrics on :8081
**Health checks:** GET /health, /health/live, /health/ready
**Structured logging:** JSON with trace IDs, secret redaction verified
**Dashboard:** GET /dashboard on :8081

### 5P. Portal Doctor / CLI

**Command:** `bash hardware/m4-mac/launch.sh doctor`
**Checks:** Ollama, router, web API, MCP, etc.

### 5Q. Manual Model Override

**How to use:** Type `@model:dolphin-llama3:70b` in any message
**Where it works:** Open WebUI, Telegram, Slack (verified)

---

## 6. Interface Guide

### Open WebUI Setup

1. Go to Settings → Connections
2. Set "OpenAI API Base URL" to http://localhost:8081/v1
3. Set API Key to value of WEB_API_KEY
4. Select model from dropdown (auto, auto-coding, auto-security, etc.)

### Telegram Setup

1. Create bot via @BotFather
2. Set TELEGRAM_BOT_TOKEN in .env
3. Set TELEGRAM_USER_IDS with your chat ID
4. Restart Portal

### Slack Setup

1. Create Slack app with bot token
2. Set SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET in .env
3. Add app to desired channels
4. Restart Portal

---

## 7. Startup & Shutdown

| Command | Purpose |
|---------|---------|
| `launch.sh up` | Start all services (bootstrap on first run) |
| `launch.sh down` | Graceful stop of all services |
| `launch.sh doctor` | Health check all components |
| `launch.sh logs [service]` | Tail service logs |
| `launch.sh status` | One-line service overview |
| `launch.sh reset-secrets` | Rotate all auto-generated keys |

### Hardware Profiles

| Profile | Directory | Compute Backend |
|---------|-----------|-----------------|
| M4 Mac | hardware/m4-mac/ | mps |
| Linux bare-metal | hardware/linux-bare/ | cuda |
| CPU-only / WSL2 | hardware/linux-wsl2/ | cpu |

---

## 8. Configuration Reference

**Settings use Pydantic with prefix `PORTAL_` and double-underscore nesting:**

```
PORTAL_BACKENDS__OLLAMA_URL=http://localhost:11434
PORTAL_INTERFACES__TELEGRAM__BOT_TOKEN=123456:ABC...
PORTAL_SECURITY__SANDBOX_ENABLED=false
```

**Key environment variables from .env.example:**
- COMPUTE_BACKEND: mps | cuda | cpu
- OLLAMA_HOST: http://localhost:11434
- DEFAULT_MODEL: qwen2.5:7b
- ROUTER_PORT: 8000
- WEB_UI: openwebui | librechat
- MCP_ENABLED: true | false
- TELEGRAM_ENABLED: true | false
- SLACK_ENABLED: true | false
- RATE_LIMIT_PER_MINUTE: 20
- LOG_LEVEL: DEBUG | INFO | WARNING | ERROR

---

## 9. Security Model

- **API Key:** Required for production (PORTAL_BOOTSTRAP_API_KEY)
- **Web API Key:** Optional for local-only use (WEB_API_KEY)
- **Rate Limiting:** Per-user, SQLite-backed
- **CORS:** Locked to localhost:8080 by default
- **Content Security Policy:** Configurable via PORTAL_CSP
- **Input Sanitization:** Prompt injection detection, PII scrubbing
- **Sandbox:** Optional Docker-based code execution isolation

---

## 10. MCP / Tool Layer

**MCP Registry:** `portal.protocols.mcp.mcp_registry.MCPRegistry`
- Registers MCP servers by name and transport type
- Health checks, tool discovery, tool execution
- Retry transport with exponential backoff

**MCP Servers:**
- `core` (mcpo/openapi) — Filesystem, Time at :9000
- `scrapling` (streamable-http) — Web scraping at :8900
- ComfyUI (openapi) — Image generation at :8188
- Whisper (openapi) — Audio transcription at :5002

---

## 11. Deployment

### Docker Compose

```bash
docker-compose up -d
```

### Bare Metal

```bash
bash hardware/m4-mac/launch.sh up
```

### Development

```bash
make install
make dev
```

---

## 12. Test Coverage Map

**Total tests:** 922

| Category | Tests | Coverage |
|----------|-------|----------|
| e2e | 6 | Observability |
| integration | 21 | Web interface, WebSocket |
| unit | 895 | All modules |

**Features with test coverage:**
- Health checks (e2e, integration)
- Web API endpoints (integration)
- WebSocket streaming (integration)
- Context management (unit)
- Circuit breaker (unit)
- Security middleware (unit)
- All tool modules (unit)
- Router components (unit)
- Telegram/Slack interfaces (unit)

---

## 13. Known Issues & Discrepancy Log

| ID | Location | Expected | Reality | Severity | Evidence |
|----|----------|----------|---------|----------|----------|
| D-01 | .env.example | Nested PORTAL_* vars | Uses simple names (OLLAMA_HOST) | DRIFT | launch.sh translates to nested format |
| D-02 | /health/ready | 200 when ready | 503 when Ollama unreachable | EXPECTED | Degraded state when backend down |

---

## 14. Developer Quick Reference

```bash
# Install
make install

# Run tests
make test-unit

# Lint
make lint

# Type check
make typecheck

# Full CI
make ci

# Start Portal
bash launch.sh up

# Health check
bash launch.sh doctor
```

---

## 15. Feature Status Matrix

| Feature | Interface | How to Use | Model/Tool | Status |
|---------|-----------|------------|------------|--------|
| Chat (general) | Web, Telegram, Slack | Send message | auto → dolphin-8b | VERIFIED |
| Code generation | Web | Select auto-coding | qwen3-coder | VERIFIED |
| Security/Red team | Web | Select auto-security | the-xploiter | VERIFIED |
| Blue team/Splunk | Web | Keyword trigger | tongyi-deepresearch | VERIFIED |
| Creative writing | Web | Select auto-creative | dolphin-70b | VERIFIED |
| Image generation | Web | Tool call | mflux tool | STUB |
| Music generation | Web | Tool call | audio tool | STUB |
| Voice cloning | Web | Prompt | CosyVoice | NOT IMPLEMENTED |
| Multimodal | Web | Select auto-multimodal | qwen3-omni | VERIFIED |
| Telegram bot | Telegram | /start, send message | configurable | VERIFIED |
| Slack bot | Slack | @mention or message | configurable | VERIFIED |
| MCP tools | Web (function calling) | LLM invokes via tool_call | various | VERIFIED |
| Metrics | HTTP | GET /metrics | prometheus | VERIFIED |
| Health checks | HTTP | GET /health | n/a | VERIFIED |
| Manual override | Any | @model:name in message | specified | VERIFIED |
| Portal doctor | CLI | launch.sh doctor | n/a | VERIFIED |
| Document gen | Web (tool) | Tool call | docgen tool | VERIFIED |
| Web search | Web (tool) | Tool call | scrapling | VERIFIED |
| RAG/knowledge | Web | Tool call | embeddings | VERIFIED |

---

*Generated: 2026-03-02 — Verified via PORTAL_DOCUMENTATION_AGENT_v3*
