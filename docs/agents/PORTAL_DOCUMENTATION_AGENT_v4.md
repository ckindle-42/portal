# Portal — Codebase Documentation & Behavioral Verification Agent v4

## Role

You are a senior technical documentation agent in a **Claude Code session with full filesystem and shell access**. Your job is to produce production-grade developer documentation by **building, running, and testing every component** — then documenting what actually happened, not what was supposed to happen.

**You are a QA engineer who writes docs, not a doc writer who reads code.**

Every claim in the output documentation must be backed by a command you ran and its output. If you can't prove it works, document that you can't prove it works and why.

**Your outputs:**
1. `PORTAL_HOW_IT_WORKS.md` — comprehensive technical documentation verified against running code
2. Updated `PORTAL_ROADMAP.md` — every defect, missing dependency, broken feature, or gap added as a fix item
3. `VERIFICATION_LOG.md` — raw log of every test you ran, every command output, every pass/fail

**Your constraint:** Do not fix code. Do not modify source files. Document what exists. If something is broken, document that it's broken, capture the exact error, and add it to the roadmap. Your job is truth, not repair.

---

## What Portal Is

Portal is a **total inclusive offline AI platform** (Python 3.11 / FastAPI / async). Self-hosted inference routing for a single owner on Apple M4 Pro and Linux/NVIDIA RTX 5090.

The intent is a complete local replacement for cloud AI — covering text generation, code, security analysis, image creation, video creation, music generation, document production, research, and more. All private, all on-device.

| Fact | Detail |
|------|--------|
| Entry point | `src/portal/`, launched via `hardware/<target>/launch.sh` or `launch.sh` |
| Public surface | OpenAI-compatible REST API on `:8081/v1/*` (Open WebUI, LibreChat). Health/routing on `:8000`. File delivery on `:8081/v1/files` |
| Inference | Ollama (local), MLX (Apple Silicon), wrapped in OpenAI-compatible shim |
| Tools | MCP via `mcpo`, surfaced through `mcp/` directory. Includes document gen, video gen, music gen, code sandbox, web research |
| Orchestration | Multi-step task decomposition via `portal.core.orchestrator.TaskOrchestrator` |
| Deploy | Docker Compose or bare-metal via hardware-specific launch scripts; `portal doctor` CLI |
| Security | Localhost-only. API key auth (`WEB_API_KEY`, `MCP_API_KEY`). CORS locked to `localhost:8080` |
| Workspaces | Virtual models (personas) in config, routed through `AgentCore`. 11 workspaces covering code, security, creative, documents, video, music, research, multimodal |
| Channels | Telegram/Slack as optional push-notification sidecars |
| Lineage | Forked from PocketPortal (Telegram-first). Legacy assumptions may persist |

---

## Phase 0 — Full Environment Build & Dependency Verification

This phase doesn't just install — it verifies every dependency, documents what's missing, and proves the project can actually run.

### 0A — Repository & Python
```bash
ls -la pyproject.toml src/ tests/
python3 --version
git log --oneline -5
```

### 0B — Virtual Environment & Install
```bash
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
pip install -e ".[all,dev,test]" 2>&1 | tee /tmp/portal_install.log
grep -iE "error|failed|not found|no matching|conflict" /tmp/portal_install.log || echo "CLEAN INSTALL"
```
If install fails, try each extra individually and document which succeed/fail with exact errors.

### 0C — Dependency Completeness Audit

For EVERY package in `pyproject.toml`, verify it actually imports. Write a Python script that reads `pyproject.toml` via `tomllib`, extracts all deps (core + every optional group), maps pip names to import names (e.g., `python-telegram-bot` → `telegram`, `pyyaml` → `yaml`), attempts `importlib.import_module()` on each, and reports OK/MISSING/ERROR counts with exact error messages. Every missing dep is a finding.

### 0D — Portal Module Import Verification

Walk `src/portal/`, attempt `importlib.import_module()` on every `.py` file. Report importable count vs failed count with exact exceptions for every failure. This catches circular imports, missing deps that 0C missed, and broken init chains.

### 0E — Full Test Suite, Lint, Type Check
```bash
python3 -m pytest tests/ -v --tb=long 2>&1 | tee /tmp/portal_tests.log
python3 -m ruff check src/ tests/ 2>&1 | tee /tmp/portal_lint.log
python3 -m mypy src/portal/ --ignore-missing-imports 2>&1 | tee /tmp/portal_mypy.log
```
For EVERY test failure: document which test, exact error, root cause (missing dep, real bug, needs Ollama, test itself broken).

### 0F — Read Existing Project Artifacts

Check existence and read: `PORTAL_AUDIT_REPORT.md`, `PORTAL_ROADMAP.md`, `ACTION_PROMPT_FOR_CODING_AGENT.md`, `docs/ARCHITECTURE.md`, `CHANGELOG.md`, `README.md`, `.env.example`, `CLAUDE.md`, `QUICKSTART.md`, `KNOWN_ISSUES.md`. These are claims to verify in Phase 2.

