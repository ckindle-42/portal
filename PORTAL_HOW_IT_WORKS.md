# Portal — How It Works

**Version:** 1.4.7
**Updated:** 2026-03-02
**Verification:** Full test suite passed (933 passed, 1 skipped)

---

## 1. System Overview

Portal is a **total inclusive offline AI platform** that runs entirely on user hardware — no cloud required, no data leaves the machine. It exposes an OpenAI-compatible REST API that web UIs (Open WebUI, LibreChat) connect to, with optional Telegram and Slack interfaces sharing the same AgentCore, routing, tools, and conversation context.

**Mission:** Replace cloud AI subscriptions with a fully local platform covering text generation, code, security analysis, image creation, video creation, music generation, document production, research, and more — all private, all local.

**Hardware targets:** Apple M4 (primary), NVIDIA CUDA (Linux), CPU/WSL2.

### Verified Health Status

| Component | Status | Evidence |
|-----------|--------|----------|
| Dependencies | **VERIFIED** | 40 packages import OK, 0 missing |
| Module Imports | **VERIFIED** | 36 key modules import successfully |
| Tests | **VERIFIED** | 933 passed, 1 skipped |
| Lint | **VERIFIED** | 2 minor issues (1 fixable) |
| Type Check | **VERIFIED** | 0 errors in 103 source files |
| Docker Compose | **VALID** | docker-compose.yml, override.yml parse OK |
| Launch Scripts | **VALID** | 4/4 scripts pass bash -n |

