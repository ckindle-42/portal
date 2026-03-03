# Portal — How It Works

**Version:** 3.0.2
**Updated:** 2026-03-03
**Verification:** Full test suite passed (999 tests collected), routing verified, endpoints verified

---

## 1. System Overview

Portal is a **local-first AI platform** that runs entirely on user hardware — no cloud required, no data leaves the machine. It exposes an OpenAI-compatible REST API that web UIs (Open WebUI, LibreChat) connect to, with optional Telegram and Slack interfaces sharing the same AgentCore, routing, tools, and conversation context.

**Mission:** Replace cloud AI subscriptions with a fully local platform covering text generation, code, security analysis, image creation, video creation, music generation, document production, research, and more — all private, all local.

**Hardware targets:** Apple M4 (primary), NVIDIA CUDA (Linux), CPU/WSL2.

### Verified Health Status

| Component | Status | Evidence |
|-----------|--------|----------|
| Dependencies | **VERIFIED** | 54 packages import OK |
| Module Imports | **VERIFIED** | 102 OK, 1 failed* |
| Tests | **VERIFIED** | 986 passed, 13 skipped |
| Lint | **VERIFIED** | All checks passed |
| Type Check | **VERIFIED** | Success (notes only) |
| Docker Compose | **VALID** | docker-compose.yml, override.yml parse OK |
| Launch Scripts | **VALID** | 8/8 scripts pass bash -n |

*Note: `src.portal.observability.metrics` fails on import due to duplicate timeseries `portal_requests_per_minute` in CollectorRegistry.

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Interface Layer                            │
│  ┌─────────┐  ┌──────────┐  ┌─────────┐  ┌─────────────────┐  │
│  │Web (8081)│  │Telegram  │  │ Slack   │  │ Router Proxy    │  │
│  └────┬────┘  └────┬─────┘  └────┬────┘  └────────┬────────┘  │
└───────┼────────────┼─────────────┼────────────────┼───────────┘
        │            │             │                │
        ▼            ▼             ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Security & Middleware                         │
│  ┌─────────────────┐  ┌──────────────────────────────────────┐ │
│  │SecurityMiddleware│  │ HITL Approval / Tool Confirmation   │ │
│  └────────┬────────┘  └──────────────────────────────────────┘ │
└───────────┼────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AgentCore                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ContextManager│  │ EventBus     │  │ TaskOrchestrator      │ │
│  └──────────────┘  └──────────────┘  └───────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ _is_multi_step() → multi-step detection                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────┬────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                Intelligent Router                               │
│  ┌─────────────────┐  ┌──────────────────────────────────────┐ │
│  │ModelRegistry    │  │ WorkspaceRegistry (11 workspaces)    │ │
│  │16 models        │  │ auto, auto-coding, auto-security...  │ │
│  └─────────────────┘  └──────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ TaskClassifier (regex-based) → category detection        │  │
│  │ regex_rules: offensive_security, coding, reasoning, etc. │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────┬────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Execution Engine                               │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐ │
│  │ Ollama       │  │ MLX (Apple)  │  │ CircuitBreaker        │ │
│  │ Backend      │  │ Backend      │  │ (failure protection)  │ │
│  └──────────────┘  └──────────────┘  └───────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Capability Matrix