### 0G — Environment Report
```
ENVIRONMENT REPORT
==================
Python:          3.X.X
Install:         [CLEAN | PARTIAL | FAILED]
Dependencies:    X OK, X missing, X error
Module imports:  X OK, X failed
Tests:           X passed, X failed, X skipped, X error
Lint:            X violations
Type check:      X errors
```

Save all outputs to `/tmp/portal_*.log`.

---

## Phase 1 — Structural Map

Read every file in `src/portal/`. For each module:

```
Module:        [import path]
File:          [path, LOC]
Purpose:       [verified by reading code, not comments]
Classes:       [name: purpose]
Functions:     [name: purpose]
Called by:      [which modules import this]
Calls:         [what this imports]
Config reads:  [env vars / config keys]
Import status: [OK | FAILS — from 0D]
Test coverage: [test files covering this, or NONE]
```

Trace with file:line references:
- **Startup:** `launch.sh up` → uvicorn → app → lifespan → agent_core → router → ready
- **Request lifecycle:** POST `/v1/chat/completions` → every function in the chain to Ollama response
- **Routing paths:** model="auto" vs model="auto-security" vs explicit model name — trace each
- **Orchestrator path:** message → `_is_multi_step()` → `_handle_orchestrated_request()` → `TaskOrchestrator` — trace when and how this intercepts

---

## Phase 2 — Behavioral Verification (Exercise Every Feature)

### 2A — Component Instantiation Tests

Write and run a Python test script that tries to construct every major class. For each, capture success or exact exception:

- `ModelRegistry()` — loads? How many models? All capabilities valid?
- `TaskClassifier()` — classify test queries: "hello", "write python sort", "exploit kerberos", "generate image", "analyze pros and cons", "create a video of sunset", "compose jazz piano", "create a word document", "deep research quantum physics"
- `WorkspaceRegistry(rules)` — loads? Workspaces listed? Each resolves to a model? How many workspaces?
- `router_rules.json` — parses? default_model set? All workspace models reference valid entries? How many classifier categories? How many regex rules?
- `IntelligentRouter(registry, workspace_registry=ws)` — constructs?
- `ExecutionEngine(registry, router)` — constructs? What backends?
- `create_app()` from `web/server.py` — FastAPI app builds? What routes? Does it include `/v1/files` and `/v1/files/{filename}`?
- `router.app` from `routing/router.py` — proxy app loads? What routes?
- `TelegramInterface` — imports? Constructs with mock config?
- `SlackInterface` — imports? Constructs with mock config?
- `SecurityMiddleware` — imports? Constructs?
- `MCPBridge` / MCP protocol — imports?
- Tools `__init__` / `TOOL_REGISTRY` — what's registered? Each importable?
- `CircuitBreaker()` — constructs?
- `HealthChecker` — imports?
- Structured logger `get_logger()` — works?
- Every module in `tools/` — each importable?
- `TaskOrchestrator` — constructs with mock executors? Can `build_plan()`? Can execute a single-step plan?
- `agent_core._is_multi_step()` — test with these exact inputs and document True/False for each:
  - "Write a Python function that generates CSV files" → expected: **False**
  - "First, let me explain quantum computing" → expected: **False**
  - "Find and summarize the key points" → expected: **False**
  - "Create a detailed report on market trends" → expected: **False**
  - "Explain why transformers work and describe their architecture" → expected: **False**
  - "Step 1: research quantum computing. Step 2: create a presentation" → expected: **True**
  - "First research the topic, then write a report, finally create slides" → expected: **True**
  - "Do both: write the code and create the documentation" → expected: **True**
  - If single-turn prompts return True → **BROKEN finding: OVERLY_AGGRESSIVE detection**

### 2B — Routing Chain Verification (async)

Write and run an async Python test that exercises the routing brain:

| Query | workspace_id | Expected behavior |
|-------|-------------|-------------------|
| "hello" | None | default/fast model |
| "write a python sort function" | None | code model |
| "explain step by step" | None | reasoning model |
| "write a creative story" | None | creative model |
| "write a reverse shell exploit" | None | security model if exists |
| "generate an image of sunset" | None | image_gen if exists |
| "clone my voice" | None | audio_gen if exists |
| "create a video of a sunset" | None | video_gen category |
| "compose jazz piano music" | None | music_gen category |
| "create a word document summarizing" | None | document_gen category |
| "deep research quantum computing" | None | research category |
| "hello" | "auto-coding" | workspace model regardless of query |
| "hello" | "auto-security" | workspace model regardless of query |
| "hello" | "auto-fast" | fast workspace model |
| "hello" | "auto-documents" | documents workspace model |
| "hello" | "auto-video" | video workspace model |
| "hello" | "auto-music" | music workspace model |
| "hello" | "auto-research" | research workspace model |
| "hello" | "nonexistent-workspace" | fall through to default |
| "Step 1: research X. Step 2: summarize" | None | should trigger orchestrator before routing |
| "write a function that generates CSV" | None | code model — should NOT trigger orchestrator |

For each: capture model selected, reasoning, category, fallback chain. Flag unexpected results.

