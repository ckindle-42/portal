# Portal — Feature-Complete Implementation: Phased Coding Agent Prompt

**Project:** Portal — Local-first AI platform
**Repository:** https://github.com/ckindle-42/portal
**Current state:** Text/routing works. Tool pipeline disconnected. Generation features non-functional.
**Goal:** Every feature works end-to-end. Every interface can use every capability.

---

## How to Use This Prompt

This prompt has 6 phases with **hard stop gates** between them. Execute Phase 0 first. Run the gate checks. Only proceed to Phase 1 after the gate passes. This prevents shallow work that breaks on integration.

**You MUST run the gate check after each phase and confirm all checks pass before starting the next phase.** If a gate check fails, fix it before proceeding.

---

## Session Bootstrap (Run Before Every Phase)

```bash
cd /Users/chris/portal
source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev,test]" -q
make lint && make test-unit  # must be green before any changes
```

**Non-negotiable constraints (apply to ALL phases):**
- All existing tests must continue to pass after every change
- No cloud dependencies — everything runs local
- No external AI frameworks (no LangChain, no CrewAI)
- OpenAI-compatible API contract at `/v1/chat/completions` must not change
- Commit after each logical unit of work: `feat:`, `fix:`, `docs:`, `test:`
- Run `make lint && make test` after every commit

---

## PHASE 0 — Connect the Tool Pipeline

**Why this is first:** Without this, every generation feature is dead. The LLM cannot call tools because (A) tool schemas are never included in the Ollama payload and (B) only 2 of 8 MCP servers are registered with the MCPRegistry.

### TASK 0A — Register All MCP Servers with MCPRegistry

**File:** `src/portal/core/factories.py` — method `create_mcp_registry()`

**Problem:** Currently registers only `core` (mcpo at :9000) and `scrapling` (:8900). The 6 other MCP servers launch as HTTP processes but AgentCore cannot find them.

**Action:**

After the existing `scrapling` registration, conditionally register each generation/tool MCP server:

```python
# Generation services (when GENERATION_SERVICES=true)
generation_enabled = getattr(mcp_config, "generation_enabled", False) or \
    os.getenv("GENERATION_SERVICES", "false").lower() == "true"

if generation_enabled:
    comfyui_url = os.getenv("COMFYUI_MCP_URL", "http://localhost:8910")
    await registry.register(name="comfyui", url=comfyui_url, transport="streamable-http")

    whisper_url = os.getenv("WHISPER_MCP_URL", "http://localhost:8915")
    await registry.register(name="whisper", url=whisper_url, transport="streamable-http")

    video_url = os.getenv("VIDEO_MCP_URL", f"http://localhost:{os.getenv('VIDEO_MCP_PORT', '8911')}")
    await registry.register(name="video", url=video_url, transport="streamable-http")

    music_url = os.getenv("MUSIC_MCP_URL", f"http://localhost:{os.getenv('MUSIC_MCP_PORT', '8912')}")
    await registry.register(name="music", url=music_url, transport="streamable-http")

# Document tools (always available — lightweight, no GPU needed)
documents_url = os.getenv("DOCUMENTS_MCP_URL", f"http://localhost:{os.getenv('DOCUMENTS_MCP_PORT', '8913')}")
await registry.register(name="documents", url=documents_url, transport="streamable-http")

# Sandbox (when SANDBOX_ENABLED=true)
if os.getenv("SANDBOX_ENABLED", "false").lower() == "true":
    sandbox_url = os.getenv("SANDBOX_MCP_URL", f"http://localhost:{os.getenv('SANDBOX_MCP_PORT', '8914')}")
    await registry.register(name="sandbox", url=sandbox_url, transport="streamable-http")
```

Update `.env.example` with all new URL vars.

**Test:** Write `tests/unit/test_mcp_registration.py`:
- Test that `create_mcp_registry()` with `GENERATION_SERVICES=true` registers comfyui, whisper, video, music, documents
- Test that `SANDBOX_ENABLED=true` registers sandbox
- Test that with defaults (both false) only core + scrapling + documents are registered
- Test that each registered server has the correct URL and transport type

### TASK 0B — Build Tool Schema Bridge

**File:** Create `src/portal/core/tool_schema_builder.py`

**Problem:** The ToolRegistry has metadata (name, description, parameters) for 24+ internal tools. The MCPRegistry can list tools from each server. But neither produces the OpenAI function-calling format that Ollama needs.