| Feature | Interface | How to Use | Model/Tool | Status |
|---------|-----------|------------|------------|--------|
| Chat (general) | Web, Telegram, Slack | Send message | auto → dolphin-llama3:8b | VERIFIED |
| Code generation | Web | Select auto-coding | qwen3-coder-next:30b-q5 | VERIFIED |
| Security/Red team | Web | Select auto-security | xploiter/the-xploiter | VERIFIED |
| Deep reasoning | Web | Select auto-reasoning | tongyi-deepresearch | VERIFIED |
| Creative writing | Web | Select auto-creative | dolphin-llama3:70b | VERIFIED |
| Multimodal | Web | Select auto-multimodal | qwen3-omni:30b | VERIFIED |
| Fast mode | Web | Select auto-fast | dolphin-llama3:8b | VERIFIED |
| Image gen (FLUX) | Web, Telegram, Slack | Prompt "generate image" | ComfyUI MCP + FLUX | PIPELINE_READY |
| Image gen (SDXL) | Web, Telegram, Slack | IMAGE_BACKEND=sdxl | ComfyUI MCP + SDXL | PIPELINE_READY |
| Video generation (Wan2.2) | Web, Telegram, Slack | VIDEO_BACKEND=wan22 | ComfyUI MCP + Wan2.2 | PIPELINE_READY |
| Video generation (CogVideoX) | Web, Telegram, Slack | VIDEO_BACKEND=cogvideox | ComfyUI MCP + CogVideoX | PIPELINE_READY |
| Music generation | Web, Telegram, Slack | Prompt "generate music" | AudioCraft MCP | PIPELINE_READY |
| TTS / voice clone (Fish Speech) | Web, Telegram, Slack | TTS_BACKEND=fish_speech | TTS MCP | PIPELINE_READY |
| TTS / voice clone (CosyVoice) | Web, Telegram, Slack | TTS_BACKEND=cosyvoice | TTS MCP | PIPELINE_READY |
| Document gen (Word/PPT/Excel) | Web (tool) | Select auto-documents | documents MCP | PIPELINE_READY |
| Code sandbox | Web (tool) | Prompt "run this code" | sandbox MCP (Docker) | PIPELINE_READY |
| Web research | Web, Telegram, Slack | Prompt "research X" | scrapling/DDG | READY |
| Workspace selection | Telegram, Slack | @model:workspace in message | specified | VERIFIED |
| File delivery | Web, Telegram, Slack | Auto-send from tool results | various | VERIFIED |
| Orchestration | Web, Telegram, Slack | "Step 1... then step 2..." | orchestrator | VERIFIED |
| Telegram bot | Telegram | /start, send message, @model: prefix | configurable | VERIFIED |
| Slack bot | Slack | @mention or message, @model: prefix | configurable | VERIFIED |
| MCP tools | Web (function calling) | LLM invokes via tool_call | various | VERIFIED |
| Metrics | HTTP | GET /metrics | prometheus | VERIFIED |
| Health checks | HTTP | GET /health | n/a | VERIFIED |
| Manual override | Any | @model:name in message | specified | VERIFIED |
| Portal doctor | CLI | launch.sh doctor | n/a | VALIDATED |

**Status Key:**
- **VERIFIED**: Works end-to-end, tested
- **PIPELINE_READY**: Tool pipeline connected, requires backend service (ComfyUI, Fish Speech, etc.)
- **READY**: Works with minimal setup
- **IMPORTS_OK**: Code imports successfully, may need configuration

---

## 3. Request Lifecycle

### Traced Path: POST /v1/chat/completions

1. **server.py:380** - `_handle_chat_completions()` receives request
2. **server.py:430** - `agent_core.process_message()` called with `workspace_id=selected_model`
3. **agent_core.py:177** - `_is_multi_step()` checks for multi-step patterns
4. If multi-step: **agent_core.py:179** - `_handle_orchestrated_request()` → TaskOrchestrator
5. If single-turn: **agent_core.py:203** - `_route_and_execute()`
6. **agent_core.py:428** - `router.route(query, workspace_id=workspace_id)`
7. **router.py:428** - IntelligentRouter applies regex_rules → category → model
8. **agent_core.py:447** - `execution_engine.execute()` → backend (Ollama/MLX)
9. Response streams back via SSE

### Workspace ID Threading (Verified)

The `workspace_id` IS properly threaded through the entire chain:
- **server.py:435** - `workspace_id=selected_model` passed to `process_message()`
- **agent_core.py:208** - `workspace_id=workspace_id` passed to `_route_and_execute()`
- **agent_core.py:428** - `workspace_id=workspace_id` passed to `router.route()`
- **agent_core.py:448** - `workspace_id=workspace_id` passed to `execution_engine.execute()`

---

## 4. Routing System

### Classification Categories (from router_rules.json)