**Critical verification:** Does `incoming.model` from Open WebUI actually reach `router.route(workspace_id=...)`? Trace `server.py _handle_chat_completions` → `agent_core.stream_response` → `execution_engine.generate_stream` → `router.route()`. Document whether `workspace_id` is threaded through or dropped. If dropped, this is a `BROKEN` finding.

**Critical verification:** Does `_is_multi_step()` intercept before routing? If so, does the orchestrator still respect workspace routing? If not, multi-step requests in a workspace like "auto-documents" will not use the document model. Document this behavior.

### 2C — Endpoint Verification via TestClient

Write and run a Python test that hits EVERY endpoint on BOTH FastAPI apps using `TestClient`:

**Portal Web API (`:8081`):**
- GET `/health` → 200?
- GET `/health/live` → 200?
- GET `/health/ready` → 200?
- GET `/v1/models` → 200? Contains models? Contains workspace names?
- GET `/metrics` → 200?
- GET `/v1/files` → 200? Returns JSON array?
- GET `/v1/files/nonexistent.txt` → 404?
- GET `/v1/files/../../etc/passwd` → 400 or 404? (path traversal must be blocked)
- POST `/v1/chat/completions` with model="auto" → what happens?
- POST `/v1/chat/completions` with model="auto-security" → routes differently?
- Auth: request without key → expected response? With wrong key → 401?

**Router Proxy (`:8000`):**
- GET `/health` → 200?
- GET `/api/tags` → contains workspace virtual models?
- POST `/api/dry-run` with code query → correct routing?
- POST `/api/dry-run` with security query → correct routing?
- POST `/api/dry-run` with workspace model → workspace routing?

Capture every status code and response body. Document mismatches.

### 2D — Configuration Contract Verification

Write and run a Python script that:
1. Extracts every `os.getenv`/`os.environ` call from source with file:line
2. Cross-references against `.env.example`
3. Flags: vars in code not in .env.example, vars in .env.example not in code, vars with no default (crash if unset)

Additionally verify these specific config vars are both in `.env.example` AND consumed by code:
- `VIDEO_MCP_PORT`, `VIDEO_MODEL`
- `MUSIC_MCP_PORT`
- `DOCUMENTS_MCP_PORT`, `GENERATED_FILES_DIR`
- `SANDBOX_MCP_PORT`, `SANDBOX_ENABLED`, `SANDBOX_TIMEOUT`
- `PORTAL_EMBEDDING_MODEL`

### 2E — Docker & Launch Script Verification
```bash
# Validate YAML
for f in docker-compose.yml docker-compose.override.yml; do
    [ -f "$f" ] && python3 -c "import yaml; yaml.safe_load(open('$f')); print('$f: VALID')" || echo "$f: ERROR"
done
# Validate bash syntax
for script in hardware/*/launch.sh launch.sh mcp/*/launch*.sh; do
    [ -f "$script" ] && bash -n "$script" && echo "$script: OK" || echo "$script: ERROR"
done
# Document subcommands and services per script
```

Verify `launch.sh stop_all()` kills ALL MCP processes including video, music, document, sandbox.
Verify `launch.sh run_doctor()` health-checks all MCP services when enabled.

### 2F — Test Coverage Mapping
```bash
python3 -m pytest tests/ -v --collect-only 2>&1 | grep "::test_"
```
Map each test to the feature it covers. List features with ZERO coverage. Pay special attention to:
- File delivery endpoint (`/v1/files`) — any tests?
- Orchestrator integration (not just unit tests of TaskOrchestrator, but `_is_multi_step` and `_handle_orchestrated_request` in agent_core) — any tests?
- MCP servers in `mcp/` (document_mcp, code_sandbox_mcp, video_mcp, music_mcp) — any tests?

### 2G — Discrepancy Log

| ID | Phase | Location | Expected | Reality | Severity | Evidence |
|----|-------|----------|----------|---------|----------|----------|

**Severity:** `BROKEN` | `DEGRADED` | `DRIFT` | `MISSING_DEP` | `MISSING_FEATURE` | `UNDOCUMENTED` | `TEST_GAP` | `OVERLY_AGGRESSIVE`

**Evidence = command output or file:line. Never "I think."**

---

## Phase 3 — Feature Catalog & Usage Guide (Exercise Every Capability)

Phase 2 proved what constructs and what responds. This phase documents **how a real user operates every feature**, across every interface, with actual input/output examples. For each capability, answer: What is it? How do you invoke it? What do you send? What comes back? Which interfaces support it? What model handles it?

**Method:** For features that can run without Ollama (routing decisions, tool registration, endpoint responses), run them and capture real output. For features that require a running LLM (actual inference, music gen, image gen), trace the code path, document the expected invocation, and mark as `UNTESTABLE (needs running service)` with the exact API call a user would make.

### 3A — Workspace Personas (the model dropdown)

For every workspace defined in `router_rules.json`, document:

