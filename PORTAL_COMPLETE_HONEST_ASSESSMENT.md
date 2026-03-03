# Portal — Complete Honest Assessment & Remaining Work to Feature-Complete

**Generated:** 2026-03-02
**Reviewed commit:** bfc8096
**Purpose:** Stop polishing a car with no engine. Document what actually works end-to-end vs what is scaffolding, then list every task needed to reach feature-complete.

---

## The Core Problem Nobody Has Said Out Loud

Portal has a well-engineered routing system, a solid test suite, clean architecture, and 8 MCP server files. But **the tool-calling pipeline is not connected end-to-end.** Here is exactly what happens when a user asks "generate an image of a sunset" through Open WebUI:

1. Open WebUI sends `POST /v1/chat/completions` with `model: "auto"` and the user's message
2. Portal's WebInterface extracts the message, builds an `IncomingMessage`
3. AgentCore routes it → TaskClassifier sees "image" → classifies as `image_gen` → selects `dolphin-llama3:8b`
4. ExecutionEngine calls Ollama `/api/chat` with this payload:
   ```json
   {"model": "dolphin-llama3:8b", "messages": [...], "stream": false, "options": {...}}
   ```
5. **There is no `tools` field in that payload.** Ollama has no idea that image generation tools exist.
6. Dolphin writes a text response like "I'd be happy to help generate an image. Here's a description..." — it **cannot** make a tool call because it was never told tools exist.
7. The text response streams back to Open WebUI. No image is generated.

**This is the fundamental disconnect.** The Ollama payload is `{model, messages, stream, options}`. The OpenAI function-calling format requires a `tools` array in the payload so the model knows it can call functions. Portal never builds or sends this array.

### What the MCP registry actually registers:

`create_mcp_registry()` in `factories.py` registers exactly **2 servers**:
- `core` → mcpo at `:9000` (which serves filesystem + fetch tools)
- `scrapling` → streamable-http at `:8900`

The 6 other MCP servers (comfyui, whisper, video, music, documents, sandbox) **launch as HTTP processes** but are **never registered** with the MCPRegistry. AgentCore cannot find them. Even if Ollama did make a tool call, the dispatch would fail for any tool that isn't filesystem or fetch.

### What this means practically:

| Feature | Code Exists | Can Actually Execute End-to-End | Why Not |
|---|---|---|---|
| Image generation (ComfyUI) | Yes | **No** | LLM never told about tools; MCP not registered |
| Image generation (mflux) | Yes | **No** | Same — LLM can't invoke it |
| Video generation | Yes | **No** | Same + wrong workflow for Wan2.2 |
| Music generation | Yes | **No** | Same |
| TTS / Voice clone | Yes | **No** | Same + CosyVoice only, no Fish Speech |
| Document creation (MCP) | Yes | **No** | Same — MCP not registered |
| Code sandbox | Yes | **No** | Same |
| Web search | Partial | **Partial** | Scrapling IS registered, DDG fallback works if internet available |
| RAG / Knowledge | Yes | **No** | LLM can't invoke knowledge tools |
| Text chat | Yes | **Yes** | No tools needed — pure LLM text |
| Code generation | Yes | **Yes** | No tools needed — pure LLM text |
| Security analysis | Yes | **Yes** | No tools needed — pure LLM text |
| Creative writing | Yes | **Yes** | No tools needed — pure LLM text |
| Workspace routing | Yes | **Yes** | Pure routing, no tools involved |

**Everything that is pure text LLM works correctly.** Everything that requires tool invocation does not.

---

## How Telegram and Slack Actually Work

### Telegram
- User sends message → `handle_text_message()` is called
- Checks authorization (user ID whitelist from `TELEGRAM_USER_IDS`)
- Checks rate limit
- Calls `self.agent_core.process_message(chat_id, message, interface=TELEGRAM)`
- Receives `ProcessingResult` with text response
- Sends text response back via Telegram Bot API
- Commands: `/start`, `/help`, `/tools` (lists available tools), `/stats`, `/health`
- **Model selection:** Does NOT pass workspace_id — always routes as "auto"
- **Tool calling:** Same broken pipeline as web — LLM doesn't know about tools
- **File delivery:** Cannot send generated files back through Telegram (no file handling)
- **What actually works:** Text chat, creative writing, code help, security analysis — anything that's pure LLM text