**Action:**

```python
"""Build OpenAI-compatible tool schemas from ToolRegistry and MCPRegistry."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_tool_schemas(
    tool_registry=None,
    mcp_registry=None,
) -> list[dict[str, Any]]:
    """
    Build a combined list of tool definitions in OpenAI function-calling format.

    Returns a list of dicts like:
    [
        {
            "type": "function",
            "function": {
                "name": "generate_image",
                "description": "Generate an image using FLUX via ComfyUI",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Image description"},
                        "width": {"type": "integer", "description": "Width in pixels", "default": 1024},
                    },
                    "required": ["prompt"],
                },
            },
        }
    ]
    """
    tools = []

    # Internal tools from ToolRegistry
    if tool_registry:
        for tool in tool_registry.get_all_tools():
            schema = _convert_internal_tool(tool)
            if schema:
                tools.append(schema)

    # MCP server tools (discovered at startup via list_tools)
    # These are cached after first discovery
    if mcp_registry:
        for server_name in mcp_registry.list_servers():
            # MCP tools are discovered asynchronously — use cached manifests
            pass  # Populated by async initialization, see below

    return tools


def _convert_internal_tool(tool) -> dict[str, Any] | None:
    """Convert a BaseTool instance to OpenAI function schema."""
    try:
        metadata = tool.metadata
        properties = {}
        required = []

        if hasattr(metadata, "parameters") and isinstance(metadata.parameters, list):
            for param in metadata.parameters:
                prop = {"type": getattr(param, "type", "string")}
                if hasattr(param, "description"):
                    prop["description"] = param.description
                if hasattr(param, "default") and param.default is not None:
                    prop["default"] = param.default
                properties[param.name] = prop
                if getattr(param, "required", True):
                    required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": metadata.name,
                "description": metadata.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }
    except Exception as e:
        logger.warning("Failed to convert tool %s: %s", getattr(tool, "metadata", {}).get("name", "?"), e)
        return None
```

Also create an async variant `async def discover_mcp_tool_schemas(mcp_registry)` that calls `list_tools()` on each registered server, converts to OpenAI format, and caches the result.

**Test:** Write `tests/unit/test_tool_schema_builder.py`:
- Test converting a mock BaseTool to OpenAI schema format
- Test that missing metadata is handled gracefully
- Test that the output format matches OpenAI spec (type: function, function: {name, description, parameters})

### TASK 0C — Pass Tool Schemas to Ollama

**File:** `src/portal/routing/model_backends.py` (OllamaBackend)
**File:** `src/portal/routing/execution_engine.py` (ExecutionEngine.execute)
**File:** `src/portal/core/agent_core.py` (AgentCore)

**Problem:** `OllamaBackend.generate()` builds the payload as `{model, messages, stream, options}`. There is no `tools` field. Without it, Ollama models cannot make function calls.

**Action:**

1. Add `tools` parameter to `OllamaBackend.generate()` and `generate_stream()`:

```python
async def generate(
    self,
    prompt: str,
    model_name: str,
    system_prompt: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
    messages: list[dict[str, Any]] | None = None,
    tools: list[dict[str, Any]] | None = None,  # NEW
) -> GenerationResult:
    payload = {
        "model": model_name,
        "messages": self._build_chat_messages(prompt, system_prompt, messages),
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": temperature},
    }
    if tools:
        payload["tools"] = tools
    # ... rest unchanged
```

2. Thread `tools` through `ExecutionEngine.execute()` → `_execute_with_timeout()` → backend.generate()

3. In `AgentCore`, build the tools list at startup using `build_tool_schemas()` and pass it through the execution chain. Cache it — tools don't change at runtime.

4. For `generate_stream()`: Note that when an Ollama model decides to make a tool call during streaming, it returns the tool call in the final chunk. The existing `_resolve_preflight_tools()` handles this for the non-streaming preflight. For streaming, the tool-call-then-final-response loop already exists in `stream_response()`. Just ensure `tools` is passed in the stream payload too.

**Test:** Write `tests/unit/test_tool_pipeline.py`:
- Test that `OllamaBackend.generate()` includes `tools` in payload when provided
- Test that `OllamaBackend.generate()` omits `tools` from payload when None
- Test that `ExecutionEngine.execute()` threads tools through to backend
- Mock Ollama returning a tool_call response, verify it's normalized correctly

### PHASE 0 — GATE CHECK