```
Workspace: auto-security
  Select in UI:  Choose "auto-security" from Open WebUI model dropdown
  Routes to:     xploiter/the-xploiter (verify via dry-run or routing test)
  Fallbacks:     [list from rules]
  Use case:      Red team — exploits, shellcode, pentesting, CVE analysis
  Example prompt: "Write a Kerberoasting attack chain for an AD environment"
  Expected:      Response from The-Xploiter, no refusals
  Also works via: curl, Telegram (@model:auto-security), Slack
  Status:        [VERIFIED via Phase 2B | BROKEN — workspace_id not threaded]
```

Do this for EVERY workspace: auto, auto-coding, auto-security, auto-creative, auto-multimodal, auto-fast, auto-reasoning, auto-documents, auto-video, auto-music, auto-research, and any others found in the config.

**Verify via dry-run or routing test that each workspace actually resolves to its target model.** If routing is broken (workspace_id dropped), document exactly where the wire is cut.

### 3B — Intelligent Routing (the auto-classification brain)

Document how automatic routing works when user selects "auto" or doesn't select a model:

```
Feature: Automatic query classification
  Trigger:     User selects "auto" or sends message without model selection
  How it works: LLMClassifier (if Ollama available) or TaskClassifier (regex fallback)
  Categories:  [list every TaskCategory and what triggers each — including video_gen, music_gen, document_gen, research]

  Example routing decisions (from Phase 2B results):
    "write a python function"     → [model] (category: code)
    "explain step by step"        → [model] (category: reasoning)
    "write a reverse shell"       → [model] (category: security)
    "generate an image of sunset" → [model] (category: image_gen)
    "create a video of sunset"    → [model] (category: video_gen)
    "compose jazz piano"          → [model] (category: music_gen)
    "create a word document"      → [model] (category: document_gen)
    "deep research quantum"       → [model] (category: research)

  Manual override: Type "@model:dolphin-llama3:70b" in your message
  Status: [VERIFIED | PARTIAL | BROKEN]
```

### 3C — Chat Interface (Open WebUI / LibreChat)

Document the primary user experience:

```
Feature: Web chat via Open WebUI
  URL:         http://localhost:8080 (via Caddy) or http://localhost:8081/v1 (direct)
  Setup:       Point Open WebUI's "OpenAI API Base URL" to http://localhost:8081/v1
  API key:     Value of WEB_API_KEY from .env (or empty if auth disabled)

  Available models in dropdown: [list what /v1/models returns — from Phase 2C]
  Do workspace names appear? [YES/NO — critical finding from Phase 2C]

  How to chat:
    1. Select model from dropdown (e.g., "auto-security")
    2. Type message
    3. Response streams back via SSE

  Streaming: POST /v1/chat/completions with stream=true
  Non-streaming: POST /v1/chat/completions with stream=false

  Example curl (streaming):
    curl http://localhost:8081/v1/chat/completions \
      -H "Authorization: Bearer $WEB_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"model":"auto-security","messages":[{"role":"user","content":"explain kerberoasting"}],"stream":true}'

  Expected response format: SSE chunks with data: {JSON}\n\n, ending with data: [DONE]
  Status: [VERIFIED via TestClient | UNTESTABLE needs Ollama for actual response]
```

### 3D — Telegram Bot

Read `src/portal/interfaces/telegram/` and document:

```
Feature: Telegram bot interface
  Setup:       Set TELEGRAM_BOT_TOKEN in .env, enable in config
  How to start: Launches automatically with portal if configured
  Bot commands: [list every command handler found in the code — /start, /help, etc.]
  Message flow: User sends message → TelegramInterface → AgentCore → response → Telegram reply

  How to select a model:  [does it support @model: override? workspace selection?]
  How to use tools:       [can Telegram users invoke MCP tools?]
  Rate limiting:          [is per-user rate limiting active?]
  Auth:                   [how are users authenticated? per-user allowlist?]
  HITL (human-in-the-loop): [is tool confirmation middleware active for Telegram?]

  Dependencies required: python-telegram-bot [version]
  Import status: [OK | FAILS — from Phase 0D]
  Construction status: [OK | FAILS — from Phase 2A]
  Status: [VERIFIED | BROKEN | UNTESTABLE]
```

### 3E — Slack Bot

Read `src/portal/interfaces/slack/` and document:

```
Feature: Slack bot interface
  Setup:       Set SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET in .env
  How to start: Launches with portal if configured
  Event types: [message, app_mention, etc. — read from code]
  Channel whitelist: [is there one? how configured?]

  How to select a model:  [supported?]
  How to use tools:       [supported?]
  Streaming replies:      [does it stream or send complete?]

  Dependencies required: [slack packages]
  Import status: [from Phase 0D]
  Construction status: [from Phase 2A]
  Status: [VERIFIED | BROKEN | UNTESTABLE]
```

### 3F — MCP Tools (Internal Tool Registry)

Read `src/portal/tools/` and `mcp/` directories. For EVERY tool module, document:

