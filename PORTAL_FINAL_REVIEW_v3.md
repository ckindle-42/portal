# Portal 3.0.1 — Final Review & Remaining Corrections

**Reviewed:** commit 80cebda (version 3.0.1)
**Date:** 2026-03-03

---

## Summary

The project has come a long way. The Phase 0-6 implementation plus the post-review fixes have addressed the vast majority of issues. The tool pipeline is connected, MCP servers are registered, Wan2.2 and SDXL workflows are correct, Fish Speech TTS exists, interfaces have workspace selection and file delivery, output paths are unified, tests cover the new features (1,002 test functions), and documentation has 19 per-feature sections with setup guides.

What remains is a short list of specific items — no more structural disconnects, no more fundamental architecture gaps. These are targeted fixes.

---

## Remaining Issues

### FIX-1: Orchestrator ProcessingResult Missing tool_results (BUG)

**Severity:** Medium (only affects multi-step requests that use tools)

The normal processing path (line 327) now correctly sets `tool_results=tool_results` on ProcessingResult. But the orchestrator path (line 380) still does not:

```python
# Line 380 — missing tool_results
return ProcessingResult(
    response=combined_response,
    model_used="orchestrator",
    prompt_tokens=0,
    completion_tokens=len(combined_response.split()),
)
```

If a multi-step orchestrated request calls tools that generate files, the file paths won't flow to Telegram/Slack for delivery.

