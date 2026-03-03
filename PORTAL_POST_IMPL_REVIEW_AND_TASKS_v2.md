# Portal — Post-Implementation Honest Review & Targeted Corrections

**Reviewed:** commit c556209 (after all Phase 0-6 implementation)
**Version:** 3.0.0
**Date:** 2026-03-02

---

## Overall Verdict

The Phase 0-6 implementation landed the critical architecture changes. The tool pipeline IS connected — tool schemas are built, threaded through execution engine to Ollama, and MCP servers are registered. This is a real, structural improvement. The Wan2.2 video workflow, SDXL image workflow, Fish Speech TTS MCP, Telegram/Slack workspace selection, file delivery, and conservative orchestrator detection are all present.

But the execution was uneven. Several wires got connected on one end but not the other. Here is every issue found, organized by severity.

---

## CRITICAL — Breaks Intended Functionality

### C-1: ProcessingResult.tool_results Never Populated

**Impact:** Telegram and Slack file delivery is dead. The code checks `result.tool_results` to find generated files, but `tool_results` is never set on the ProcessingResult object.

**Evidence:** `agent_core.py` line 327 and 379 — both `ProcessingResult()` constructors do NOT include `tool_results=`. The tool results are placed in `metadata["tool_results"]` instead.

**The dataclass has the field** (`types.py` line 83: `tool_results: list[dict[str, Any]]`). **The Telegram code reads it** (`interface.py` line 544: `if result.tool_results:`). But agent_core never sets it.

**Fix:** In `_build_processing_result()` (line 327), add `tool_results=tool_results,` to the ProcessingResult constructor. Same for the orchestrated request result (line 379).

### C-2: video_generator.py Still Uses CogVideoX Workflow

**Impact:** The internal tool (used by ToolRegistry/BaseTool path) still has the old CogVideoX `CheckpointLoaderSimple` workflow. Only the MCP server (`video_mcp.py`) was updated to Wan2.2.

**Evidence:** `src/portal/tools/media_tools/video_generator.py` line 17: `"# Minimal CogVideoX workflow template"`, line 20: `"class_type": "CheckpointLoaderSimple"`.

