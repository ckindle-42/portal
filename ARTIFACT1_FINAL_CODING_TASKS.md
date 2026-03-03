# Portal v3.0 — Final Corrections Task List

**Reviewed:** commit 37a4ffc (post Phase 0-6 + personas + health endpoints + integration tests)
**Date:** 2026-03-03

---

## Validation Summary

The project has come a long way. The fundamental architecture is sound and connected:

**Confirmed working:**
- Tool schemas built and passed to Ollama via `tools` field in payload ✓
- 9 MCP servers registered at startup (core, scrapling, documents, comfyui, whisper, video, music, tts, sandbox) ✓
- All MCP servers have `/health` and `/tools` discovery endpoints ✓
- Wan2.2 workflow in both `video_mcp.py` AND `video_generator.py` ✓
- SDXL workflow in `comfyui_mcp.py` alongside FLUX ✓
- Fish Speech TTS MCP with CosyVoice fallback ✓
- `ProcessingResult.tool_results` populated at top level ✓
- All generation outputs unified to `data/generated/` ✓
- Telegram: @model: prefix parsing + file delivery (photo/audio/video/document) ✓
- Slack: @model: prefix parsing + file upload ✓
- Conservative orchestrator detection (regex-based) ✓
- BaronLLM in security fallback chain ✓
- Metrics duplicate timeseries fix (try/except guard) ✓
- All new env vars in `.env.example` (VIDEO_BACKEND, IMAGE_BACKEND, TTS_BACKEND, etc.) ✓
- launch.sh: all MCPs in stop_all + doctor health checks ✓
- 30 persona YAML files imported ✓
- 1022 test functions across 82 test files ✓
- Comprehensive HOW_IT_WORKS.md with 19 feature subsections + Telegram/Slack setup guides ✓
- Open WebUI setup README with admin/workspace instructions ✓

**Remaining issues — all LOW to MEDIUM severity:**

---

## TASK 1: TESTING_PROMPTS.md Missing Red/Blue Team and Workspace Selection Tests

**Problem:** The 780-line TESTING_PROMPTS.md covers 30 feature categories but is missing:
- Red team / offensive security prompts (zero mentions of exploit, pentest, kerberos, reverse shell)
- Blue team / defensive security prompts (zero mentions of Splunk, SIEM, YARA, sigma)
- Workspace selection via UI dropdown (only mentions personas, not `auto-security`, `auto-coding`, etc.)
- @model: prefix examples for Telegram and Slack
- Creative writing with workspace selection

**This is addressed by Artifact 2 (the comprehensive test prompts document). No code change needed — just replace or merge TESTING_PROMPTS.md with the new version.**

## TASK 2: HOW_IT_WORKS Wan2.2 Setup Instructions

**Problem:** Section 5.4 mentions Wan2.2 but has only 9 setup command instances total across the entire doc. Missing the actual `huggingface-cli download` commands for Wan2.2 models from the guide you provided.

**File:** `PORTAL_HOW_IT_WORKS.md` Section 5.4

**Add:**
```markdown
#### Wan2.2 Model Setup (M4 Mac — 5B starter)
\`\`\`bash
pip3 install huggingface_hub
huggingface-cli download Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
  split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors \
  --local-dir ~/comfy/ComfyUI/models/diffusion_models
huggingface-cli download Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
  split_files/vae/wan2.2_vae.safetensors \
  --local-dir ~/comfy/ComfyUI/models/vae
huggingface-cli download Comfy-Org/Wan_2.1_ComfyUI_repackaged \
  split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors \
  --local-dir ~/comfy/ComfyUI/models/text_encoders
\`\`\`

#### Wan2.2 14B (Production Quality — M4 64GB handles this)
\`\`\`bash
huggingface-cli download Comfy-Org/Wan_2.2_ComfyUI_Repackaged \
  split_files/diffusion_models/wan2.2_t2v_high_noise_14B_fp8_scaled.safetensors \
  --local-dir ~/comfy/ComfyUI/models/diffusion_models
\`\`\`
```

Also add SDXL and FLUX setup commands in Section 5.3, and ComfyUI install instructions:
```markdown
#### ComfyUI Setup
\`\`\`bash
pip3 install comfy-cli
comfy install
comfy launch -- --mps --highvram
\`\`\`
```

## TASK 3: TESTING_PROMPTS.md Has No Workspace-Specific Security or Creative Tests

**Problem:** Section 20 "Persona Selection" and Section 23 "Model Selection / Routing" exist but don't include explicit prompts for testing each workspace. No prompts test the security workspace with actual offensive prompts, or the creative workspace with actual fiction prompts.

**Fix:** Replace TESTING_PROMPTS.md with Artifact 2 from this review which covers all workspaces with real-world prompts.

## TASK 4: Existing CLAUDE_REVIEW_TASKS.md Has Stale Items

**Problem:** `CLAUDE_REVIEW_TASKS.md` has items marked as fixed alongside items that may still be open (video MCP backend dependency, MLX requirement, shell safety, etc.). Should be cleaned up to reflect current state.

**Fix:** Review each item against current code state. Mark completed items. Remove or update stale items.

---

## Priority

| # | Task | Severity | Effort |
|---|---|---|---|
| 1 | Replace TESTING_PROMPTS.md | LOW | Use Artifact 2 |
| 2 | Add Wan2.2/SDXL/ComfyUI setup commands to docs | MEDIUM | 30 min |
| 3 | Workspace-specific test prompts | LOW | Covered by Artifact 2 |
| 4 | Clean up CLAUDE_REVIEW_TASKS.md | LOW | 15 min |

**Total remaining work: ~1 hour of documentation updates. No code changes needed.**

The project is feature-complete at the code level. What remains is documentation polish and the test prompt library.