### Architecture

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
│   ModelRegistry      │   │  Ollama, MLX              │
│   RoutingStrategy    │   │  circuit-breaker pattern  │
└──────────────────────┘   └──────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────┐
│                    MCP Layer                          │
│  MCPRegistry  →  mcpo proxy  →  MCP servers          │
│                               (Filesystem, Time,      │
│                                ComfyUI, Whisper,      │
│                                Documents, Video,      │
│                                Music, Sandbox)        │
└──────────────────────────────────────────────────────┘
```

---

## 2. Capability Matrix

| Capability | Status | Backend Required | Hardware |
|---|---|---|---|
| Text chat | READY | Ollama | All |
| Code generation | READY | Ollama | All |
| Image generation (ComfyUI) | NEEDS BACKEND | ComfyUI + FLUX model | All |
| Image generation (mflux) | NEEDS BACKEND | mflux CLI | Mac/MLX only |
| Video generation | NEEDS BACKEND | ComfyUI + video model | CUDA recommended |
| Music generation | NEEDS BACKEND | AudioCraft/MusicGen | CUDA / MPS |
| TTS (text-to-speech) | NEEDS BACKEND | CosyVoice2 + torchaudio | CUDA / MPS |
| Voice cloning | NEEDS BACKEND | CosyVoice2 + torchaudio | CUDA / MPS |
| Speech-to-text | NEEDS BACKEND | Whisper / faster-whisper | All |
| Word / PowerPoint / Excel | READY | python-docx / python-pptx | All |
| Red team / offensive security | READY | Ollama | All |
| Blue team / SIEM | READY | Ollama | All |
| Creative writing | READY | Ollama | All |
| Deep reasoning | READY | Ollama | All |
| Web search | READY (internet required) | DuckDuckGo / Scrapling | All |
| Local knowledge / RAG | NEEDS BACKEND | sentence-transformers | All |
| Code execution sandbox | READY | Docker | All |
| Multimodal (vision/audio) | READY | Ollama (qwen3-omni) | All |

**Status legend:**
- **READY** — code is complete, no external backend required beyond Ollama
- **NEEDS BACKEND** — code is complete, install the listed backend to activate
- **PARTIAL** — functional but with noted limitations
- **PLANNED** — not yet implemented; see PORTAL_ROADMAP.md

---

## 3. Module Reference

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
| `portal.tools` | OK | 27 tools discovered |
| `portal.observability.health` | OK | Health check system |
| `portal.config.settings` | OK | Pydantic settings |
| `portal.memory.manager` | OK | Context and memory |
| `portal.core.orchestrator` | OK | Multi-step task orchestration |

---

## 4. Request Lifecycle

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

## 5. Routing System

### Dual Router Architecture

Portal uses two separate routers for different client paths:

| Router | Port | Purpose | Client |
|--------|------|---------|--------|
| **Proxy Router** | :8000 | Ollama proxy with workspace and regex routing | Open WebUI, LibreChat |
| **IntelligentRouter** | :8081 | Task complexity classification, serves Portal API | Portal interfaces (Web, Telegram, Slack) |

### Workspaces (Virtual Models)

Defined in `src/portal/routing/router_rules.json`:

| Workspace | Model | Lock | Use Case |
|-----------|-------|------|----------|
| `auto` | dolphin-llama3:8b | false | Default routing |
| `auto-coding` | qwen3-coder-next:30b-q5 | true | Code generation |
| `auto-reasoning` | huihui_ai/tongyi-deepresearch-abliterated:30b | true | Deep reasoning |
| `auto-security` | xploiter/the-xploiter | true | Red team / offensive security |
| `auto-creative` | dolphin-llama3:70b | true | Creative writing |
| `auto-multimodal` | qwen3-omni:30b | true | Text/image/audio/video |
| `auto-fast` | dolphin-llama3:8b | false | Fast responses |
| `auto-documents` | qwen3-coder-next:30b-q5 | true | Document creation (Word/PPT/Excel) |
| `auto-video` | dolphin-llama3:8b | false | Video generation |
| `auto-music` | dolphin-llama3:8b | false | Music generation |
| `auto-research` | huihui_ai/tongyi-deepresearch-abliterated:30b | true | Deep research with RAG |

### Automatic Query Classification

**Task Categories:** general, code, reasoning, creative, tool_use, security, image_gen, audio_gen, video_gen, music_gen, document_gen, research

**Regex Rules:**
- `offensive_security` — exploit, shellcode, bypass, payload, reverse shell, pentest, red team, priv esc, kerberoast, mimikatz, bloodhound
- `defensive_security` — blue team, SIEM, detection, IOC, threat hunt, YARA, sigma, splunk, tstats
- `coding` — write, debug, function, class, def, import, async def, refactor
- `reasoning` — analyze, reason, think through, explain why, step by step
- `document_gen` — write doc, create presentation, make spreadsheet, generate report
- `video_gen` — create video, animate, video clip, video generation
- `music_gen` — compose, create music, generate song, soundtrack, beat
- `research` — research, deep dive, find information about, investigate

**Manual Override:** Use `@model:modelname` prefix in message (e.g., `@model:dolphin-llama3:70b explain quantum computing`)

---

## 6. Feature Guide — Use Cases

### "I want to chat / ask questions"

**Interface:** Open WebUI, LibreChat, Telegram, Slack
**Workspace:** `auto` (auto-routing) or any specific workspace
**Setup:** Ollama running with at least one model pulled
**Example:**
```bash
curl http://localhost:8081/v1/chat/completions \
  -H "Authorization: Bearer $WEB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"explain quantum computing"}],"stream":true}'
```

### "I want to generate images"

Two paths available:

**Path A — ComfyUI (all hardware):**
- Install ComfyUI + FLUX.1-schnell model
- Start ComfyUI: `python main.py --listen`
- Set `COMFYUI_URL=http://localhost:8188` in .env
- MCP server: `mcp/generation/comfyui_mcp.py`
- Trigger: Ask the LLM to generate an image — it will call the ComfyUI MCP tool

**Path B — mflux (Mac/MLX only):**
- Install: `uv tool install --upgrade mflux`
- Tool: `src/portal/tools/media_tools/image_generator.py`
- Trigger: Ask the LLM to draw or generate an image

### "I want to generate video"

