# Portal — Gap Analysis & Action Prompt for Finish Line

**Generated:** 2026-03-02
**Source:** Deep-dive audit of https://github.com/ckindle-42/portal (commit latest on main)
**Current version:** 1.4.7
**Target state:** Total inclusive offline AI platform — images, video, music, red/blue team, creative writing, programming, documents, presentations, and more — all local-first, zero cloud.

---

## 1. Executive Summary

Portal has an exceptionally solid foundation: clean architecture, 919 passing tests, zero lint/mypy issues, modular interfaces, intelligent routing, workspace system, MCP tool layer, and multi-hardware support. The *engineering quality* is production-grade.

However, the **"How It Works" documentation and feature catalog** do not align with the **intended vision** of a total inclusive offline platform. Multiple capabilities are listed as "VERIFIED" that are actually stubs or have no end-to-end path. Several core capabilities needed for the finish line (video generation, music generation, offline search, multi-step orchestration) are entirely absent from both code and docs. The docker-compose deployment doesn't wire up generation services at all.

This document identifies every gap between **current reality** and **finish-line vision**, organized into actionable work items.

---

## 2. Documentation Corrections (HOW_IT_WORKS.md Misalignments)

These items are factual inaccuracies in PORTAL_HOW_IT_WORKS.md that need immediate correction.

### D-01: Image Generation Status Is Wrong

**Current doc says:** "STUB — Image generator module exists but requires mflux CLI"
**Reality:** Two separate, complete implementations exist:
- `src/portal/tools/media_tools/image_generator.py` — full mflux CLI wrapper (Mac/MLX only)
- `mcp/generation/comfyui_mcp.py` — full ComfyUI FLUX.1-schnell MCP server (hardware-agnostic)

**Fix:** Change status to "IMPLEMENTED (requires mflux or ComfyUI backend)" and document both paths with setup instructions per hardware profile.

### D-02: Voice Cloning Status Is Wrong

**Current doc says:** "NOT IMPLEMENTED — CosyVoice integration planned but not complete"
**Reality:** `audio_generator.py` has a complete `clone_voice()` function with CosyVoice zero-shot mode support (lines 138-224). It follows the same pattern as `generate_audio()` which the doc marks as implemented.

**Fix:** Change to "IMPLEMENTED (requires CosyVoice + torchaudio installation)".

### D-03: Audio Generation Status Is Misleading

**Current doc says:** "STUB — Audio generator module exists but requires CosyVoice2 installation"
**Reality:** The module is not a stub — it's a complete implementation with TTS, voice selection, and voice cloning. It just has a runtime dependency that must be installed.

**Fix:** Change to "IMPLEMENTED (requires CosyVoice2 + torchaudio). Supports TTS and voice cloning."

### D-04: Feature Status Matrix Uses "VERIFIED" Misleadingly

The matrix conflates "code exists and unit tests pass" with "works end-to-end on hardware." For example, image generation is marked "STUB" in the feature catalog but the code is complete — the distinction is whether the *backend* (mflux, ComfyUI) is installed.

**Fix:** Add a third column "Backend Required" and use statuses: READY (no external dep), NEEDS BACKEND (code complete, requires X), NOT IMPLEMENTED (no code exists).

### D-05: CLAUDE.md Version and Architecture Drift

- CLAUDE.md says version 1.4.6 but project is 1.4.7
- CLAUDE.md still references LMStudio backend which was removed (ROAD-D01)
- Architecture line says "Ollama/LMStudio/MLX" — should be "Ollama/MLX"

**Fix:** Update version, remove all LMStudio references.

### D-06: Music Generation Is Not CosyVoice

CosyVoice is TTS (text-to-speech), not music generation. The routing classifier has `audio_gen` as a category and regex matches for `music gen` and `sound effect`, but these route to the same generic model with no actual music generation backend.

**Fix:** Clearly separate TTS (CosyVoice — implemented) from music generation (AudioCraft/MusicGen — not implemented) in all docs.