```
Tool: [name from tools/__init__.py or directory name]
  Module:      src/portal/tools/[path]
  Purpose:     [what it does — read the code]
  How invoked: Function calling from LLM / direct MCP call
  Input schema: [parameters the tool accepts]
  Output:      [what it returns]
  Dependencies: [required packages]
  Import status: [OK | FAILS]

  Example invocation (if testable):
    [show function call or MCP request]

  Status: [VERIFIED | STUB | BROKEN | UNTESTABLE]
```

Group tools by category and document each:

**Document Processing:** docx generation, PowerPoint, Excel, PDF, markdown — what tools exist? Do they import?
**Media Tools:** audio transcription, image generation (mflux), audio generation (CosyVoice), **video generation (ComfyUI), music generation (AudioCraft)** — what's implemented vs stub?
**Dev Tools:** git operations, code analysis — what's available?
**Data Tools:** CSV, data processing — what exists?
**System Tools:** docker, system info — what's available?
**Web Tools:** search, scraping — what works?
**Knowledge Tools:** RAG, embeddings — what's implemented?
**Automation Tools:** scheduled tasks, workflows — what exists?

### 3F-MCP — MCP Server Verification

For each MCP server in `mcp/`:

```
MCP Server: [directory/filename]
  Tools exposed:   [list @mcp.tool() decorated functions]
  Transport:       [streamable-http / openapi]
  Port:            [default port]
  Launch script:   [if exists — path]
  Dependencies:    [what must be installed]
  Docker service:  [name in docker-compose.yml, if present]
  Status:          [IMPLEMENTED | NEEDS BACKEND — detail what backend]
```

Verify these specific servers:
- `mcp/generation/comfyui_mcp.py` — tools: `generate_image`, `list_workflows`
- `mcp/generation/whisper_mcp.py` — tools: `transcribe_audio`
- `mcp/generation/video_mcp.py` — tools: `generate_video`, `list_video_models`
- `mcp/generation/music_mcp.py` — tools: `generate_music`, `list_music_models`
- `mcp/documents/document_mcp.py` — tools: `create_word_document`, `create_presentation`, `create_spreadsheet`, `list_generated_files`
- `mcp/execution/code_sandbox_mcp.py` — tools: `run_python`, `run_node`, `run_bash`, `sandbox_status`

### 3G — Music / Audio Generation

```
Feature: Music generation (distinct from TTS)
  MCP server:    mcp/generation/music_mcp.py (AudioCraft/MusicGen)
  Tool module:   src/portal/tools/media_tools/music_generator.py
  Workspace:     auto-music
  Backend:       Meta AudioCraft MusicGen (small/medium/large)
  Setup:         pip install audiocraft (models auto-downloaded from HuggingFace)
  Example prompt: "Compose a 10-second upbeat jazz piano track"
  Output:        WAV file in ~/AI_Output/music/
  IMPORTANT:     Output dir is ~/AI_Output/music/ — verify whether /v1/files serves from this dir.
                 If not, generated music files are NOT downloadable via the API. Document this gap.
  Status:        [NEEDS BACKEND | BROKEN | document actual state]
```

### 3H — Image Generation

```
Feature: Image generation
  Path A — ComfyUI (all hardware):
    MCP server: mcp/generation/comfyui_mcp.py
    Backend:    ComfyUI + FLUX.1-schnell model
    Setup:      Install ComfyUI, download flux1-schnell.safetensors
    Status:     [NEEDS BACKEND]

  Path B — mflux (Mac only):
    Tool module: src/portal/tools/media_tools/image_generator.py
    Backend:     mflux CLI (MLX-native)
    Setup:       uv tool install mflux
    Output:      ~/AI_Output/images/
    Status:      [NEEDS BACKEND]
```

### 3I — Voice Cloning / TTS

```
Feature: Voice cloning / text-to-speech
  Tool module:   src/portal/tools/media_tools/audio_generator.py
  Backend:       CosyVoice2 + torchaudio
  Functions:     generate_audio() (TTS), clone_voice() (zero-shot voice cloning)
  Setup:         pip install cosyvoice torchaudio
  Status:        [NEEDS BACKEND — requires CosyVoice2 installation]
```

### 3J — Video Generation

```
Feature: Video generation
  MCP server:    mcp/generation/video_mcp.py
  Tool module:   src/portal/tools/media_tools/video_generator.py
  Workspace:     auto-video
  Backend:       ComfyUI + video model (CogVideoX, Wan2.1, Mochi)
  Setup:         Install ComfyUI + video model checkpoint via ComfyUI Manager
  Output:        ComfyUI serves the video — returned as URL, NOT saved to data/generated/
  IMPORTANT:     Video output is a ComfyUI URL, not a local file in data/generated/.
                 It is NOT served via /v1/files. Document this architectural difference.
  Hardware:      CUDA GPU strongly recommended. M4 Mac possible with Mochi-small.
  Status:        [NEEDS BACKEND]
```

### 3K — Red Team / Offensive Security

```
Feature: Red team / offensive security workspace
  Workspace:     auto-security
  Primary model:  xploiter/the-xploiter
  Fallbacks:     [list]
  Capabilities:  Exploit generation, shellcode, AD attack chains, bypass techniques
  Example prompts:
    "Write a reverse shell payload for Windows"
    "Create a Kerberoasting attack script"
    "Analyze this CVE and suggest exploitation"
  Status: [VERIFIED routing | UNTESTABLE needs Ollama + pulled model]
```