**Backend required:** ComfyUI + a video generation model (CogVideoX, Wan2.1, or Mochi-small)
- MCP server: `mcp/generation/video_mcp.py`
- Tool: `src/portal/tools/media_tools/video_generator.py`
- Workspace: `auto-video`
- Hardware note: CUDA GPU strongly recommended (M4 Mac possible with Mochi-small)
- Trigger: "create a video of..." or select `auto-video` workspace

### "I want to generate music"

**Backend required:** Meta AudioCraft (MusicGen-Medium) — runs on 16GB VRAM or M4 unified memory
- MCP server: `mcp/generation/music_mcp.py`
- Tool: `src/portal/tools/media_tools/music_generator.py`
- Workspace: `auto-music`
- Supports: text-to-music, genre, duration, tempo parameters
- Trigger: "compose music for...", "generate a soundtrack", or select `auto-music` workspace

### "I want text-to-speech or voice cloning"

**Backend required:** CosyVoice2 + torchaudio
- Install: `pip install cosyvoice torchaudio`
- Download model: `pretrained_models/CosyVoice-300M-SFT` (TTS) or `CosyVoice-300M-ZeroShot` (clone)
- Tool: `src/portal/tools/media_tools/audio_generator.py`
- Supports: 6 voices (Chinese/English/Japanese male/female), zero-shot voice cloning from reference audio
- Trigger: Ask the LLM to speak text or clone a voice

### "I want to write/edit Word, PowerPoint, or Excel files"

**Setup:** `pip install python-docx python-pptx openpyxl` (included in Portal extras)
- Tools: `word_processor`, `powerpoint_processor`, `excel_processor`
- MCP endpoint: `mcp/documents/document_mcp.py`
- Workspace: `auto-documents`
- Generated files saved to `data/generated/`
- Trigger: "create a Word document about...", "make a presentation on...", or select `auto-documents`

### "I want to download generated files"

**Endpoint:** `GET /v1/files` and `GET /v1/files/{filename}`

After generating documents, images, videos, or music, files are saved to `data/generated/`. Use these endpoints to download:

```bash
# List recently generated files
curl http://localhost:8081/v1/files

# Download a specific file
curl -o document.docx http://localhost:8081/v1/files/document.docx
```