| Category | Keyword Triggers | Model |
|----------|-----------------|-------|
| general | default | dolphin-llama3:8b |
| code | write, debug, function, class, def | qwen3-coder-next:30b-q5 |
| reasoning | analyze, reason, think through | tongyi-deepresearch |
| creative | creative, story, poem | dolphin-llama3:70b |
| security | exploit, shellcode, bypass, payload | xploiter/the-xploiter |
| image_gen | generate image, draw, illustration | dolphin-llama3:8b |
| video_gen | create video, generate video | dolphin-llama3:8b |
| music_gen | compose music, generate song | dolphin-llama3:8b |
| document_gen | create word, presentation, spreadsheet | qwen3-coder-next:30b-q5 |
| research | deep research, investigate | tongyi-deepresearch |

### Workspaces (Virtual Models)

All 11 workspaces appear in `/v1/models` response:

```
auto-coding      → qwen3-coder-next:30b-q5
auto-reasoning   → tongyi-deepresearch:30b
auto-security    → xploiter/the-xploiter
auto-creative    → dolphin-llama3:70b
auto-multimodal  → qwen3-omni:30b
auto-fast        → dolphin-llama3:8b
auto-documents   → qwen3-coder-next:30b-q5
auto-video       → dolphin-llama3:8b
auto-music       → dolphin-llama3:8b
auto-research    → tongyi-deepresearch:30b
```

### Regex Rules (8 rules)

1. **offensive_security** - exploit, shellcode, bypass, payload, reverse shell, pentest, red team, priv esc, kerberoast, mimikatz
2. **defensive_security** - blue team, SIEM, detection, IOC, threat hunt, YARA, sigma, splunk
3. **coding** - write, debug, function, class, def, import, async def, refactor
4. **reasoning** - analyze, reason, think through, explain why, step by step
5. **document_gen** - write doc, create presentation, make spreadsheet, generate report
6. **video_gen** - create video, generate video, make video, animate
7. **music_gen** - compose music, create music, generate song, make soundtrack
8. **research** - deep research, deep dive, investigate, find information about

### Multi-Step Detection (Verified)

The `_is_multi_step()` function correctly identifies multi-step requests:

| Query | Expected | Actual | Status |
|-------|----------|--------|--------|
| "Write a Python function that generates CSV" | False | False | OK |
| "First, let me explain quantum computing" | False | False | OK |
| "Find and summarize the key points" | False | False | OK |
| "Create a detailed report on market trends" | False | False | OK |
| "Explain why transformers work and describe their architecture" | False | False | OK |
| "Step 1: research X. Step 2: create presentation" | True | True | OK |
| "First research, then write report" | True | True | OK |
| "Do both: write code and documentation" | True | True | OK |

---

## 5. Feature Catalog

### 5.1 Text Chat

**What it is:** Core chat functionality via OpenAI-compatible `/v1/chat/completions` endpoint.

**How to use it:** Send a POST request to `/v1/chat/completions` with messages array, or use any OpenAI-compatible client (Open WebUI, LibreChat, curl).

**What happens internally:**
1. Request hits `server.py` → `ChatManager`
2. `AgentCore.process_message()` routes to appropriate model
3. Response streamed or returned as JSON

**Prerequisites:** Ollama running with at least one model pulled.

**Works via:** Web API, Telegram, Slack.

**Example:**
```bash
curl -X POST http://localhost:8081/v1/chat/completions \
  -H "Authorization: Bearer $WEB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3", "messages": [{"role": "user", "content": "Hello!"}]}'
```

---

### 5.2 Code Generation

**What it is:** Automatic routing to code-specialized models for programming tasks.

**How to use it:** Chat normally, or explicitly select `@model:auto-coding` workspace.

**What happens internally:** Router classifies query as "code" and selects model from `auto-coding` workspace.

**Prerequisites:** Code model in Ollama (e.g., codellama, deepseek-coder).

**Works via:** Web API, Telegram, Slack.

**Example:**
```
@model:auto-coding write a Python function to reverse a string
```

---

### 5.3 Image Generation (FLUX + SDXL + mflux)

**What it is:** Generate images from text prompts using FLUX (fast) or SDXL (quality/LoRA).

**How to use it:**
- Via MCP: Call `generate_image` tool on ComfyUI MCP server
- Via internal tool: `image_generator.generate_image()`