**Fix:** Mirror the Wan2.2 workflow changes from `video_mcp.py` into `video_generator.py`. Add `VIDEO_BACKEND` support. Or deprecate the internal tool in favor of the MCP server (it's redundant).

### C-3: File Output Path Fragmentation

**Impact:** `/v1/files` serves ONLY from `data/generated/`. But music writes to `~/AI_Output/music/`, TTS writes to `~/AI_Output/tts/`, video returns a ComfyUI URL. So:
- Document creation → downloadable via `/v1/files` ✓
- Music generation → file exists but NOT downloadable ✗
- TTS generation → file exists but NOT downloadable ✗
- Video generation → URL only, no local file ✗
- Image generation (ComfyUI) → ComfyUI URL only ✗
- Image generation (mflux) → `~/AI_Output/images/`, NOT downloadable ✗

Telegram file delivery reads `tool_results` paths — but even if C-1 is fixed, the files are in `~/AI_Output/` which the Telegram process CAN access (same host). However, Open WebUI users cannot download them via the web API.

**Fix:** Either:
- (A) Make all tools write to `data/generated/` (simplest, unified)
- (B) Make `/v1/files` serve from multiple directories
- (C) Add a file copy step in tool dispatch that copies outputs to `data/generated/`

Option A is cleanest. Change `OUTPUT_DIR` in `music_mcp.py`, `tts_mcp.py`, and `image_generator.py` to use `data/generated/` by default.

---

## HIGH — Missing or Incomplete

### H-1: No Tests for Any Phase 0-6 Feature

**Impact:** Zero regression protection for the entire tool pipeline.

**Missing tests:**
- Tool schema builder (`tool_schema_builder.py`) — 0 tests
- MCP server registration in factories — 0 tests
- Tools field in Ollama payload — 0 tests
- Wan2.2 workflow structure — 0 tests
- SDXL workflow structure — 0 tests
- Fish Speech TTS MCP — 0 tests
- Telegram workspace parsing — 0 tests
- Slack workspace parsing — 0 tests
- File delivery endpoint — exists (`test_file_delivery.py`) but check coverage
- Multi-step detection — exists (`test_multi_step_detection.py`) but check coverage

Only 2 of ~12 expected test files were created.

### H-2: launch.sh Missing TTS in stop_all and doctor

**Evidence:** `pkill -f "tts_mcp"` is NOT in `stop_all()`. TTS and Whisper health checks are NOT in `run_doctor()`.

### H-3: .env.example Missing VIDEO_BACKEND, IMAGE_BACKEND, VIDEO_TEXT_ENCODER, VIDEO_VAE

**Evidence:** Code reads `VIDEO_BACKEND` (default `wan22`) and `IMAGE_BACKEND` (default `flux`) but `.env.example` doesn't document them. Users won't know these exist.

### H-4: BaronLLM Not in Security Fallback Chain

**Evidence:** `router_rules.json` auto-security fallbacks: `["lazarevtill/Llama-3-WhiteRabbitNeo-8B-v2.0:q4_0", "dolphin-llama3:70b"]`. BaronLLM is in `default_models.json` (auto-pulled) but never routed to.

### H-5: Metrics Import Failure

**Evidence:** HOW_IT_WORKS.md documents: `src.portal.observability.metrics fails on import due to duplicate timeseries 'portal_requests_per_minute'`. This breaks the metrics endpoint.

---

## MEDIUM — Documentation Gaps

### M-1: Feature Catalog Has No End-to-End Usage Guides

The HOW_IT_WORKS Section 5 "Feature Catalog" is 79 lines covering 8 subsections (with duplicate numbering). It doesn't have per-feature "I want to..." → step-by-step → result guides for:
- Image generation (either path)
- Video generation
- Music generation
- TTS / voice cloning
- Document creation
- Code sandbox
- RAG / knowledge base
- Red team / blue team workflows
- Web research
- Orchestration

### M-2: No Wan2.2 / ComfyUI / SDXL Setup Instructions

Zero `huggingface-cli download` commands. Zero `comfy install` instructions. Zero `comfy launch -- --mps --highvram` guidance. Users have no idea how to install the backends. Your uploaded guide has all of this — it needs to be in the docs.

### M-3: Telegram / Slack Not Fully Documented

Current docs list config vars and commands in 4 lines each. Missing:
- How to create a Telegram bot via @BotFather
- How to get your Telegram chat ID
- How @model: prefix works with examples
- How file delivery works (images sent as photos, audio as audio, etc.)
- Rate limiting behavior
- HITL approval flow
- Same depth for Slack (creating app, setting up Events API, Request URL, etc.)

### M-4: Section Numbering Broken

Feature catalog has two 5.4s and two 5.5s.

### M-5: ARCHITECTURE.md Barely Updated

Only 2 mentions of new components. Missing: tool_schema_builder, tts_mcp, complete MCP server list, file delivery endpoint, orchestrator integration.

---

## Coding Agent Task — Targeted Corrections

### Session Bootstrap
```bash
cd /Users/chris/portal
source .venv/bin/activate
pip install -e ".[all,dev,test]" -q
make lint && make test-unit
```

### TASK 1: Fix ProcessingResult.tool_results Population (CRITICAL)

**Files:** `src/portal/core/agent_core.py`

In `_build_processing_result()` (~line 327), the ProcessingResult constructor has `metadata={"tool_results": tool_results}` but NOT `tool_results=tool_results` at the top level.

Add `tool_results=tool_results,` to the ProcessingResult() call. There are two constructor sites (line 327 for normal flow, line 379 for orchestrator flow) — fix both.

**Test:** `tests/unit/test_tool_results_delivery.py`
- Build a ProcessingResult with tool_results
- Verify `result.tool_results` is populated (not empty)
- Verify it's not only in metadata

### TASK 2: Unify File Output Paths (CRITICAL)

**Files:** `mcp/generation/music_mcp.py`, `mcp/generation/tts_mcp.py`

Change `OUTPUT_DIR` from `~/AI_Output/music/` and `~/AI_Output/tts/` to `Path(os.getenv("GENERATED_FILES_DIR", "data/generated"))`. This way all generated files are served by `/v1/files`.

For the internal `image_generator.py`, change default `output_dir` to `data/generated` as well.

Keep the env var override so users can redirect output if desired.

**Test:** Verify music/TTS/image tools write to `data/generated/` by default.

### TASK 3: Update video_generator.py with Wan2.2 (CRITICAL)

**File:** `src/portal/tools/media_tools/video_generator.py`

Mirror the changes from `mcp/generation/video_mcp.py`:
- Add `_WAN22_T2V_WORKFLOW` with correct node types
- Keep `_COGVIDEOX_WORKFLOW` as fallback
- Add `VIDEO_BACKEND` env var support
- Update defaults (fps=16, frames=81, model=wan2.2_ti2v_5B_fp16.safetensors)

### TASK 4: Fix launch.sh Gaps (HIGH)

**File:** `launch.sh`

Add to `stop_all()`:
```bash
pkill -f "tts_mcp" 2>/dev/null && echo "[tts_mcp] stopped" || true
```

Add to `run_doctor()` (inside the MCP check block):
```bash
check_service "mcp-tts" "http://localhost:${TTS_MCP_PORT:-8916}/health" "true"
check_service "mcp-whisper" "http://localhost:${WHISPER_MCP_PORT:-8915}/health" "true"
```

### TASK 5: Fix .env.example (HIGH)

Add these documented vars:
```bash
# Video backend workflow: wan22 (default, M4 optimized) | cogvideox (CUDA)
# VIDEO_BACKEND=wan22
# Wan2.2 text encoder model
# VIDEO_TEXT_ENCODER=umt5_xxl_fp8_e4m3fn_scaled.safetensors
# Wan2.2 VAE model
# VIDEO_VAE=wan2.2_vae.safetensors

# Image backend: flux (default, fast) | sdxl (quality, LoRA ecosystem)
# IMAGE_BACKEND=flux
```

### TASK 6: Add BaronLLM to Security Fallback (HIGH)

**File:** `src/portal/routing/router_rules.json`

Change auto-security fallback from:
```json
["lazarevtill/Llama-3-WhiteRabbitNeo-8B-v2.0:q4_0", "dolphin-llama3:70b"]
```
to:
```json
["lazarevtill/Llama-3-WhiteRabbitNeo-8B-v2.0:q4_0", "huihui_ai/baronllm-abliterated", "dolphin-llama3:70b"]
```

### TASK 7: Fix Metrics Duplicate Timeseries (HIGH)

**File:** `src/portal/observability/metrics.py`

The `portal_requests_per_minute` Gauge is registered twice or conflicts with an existing registration. Fix by using `try/except` around registration or checking if it already exists in the CollectorRegistry.

### TASK 8: Write Missing Tests (HIGH)

Create these test files:

**`tests/unit/test_tool_schema_builder.py`:**
- Test `_convert_internal_tool()` with a mock BaseTool
- Test `build_tool_schemas()` with a populated ToolRegistry
- Test output format matches OpenAI spec (`type: "function"`)
- Test graceful handling of tools with missing metadata

**`tests/unit/test_mcp_registration.py`:**
- Test `create_mcp_registry()` with GENERATION_SERVICES=true registers video, music, comfyui, whisper, tts
- Test with SANDBOX_ENABLED=true registers sandbox
- Test documents always registered
- Test with defaults: only core + scrapling + documents

**`tests/unit/test_ollama_tools_payload.py`:**
- Test `OllamaBackend.generate()` includes `tools` in payload when provided
- Test omits `tools` when None
- Test `ExecutionEngine.execute()` threads tools parameter through

**`tests/unit/mcp/test_wan22_workflow.py`:**
- Test `_WAN22_T2V_WORKFLOW` has UNETLoader, CLIPLoader, VAELoader, EmptyHunyuanLatentVideo
- Test `_COGVIDEOX_WORKFLOW` has CheckpointLoaderSimple
- Test workflow selection via VIDEO_BACKEND env var

**`tests/unit/mcp/test_sdxl_workflow.py`:**
- Test SDXL workflow has 2 CLIPTextEncode nodes (positive + negative)
- Test FLUX workflow is default
- Test IMAGE_BACKEND selection

**`tests/unit/test_telegram_workspace.py`:**
- Test @model:auto-security prefix parsing
- Test message without @model: gets workspace_id=None
- Test @model: is stripped from the message text

**`tests/unit/test_slack_workspace.py`:**
- Same as Telegram

### TASK 9: Write Complete Feature Documentation (MEDIUM)

**File:** `PORTAL_HOW_IT_WORKS.md` — Rewrite Section 5 "Feature Catalog"

Fix section numbering. Add per-feature subsections for EVERY capability:

For each feature, document:
1. **What it is** (one line)
2. **How to use it** (step-by-step from user's perspective)
3. **What happens internally** (brief)
4. **Prerequisites** (what backend/model to install)
5. **Setup commands** (huggingface-cli download, pip install, etc.)
6. **Works via** (Web, Telegram, Slack — which ones)
7. **Example prompt and expected result**

Features to cover:
- 5.1 Text Chat
- 5.2 Code Generation
- 5.3 Image Generation (FLUX + SDXL + mflux)
- 5.4 Video Generation (Wan2.2 + CogVideoX)
- 5.5 Music Generation (AudioCraft)
- 5.6 TTS / Voice Cloning (Fish Speech + CosyVoice)
- 5.7 Speech-to-Text (Whisper)
- 5.8 Document Creation (Word, PowerPoint, Excel)
- 5.9 Code Execution Sandbox
- 5.10 Red Team / Offensive Security
- 5.11 Blue Team / Defensive Security / Splunk
- 5.12 Creative Writing
- 5.13 Deep Reasoning / Research
- 5.14 Web Research (Scrapling/DDG)
- 5.15 RAG / Knowledge Base
- 5.16 Multi-Step Orchestration
- 5.17 Multimodal (Qwen3-Omni)

Add Section 5.18 "Telegram Bot — Complete Setup Guide" and Section 5.19 "Slack Bot — Complete Setup Guide" with full setup-to-usage walkthroughs.

### TASK 10: Update Supporting Docs (MEDIUM)

**`docs/ARCHITECTURE.md`:** Add tool_schema_builder, tts_mcp, all MCP servers, file delivery endpoint, orchestrator, and updated architecture diagram

**`README.md`:** Add Capabilities section listing all 17 feature verticals

**`.env.example`:** Per TASK 5

---

## Priority Order

| # | Task | Severity | Effort |
|---|---|---|---|
| 1 | Fix ProcessingResult.tool_results | CRITICAL | 15 min |
| 2 | Unify file output paths | CRITICAL | 30 min |
| 3 | Update video_generator.py Wan2.2 | CRITICAL | 1 hour |
| 4 | Fix launch.sh (tts stop + doctor) | HIGH | 15 min |
| 5 | Fix .env.example | HIGH | 15 min |
| 6 | BaronLLM fallback | HIGH | 5 min |
| 7 | Fix metrics duplicate | HIGH | 30 min |
| 8 | Write missing tests | HIGH | 3-4 hours |
| 9 | Feature documentation rewrite | MEDIUM | 4-6 hours |
| 10 | Supporting docs update | MEDIUM | 2 hours |

**Total: ~12-14 hours. Tasks 1-7 are under 3 hours combined — do those first.**

---

## What Actually Works Now (Updated Honest List)

**End-to-end functional (no gaps):**
1. Text chat via all interfaces ✓
2. Workspace routing (11 workspaces, correct models) ✓
3. Intelligent query classification (12 categories) ✓
4. @model: override in router ✓
5. Health checks, metrics endpoint, doctor ✓
6. API key auth, rate limiting, CORS, input sanitization ✓
7. File delivery endpoint for `data/generated/` ✓
8. Web research (scrapling + DDG) ✓
9. Conservative orchestrator detection ✓
10. Tool schemas passed to Ollama ✓ (NEW)
11. MCP servers registered at startup ✓ (NEW)
12. Telegram @model: workspace selection ✓ (NEW)
13. Slack @model: workspace selection ✓ (NEW)

**Pipeline connected but needs backend service:**
14. Image gen via ComfyUI (FLUX + SDXL workflows) — needs ComfyUI running
15. Video gen via ComfyUI MCP (Wan2.2 workflow) — needs ComfyUI + Wan2.2 models
16. Music gen via AudioCraft MCP — needs AudioCraft installed
17. TTS via Fish Speech MCP — needs Fish Speech installed
18. Document creation via MCP — needs python-docx/pptx/openpyxl
19. Code sandbox via MCP — needs Docker + SANDBOX_ENABLED

**Broken (need the fixes above):**
20. Telegram/Slack file delivery — tool_results not populated (C-1)
21. Music/TTS/Image files not downloadable via /v1/files — wrong output dir (C-3)
22. Internal video tool uses wrong workflow (C-2)
23. Metrics import fails (H-5)