---

## 3. Missing Capabilities for "Total Inclusive" Vision

These are features that must exist for the project to deliver on its stated intent. Each item includes scope, suggested implementation, and estimated effort.

### F-01: Video Generation (NOT IMPLEMENTED)

**Current state:** Only a comment in `media_tools/__init__.py`: `"(future) video/: Video processing"`. No code, no MCP, no workspace.

**Required for finish line:**
- Video generation MCP server wrapping a local backend (CogVideoX, Mochi, or Wan2.1 via ComfyUI)
- `auto-video` workspace in `router_rules.json`
- Routing regex for video generation keywords
- Integration with ComfyUI workflow API (same pattern as `comfyui_mcp.py` image gen)

**Suggested approach:**
1. Create `mcp/generation/video_mcp.py` using FastMCP, wrapping ComfyUI video workflows
2. Add `auto-video` workspace to `router_rules.json` mapped to multimodal model
3. Add video regex rule to task classifier
4. Add `video_generator.py` tool to `media_tools/`
5. Hardware profile notes: CUDA required for reasonable performance; M4 Mac possible with Mochi-small

**Effort:** 2-3 days

### F-02: Music Generation (NOT IMPLEMENTED)

**Current state:** TTS exists via CosyVoice. No actual music/audio content generation.

**Required for finish line:**
- Music generation MCP server wrapping AudioCraft/MusicGen or Stable Audio
- `auto-music` workspace in `router_rules.json`
- `music_generator.py` tool in `media_tools/`
- Routing regex for music-specific keywords

**Suggested approach:**
1. Create `mcp/generation/music_mcp.py` wrapping Meta AudioCraft (MusicGen-Medium runs on 16GB VRAM / M4 unified)
2. Add `auto-music` workspace
3. Add `music_generator.py` with genre, duration, tempo parameters
4. Support both text-to-music and melody conditioning modes

**Effort:** 2-3 days

### F-03: Offline Web Search / Knowledge Retrieval (PARTIALLY IMPLEMENTED)

**Current state:** `web_scrape_mcp_server.py` uses DuckDuckGo API which requires internet. This violates the "zero cloud" principle. Local knowledge base exists but is limited to pre-ingested documents.

**Required for finish line:**
- Local search engine (SearXNG self-hosted or cached Wikipedia/docs)
- Or: expanded RAG pipeline with automated document ingestion from user-specified directories
- Offline-first search that works without any internet connection

**Suggested approach:**
1. Add SearXNG to docker-compose as a local search aggregator (can run fully offline with cached indices)
2. Or: Create a filesystem-crawler MCP that indexes local directories and provides full-text search
3. Enhance `local_knowledge.py` with automatic directory watching and re-indexing
4. Update `web_scrape_mcp_server.py` to try local SearXNG first, DDG as fallback

**Effort:** 2-3 days

### F-04: Multi-Step Task Orchestration / Agent Chains (NOT IMPLEMENTED)

**Current state:** AgentCore processes single request → single response. No ability to chain tasks like "research X → create slides → generate cover image."

**Required for finish line:**
- Task decomposition system that breaks complex prompts into sequential tool calls
- Pipeline/workflow definitions (YAML or JSON)
- Progress tracking and intermediate result passing

**Suggested approach:**
1. Add `portal.core.orchestrator` module with `TaskPlan` and `StepExecutor`
2. Orchestrator uses the routing LLM to decompose into steps
3. Each step maps to a tool call or LLM call
4. Results pass forward as context to subsequent steps
5. Keep it simple: linear chains first, DAG later

**Effort:** 3-5 days

### F-05: Document Tools Not Exposed via MCP (PARTIALLY IMPLEMENTED)

**Current state:** Word, PowerPoint, Excel processors exist as `BaseTool` subclasses with full implementations. But they're only discoverable through the internal `ToolRegistry` — they're not exposed as MCP endpoints that external UIs can call, and there's no file upload/download path from Open WebUI.

