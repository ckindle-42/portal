# Portal v3.0 — GUI Integration Review & Path Forward

**Date:** 2026-03-03
**Issue:** Workspaces, routing, personas, and tool calling don't work in Open WebUI

---

## The Root Cause

Open WebUI is configured with TWO model connections:

```
OPENAI_API_BASE_URL=http://portal-core:8081/v1   (Portal)
OLLAMA_BASE_URL=http://host.docker.internal:11434  (Direct Ollama)
```

This creates a split brain. The model dropdown shows Ollama models AND Portal models. When a user selects `llama3.2:3b` (an Ollama model), Open WebUI talks directly to Ollama. Portal is never contacted. No routing, no workspaces, no tool schemas, no MCP dispatch. That is why it defaults to llama3.2:3b and does nothing special.

Even when selecting a Portal model like "auto", the tool calling fails because Portal handles tool dispatch invisibly server-side. Portal sends tool schemas to Ollama, Ollama returns tool_calls, Portal dispatches to MCP servers, Portal injects results, then sends final text to Open WebUI. But Open WebUI has NO IDEA that images were generated, files were created, or audio was produced. It just shows the text response.

## What Open WebUI Actually Supports Natively

Open WebUI has mature built-in support for ALL of Portal's generation features:

- ComfyUI image generation (Admin > Settings > Images) - shows images inline in chat
- MCP tool servers (Admin > Settings > Tools > Add Tool Server) - handles tool calling and result display
- Native function calling (Chat Controls > Advanced Params > Native mode) - structured tool calls
- Web search (built-in SearXNG/DuckDuckGo/Google)
- TTS (multiple providers including local OpenAI-compatible endpoints)
- RAG (built-in document upload, chunking, embedding)

These work because Open WebUI manages them directly. It knows how to display images inline, play audio, offer file downloads. Portal's middleware approach bypasses all of this.

## The Fix: Hybrid Architecture

Use each system for what it does best.

Portal handles: Model routing (auto-security, auto-coding, etc.), intelligent classification, Telegram/Slack interfaces

Open WebUI handles: Image generation (ComfyUI native), tool calling UI, TTS, web search, RAG, file display

### Key change: Remove direct Ollama connection

Make Portal the SOLE model endpoint for Open WebUI. This forces all chat through Portal's routing:

```yaml
environment:
  - OPENAI_API_BASE_URL=http://portal-core:8081/v1
  - OPENAI_API_KEY=portal
  # REMOVED: OLLAMA_BASE_URL
  - ENABLE_IMAGE_GENERATION=True
  - IMAGE_GENERATION_ENGINE=comfyui
  - COMFYUI_BASE_URL=http://host.docker.internal:8188
```

Then register MCP tools DIRECTLY with Open WebUI so it handles tool calling and result display.

---

## Coding Tasks

### TASK 1: Fix Open WebUI Connection Config (CRITICAL)

File: deploy/web-ui/openwebui/docker-compose.yml

Remove OLLAMA_BASE_URL. Add ComfyUI env vars. Portal becomes the only model source.

### TASK 2: Create Pre-Built ComfyUI Workflow Exports

Create workflow JSON files in API format that users upload to Open WebUI's Image settings:

- deploy/web-ui/openwebui/workflows/flux_schnell_api.json
- deploy/web-ui/openwebui/workflows/sdxl_api.json
- deploy/web-ui/openwebui/workflows/wan22_video_api.json

These must be in ComfyUI's API format (not regular workflow format). Include node ID mappings in a README.

### TASK 3: Document MCP Tool Registration in Open WebUI

Create deploy/web-ui/openwebui/SETUP_TOOLS.md documenting:

For each MCP server, register as a Tool Server in Open WebUI Admin > Settings > Tools:
- http://host.docker.internal:8912 (music generation)
- http://host.docker.internal:8913 (document creation)
- http://host.docker.internal:8914 (code sandbox)
- http://host.docker.internal:8916 (TTS)

Then in chat: click + icon to enable tools, set Function Calling to Native mode.

### TASK 4: Update /v1/models Response

File: src/portal/interfaces/web/server.py

Ensure Portal returns ONLY workspace and persona models (not raw Ollama model names). When Open WebUI is the sole connection to Portal, users should see:
- auto, auto-coding, auto-security, auto-creative, auto-reasoning, auto-documents, auto-video, auto-music, auto-research, auto-fast, auto-multimodal
- All 30 persona names
- NOT raw Ollama models like dolphin-llama3:8b (these bypass routing if selected directly)

### TASK 5: Write Complete Setup Guide

File: deploy/web-ui/openwebui/README.md (rewrite)

Step-by-step first-run guide covering:
1. Start the stack (docker compose up)
2. Create admin account
3. Set up ComfyUI image generation (Admin > Settings > Images)
4. Upload workflow JSON, map node IDs
5. Register MCP tool servers (Admin > Settings > Tools)
6. Enable Native function calling
7. Configure TTS (Admin > Settings > Audio)
8. Configure web search if desired
9. Select a workspace from dropdown and test

### TASK 6: Create Open WebUI Workspace Setup Script

File: scripts/setup_openwebui.py

Use Open WebUI's API to pre-configure workspaces with:
- Display names
- System prompts from persona YAML files
- Assigned tool sets per workspace
- Default function calling mode

### TASK 7: Update All Documentation

- PORTAL_HOW_IT_WORKS.md: Rewrite Section 5.1 explaining the hybrid architecture
- QUICKSTART.md: Update first-run flow
- README.md: Update architecture description

### TASK 8: Ensure Portal /v1/models Works Without Direct Ollama Discovery

Currently Portal's model list may depend on querying Ollama directly to discover models. When Open WebUI no longer has OLLAMA_BASE_URL, Portal still needs to return the workspace list. Verify that /v1/models returns all workspaces and personas even without an Ollama health check.

---

## What Stays the Same

- Portal's routing engine (excellent, no changes needed)
- Portal's MCP server ecosystem (video, music, TTS, documents, sandbox)
- Telegram and Slack interfaces (work correctly with Portal's tool pipeline)
- All the generation code (Wan2.2, SDXL, AudioCraft, Fish Speech)
- Tool schema builder (still used for Telegram/Slack)
- Security, rate limiting, CORS, auth

## What Changes

- Open WebUI talks ONLY to Portal for LLM chat (no direct Ollama)
- Open WebUI talks DIRECTLY to ComfyUI for image/video gen (native integration)
- Open WebUI talks DIRECTLY to MCP servers for other tools (native tool calling)
- Portal stops trying to handle tool dispatch for web users (Open WebUI does it better)
- Documentation reflects the actual user experience

---

## Estimated Effort

| Task | Effort |
|---|---|
| 1. Fix docker-compose | 15 min |
| 2. Create workflow JSONs | 1 hour |
| 3. Document MCP registration | 30 min |
| 4. Update /v1/models | 1 hour |
| 5. Complete setup guide | 2 hours |
| 6. Setup script | 1-2 hours |
| 7. Update docs | 2 hours |
| 8. Verify model list | 30 min |
| **Total** | **~8-10 hours** |

This is primarily configuration and documentation work with one code change (Task 4). No architectural rewrite needed. The pieces are all built, they just need to be connected through Open WebUI's native systems instead of Portal's middleware layer.