```bash
# All tests pass
make lint && make test

# MCP registry registers generation servers
python3 -c "
import asyncio, os
os.environ['GENERATION_SERVICES'] = 'true'
os.environ['SANDBOX_ENABLED'] = 'true'
from portal.core.factories import DependencyContainer
from portal.config.settings import load_settings
settings = load_settings()
container = DependencyContainer(settings.to_agent_config())
async def check():
    reg = await container.create_mcp_registry(settings.mcp if hasattr(settings, 'mcp') else None)
    servers = reg.list_servers()
    print(f'Registered servers: {servers}')
    assert len(servers) >= 6, f'Expected 6+ servers, got {len(servers)}: {servers}'
    print('GATE CHECK: PASS')
asyncio.run(check())
"

# Tool schemas build correctly
python3 -c "
from portal.core.tool_schema_builder import build_tool_schemas
from portal.tools import ToolRegistry
reg = ToolRegistry()
reg.discover_and_load()
schemas = build_tool_schemas(tool_registry=reg)
print(f'Tool schemas built: {len(schemas)}')
assert len(schemas) > 0, 'No tool schemas built'
assert schemas[0]['type'] == 'function', 'Wrong schema format'
print('GATE CHECK: PASS')
"

# Ollama payload includes tools field
python3 -c "
# Verify the generate method signature accepts tools parameter
import inspect
from portal.routing.model_backends import OllamaBackend
sig = inspect.signature(OllamaBackend.generate)
assert 'tools' in sig.parameters, 'OllamaBackend.generate() missing tools parameter'
print('GATE CHECK: PASS')
"
```

**All three gate checks must print PASS before starting Phase 1.**

---

## PHASE 1 — Wan2.2 Video + SDXL Images

**Depends on:** Phase 0 (MCP servers registered, tools passed to Ollama)

### TASK 1A — Rewrite Video MCP with Wan2.2 Workflow

**File:** `mcp/generation/video_mcp.py`
**File:** `src/portal/tools/media_tools/video_generator.py`

Replace the CogVideoX workflow (which uses `CheckpointLoaderSimple` — wrong node type for Wan2.2) with a proper Wan2.2 workflow using `UNETLoader`, `CLIPLoader`, `VAELoader`, and `EmptyHunyuanLatentVideo`.

Keep CogVideoX workflow as a fallback selected via `VIDEO_BACKEND=cogvideox` env var. Default: `wan22`.

See the previous Wan2.2 pivot task document for the exact workflow dict, parameters, and env vars. Key changes:
- Default model: `wan2.2_ti2v_5B_fp16.safetensors`
- Default fps: 16 (not 8)
- Default frames: 81 (not 49)
- Add negative_prompt parameter
- Add text_encoder and vae parameters
- `list_video_models()` checks both `UNETLoader` and `CheckpointLoaderSimple`

### TASK 1B — Add SDXL Workflow to Image MCP

**File:** `mcp/generation/comfyui_mcp.py`

Add `_SDXL_WORKFLOW` alongside `FLUX_WORKFLOW`. Select via `IMAGE_BACKEND=sdxl` env var. Default: `flux`.

Key differences from FLUX:
- SDXL uses `EmptyLatentImage` (not `EmptySD3LatentImage`)
- SDXL has negative prompt (separate CLIPTextEncode node)
- SDXL defaults: steps=25, cfg=7.5, sampler=dpmpp_2m_karras
- SDXL checkpoint: `sd_xl_base_1.0.safetensors`

### PHASE 1 — GATE CHECK

```bash
make lint && make test

# Wan2.2 workflow has correct node types
python3 -c "
from mcp.generation.video_mcp import _WAN22_T2V_WORKFLOW
nodes = {v['class_type'] for v in _WAN22_T2V_WORKFLOW.values()}
required = {'UNETLoader', 'CLIPLoader', 'VAELoader', 'EmptyHunyuanLatentVideo'}
assert required.issubset(nodes), f'Missing nodes: {required - nodes}'
print('Wan2.2 workflow: CORRECT')
"

# SDXL workflow exists and has negative prompt
python3 -c "
from mcp.generation.comfyui_mcp import _SDXL_WORKFLOW
node_types = [v['class_type'] for v in _SDXL_WORKFLOW.values()]
assert node_types.count('CLIPTextEncode') == 2, 'SDXL needs 2 CLIPTextEncode (positive + negative)'
print('SDXL workflow: CORRECT')
"
```