### 3L — Blue Team / Defensive Security

```
Feature: Defensive security / Splunk / SIEM
  Routing trigger: Queries containing splunk, tstats, notable, SIEM keywords
  Routes to:       [model from regex rules]
  Example prompts:
    "Write a Splunk correlation search for brute force detection"
    "Create a YARA rule for detecting mimikatz"
  Status: [VERIFIED routing | UNTESTABLE needs Ollama]
```

### 3M — Coding Specialist

```
Feature: Code generation workspace
  Workspace:     auto-coding
  Primary model:  qwen3-coder-next:30b-q5
  Fallbacks:     [list]
  Example prompts:
    "Write a FastAPI endpoint with auth middleware"
    "Debug this Python function: [code]"
  Status: [VERIFIED routing]
```

### 3N — Creative Writing / Stories

```
Feature: Creative writing workspace
  Workspace:     auto-creative
  Primary model:  dolphin-llama3:70b
  Use case:      Stories, roleplay, screenplays, uncensored creative content
  Status: [VERIFIED routing]
```

### 3O — Multimodal (Text + Image + Audio + Video)

```
Feature: Multimodal workspace
  Workspace:     auto-multimodal
  Primary model:  qwen3-omni:30b
  Capabilities:  Native text/image/audio/video understanding
  Status: [VERIFIED routing | UNTESTABLE needs model pulled]
```

### 3P — Observability & Metrics

```
Feature: Prometheus metrics
  Endpoint:    GET /metrics on :8081
  Status:      [VERIFIED — show actual /metrics output]

Feature: Health checks
  Endpoints:   /health, /health/live, /health/ready
  Status:      [VERIFIED — show actual response]

Feature: Structured logging
  Format:      [JSON with trace IDs? plain text?]
  Secret redaction: [does it redact API keys from logs?]
  Status:      [VERIFIED — show log output sample]
```

### 3Q — Portal Doctor / CLI

```
Feature: portal doctor
  How to invoke: bash launch.sh doctor
  What it checks: [Ollama, router, web API, MCP services, etc.]
  Does it check new MCPs? [video, music, documents, sandbox — YES/NO]
  Status: [VERIFIED — document what the script checks]
```

### 3R — Manual Model Override

```
Feature: @model: override
  How to use:  Type "@model:dolphin-llama3:70b explain quantum computing" in any message
  Where it works: [Open WebUI? Telegram? Slack? All?]
  Status: [VERIFIED via dry-run or routing test]
```

### 3S — Multi-Step Task Orchestration

```
Feature: Task Orchestrator
  Module:       portal.core.orchestrator.TaskOrchestrator
  Wired into:   agent_core.py → _is_multi_step() → _handle_orchestrated_request()
  Detection:    _is_multi_step() scans message for multi-step markers
  Trigger:      User sends explicitly structured multi-step prompt
  Behavior:     Decomposes into sequential steps (max 8), executes each, passes context forward
  Falls back:   If orchestrator fails, normal single-turn processing handles the message
  model_used:   "orchestrator" — NOTE: this is not a real model. Check if it breaks metrics or UI model attribution.

  VERIFY — Multi-step detection accuracy:
    These MUST return False (single-turn prompts that happen to contain common words):
    - "Write a Python function that generates CSV files"
    - "First, let me explain quantum computing"
    - "Find and summarize the key points about AI safety"
    - "Create a detailed report on market trends"
    - "Explain why transformers work and describe their architecture"

    These MUST return True (explicitly structured multi-step):
    - "Step 1: research quantum computing. Step 2: create a presentation about it"
    - "First research the topic, then write a report, finally create slides"
    - "Do both: write the code and create the documentation for it"

    Run _is_multi_step() with ALL of these inputs. Document True/False for each.
    If ANY single-turn prompt above returns True → BROKEN finding: OVERLY_AGGRESSIVE detection.
    This is a critical finding because it hijacks normal processing, bypassing context, routing, streaming, and metrics.

  VERIFY — Orchestrator execution:
    Build a plan with explicit steps using mock executors.
    Confirm results accumulate across steps. Confirm multi-step summary returned.
    Confirm fallback to normal processing if orchestrator raises an exception.

  Status: [VERIFIED | BROKEN — detail which prompts misfire]
```

### 3T — File Delivery Endpoint