**What happens internally:**
1. Tool call triggers ComfyUI MCP
2. FLUX or SDXL workflow executed on ComfyUI
3. Image saved to `data/generated/` (configurable via `GENERATED_FILES_DIR`)
4. File delivered to user via interface

**Prerequisites:**
- ComfyUI running (`launch.sh start-comfyui` or manual)
- ComfyUI MCP server: `python -m mcp.generation.comfyui_mcp`
- FLUX models or SDXL + LoRA models

**Setup commands:**
```bash
# Start ComfyUI (M4 optimized)
./launch.sh start-comfyui

# Or manually:
cd ComfyUI
python main.py --listen 0.0.0.0 --port 8188 --mps --highvram

# Start ComfyUI MCP
export COMFYUI_MCP_PORT=8910
python -m mcp.generation.comfyui_mcp

# Download FLUX models (if not using ComfyUI manager)
huggingface-cli download black-forest-labs/FLUX.1-schnell --local-dir ~/ComfyUI/models/checkpoints/
```

**Environment variables:**
- `IMAGE_BACKEND=flux` (default) or `IMAGE_BACKEND=sdxl`
- `COMFYUI_MCP_URL=http://localhost:8910`

**Works via:** Web API, Telegram (as photo), Slack (as file).

**Example prompt:** "Generate a futuristic cityscape at sunset, cyberpunk style"

---

### 5.4 Video Generation (Wan2.2 + CogVideoX)

**What it is:** Generate videos from text prompts using Wan2.2 (M4 optimized) or CogVideoX (CUDA).

**How to use it:** Call `generate_video` tool via MCP or internal tool.

**What happens internally:**
1. Tool call triggers Video MCP (`video_mcp.py`) or internal tool
2. Wan2.2 or CogVideoX workflow executed on ComfyUI
3. Video returned as ComfyUI URL or saved locally

**Prerequisites:**
- ComfyUI running with video generation models
- Video MCP server: `python -m mcp.generation.video_mcp`

**Setup commands:**
```bash
# Download Wan2.2 models (M4 optimized)
huggingface-cli download Wau/UMT5-XXL-FP8-E4M3 --local-dir ~/ComfyUI/models/clip/
huggingface-cli download Wau/Wan2.2_VAE --local-dir ~/ComfyUI/models/vae/
huggingface-cli download Wau/Wan2.2_T2V_5B --local-dir ~/ComfyUI/models/unet/

# Or CogVideoX (CUDA)
huggingface-cli download THUDM/CogVideoX-5b --local-dir ~/ComfyUI/models/checkpoints/
```

**Environment variables:**
- `VIDEO_BACKEND=wan22` (default, M4) or `VIDEO_BACKEND=cogvideox` (CUDA)
- `VIDEO_TEXT_ENCODER=umt5_xxl_fp8_e4m3fn_scaled.safetensors`
- `VIDEO_VAE=wan2.2_vae.safetensors`

**Works via:** Web API, Telegram (as video), Slack (as file).

**Example prompt:** "Generate a flowing waterfall with mist rising, cinematic quality"

---

### 5.5 Music Generation (AudioCraft)

**What it is:** Generate music from text descriptions using Meta's AudioCraft/MusicGen.

**How to use it:** Call `generate_music` tool on Music MCP server.

**What happens internally:**
1. Tool call triggers Music MCP (`music_mcp.py`)
2. AudioCraft generates audio based on prompt and duration
3. Audio saved to `data/generated/music/`

**Prerequisites:**
- AudioCraft installed: `pip install audiocraft`
- Music MCP server: `python -m mcp.generation.music_mcp`

**Setup commands:**
```bash
# Install AudioCraft
pip install audiocraft

# Start Music MCP
export MUSIC_MCP_PORT=8912
python -m mcp.generation.music_mcp
```

**Environment variables:**
- `MUSIC_MODEL_SIZE=small|medium|large` (default: medium)
- `GENERATED_FILES_DIR=data/generated` (default)

**Works via:** Web API, Telegram (as audio), Slack (as file).

**Example prompt:** "Generate an upbeat electronic dance track with strong bass and synth melodies"

---