---

## PHASE 2 — Fish Speech TTS

**Depends on:** Phase 0 (MCP registration pattern established)

### TASK 2A — Create Fish Speech TTS MCP Server

**File:** Create `mcp/generation/tts_mcp.py`

Fish Speech is a modern TTS engine with MPS support. The MCP server wraps it with three tools:

- `speak(text, voice, speed, output_format)` → generates speech, saves WAV file, returns path
- `clone_voice(text, reference_audio_path)` → zero-shot voice clone, returns path
- `list_voices()` → available voices

Pattern: same as `music_mcp.py` — check if `fish_speech` is importable, run in thread pool to avoid blocking, save to `~/AI_Output/audio/tts/`.

Add `TTS_BACKEND` env var: `fish_speech` (default) or `cosyvoice` (fallback).

Keep existing `audio_generator.py` CosyVoice code as the fallback implementation.

### TASK 2B — Register TTS MCP and Create Launch Script

**File:** `src/portal/core/factories.py` — add TTS server registration (same pattern as video/music)
**File:** Create `mcp/generation/launch_tts_mcp.sh` — same pattern as other launch scripts
**File:** `launch.sh` — add `pkill -f "tts_mcp"` to `stop_all()`, health check to `run_doctor()`
**File:** `.env.example` — add `TTS_MCP_PORT=8916`, `TTS_BACKEND=fish_speech`

### PHASE 2 — GATE CHECK

```bash
make lint && make test

# TTS MCP file exists and has correct tools
python3 -c "
import ast, pathlib
source = pathlib.Path('mcp/generation/tts_mcp.py').read_text()
tree = ast.parse(source)
tools = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and any(
    isinstance(d, ast.Attribute) and d.attr == 'tool' for d in getattr(n, 'decorator_list', [])
)]
print(f'TTS tools: {tools}')
assert 'speak' in tools, 'Missing speak tool'
print('GATE CHECK: PASS')
"

# TTS MCP registered when generation enabled
python3 -c "
import asyncio, os
os.environ['GENERATION_SERVICES'] = 'true'
from portal.core.factories import DependencyContainer
from portal.config.settings import load_settings
settings = load_settings()
container = DependencyContainer(settings.to_agent_config())
async def check():
    reg = await container.create_mcp_registry(settings.mcp if hasattr(settings, 'mcp') else None)
    servers = reg.list_servers()
    assert 'tts' in servers, f'TTS not registered. Servers: {servers}'
    print('GATE CHECK: PASS')
asyncio.run(check())
"
```

---

## PHASE 3 — Interface Integration (Telegram + Slack)