**Required for finish line:**
- Document tools exposed as MCP endpoints with file handling
- File upload endpoint on the API (or leverage Open WebUI's file handling)
- Download links for generated documents
- `auto-documents` workspace for document-focused tasks

**Suggested approach:**
1. Create `mcp/documents/document_mcp.py` wrapping word_processor, powerpoint_processor, excel_processor
2. Add file upload endpoint at `/v1/files/upload` and download at `/v1/files/{id}`
3. Store generated files in `data/generated/` with unique IDs
4. Add `auto-documents` workspace routed to a model strong at structured output
5. Wire into Open WebUI's file handling if supported

**Effort:** 2-3 days

### F-06: Code Execution Sandbox Not Wired Up (PARTIALLY IMPLEMENTED)

**Current state:** `security/sandbox/docker_sandbox.py` exists with a full Docker-based sandbox. `SANDBOX_ENABLED=false` by default. No docker-compose service. The `mcp-shell` service in compose only allows a tiny whitelist of read-only commands.

**Required for finish line:**
- Sandbox available as a first-class execution environment for code the LLM generates
- Auto-installs common packages (numpy, pandas, matplotlib, etc.)
- Returns stdout, stderr, and generated files
- Security boundary: no network, resource limits, timeout

**Suggested approach:**
1. Create a dedicated sandbox Docker image with common Python/Node packages pre-installed
2. Add `mcp/execution/code_sandbox_mcp.py` exposing `run_python`, `run_node`, `run_bash`
3. Add to docker-compose with `network_mode: none` and resource limits
4. Integrate with agent_core tool dispatch
5. Return generated files (images, CSVs) via the file endpoint (F-05)

**Effort:** 2-3 days

### F-07: Embedding Model Management (MISSING)

**Current state:** Knowledge base tools assume `sentence-transformers` is installed and a model is cached. No management of which embedding model to use, no automated download, no fallback.

**Required for finish line:**
- Embedding model auto-download on first use
- Hardware-appropriate model selection (smaller for CPU, larger for GPU/MPS)
- Config option for embedding model in settings
- Graceful degradation when no embedding model is available

**Suggested approach:**
1. Add `PORTAL_EMBEDDING_MODEL` to settings with default `all-MiniLM-L6-v2`
2. Add auto-download logic to knowledge base initialization
3. Add health check for embedding model availability
4. Use Ollama's embedding endpoint as an alternative backend

**Effort:** 1 day

---

## 4. Deployment / docker-compose Gaps

The current `docker-compose.yml` is missing services that the codebase supports.

### DC-01: No ComfyUI Service

ComfyUI MCP server exists at `mcp/generation/comfyui_mcp.py` but ComfyUI itself isn't in docker-compose. Image generation (and future video generation) requires it.

**Fix:** Add ComfyUI container with appropriate GPU passthrough config per hardware profile.

### DC-02: No Generation MCP Services in Compose

`mcp/generation/launch_generation_mcps.sh` launches ComfyUI and Whisper MCPs but only for bare-metal. Docker users get no generation services.

**Fix:** Add `mcp-comfyui` and `mcp-whisper` services to docker-compose, or add them to the Portal API container's startup.

### DC-03: No Proxy Router Service

The proxy router at `:8000` (`src/portal/routing/router.py`) is referenced throughout docs but isn't in docker-compose. Open WebUI needs it for workspace-based routing.

**Fix:** Add a `portal-router` service running the proxy router, or integrate it into the portal-api service startup.

### DC-04: No MLX Server for Mac Docker

MLX backend (`MLXServerBackend`) exists but the `mlx_lm.server` process isn't started by docker-compose.

**Fix:** For Mac bare-metal (primary target), add MLX server to launch.sh. For Docker, document that MLX must run on host and be accessible at configured URL.

### DC-05: Model Auto-Pull Not in Docker Init

`ModelPuller` auto-downloads missing Ollama models but only runs at application startup, not as a docker-compose init step. First boot with Docker takes a very long time with no progress indication.

**Fix:** Add an init container or healthcheck dependency that pulls required models from `router_rules.json` before portal-api starts.

---

## 5. Workspace & Routing Gaps

### R-01: Missing Workspaces for New Capabilities

The workspace system needs entries for every capability vertical:

| Missing Workspace | Target Model | Use Case |
|---|---|---|
| `auto-documents` | qwen3-coder-next or dolphin-70b | Word, PowerPoint, Excel creation |
| `auto-video` | dolphin-llama3:8b (routes to tool) | Video generation |
| `auto-music` | dolphin-llama3:8b (routes to tool) | Music generation |
| `auto-research` | tongyi-deepresearch | Deep research with RAG |

### R-02: Routing Classifier Missing Categories

`router_rules.json` classifier categories need additions:

| Missing Category | Keywords | Action |
|---|---|---|
| `document_gen` | write doc, create presentation, make spreadsheet, generate report | Route to doc-capable model + trigger document tools |
| `video_gen` | create video, animate, video clip, video generation | Route to multimodal model + trigger video tool |
| `music_gen` | compose, create music, generate song, soundtrack, beat | Route to general model + trigger music tool |
| `research` | research, deep dive, find information about, investigate | Route to reasoning model + trigger search/RAG tools |

### R-03: Regex Rules Missing for New Domains

Add regex rules for document, video, music, and research trigger patterns to complement LLM classification.

---

## 6. HOW_IT_WORKS.md Rewrite Specification

The document needs a structural rewrite to match the project's actual intent. Current version reads like a technical verification report. It should read like a comprehensive user and developer guide for a total offline AI workstation.

### Structural Changes Needed

1. **Section 1 (System Overview):** Add a clear mission statement: "Portal replaces cloud AI with a fully local platform covering: text generation, code, security analysis, image creation, video creation, music generation, document production, research, and more."

2. **Section 5 (Feature Catalog):** Restructure around use cases, not module names:
   - "I want to generate images" → ComfyUI path (all hardware) + mflux path (Mac only)
   - "I want to create documents" → Word/PowerPoint/Excel tools + how to trigger
   - "I want security analysis" → auto-security workspace + what models
   - Include setup requirements for each capability (what to install/pull)

3. **Add Section: Capability Matrix with honest statuses:**

| Capability | Status | Backend Required | Hardware |
|---|---|---|---|
| Text chat | READY | Ollama | All |
| Code generation | READY | Ollama | All |
| Image generation | READY (needs backend) | ComfyUI or mflux | All / Mac |
| Video generation | PLANNED | ComfyUI + video model | CUDA recommended |
| Music generation | PLANNED | AudioCraft | CUDA / MPS |
| TTS / Voice clone | READY (needs backend) | CosyVoice | CUDA / MPS |
| Speech-to-text | READY (needs backend) | Whisper | All |
| Word/PPT/Excel | READY | python-docx/pptx | All |
| Red team security | READY | Ollama | All |
| Blue team / SIEM | READY | Ollama | All |
| Creative writing | READY | Ollama | All |
| Web search | PARTIAL (needs internet) | DDG API | All |
| Local knowledge / RAG | READY (needs embeddings) | sentence-transformers | All |
| Code execution | PARTIAL (limited sandbox) | Docker | All |

4. **Add Section: First-Run Setup by Capability** — what models to pull, what backends to install, what config to set for each capability the user wants.

5. **Remove verification artifacts** — The "Environment Verification Results" table (Python 3.14.3, 41 deps) and test counts are audit artifacts, not user documentation. Move to AUDIT_REPORT.md.

---

## 7. Priority Order for Finish Line

### Phase 1: Documentation Truth (1-2 days)
1. Fix D-01 through D-06 (correct all misstatements)
2. Rewrite HOW_IT_WORKS.md per Section 6 spec
3. Update CLAUDE.md version and remove LMStudio refs
4. Update Feature Status Matrix with honest statuses

### Phase 2: Wire Up What Exists (2-3 days)
1. DC-01/DC-02: Add ComfyUI + generation MCPs to docker-compose
2. DC-03: Add proxy router to docker-compose
3. DC-05: Add model auto-pull init container
4. F-05: Expose document tools as MCP endpoints with file handling
5. F-07: Add embedding model management

### Phase 3: Missing Core Capabilities (5-8 days)
1. F-01: Video generation MCP + workspace
2. F-02: Music generation MCP + workspace
3. F-03: Offline search (SearXNG or expanded RAG)
4. F-06: Full code execution sandbox
5. R-01/R-02/R-03: All new workspaces and routing rules

### Phase 4: Orchestration & Polish (3-5 days)
1. F-04: Multi-step task orchestration
2. End-to-end integration testing for each capability
3. Per-hardware setup guides (Mac vs Linux vs WSL2)
4. First-run guided setup for capability selection
5. Final HOW_IT_WORKS.md and README updates

---

## 8. Session Bootstrap for Coding Agent

```bash
# Clone and verify
cd /Users/chris/portal
source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev,test]" -q

# Verify baseline (all should pass before starting)
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m mypy src/portal
python3 -m pytest tests/ -v --tb=short

# Read key files before any changes
cat PORTAL_HOW_IT_WORKS.md
cat PORTAL_ROADMAP.md
cat CLAUDE.md
cat docker-compose.yml
cat src/portal/routing/router_rules.json
```

**Non-negotiable constraints:**
- All existing tests must continue to pass
- No cloud dependencies (everything runs local)
- No external AI frameworks (no LangChain, no CrewAI)
- OpenAI-compatible API contract must not change
- New interfaces must remain addable in ≤50 lines of Python
- Every new feature must have unit tests
- Lint and mypy must stay at zero

**Commit convention:** `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`

---

## 9. Files That Need Changes

| File | Change Type | Items |
|---|---|---|
| `PORTAL_HOW_IT_WORKS.md` | Rewrite | D-01 through D-06, Section 6 structural rewrite |
| `CLAUDE.md` | Fix | D-05 (version, LMStudio refs) |
| `PORTAL_ROADMAP.md` | Update | Add F-01 through F-07 as planned items |
| `README.md` | Update | Add capability overview matching new vision |
| `docker-compose.yml` | Add services | DC-01 through DC-05 |
| `src/portal/routing/router_rules.json` | Add | R-01 workspaces, R-02 categories, R-03 regex rules |
| `src/portal/routing/task_classifier.py` | Add | R-02 new category patterns |
| `src/portal/routing/llm_classifier.py` | Add | R-02 new categories in prompt |
| `mcp/generation/video_mcp.py` | Create | F-01 video generation MCP |
| `mcp/generation/music_mcp.py` | Create | F-02 music generation MCP |
| `mcp/documents/document_mcp.py` | Create | F-05 document tools as MCP |
| `mcp/execution/code_sandbox_mcp.py` | Create | F-06 code sandbox MCP |
| `src/portal/tools/media_tools/video_generator.py` | Create | F-01 video gen tool |
| `src/portal/tools/media_tools/music_generator.py` | Create | F-02 music gen tool |
| `src/portal/core/orchestrator.py` | Create | F-04 multi-step orchestration |
| `src/portal/config/settings.py` | Update | F-07 embedding model config |
| `.env.example` | Update | New config vars for video, music, sandbox, search |
| `launch.sh` | Update | Generation service management for new MCPs |
| `hardware/*/launch.sh` | Update | Hardware-specific generation service configs |

---

*This document is the authoritative action plan for bringing Portal from its current 1.4.7 state to the "total inclusive offline AI platform" finish line.*