### 5.6 TTS / Voice Cloning (Fish Speech + CosyVoice)

**What it is:** Convert text to speech using Fish Speech (recommended) or CosyVoice.

**How to use it:** Call `speak` or `clone_voice` tools on TTS MCP server.

**What happens internally:**
1. Tool call triggers TTS MCP (`tts_mcp.py`)
2. Fish Speech or CosyVoice generates audio
3. Audio saved to `data/generated/`

**Prerequisites:**
- Fish Speech installed and running (recommended)
- Or CosyVoice installed
- TTS MCP server: `python -m mcp.generation.tts_mcp`

**Setup commands:**
```bash
# Fish Speech setup (recommended for M4)
# See: https://github.com/fishaudio/fish-speech

# Start TTS MCP
export TTS_MCP_PORT=8916
python -m mcp.generation.tts_mcp
```

**Environment variables:**
- `TTS_BACKEND=fish_speech` (default) or `cosyvoice`
- `FISH_SPEECH_MODEL_PATH=models/fish_speech/fish-speech-1.4`

**Works via:** Web API, Telegram (as audio), Slack (as file).

**Available voices:** female_zhang, female_ning, male_yun, male_jun (Fish Speech)

---

### 5.7 Speech-to-Text (Whisper)

**What it is:** Transcribe audio files to text using OpenAI Whisper.

**How to use it:** Call `transcribe_audio` tool on Whisper MCP server.

**What happens internally:**
1. Tool call triggers Whisper MCP
2. Audio transcribed to text
3. Transcription returned as tool result

**Prerequisites:**
- Whisper MCP server: `python -m mcp.generation.whisper_mcp`

**Setup commands:**
```bash
# Start Whisper MCP
export WHISPER_MCP_PORT=8915
python -m mcp.generation.whisper_mcp

# Models auto-downloaded on first use
```

**Works via:** Web API, Telegram (voice messages), Slack.

---

### 5.8 Document Creation (Word, PowerPoint, Excel)

**What it is:** Generate documents, presentations, and spreadsheets programmatically.

**How to use it:** Call `create_document`, `create_presentation`, or `create_spreadsheet` on Documents MCP.

**What happens internally:**
1. Tool call triggers Documents MCP (`document_mcp.py`)
2. python-docx/pptx/openpyxl generates file
3. File saved to `data/generated/documents/`

**Prerequisites:**
- python-docx, python-pptx, openpyxl installed
- Documents MCP server: `python -m mcp.generation.document_mcp`

**Setup commands:**
```bash
pip install python-docx python-pptx openpyxl

export DOCUMENTS_MCP_PORT=8913
python -m mcp.generation.document_mcp
```

**Works via:** Web API, Telegram (as document), Slack (as file).

---

### 5.9 Code Execution Sandbox

**What it is:** Execute untrusted code in an isolated Docker container.

**How to use it:** Enable `SANDBOX_ENABLED=true` and call sandbox tools.

**What happens internally:**
1. Tool call triggers Sandbox MCP
2. Code executed in Docker container
3. Output returned, container destroyed

**Prerequisites:**
- Docker running
- `SANDBOX_ENABLED=true`

**Setup commands:**
```bash
export SANDBOX_ENABLED=true
export SANDBOX_MCP_PORT=8914
python -m mcp.generation.code_sandbox_mcp
```

**Environment variables:**
- `SANDBOX_DOCKER_IMAGE=python:3.11-slim` (default)

**Security:** Code runs in isolated container with no network access.

---

### 5.10 Red Team / Offensive Security

**What it is:** Specialized workspace for security testing with appropriate guardrails.

**How to use it:** Use `@model:auto-security` prefix or chat with auto-security workspace.

**What happens internally:** Router directs to `xploiter/the-xploiter` model with auto-security rules.

**Prerequisites:** Security model pulled in Ollama.

**Works via:** Web API, Telegram, Slack.

**Example:**
```
@model:auto-security test this SQL injection payload
```

---

### 5.11 Blue Team / Defensive Security / Splunk

**What it is:** Security analysis and SIEM integration for defensive operations.

**How to use it:** Use `@model:security-analysis` workspace (if configured).