**Depends on:** Phase 0 (tools work so there's something to integrate)

### TASK 3A — Telegram: Workspace Selection via @model: Prefix

**File:** `src/portal/interfaces/telegram/interface.py`

In `handle_text_message()`, before calling `agent_core.process_message()`:

```python
# Parse @model: prefix for workspace selection
workspace_id = None
if message.startswith("@model:"):
    parts = message.split(" ", 1)
    workspace_id = parts[0].replace("@model:", "")
    message = parts[1] if len(parts) > 1 else ""

result = await self.agent_core.process_message(
    chat_id=chat_id,
    message=message,
    interface=InterfaceType.TELEGRAM,
    user_context={"user_id": user_id},
    workspace_id=workspace_id,  # NOW PASSED
)
```

### TASK 3B — Slack: Workspace Selection + Stop Hardcoding "auto"

**File:** `src/portal/interfaces/slack/interface.py`

In `_handle_message()`, parse `@model:` prefix same as Telegram. Change `model="auto"` in IncomingMessage to use the parsed workspace or default to `"auto"`.

### TASK 3C — Telegram: File Delivery

**File:** `src/portal/interfaces/telegram/interface.py`

After receiving `ProcessingResult`, check if the response contains file paths or URLs from tool results. If so, send as Telegram media:

```python
# Detect generated files in response
if result.tools_used:
    for tool_result in getattr(result, "tool_results", []):
        file_path = tool_result.get("path") or tool_result.get("image_path") or tool_result.get("audio_path")
        if file_path and Path(file_path).exists():
            suffix = Path(file_path).suffix.lower()
            if suffix in (".png", ".jpg", ".jpeg", ".webp"):
                await update.message.reply_photo(open(file_path, "rb"))
            elif suffix in (".wav", ".mp3", ".ogg"):
                await update.message.reply_audio(open(file_path, "rb"))
            elif suffix in (".mp4", ".webm"):
                await update.message.reply_video(open(file_path, "rb"))
            else:
                await update.message.reply_document(open(file_path, "rb"))
```

Note: `ProcessingResult` may need a `tool_results` field added to carry file paths from tool dispatch back to the interface. Check the dataclass definition and add it if missing.

### TASK 3D — Slack: File Delivery

Same pattern using `self.client.files_upload_v2(channel=channel, file=file_path)`.

### PHASE 3 — GATE CHECK

```bash
make lint && make test

# Telegram parses @model: prefix
python3 -c "
# Verify workspace_id is passed to process_message
import ast, pathlib
source = pathlib.Path('src/portal/interfaces/telegram/interface.py').read_text()
assert 'workspace_id' in source, 'Telegram does not pass workspace_id'
print('Telegram workspace: PASS')
"

# Slack no longer hardcodes model='auto'
python3 -c "
import pathlib
source = pathlib.Path('src/portal/interfaces/slack/interface.py').read_text()
# Should not have model=\"auto\" hardcoded in IncomingMessage constructor
lines = [l for l in source.split('\n') if 'model=\"auto\"' in l and 'IncomingMessage' in source[max(0,source.find(l)-200):source.find(l)+10]]
# This is a heuristic check — verify manually if needed
print('Slack model selection: CHECK MANUALLY')
"
```

---

## PHASE 4 — Fix Orchestrator Detection

**Depends on:** Nothing — can run in parallel with other phases

### TASK 4A — Rewrite _is_multi_step() with Conservative Regex

**File:** `src/portal/core/agent_core.py`

Replace the current keyword/verb-count heuristic with regex that only matches explicitly structured multi-step requests:

```python
import re

_MULTI_STEP_PATTERNS = [
    re.compile(r"step\s*1\b.*step\s*2\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"\bfirst\b.{5,}\bthen\b.{5,}\b(?:then|finally|lastly)\b", re.IGNORECASE | re.DOTALL),
    re.compile(r"(?:do|perform)\s+both\b", re.IGNORECASE),
    re.compile(r"\b1\)\s.+\b2\)\s", re.IGNORECASE | re.DOTALL),
]

def _is_multi_step(self, message: str) -> bool:
    """Detect ONLY explicitly structured multi-step requests.
    Conservative: false negatives are fine (normal processing handles single-turn).
    False positives break context, routing, streaming, and metrics.
    """
    return any(p.search(message) for p in _MULTI_STEP_PATTERNS)
```

### TASK 4B — Tests for Detection Accuracy

**File:** Create `tests/unit/test_multi_step_detection.py`

```python
MUST_BE_FALSE = [
    "Write a Python function that generates CSV files",
    "First, let me explain quantum computing",
    "Find and summarize the key points about AI safety",
    "Create a detailed report on market trends",
    "Explain why transformers work and describe their architecture",
    "Write a function that creates and returns a dictionary",
    "Generate an image of a sunset over the ocean",
    "Can you help me find a good restaurant",
]

MUST_BE_TRUE = [
    "Step 1: research quantum computing. Step 2: create a presentation about it",
    "First research the topic, then write a report, then finally create slides",
    "Do both: write the code and create the documentation for it",
    "1) Research AI safety 2) Write a summary 3) Create slides",
]
```

### PHASE 4 — GATE CHECK

```bash
make lint && make test

python3 -c "
from portal.core.agent_core import AgentCore
# Test with a minimal mock — we just need the method
class FakeCore:
    pass
core = FakeCore()
core._is_multi_step = AgentCore._is_multi_step.__get__(core)

false_cases = [
    'Write a Python function that generates CSV files',
    'First, let me explain quantum computing',
    'Find and summarize the key points',
    'Create a detailed report on market trends',
]
true_cases = [
    'Step 1: research quantum computing. Step 2: create a presentation',
    'First research the topic, then write a report, then finally create slides',
]

for msg in false_cases:
    assert not core._is_multi_step(msg), f'FALSE POSITIVE: {msg}'
for msg in true_cases:
    assert core._is_multi_step(msg), f'FALSE NEGATIVE: {msg}'
print('GATE CHECK: PASS — all detection tests correct')
"
```

---

## PHASE 5 — Documentation

**Depends on:** Phases 0-4 complete (document reality, not aspiration)

### TASK 5A — Rewrite PORTAL_HOW_IT_WORKS.md Feature Statuses

Re-evaluate every feature status now that the tool pipeline is connected. Update the capability matrix. Every "NEEDS BACKEND" item should clarify exactly which backend and how to install it.

### TASK 5B — Write End-to-End Usage Guide for Each Capability

For each feature, document the exact user flow from "I want to..." to result:
- What interface to use
- What to type / select
- What happens internally (briefly)
- What the user sees
- What prerequisites are needed
- Example with expected output

### TASK 5C — Document Telegram and Slack Completely

Full setup guides:
- How to create bot / app
- How to get your user/chat ID
- Every env var with examples
- Every command available
- How workspace selection works (@model: prefix)
- How file delivery works
- Rate limiting behavior
- What works vs what needs backends

### TASK 5D — ComfyUI + Wan2.2 + SDXL Setup Guide

Model download commands, ComfyUI installation, MPS launch flags, custom nodes needed. Pull from the uploaded video_comparison.md guide.

### TASK 5E — Update ARCHITECTURE.md, README.md, CLAUDE.md

- ARCHITECTURE.md: orchestrator, /v1/files, all MCP servers, tool schema builder
- README.md: capabilities overview section
- CLAUDE.md: version, new components in project layout

### PHASE 5 — GATE CHECK

```bash
make lint && make test

# Verify docs mention all key components
python3 -c "
import pathlib
hiw = pathlib.Path('PORTAL_HOW_IT_WORKS.md').read_text()
required = ['Wan2.2', 'Fish Speech', 'SDXL', '/v1/files', 'orchestrat', '@model:', 'Telegram', 'Slack']
for term in required:
    assert term.lower() in hiw.lower(), f'HOW_IT_WORKS missing: {term}'
print('GATE CHECK: PASS — all terms present in docs')
"
```

---

## PHASE 6 — Deployment Alignment

**Depends on:** Phases 0-2 (new servers to deploy)

### TASK 6A — launch.sh Doctor Checks All MCP Ports

**File:** `launch.sh`

Add health checks for all MCP servers in `run_doctor()`:
- video_mcp (:8911)
- music_mcp (:8912)
- documents_mcp (:8913)
- sandbox_mcp (:8914)
- whisper_mcp (:8915)
- tts_mcp (:8916)

### TASK 6B — docker-compose.yml Registration

**File:** `docker-compose.yml`

Ensure portal-api environment includes MCP server URLs pointing to Docker service names (e.g., `VIDEO_MCP_URL=http://mcp-video:8911`).

Add `comfyui_custom_nodes` volume to persist installed ComfyUI nodes.

### TASK 6C — Model Download Documentation

Add comments to docker-compose.yml explaining how to download Wan2.2 models, FLUX models, and SDXL models for the ComfyUI container.

### PHASE 6 — GATE CHECK

```bash
# YAML valid
python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml')); print('docker-compose: VALID')"

# Bash syntax
bash -n launch.sh && echo "launch.sh: OK"

# Doctor checks new ports
grep -c "8911\|8912\|8913\|8914\|8915\|8916" launch.sh
# Should be >= 6

make lint && make test
echo "ALL PHASES COMPLETE"
```

---

## After All Phases: Run Documentation Agent v4

Once all 6 phases are complete and all gate checks pass, run the `PORTAL_DOCUMENTATION_AGENT_v4.md` prompt in a fresh Claude Code session. It will:
1. Build the environment from scratch
2. Run every test
3. Exercise every feature
4. Verify every tool pipeline
5. Document what actually works vs what doesn't
6. Generate verified `PORTAL_HOW_IT_WORKS.md`

Any discrepancies it finds become the next round of fixes.

---

## Summary

| Phase | What | Unlocks | Effort |
|---|---|---|---|
| 0 | Tool pipeline (schemas + registration) | Every generation feature | 2-3 days |
| 1 | Wan2.2 video + SDXL images | Correct model workflows | 1 day |
| 2 | Fish Speech TTS | Voice synthesis on M4 | 1 day |
| 3 | Telegram + Slack integration | Full-featured interfaces | 1-2 days |
| 4 | Orchestrator fix | Stop hijacking normal prompts | 2 hours |
| 5 | Documentation | Truth in docs | 2-3 days |
| 6 | Deployment | Docker + launch alignment | 1 day |

**Total: ~10-12 days. Phase 0 is the foundation. Start there.**