**Fix:** Add `tool_results=[]` (or collect results from the orchestrator plan's completed steps) to this ProcessingResult constructor.

---

### FIX-2: .env.example VIDEO_TEXT_ENCODER Has Wrong Default (BUG)

**Severity:** Low (comment only, code uses the correct default)

`.env.example` says:
```
# VIDEO_TEXT_ENCODER=clip_l.safetensors
```

Should be:
```
# VIDEO_TEXT_ENCODER=umt5_xxl_fp8_e4m3fn_scaled.safetensors
```

The Wan2.2 text encoder is UMT5-XXL, not CLIP-L. The code in `video_mcp.py` already uses the correct default — this is just the documentation comment being wrong.

---

### FIX-3: HOW_IT_WORKS Section 5.17 Says "Qwen2-Omni" (TYPO)

**Severity:** Low (cosmetic)

The section title and body say "Qwen2-Omni" but `router_rules.json` maps to `qwen3-omni:30b`. Should be "Qwen3-Omni" throughout.

---

### FIX-4: Missing Test for tool_results Delivery to Interfaces (TEST GAP)

No test verifies that `ProcessingResult.tool_results` is populated and accessible at the top level (not just in metadata). Add a test that:
1. Calls `_build_processing_result()` with mock tool results
2. Asserts `result.tool_results` is not empty
3. Asserts the file paths are present in the list

---

## What Actually Works — Complete Feature Audit

### End-to-End Functional (no gaps, tested):
| # | Feature | Evidence |
|---|---|---|
| 1 | Text chat via Web, Telegram, Slack | 11 workspaces route to correct models |
| 2 | Workspace routing (11 workspaces) | router_rules.json verified, all resolve |
| 3 | Query classification (12 categories) | video_gen, music_gen, document_gen, research all classify correctly |
| 4 | @model: override | Telegram + Slack parse prefix, pass workspace_id |
| 5 | Tool schemas passed to Ollama | tool_schema_builder.py builds, OllamaBackend includes in payload |
| 6 | MCP server registration (9 servers) | core, scrapling, comfyui, whisper, video, music, tts, documents, sandbox |
| 7 | Health checks + metrics + doctor | All ports checked including TTS and Whisper |
| 8 | Security (auth, rate limit, CORS) | Tested |
| 9 | File delivery (web) | /v1/files serves from data/generated/ |
| 10 | File delivery (Telegram/Slack) | Reads tool_results, sends as photo/audio/video/document |
| 11 | Conservative orchestrator detection | Regex-only, no false positives on common prompts |
| 12 | Web research | Scrapling + DDG fallback, targeted research only |
| 13 | Output path unification | Music, TTS, images all write to data/generated/ |

### Pipeline Ready (code connected, needs backend service installed):
| # | Feature | Backend Required | Setup Commands in Docs |
|---|---|---|---|
| 14 | Image gen (FLUX) | ComfyUI + flux1-schnell model | Yes (5.3) |
| 15 | Image gen (SDXL) | ComfyUI + sd_xl_base_1.0 model | Yes (5.3) |
| 16 | Image gen (mflux) | mflux CLI (Mac only) | Yes (5.3) |
| 17 | Video gen (Wan2.2) | ComfyUI + Wan2.2 models | Yes (5.4) with huggingface-cli commands |
| 18 | Video gen (CogVideoX) | ComfyUI + CogVideoX model | Yes (5.4) |
| 19 | Music gen | AudioCraft (pip install audiocraft) | Yes (5.5) |
| 20 | TTS (Fish Speech) | Fish Speech installation | Yes (5.6) |
| 21 | TTS (CosyVoice) | CosyVoice + torchaudio | Yes (5.6) |
| 22 | Speech-to-text | Whisper / faster-whisper | Yes (5.7) |
| 23 | Document creation | python-docx/pptx/openpyxl | Yes (5.8) |
| 24 | Code sandbox | Docker + SANDBOX_ENABLED=true | Yes (5.9) |
| 25 | RAG/Knowledge | sentence-transformers | Yes (5.15) |

### Documentation Coverage:
| Section | Content | Status |
|---|---|---|
| 5.1-5.17 | Per-feature usage guides | 17 features documented with prerequisites, setup commands, examples |
| 5.18 | Telegram complete setup | BotFather, chat ID, @model: prefix, commands, file delivery |
| 5.19 | Slack complete setup | App creation, Events API, signing secret, @model: prefix |
| README | Capabilities table | Present |
| ARCHITECTURE.md | New components | tool_schema_builder, orchestrator, MCP servers, /v1/files |
| .env.example | All config vars | VIDEO_BACKEND, IMAGE_BACKEND, TTS_BACKEND, all MCP ports |

### Test Coverage:
| Area | Test File | Functions |
|---|---|---|
| Tool schema builder | test_tool_schema_builder.py | Present |
| MCP registration | test_mcp_registration.py | Present |
| Ollama tools payload | test_ollama_tools_payload.py | Present |
| Wan2.2 workflow | mcp/test_wan22_workflow.py | Present |
| SDXL workflow | mcp/test_sdxl_workflow.py | Present |
| Multi-step detection | test_multi_step_detection.py | Present |
| File delivery | test_file_delivery.py | Present |
| Telegram workspace | test_telegram_workspace.py | Present |
| Slack workspace | test_slack_workspace.py | Present |
| Document MCP | mcp/test_document_mcp.py | Present |
| Sandbox MCP | mcp/test_code_sandbox_mcp.py | Present |
| **Total** | **80 test files** | **1,002 test functions** |

---

## Coding Agent Task (4 Items)

```bash
cd /Users/chris/portal
source .venv/bin/activate
pip install -e ".[all,dev,test]" -q
make lint && make test-unit
```

### FIX-1: Orchestrator ProcessingResult

**File:** `src/portal/core/agent_core.py` (~line 380)
**Action:** Add `tool_results=[]` to the orchestrator's ProcessingResult constructor.
**Test:** Add test in `test_agent_core_orchestrator.py` that verifies orchestrated requests return ProcessingResult with `tool_results` field accessible (even if empty).

### FIX-2: .env.example TEXT_ENCODER default

**File:** `.env.example`
**Action:** Change `# VIDEO_TEXT_ENCODER=clip_l.safetensors` to `# VIDEO_TEXT_ENCODER=umt5_xxl_fp8_e4m3fn_scaled.safetensors`

### FIX-3: Qwen3-Omni typo

**File:** `PORTAL_HOW_IT_WORKS.md`
**Action:** Change "Qwen2-Omni" to "Qwen3-Omni" in section 5.17 title and body.

### FIX-4: tool_results delivery test

**File:** Create `tests/unit/test_tool_results_delivery.py`
**Tests:**
- Build ProcessingResult with tool_results populated
- Assert `result.tool_results` is not empty
- Assert it's the same list passed in (not in metadata)

**After fixes:**
```bash
make lint && make test
# Commit: fix: address final review items — orchestrator tool_results, env typo, doc typo
```

---

**That's it. Four items, under 1 hour of work. The project is structurally complete.**