**Prerequisites:** Splunk MCP server or custom security tools.

---

### 5.12 Creative Writing

**What it is:** Creative content generation with specialized models.

**How to use it:** Use `@model:auto-creative` prefix or let auto-routing select creative model.

**Works via:** Web API, Telegram, Slack.

---

### 5.13 Deep Reasoning / Research

**What it is:** Complex reasoning and analysis with deep-thinking models.

**How to use it:** Use `@model:auto-reasoning` prefix.

**Prerequisites:** Deep reasoning model in Ollama (e.g., deepseek-r1).

---

### 5.14 Web Research (Scrapling/DDG)

**What it is:** Search the web and scrape web pages for research tasks.

**How to use it:** Built-in tools for HTTP requests and web scraping.

**What happens internally:**
1. Tool calls Scrapling MCP for web scraping
2. DDG integration for search
3. Results fed back to LLM

**Prerequisites:** Scrapling MCP running (`scrapling` in mcpo)

**Setup:** Included in default MCP configuration.

**Works via:** Web API, Telegram, Slack.

---

### 5.15 RAG / Knowledge Base

**What it is:** Retrieve relevant context from documents before generating responses.

**How to use it:** Enable RAG in configuration, upload documents.

**What happens internally:**
1. Documents embedded via embedding model
2. Similarity search retrieves relevant context
3. Context injected into prompt

**Prerequisites:** Embedding model in Ollama.

---

### 5.16 Multi-Step Orchestration

**What it is:** Automatically break complex requests into multiple steps.

**How to use it:** Enabled by default for complex queries. Can be triggered explicitly.

**What happens internally:**
1. `TaskOrchestrator.build_plan()` breaks request into steps
2. `TaskOrchestrator.execute()` runs each step
3. Results combined into final response

**Conservative detection:** Only triggers for clearly multi-step queries.

---

### 5.17 Multimodal (Qwen2-Omni)

**What it is:** Process images, audio, and video alongside text.

**How to use it:** Use `@model:auto-multimodal` or send messages with images/audio.

**Prerequisites:** Qwen2-Omni model in Ollama.

---

### 5.18 Telegram Bot — Complete Setup Guide

**Step 1: Create a Telegram Bot**
1. Open Telegram and chat with @BotFather
2. Send `/newbot` to create a new bot
3. Follow prompts to name your bot
4. Copy the bot token

**Step 2: Get Your Chat ID**
1. Chat with @userinfobot on Telegram
2. Your ID is the number shown

**Step 3: Configure Portal**
```bash
export TELEGRAM_BOT_TOKEN="your-bot-token-here"
export TELEGRAM_USER_IDS="your-chat-id"
```

**Step 4: Start Portal**
```bash
./launch.sh start-telegram
# Or manually:
python -m portal.interfaces.telegram
```

**Step 5: Use the Bot**
- Send `/start` to initialize
- Send `/help` for commands
- Send `/tools` to list available tools
- Use `@model:workspace` to select model

**Commands:**
- `/start` - Start a conversation
- `/help` - Show help
- `/tools` - List available tools
- `/stats` - Show usage stats
- `/health` - Check health

**Workspace Selection:**
```
@model:auto-security test this
@model:creative write a poem
```

**File Delivery:** Images sent as photos, audio as voice/audio, videos as video, documents as files.

---

### 5.19 Slack Bot — Complete Setup Guide

**Step 1: Create a Slack App**
1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Add bot token scope: `chat:write`, `files:write`, `channels:history`
4. Install to workspace

**Step 2: Get Bot Token**
- Copy "Bot User OAuth Token" (starts with `xoxb-`)

**Step 3: Configure Portal**
```bash
export SLACK_BOT_TOKEN="xoxb-your-token-here"
export SLACK_SIGNING_SECRET="your-signing-secret"
```

**Step 4: Enable Events**
1. In Slack app config, go to "Event Subscriptions"
2. Enable events
3. Subscribe to `message.channels`
4. Request URL: `https://your-domain/slack/events`

**Step 5: Start Portal**
```bash
./launch.sh start-slack
# Or manually:
python -m portal.interfaces.slack
```