```
Feature: Generated file download
  Endpoints:   GET /v1/files (list), GET /v1/files/{filename} (download)
  Source dir:   data/generated/
  Security:     Path traversal protection (rejects .., /, \)
  Used by:      Document MCP writes to data/generated/ → files ARE served
                Music MCP writes to ~/AI_Output/music/ → files are NOT served (different dir)
                Video MCP returns ComfyUI URLs → files are NOT served (external service)

  VERIFY via TestClient:
    1. GET /v1/files → 200, JSON array (may be empty)
    2. Create a test file in data/generated/test_verify.txt
    3. GET /v1/files → should include test_verify.txt
    4. GET /v1/files/test_verify.txt → 200, correct content
    5. GET /v1/files/nonexistent.txt → 404
    6. GET /v1/files/../../etc/passwd → 400 or 404 (path traversal blocked)
    7. Clean up test file

  IMPORTANT: Document whether music and video outputs are actually downloadable.
  If they write to different directories than data/generated/, this is a DISCONNECTED_WIRE finding.

  Status: [VERIFIED | BROKEN | DISCONNECTED_WIRE]
```

### 3U — Web Search / Research Tool

```
Feature: Web search for targeted research
  Purpose:     Retrieve current or specialized information the LLM doesn't have in training data.
               Designed for when you need to research something the model doesn't know
               or that requires more up-to-date information than training data contains.
               NOT intended for general internet browsing or entertainment.

  MCP server:  mcp/scrapling/launch_scrapling.sh (streamable-http on :8900)
  Fallback:    scripts/mcp/web_scrape_mcp_server.py (DuckDuckGo instant answer API on :8092)
  Requires:    Internet connection for the specific query

  Appropriate use cases:
    - "What is the latest CVE for Log4j?" → needs current vulnerability data
    - "Research current NERC CIP v7 standard changes" → specialized/regulatory
    - "What's the latest on MCP protocol development?" → evolving tech

  NOT appropriate for:
    - General web browsing or entertainment
    - "Browse Reddit for me" or "What's trending on Twitter"

  VERIFY:
    1. Can web_scrape_mcp_server.py be started?
    2. Does POST /tool/search with {"query": "test"} return a response?
    3. Is scrapling installable? Does its launch script pass syntax check?

  Status: [READY — requires internet | DEGRADED — only DDG fallback | BROKEN]
```

### 3V — Document Generation (Word / PowerPoint / Excel)

```
Feature: Document creation
  MCP server:    mcp/documents/document_mcp.py
  Workspace:     auto-documents
  Tools:         create_word_document, create_presentation, create_spreadsheet, list_generated_files
  Output dir:    data/generated/
  Download:      GET /v1/files/{filename} after creation

  VERIFY (if dependencies available):
    1. Can document_mcp.py be imported?
    2. Does create_word_document(title="Test", content="# Hello\n\nWorld") produce a .docx?
    3. Does the file appear in data/generated/?
    4. Can it be downloaded via /v1/files/{filename}?

  Status: [READY | NEEDS BACKEND (python-docx) | BROKEN]
```

### 3W — Code Execution Sandbox

```
Feature: Code execution sandbox
  MCP server:    mcp/execution/code_sandbox_mcp.py
  Tools:         run_python, run_node, run_bash, sandbox_status
  Security:      Docker-based isolation — no network, 256MB RAM, 0.5 CPU, 30s timeout
  Requires:      Docker running + SANDBOX_ENABLED=true

  VERIFY:
    1. Can code_sandbox_mcp.py be imported?
    2. Does sandbox_status() return expected structure?
    3. Does _run_in_docker use file mount (not -c flag) for code?

  Status: [NEEDS BACKEND (Docker) | BROKEN]
```

### 3X — Feature Status Matrix

Compile everything into a single table:

| Feature | Interface | How to Use | Model/Tool | Status | Evidence |
|---------|-----------|-----------|------------|--------|----------|
| Chat (general) | Web, Telegram, Slack | Send message | auto → dolphin-8b | [status] | Phase 2C |
| Code generation | Web | Select auto-coding | qwen3-coder | [status] | Phase 2B |
| Security/Red team | Web | Select auto-security | the-xploiter | [status] | Phase 2B |
| Blue team/Splunk | Web | Keyword trigger | tongyi-deepresearch | [status] | Phase 2B |
| Creative writing | Web | Select auto-creative | dolphin-70b | [status] | Phase 2B |
| Deep reasoning | Web | Select auto-reasoning | tongyi-deepresearch | [status] | Phase 2B |
| Image gen (ComfyUI) | Web (tool) | Prompt "generate image" | ComfyUI MCP | [status] | 3H |
| Image gen (mflux) | Web (tool) | Prompt "generate image" | mflux CLI | [status] | 3H |
| Video generation | Web (tool) | Select auto-video / prompt | video MCP | [status] | 3J |
| Music generation | Web (tool) | Select auto-music / prompt | AudioCraft MCP | [status] | 3G |
| TTS / voice clone | Web (tool) | Prompt "speak this" | CosyVoice | [status] | 3I |
| Speech-to-text | Web | Upload audio | Whisper | [status] | 3F |
| Document gen (Word/PPT/Excel) | Web (tool) | Select auto-documents | doc MCP | [status] | 3V |
| Code sandbox | Web (tool) | Prompt "run this code" | Docker sandbox | [status] | 3W |
| Web research | Web (tool) | Prompt "research X" | scrapling/DDG | [status] | 3U |
| RAG/knowledge | Web | Tool call | sentence-transformers | [status] | 3F |
| Orchestration | Web, Telegram, Slack | Multi-step prompt | orchestrator | [status] | 3S |
| File delivery | Web | GET /v1/files | FileResponse | [status] | 3T |
| Multimodal | Web | Select auto-multimodal | qwen3-omni | [status] | 3O |
| Telegram bot | Telegram | /start, send message | configurable | [status] | 3D |
| Slack bot | Slack | @mention or message | configurable | [status] | 3E |
| MCP tools | Web (function calling) | LLM invokes via tool_call | various | [status] | 3F |
| Metrics | HTTP | GET /metrics | prometheus | [status] | 3P |
| Health checks | HTTP | GET /health | n/a | [status] | 3P |
| Manual override | Any | @model:name in message | specified | [status] | 3R |
| Portal doctor | CLI | launch.sh doctor | n/a | [status] | 3Q |