**Features:**
- Path traversal protection (rejects `..`, `/`, `\`)
- Automatic MIME type detection
- `Content-Disposition: attachment` for documents
- Lists 50 most recent files

### "I want security analysis / red team"

**Workspace:** `auto-security`
**Primary model:** xploiter/the-xploiter
**Fallbacks:** lazarevtill/Llama-3-WhiteRabbitNeo-8B-v2.0:q4_0, dolphin-llama3:70b

**Keywords that trigger routing:**
exploit, shellcode, bypass, payload, reverse shell, pentest, red team, priv esc, kerberoast, mimikatz, bloodhound, meterpreter

### "I want blue team / SIEM / threat hunting"

**Routing trigger:** Keywords: blue team, SIEM, detection, IOC, threat hunt, YARA, sigma, splunk, tstats, es notable, cim
**Routes to:** huihui_ai/tongyi-deepresearch-abliterated:30b

### "I want to write code"

**Workspace:** `auto-coding`
**Primary model:** qwen3-coder-next:30b-q5
**Fallbacks:** devstral:24b, dolphin-llama3:8b
**Keywords that trigger routing:** write, debug, function, class, def, import, async def, refactor

### "I want to execute code safely"

**Backend required:** Docker (for sandbox isolation)
- Set `SANDBOX_ENABLED=true` in .env and ensure Docker is running
- MCP server: `mcp/execution/code_sandbox_mcp.py`
- Supports: Python, Node.js, Bash
- Security: network disabled, resource limits, timeout enforced
- Returns: stdout, stderr, generated files

### "I want to research a topic deeply"

**Workspace:** `auto-research`
**Model:** huihui_ai/tongyi-deepresearch-abliterated:30b + RAG tools
- Requires: sentence-transformers (`pip install sentence-transformers`)
- Local knowledge base at `data/knowledge/`
- Web search via DuckDuckGo (requires internet) or local SearXNG (offline-capable)
- Trigger: "research...", "deep dive into...", or select `auto-research`

### "I want to do a multi-step task"

**Automatic Detection:** Portal automatically detects multi-step requests and uses the TaskOrchestrator.

**Triggers:**
- Explicit keywords: "then", "after that", "and also", "next step"
- Multiple action verbs: "write X and create Y", "research topic and write report"

**How it works:**
1. AgentCore detects multi-step pattern in user message
2. TaskOrchestrator breaks down the request into steps
3. Each step executes sequentially, passing context to the next
4. Results are combined into a single response

**Example:**
> "Research quantum computing and write a report, then create a presentation"

This triggers the orchestrator to:
1. Research quantum computing
2. Write a report document
3. Create a PowerPoint presentation
4. Return all results combined

### "I want creative writing"

**Workspace:** `auto-creative`
**Primary model:** dolphin-llama3:70b
**Fallbacks:** dolphin-llama3:8b

### "I want multimodal (image/audio/video understanding)"

**Workspace:** `auto-multimodal`
**Primary model:** qwen3-omni:30b
**Capabilities:** Native text/image/audio/video understanding

---

## 7. First-Run Setup by Capability

### Minimum (text chat only)

```bash
# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Pull a model
ollama pull dolphin-llama3:8b

# Start Portal
bash launch.sh up
```

### Add image generation (ComfyUI, all hardware)

```bash
# Install ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI && cd ComfyUI
pip install -r requirements.txt

# Download FLUX.1-schnell
# Place flux1-schnell.safetensors in ComfyUI/models/checkpoints/

# Start ComfyUI
python main.py --listen

# Set in .env
COMFYUI_URL=http://localhost:8188
GENERATION_SERVICES=true
```

### Add image generation (mflux, Mac only)

```bash
uv tool install --upgrade mflux
# Models download automatically on first use
```

### Add TTS / voice cloning

```bash
pip install cosyvoice torchaudio

# Download CosyVoice models (run once)
python -c "from cosyvoice.cli.cosyvoice import CosyVoice; CosyVoice('pretrained_models/CosyVoice-300M-SFT')"
```

### Add local knowledge / RAG

```bash
pip install sentence-transformers

# Default embedding model (auto-downloaded on first use)
# Override: PORTAL_EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Add music generation

```bash
pip install audiocraft

# Models download automatically on first use (~1.5GB for MusicGen-Medium)
```

### Add video generation

```bash
# Install ComfyUI (see above) + a video model
# Recommended: CogVideoX or Wan2.1 via ComfyUI Manager
# Set VIDEO_MCP_URL=http://localhost:8911 in .env
```

### Add code execution sandbox

```bash
# Ensure Docker is installed and running
docker --version

# Enable in .env
SANDBOX_ENABLED=true

# Run sandbox MCP
python -m mcp.execution.code_sandbox_mcp
```

---

## 8. Interface Guide

### Open WebUI Setup

1. Go to Settings → Connections
2. Set "OpenAI API Base URL" to `http://localhost:8081/v1`
3. Set API Key to value of `WEB_API_KEY`
4. Select model from dropdown (auto, auto-coding, auto-security, auto-documents, etc.)

### Telegram Setup

1. Create bot via @BotFather
2. Set `TELEGRAM_BOT_TOKEN` in .env
3. Set `TELEGRAM_USER_IDS` with your chat ID
4. Restart Portal

### Slack Setup

1. Create Slack app with bot token
2. Set `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` in .env
3. Add app to desired channels
4. Restart Portal

---

## 9. Startup & Shutdown

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

## 10. Configuration Reference

**Settings use Pydantic with prefix `PORTAL_` and double-underscore nesting:**

```
PORTAL_BACKENDS__OLLAMA_URL=http://localhost:11434
PORTAL_INTERFACES__TELEGRAM__BOT_TOKEN=123456:ABC...
PORTAL_SECURITY__SANDBOX_ENABLED=false
PORTAL_EMBEDDING_MODEL=all-MiniLM-L6-v2
```

**Key environment variables from .env.example:**
- `COMPUTE_BACKEND`: mps | cuda | cpu
- `OLLAMA_HOST`: http://localhost:11434
- `DEFAULT_MODEL`: qwen2.5:7b
- `ROUTER_PORT`: 8000
- `WEB_UI`: openwebui | librechat
- `MCP_ENABLED`: true | false
- `TELEGRAM_ENABLED`: true | false
- `SLACK_ENABLED`: true | false
- `RATE_LIMIT_PER_MINUTE`: 20
- `LOG_LEVEL`: DEBUG | INFO | WARNING | ERROR
- `COMFYUI_URL`: http://localhost:8188
- `GENERATION_SERVICES`: true | false
- `SANDBOX_ENABLED`: false
- `PORTAL_EMBEDDING_MODEL`: all-MiniLM-L6-v2

---

## 11. Security Model

- **API Key:** Required for production (PORTAL_BOOTSTRAP_API_KEY)
- **Web API Key:** Optional for local-only use (WEB_API_KEY)
- **Rate Limiting:** Per-user, SQLite-backed
- **CORS:** Locked to localhost:8080 by default
- **Content Security Policy:** Configurable via PORTAL_CSP
- **Input Sanitization:** Prompt injection detection, PII scrubbing
- **Sandbox:** Optional Docker-based code execution isolation

---

## 12. MCP / Tool Layer

**MCP Registry:** `portal.protocols.mcp.mcp_registry.MCPRegistry`
- Registers MCP servers by name and transport type
- Health checks, tool discovery, tool execution
- Retry transport with exponential backoff

**MCP Servers:**
- `core` (mcpo/openapi) — Filesystem, Time at :9000
- `scrapling` (streamable-http) — Web scraping at :8900
- `comfyui` (openapi) — Image generation at :8188
- `whisper` (openapi) — Audio transcription at :10300
- `video` (streamable-http) — Video generation at :8911
- `music` (streamable-http) — Music generation at :8912
- `documents` (streamable-http) — Document tools at :8913
- `sandbox` (streamable-http) — Code execution sandbox at :8914

---

## 13. Deployment

### Docker Compose

```bash
docker-compose up -d
```

**Services included:**
- `ollama` — LLM backend
- `redis` — HITL approval state
- `qdrant` — vector store
- `portal-api` — main Portal API on :8081
- `portal-router` — Ollama proxy router on :8000
- `open-webui` — Open WebUI on :3000
- `whisper` — Speech-to-text on :10300
- `comfyui` — Image generation on :8188 (GPU required)
- `mcp-filesystem` — Filesystem MCP
- `mcp-shell` — Shell execution MCP
- `mcp-web` — Web scraping MCP
- `mcp-documents` — Document tools MCP
- `mcp-video` — Video generation MCP
- `mcp-music` — Music generation MCP
- `mcp-sandbox` — Code execution sandbox MCP

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

## 14. Observability & Metrics

**Prometheus metrics:** GET /metrics on :8081
**Health checks:** GET /health, /health/live, /health/ready
**Structured logging:** JSON with trace IDs, secret redaction
**Dashboard:** GET /dashboard on :8081
**Portal Doctor:** `bash launch.sh doctor`

---

## 15. Developer Quick Reference

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

## 16. Feature Status Matrix

| Feature | Interface | How to Use | Model/Tool | Status |
|---------|-----------|------------|------------|--------|
| Chat (general) | Web, Telegram, Slack | Send message | auto → dolphin-8b | READY |
| Code generation | Web | Select auto-coding | qwen3-coder | READY |
| Security/Red team | Web | Select auto-security | the-xploiter | READY |
| Blue team/Splunk | Web | Keyword trigger | tongyi-deepresearch | READY |
| Creative writing | Web | Select auto-creative | dolphin-70b | READY |
| Deep reasoning | Web | Select auto-reasoning | tongyi-deepresearch | READY |
| Document gen (Word/PPT/Excel) | Web (tool) | Select auto-documents | doc tools | READY |
| Image generation (ComfyUI) | Web (tool) | Ask to generate image | ComfyUI MCP | NEEDS BACKEND |
| Image generation (mflux) | Web (tool) | Ask to generate image | mflux CLI | NEEDS BACKEND (Mac) |
| Video generation | Web (tool) | Ask to create video | video MCP | NEEDS BACKEND |
| Music generation | Web (tool) | Ask to compose music | music MCP | NEEDS BACKEND |
| TTS / text-to-speech | Web (tool) | Ask to speak text | CosyVoice | NEEDS BACKEND |
| Voice cloning | Web (tool) | Ask to clone voice | CosyVoice | NEEDS BACKEND |
| Speech-to-text | Web | Upload audio | Whisper | NEEDS BACKEND |
| Multimodal | Web | Select auto-multimodal | qwen3-omni | READY |
| Telegram bot | Telegram | /start, send message | configurable | READY |
| Slack bot | Slack | @mention or message | configurable | READY |
| MCP tools | Web (function calling) | LLM invokes via tool_call | various | READY |
| Code execution sandbox | Web (tool) | Ask to run code | Docker sandbox | READY |
| Web search | Web (tool) | Ask to search | DuckDuckGo / Scrapling | READY (internet) |
| RAG/knowledge | Web | Tool call | sentence-transformers | NEEDS BACKEND |
| Metrics | HTTP | GET /metrics | prometheus | READY |
| Health checks | HTTP | GET /health | n/a | READY |
| Manual override | Any | @model:name in message | specified | READY |
| Portal doctor | CLI | launch.sh doctor | n/a | READY |

---

## 17. Verification Evidence

### Phase 0 — Environment Build
- **Python:** 3.14.3
- **Install:** CLEAN (no errors)
- **Dependencies:** 40 OK, 0 missing, 0 errors
- **Module imports:** 36 OK, 0 failed
- **Tests:** 933 passed, 1 skipped, 27 deselected
- **Lint:** 2 issues (1 fixable import sort, 1 unused variable)
- **Type check:** 0 errors

### Phase 2A — Component Instantiation
- ModelRegistry: OK
- TaskClassifier: OK (returns TaskClassification with category, complexity, confidence)
- IntelligentRouter: OK
- ExecutionEngine: OK
- create_app(): OK
- TelegramInterface: OK (import)
- SlackInterface: OK (import)
- SecurityMiddleware: OK (import)
- MCPRegistry: OK (import)
- CircuitBreaker: OK

### Phase 2B — Routing Verification
- TaskClassifier categories verified: greeting, code, question, general, security, image_gen, music_gen, analysis
- Workspace resolution: 11 workspaces verified
- Regex rules: 8 rules verified (offensive_security, defensive_security, coding, reasoning, document_gen, video_gen, music_gen, research)
- Manual @model: override: Detected correctly

### Phase 2C — Endpoint Verification
- GET /health: 200
- GET /health/live: 200
- GET /health/ready: 503 (needs Ollama)
- GET /v1/models: 200 (20 models including workspace names)
- GET /metrics: 200
- POST /v1/chat/completions: 503 (needs Ollama running)

## 18. Known Issues & Discrepancy Log

| ID | Location | Expected | Reality | Severity |
|----|----------|----------|---------|----------|
| D-01 | .env.example | Nested PORTAL_* vars | Uses simple names (OLLAMA_HOST) | DRIFT — launch.sh translates to nested format |
| D-02 | /health/ready | 200 when ready | 503 when Ollama unreachable | EXPECTED — degraded state when backend down |
| V-01 | Lint | 0 violations | 2 minor issues | MINOR — 1 fixable |
| V-02 | Mem0 | Module present | Falls back to sqlite | EXPECTED — mem0 optional |

---

*Updated: 2026-03-02 — Portal 1.4.7 — Verified via PORTAL_DOCUMENTATION_AGENT_v3*