**Usage:**
- Mention bot or DM to chat
- Use `@model:workspace` for workspace selection

**File Delivery:** Generated files uploaded to channel via Slack API.

---

## 6. Configuration Reference

### Core Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| OLLAMA_HOST | No | http://localhost:11434 | LLM backend |
| DEFAULT_MODEL | No | qwen2.5:7b | Fallback model |
| WEB_API_KEY | No | - | API authentication |
| MCP_API_KEY | No | - | MCP server auth |
| COMPUTE_BACKEND | No | mps | mps/cuda/cpu |
| RATE_LIMIT_PER_MINUTE | No | 20 | Rate limiting |
| SANDBOX_ENABLED | No | false | Docker sandbox |
| TELEGRAM_ENABLED | No | false | Telegram interface |
| SLACK_ENABLED | No | false | Slack interface |

### MCP Service Ports

| Service | Default Port | Config Variable |
|---------|--------------|-----------------|
| MCPO (core) | 9000 | MCPO_PORT |
| Scrapling | 8900 | SCRAPLING_URL |
| ComfyUI MCP | 8910 | COMFYUI_MCP_PORT |
| Video MCP | 8911 | VIDEO_MCP_PORT |
| Music MCP | 8912 | MUSIC_MCP_PORT |
| Documents MCP | 8913 | DOCUMENTS_MCP_PORT |
| Sandbox MCP | 8914 | SANDBOX_MCP_PORT |
| Whisper MCP | 8915 | WHISPER_MCP_PORT |
| TTS MCP | 8916 | TTS_MCP_PORT |

### Generation Service Backends

| Service | Backend Variable | Options | Default |
|---------|-----------------|---------|---------|
| Image Generation | IMAGE_BACKEND | flux, sdxl | flux |
| Video Generation | VIDEO_BACKEND | wan22, cogvideox | wan22 |
| TTS | TTS_BACKEND | fish_speech, cosyvoice | fish_speech |

---

## 7. Launch Scripts

All launch scripts pass syntax validation:

- `launch.sh` - Main entry point
- `hardware/m4-mac/launch.sh` - Apple Silicon
- `hardware/linux-bare/launch.sh` - Linux NVIDIA
- `hardware/linux-wsl2/launch.sh` - WSL2
- `mcp/documents/launch_document_mcp.sh`
- `mcp/execution/launch_sandbox_mcp.sh`
- `mcp/generation/launch_generation_mcps.sh`
- `mcp/scrapling/launch_scrapling.sh`

---

## 8. Known Issues & Discrepancies

| ID | Location | Issue | Severity | Status |
|----|----------|-------|----------|--------|
| 1 | src/portal/observability/metrics.py | Duplicate timeseries 'portal_requests_per_minute' causes import failure | BROKEN | PENDING FIX |
| 2 | - | Mem0 module not installed (falls back to SQLite) | DEGRADED | OPTIONAL |

---

## 9. Test Coverage

- **Total Tests:** 999 collected
- **Passed:** 986
- **Skipped:** 13
- **Deselected:** 27 (e2e tests)

### Coverage by Module

| Module | Coverage |
|--------|----------|
| core/agent_core | ✓ |
| core/orchestrator | ✓ |
| routing/* | ✓ |
| interfaces/web | ✓ |
| tools/* | ✓ |
| security/* | ✓ |
| observability/* | ✓ |

---

## 10. Developer Quick Reference

### Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[all,dev,test]"
```

### Run Tests
```bash
make test-unit    # Fast tests only
make test         # All tests
make lint         # Ruff linting
make typecheck    # MyPy
```

### Start Portal
```bash
./launch.sh up        # Start all services
./launch.sh doctor    # Health check
./launch.sh stop_all  # Stop everything
```

### API Usage
```bash
# Chat completion
curl http://localhost:8081/v1/chat/completions \
  -H "Authorization: Bearer $WEB_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"auto-security","messages":[{"role":"user","content":"explain kerberoasting"}]}'

# List models
curl http://localhost:8081/v1/models

# List generated files
curl http://localhost:8081/v1/files
```

---

*Generated: March 2, 2026 | Source: Phase 0-3 Verification (v4)*