### Slack
- Slack sends webhook to `/slack/events` on the Portal web app
- Verifies Slack HMAC signature
- Extracts text, removes bot mention prefix
- Creates `IncomingMessage(model="auto")` — **hardcoded to "auto", no workspace selection**
- Streams response via `agent_core.stream_response(incoming)`
- Collects full response, posts via `chat.postMessage`
- **Model selection:** Hardcoded "auto" — user cannot select workspace
- **Tool calling:** Same broken pipeline
- **File delivery:** Cannot send files through Slack
- **What actually works:** Same as Telegram — text-only LLM interactions

### What's missing for both:
1. No workspace selection (Slack hardcodes "auto", Telegram doesn't pass it)
2. No `@model:` override parsing (the router supports it, but the interfaces don't extract it from the message before sending to agent_core)
3. No file attachment handling (can't send/receive images, docs, audio)
4. No tool calling (same root cause as web)

---

## How Open WebUI Tool Calling Is Supposed to Work

There are **two paths** for tools with Open WebUI:

### Path A: OpenAI Function Calling (what Portal should do)
1. Portal sends tool definitions in the Ollama payload's `tools` field
2. Ollama's model (if it supports function calling — Dolphin does) returns a `tool_calls` array
3. Portal dispatches tool calls to MCP servers
4. Portal sends results back to the model
5. Model generates final response incorporating tool results
6. **Portal has the dispatch/loop logic (steps 3-5) built.** It's step 1 that's missing.

### Path B: Open WebUI's Native MCP Support (alternative)
1. Open WebUI connects directly to MCP servers via mcpo
2. Open WebUI handles tool calling internally
3. Portal just does LLM inference
4. **This works for the "core" server (filesystem, fetch) if mcpo is running.** But the generation MCPs aren't exposed through mcpo.

### What needs to happen:
For Path A, `OllamaBackend.generate()` needs to include tool schemas in the payload. The ToolRegistry has all the metadata. The execution engine just doesn't build the `tools` array from it.

For Path B, all MCP servers need to be registered with mcpo so Open WebUI can see them.

Both paths should work. Path A is more powerful (works for all interfaces). Path B gives Open WebUI direct control.

---

## Fish Speech — Why It's Not Deferred, It's Missing

Your models CSV lists the audio/TTS row as: "CosyVoice2 / MOSS-TTS + Mochi-1 / Wan2.2 (img2vid) + Qwen3-Omni prompts" with Fish Speech mentioned in the run command column. Fish Speech is a modern, fast, high-quality TTS engine that runs on MPS (Mac). CosyVoice works but is older and heavier.

The `audio_generator.py` implements CosyVoice TTS and voice cloning. Fish Speech is not implemented anywhere — no code, no MCP server, no tool, no config. For a "total inclusive offline AI platform," TTS that works on your primary hardware is a core feature, not a nice-to-have.

What's needed: A TTS MCP server (like the music and video ones) that wraps Fish Speech or CosyVoice, registered with the MCPRegistry, with tool schemas passed to Ollama so the LLM can invoke it.

---

## Complete Task List to Feature-Complete

### TIER 0: Fix the Tool Pipeline (Nothing Else Works Without This)

**TASK-0A: Pass tool schemas to Ollama**

This is the single most important task. Without it, every generation feature is dead.

**File:** `src/portal/routing/model_backends.py` (OllamaBackend.generate and generate_stream)

The ToolRegistry already has metadata for every tool including name, description, and parameters. Convert these to OpenAI function-calling format and include them in the Ollama payload:

```python
payload = {
    "model": model_name,
    "messages": self._build_chat_messages(prompt, system_prompt, messages),
    "stream": False,
    "options": {"num_predict": max_tokens, "temperature": temperature},
    "tools": tools,  # <-- THIS IS WHAT'S MISSING
}
```

The `tools` array needs to be built from `ToolRegistry.get_tool_list()` and MCP server tool manifests, converted to the OpenAI function schema format that Ollama expects.

The execution engine needs to accept and pass through tool definitions. AgentCore needs to build the combined tool list from ToolRegistry + MCPRegistry tool manifests and pass it down.

**TASK-0B: Register ALL MCP servers with MCPRegistry**

**File:** `src/portal/core/factories.py` (create_mcp_registry)

Currently registers only `core` (mcpo) and `scrapling`. Must also register:
- `comfyui` → `http://localhost:8910` (streamable-http)
- `whisper` → `http://localhost:8915` (streamable-http)
- `video` → `http://localhost:8911` (streamable-http)
- `music` → `http://localhost:8912` (streamable-http)
- `documents` → `http://localhost:8913` (streamable-http)
- `sandbox` → `http://localhost:8914` (streamable-http)

These should be conditionally registered based on config (e.g., only register video if `GENERATION_SERVICES=true`). Each server's URL should come from env vars (they already exist in `.env.example`).

**TASK-0C: Build tool schema bridge**

Create `src/portal/core/tool_schema_builder.py` that:
1. Reads tool metadata from ToolRegistry (internal Python tools)
2. Reads tool manifests from MCPRegistry (external MCP servers)
3. Converts both to OpenAI function-calling format
4. Returns a combined `tools` array for the Ollama payload
5. Caches the result (tools don't change during runtime)

### TIER 1: Fix the Wan2.2 Video Workflow

**TASK-1A:** Rewrite video MCP with correct Wan2.2 ComfyUI node graph (per previous task document — UNETLoader, CLIPLoader, VAELoader, EmptyHunyuanLatentVideo)

**TASK-1B:** Add SDXL workflow option to image MCP alongside FLUX

### TIER 2: Add Fish Speech TTS

**TASK-2A: Create Fish Speech MCP server**

**File:** Create `mcp/generation/tts_mcp.py`

Fish Speech is a modern TTS engine with MPS support. It supports:
- Text-to-speech with multiple voices
- Voice cloning from reference audio
- Streaming audio output
- Runs efficiently on M4 Mac

The MCP server should expose:
- `speak(text, voice, speed, output_format)` → WAV/MP3 file
- `clone_voice(text, reference_audio_path)` → WAV file using cloned voice
- `list_voices()` → available voice options

Keep the existing CosyVoice code as a fallback (`TTS_BACKEND=fish_speech` vs `cosyvoice`).

**TASK-2B:** Register TTS MCP with MCPRegistry (covered by TASK-0B pattern)

### TIER 3: Fix Interface Integration Gaps

**TASK-3A: Telegram workspace selection**

**File:** `src/portal/interfaces/telegram/interface.py`

Parse `@model:workspace-name` from the beginning of messages (the router already supports this prefix). Extract it before sending to agent_core, pass as `workspace_id`. Example:
```
User: @model:auto-security write a reverse shell
→ workspace_id="auto-security", message="write a reverse shell"
```

**TASK-3B: Slack workspace selection**

**File:** `src/portal/interfaces/slack/interface.py`

Same pattern. Also stop hardcoding `model="auto"` — let users prefix messages.

**TASK-3C: Telegram file delivery**

When a tool generates a file (image, audio, document, video), the Telegram interface should detect file paths in the response and send them as Telegram media:
- Images → `send_photo()`
- Audio → `send_audio()`  
- Documents → `send_document()`
- Video → `send_video()`

**TASK-3D: Slack file delivery**

Same pattern using Slack's `files.upload` API.

### TIER 4: Fix the Orchestrator Detection

**TASK-4A:** Rewrite `_is_multi_step()` with conservative regex (per previous task document)

### TIER 5: Documentation That Tells the Truth

**TASK-5A: Rewrite PORTAL_HOW_IT_WORKS.md**

The current document says features are "READY" or "NEEDS BACKEND" when they actually cannot execute end-to-end due to the missing tool pipeline. Every feature status must be re-evaluated against the actual state after TASK-0 is complete.

**TASK-5B: Write end-to-end usage guide**

For each capability, document the complete path a user follows:

```
"I want to generate an image"
1. Open http://localhost:8080 (Open WebUI)
2. Select "auto" from the model dropdown
3. Type: "Generate an image of a medieval castle at sunset"
4. What happens: The LLM receives your prompt with tool definitions.
   It decides to call generate_image(prompt="medieval castle at sunset").
   Portal dispatches to ComfyUI MCP. ComfyUI generates the image.
   The result URL is returned to the LLM. The LLM responds with the image link.
5. Prerequisites: ComfyUI running with FLUX model installed.
6. Also works via: Telegram (image sent as photo), Slack (image posted)
```

Do this for EVERY capability.

**TASK-5C: Document Telegram and Slack setup end-to-end**

Not just "set TELEGRAM_BOT_TOKEN" — the complete flow:
1. Create bot via @BotFather
2. Get your chat ID (how?)
3. Set env vars
4. What commands are available (/start, /help, /tools, /stats, /health)
5. How to select a workspace (@model:auto-security prefix)
6. What works (text chat) vs what requires backends (generation)
7. How files are delivered back
8. Rate limiting behavior
9. HITL approval flow for high-risk tools

Same depth for Slack.

**TASK-5D: Wan2.2 and ComfyUI setup guide**

Per the uploaded guide — model download commands, ComfyUI installation, MPS launch flags.

### TIER 6: launch.sh and Docker Alignment

**TASK-6A:** launch.sh `run_doctor()` must check all MCP server ports
**TASK-6B:** docker-compose.yml must register all MCP servers with portal-api environment
**TASK-6C:** Add model download init container for Wan2.2 models (not just Ollama models)

---

## Priority Execution Order

| Phase | Tasks | What It Unlocks | Effort |
|---|---|---|---|
| **Phase 0** | 0A, 0B, 0C | Tool calling works. Every generation feature goes from dead to functional. | 2-3 days |
| **Phase 1** | 1A, 1B | Video generates with Wan2.2. Images support SDXL. | 1 day |
| **Phase 2** | 2A, 2B | TTS/voice works with Fish Speech. | 1 day |
| **Phase 3** | 3A, 3B, 3C, 3D | Telegram and Slack become full-featured interfaces. | 1-2 days |
| **Phase 4** | 4A | Orchestrator stops hijacking normal prompts. | 2 hours |
| **Phase 5** | 5A, 5B, 5C, 5D | Documentation reflects reality. | 2-3 days |
| **Phase 6** | 6A, 6B, 6C | Deployment works correctly. | 1 day |

**Total: ~10-12 days of focused agent work.**

Phase 0 is the foundation. Nothing else matters until the tool pipeline is connected. A coding agent should execute Phase 0 first, then run the Documentation Agent v4 to verify what actually works before proceeding.

---

## What Actually Works Today (The Honest List)

These features work end-to-end, tested, no gaps:

1. **Text chat** via Open WebUI, Telegram, Slack — select a workspace, get routed to the right model, receive text response
2. **Workspace routing** — 11 workspaces, all route correctly to their target models with fallback chains
3. **Intelligent classification** — regex + LLM classifier correctly categorize queries across 12 categories
4. **Manual model override** — @model:name prefix works in the router
5. **Health checks** — /health, /health/live, /health/ready all respond correctly
6. **Metrics** — Prometheus metrics at /metrics work
7. **Security** — API key auth, rate limiting, CORS, input sanitization all functional
8. **File delivery endpoint** — /v1/files serves files from data/generated/
9. **Web search** — scrapling/DDG fallback works (requires internet for targeted research)
10. **Test suite** — 950+ tests passing, lint clean, mypy clean

These features have code but **cannot execute end-to-end**:

11. Image generation — code complete, pipeline disconnected
12. Video generation — code complete, wrong workflow, pipeline disconnected
13. Music generation — code complete, pipeline disconnected
14. TTS — CosyVoice code exists, Fish Speech missing, pipeline disconnected
15. Voice cloning — CosyVoice code exists, pipeline disconnected
16. Document generation (MCP) — code complete, MCP not registered, pipeline disconnected
17. Code sandbox — code complete, MCP not registered, pipeline disconnected
18. RAG/knowledge — code complete, pipeline disconnected
19. Orchestrator — wired in but detection is overly aggressive

---

*The architecture is sound. The routing is excellent. The individual pieces are well-built. They just aren't plugged into each other. Phase 0 is the wiring job that makes everything else real.*