For every row: fill in the real status from your testing. Status options:
- **READY** — code complete, no external backend needed beyond Ollama
- **NEEDS BACKEND** — code complete, requires specific backend installation
- **VERIFIED** — tested and proven working
- **BROKEN** — code exists but crashes or produces wrong results
- **STUB** — code exists but isn't functional
- **DEGRADED** — partially working with noted limitations
- **NOT IMPLEMENTED** — no code exists
- **UNTESTABLE** — needs running external service to test

---

## Phase 4 — Write the Documentation

Produce `PORTAL_HOW_IT_WORKS.md` from verified results.

**Rules:**
- Every claim backed by command output or file:line
- Status tags from Phase 3X used throughout
- Include command outputs as evidence
- No aspirational language — document reality

**Sections:**
1. System Overview — mission, verified architecture, health summary
2. Capability Matrix — the Phase 3X table, formatted clearly
3. Module Reference — every module with verified status
4. Request Lifecycle — traced with file:line, TestClient evidence
5. Routing System — classification proven, workspace routing proven, fallbacks proven
6. **Feature Catalog & Usage Guide** — the Phase 3 feature sections, expanded with examples, inputs/outputs, and status for every feature
7. **Interface Guide** — how to use each interface (Open WebUI, Telegram, Slack, curl) with setup steps and examples
8. Startup & Shutdown — scripts traced, Docker mapped
9. Configuration Reference — every env var, source, default, .env.example status
10. Security Model — auth tested, CORS verified
11. MCP / Tool Layer — every tool and MCP server documented with schema, status, and example
12. Workspace / Virtual Model System — every workspace resolution proven, usage examples
13. Deployment — Docker, systemd, hardware differences
14. Observability — metrics, health checks, logging, portal doctor
15. Test Coverage Map — covered vs uncovered features
16. Known Issues & Discrepancy Log — full Phase 2G table
17. Developer Quick Reference — verified setup, test, extend instructions

---

## Phase 5 — Update the Roadmap

For every Phase 2G discrepancy AND every Phase 3 feature with status BROKEN, STUB, DEGRADED, or NOT IMPLEMENTED:
- `BROKEN` / `MISSING_DEP` / `OVERLY_AGGRESSIVE` → `P1-CRITICAL`
- `DEGRADED` / `DRIFT` / `DISCONNECTED_WIRE` → `P2-HIGH`
- `STUB` (code exists, not functional) → `P2-HIGH` with effort estimate
- `NOT IMPLEMENTED` (no code) → `P3-MEDIUM` with status `PLANNED`
- `MISSING_FEATURE` / `UNDOCUMENTED` / `TEST_GAP` → `P3-MEDIUM`

Preserve existing `ROAD-N` IDs. Add dated changelog. Tag: `Source: doc-verification-[date]`.

---

## Phase 6 — Produce Verification Log

Output `VERIFICATION_LOG.md` — raw evidence:
- Environment Build (full install log)
- Dependency Audit (full output)
- Module Import Audit (full output)
- Test Suite Results (full pytest output)
- Component Instantiation (full 2A output including orchestrator detection tests)
- Routing Verification (full 2B output including new categories)
- Endpoint Verification (full 2C output including /v1/files)
- Config Audit (full 2D output including new config vars)
- Launch Script Validation (full 2E output including new MCP launch scripts)
- Test Coverage Map (full 2F output)
- Feature Catalog Testing (full Phase 3 results — every feature's status evidence)
- Feature Status Matrix (the Phase 3X table with all statuses filled in)

---

## Output — Three Artifacts

1. **`PORTAL_HOW_IT_WORKS.md`** — polished docs, every claim verified
2. **`PORTAL_ROADMAP.md`** — updated with all findings
3. **`VERIFICATION_LOG.md`** — raw test evidence

---

## Begin

Start with Phase 0. Run every command. Capture every output. If a step fails, document the failure and continue. Proceed through all phases in order: Phase 0 (environment) → Phase 1 (structural map) → Phase 2 (behavioral verification) → **Phase 3 (feature catalog — exercise every capability)** → Phase 4 (write documentation) → Phase 5 (update roadmap) → Phase 6 (verification log). Do not produce artifacts until all phases complete. Output all three artifacts in full, clearly separated.
