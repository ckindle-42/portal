# Portal — Targeted Finish Line Action Prompt (Post-Review)

**Generated:** 2026-03-02
**Reviewed commit:** d6aa540 (Merge pull request #104 — finish-line Phase 1–3)
**Current version:** 1.4.7
**Purpose:** Close every remaining gap between current code and a verifiably complete offline AI platform.

---

## Executive Summary

The Phase 1–3 commit added significant new code: 5 MCP servers, 2 tool modules, an orchestrator, 4 new workspaces, expanded routing, and updated docs. **But much of it is scaffolding that isn't wired in.** The orchestrator has no callers. The file delivery path doesn't exist. The new MCPs aren't started by bare-metal launch scripts. The knowledge config is defined but ignored. There are zero tests for 6 new files.

This prompt contains **4 agent task blocks** — each is a self-contained session a coding agent can execute. Tasks are ordered by dependency: wiring first, then tests, then docs, then verification.

---

## AGENT TASK 1: Wire Everything Together

**Goal:** Connect all new code into the running system so it actually executes end-to-end.

**Session bootstrap:**
```bash
cd /Users/chris/portal
source .venv/bin/activate
pip install -e ".[all,dev,test]" -q
make lint && make test-unit  # baseline must be green
```

### 1A — Orchestrator Integration into AgentCore

**Problem:** `src/portal/core/orchestrator.py` exists with 14 passing tests but is never imported or called by `agent_core.py`. It is dead code in the request path.

**Fix:**
1. In `agent_core.py`, import `TaskOrchestrator`
2. Initialize it in `__init__` with `self._orchestrator = TaskOrchestrator(llm_executor=self._call_llm, tool_executor=self._call_tool)`
3. Add a private `_call_llm(prompt)` that wraps `ExecutionEngine.generate()` for the orchestrator
4. Add a private `_call_tool(name, args)` that wraps `execute_tool()` for the orchestrator
5. In `process_message()`, detect multi-step requests (heuristic: 2+ verbs/tasks in prompt, or user uses "then", "after that", "and also") and route through orchestrator when detected
6. Keep it opt-in: single-turn requests must not be affected. The orchestrator is only invoked for clearly multi-step requests.

**Tests:** Add `tests/unit/test_agent_core_orchestrator.py` with:
- Test that single-turn prompts bypass orchestrator
- Test that multi-step prompts invoke orchestrator
- Test that orchestrator failure falls back to normal processing

### 1B — File Delivery Endpoint

**Problem:** Document MCP, music MCP, video MCP, and image gen all write files to `data/generated/` or `~/AI_Output/` but there is **no HTTP endpoint** to serve those files back to the user or the UI. Generated files are orphaned on disk.

**Fix:**
1. In `src/portal/interfaces/web/server.py`, add two routes:
   - `GET /v1/files` — list recently generated files (JSON)
   - `GET /v1/files/{filename}` — serve file with correct MIME type (uses `FileResponse` from Starlette)
2. Files served from `data/generated/` directory only (no path traversal)
3. Add `Content-Disposition: attachment` header for document types
4. Sanitize filename parameter to prevent directory traversal (reject `..`, `/`, `\`)
5. Update document MCP to return `download_url` field: `http://localhost:8081/v1/files/{filename}`
6. Update HOW_IT_WORKS.md Section 6 "documents" to mention the download URL

**Tests:** Add `tests/integration/test_file_delivery.py` with:
- Test listing files
- Test downloading a generated file
- Test path traversal rejection
- Test 404 for nonexistent file

### 1C — Wire KnowledgeConfig into Knowledge Tools

**Problem:** `settings.py` defines `KnowledgeConfig` with `embedding_model`, `knowledge_base_dir`, and `auto_download_embeddings`, but `knowledge_base_sqlite.py` and `local_knowledge.py` still use `os.getenv()` directly and hardcode `"all-MiniLM-L6-v2"`.

**Fix:**
1. In `knowledge_base_sqlite.py`, accept optional `KnowledgeConfig` in constructor
2. Use `config.embedding_model` instead of hardcoded model name
3. Use `config.knowledge_base_dir` instead of `os.getenv("KNOWLEDGE_BASE_DIR", "data")`
4. If `auto_download_embeddings` is True, log and proceed with auto-download; if False, raise a clear error when model is missing
5. Same pattern for `local_knowledge.py`

**Tests:** Update existing knowledge tool tests to verify config is consumed.

### 1D — Update Bare-Metal Launch Scripts

**Problem:** `mcp/generation/launch_generation_mcps.sh` only starts `comfyui_mcp.py` and `whisper_mcp.py`. The 4 new MCP servers (video, music, documents, sandbox) are not started on bare-metal installs. The `launch.sh down` command only kills `comfyui_mcp` and `whisper_mcp`.

**Fix:**
1. Update `mcp/generation/launch_generation_mcps.sh`:
   - Add `launch_server "video" "video_mcp.py"`
   - Add `launch_server "music" "music_mcp.py"`
2. Create `mcp/documents/launch_document_mcp.sh` (same pattern as generation launcher)
3. Create `mcp/execution/launch_sandbox_mcp.sh` (same pattern, gated by `SANDBOX_ENABLED`)
4. Update `launch.sh` `down` command to also kill: `video_mcp`, `music_mcp`, `document_mcp`, `code_sandbox_mcp`
5. Update `launch.sh` `doctor` command to health-check new MCP ports when their services are enabled

### 1E — Fix Sandbox Code Path

**Problem:** `code_sandbox_mcp.py` `run_python()` passes code via `-c` flag AND writes it to a file mounted at `/code:ro`. The `-c` flag takes the code as a CLI argument (which has shell escaping issues with complex code), while `run_python_file()` correctly uses `/code`. The `-c` path should be removed from `run_python` — use the file mount instead.

**Fix:**
1. Change `run_python` command from `["python", "-c", code]` to `["python", "/code"]`
2. Change `run_node` command from `["node", "-e", code]` to `["node", "/code"]`
3. Change `run_bash` command from `["sh", "-c", code]` to `["sh", "/code"]`
4. Remove `run_python_file` since it's now identical to `run_python`
5. Update tool docstrings accordingly

### 1F — Update media_tools/__init__.py

**Problem:** Still says `(future) video/: Video processing` and `(future) image/: Image processing` even though both are implemented.

**Fix:** Update docstring to reflect current state:
```
- image_generator.py: Image generation (mflux CLI)
- video_generator.py: Video generation (ComfyUI)
- music_generator.py: Music generation (AudioCraft/MusicGen)
- audio_generator.py: TTS and voice cloning (CosyVoice)
- audio_transcriber.py: Speech-to-text (Whisper)
```

**Verification after Task 1:**
```bash
make lint && make typecheck && make test
# All must pass. New test count should be baseline + ~20 new tests.
```

---

## AGENT TASK 2: Test Coverage for New Code

**Goal:** Every new MCP server, tool, and routing category has verified test coverage.

### 2A — MCP Server Unit Tests

Create `tests/unit/mcp/` directory with:

**`test_video_mcp.py`**
- Test `generate_video()` with mocked httpx (ComfyUI available, returns success)
- Test `generate_video()` when ComfyUI unavailable (returns error dict)
- Test `generate_video()` timeout scenario
- Test `list_video_models()` with mocked response
- Test default seed generation when seed=-1

**`test_music_mcp.py`**
- Test `generate_music()` with mocked AudioCraft (import success path)
- Test `generate_music()` when AudioCraft not installed (import error path)
- Test `generate_music()` invalid model_size parameter
- Test `list_music_models()` return structure

**`test_document_mcp.py`**
- Test `create_word_document()` end-to-end (creates real .docx, verify it exists)
- Test `create_presentation()` end-to-end (creates real .pptx)
- Test `create_spreadsheet()` end-to-end (creates real .xlsx)
- Test markdown heading parsing in word doc (# → H1, ## → H2)
- Test `list_generated_files()` returns recent files
- Test `_unique_path()` generates unique filenames

**`test_code_sandbox_mcp.py`**
- Test `_run_in_docker()` with mocked subprocess (success case)
- Test `_run_in_docker()` with mocked subprocess (timeout case)
- Test `_run_in_docker()` when Docker not found
- Test output truncation at MAX_OUTPUT_BYTES
- Test `sandbox_status()` return structure
- Test timeout clamping (max 120 for python, max 60 for bash)

### 2B — Tool Module Unit Tests

**`tests/unit/tools/test_video_generator.py`**
- Test `generate_video()` with mocked httpx (ComfyUI response)
- Test connection error handling
- Test workflow parameter substitution

**`tests/unit/tools/test_music_generator.py`**
- Test `generate_music()` with mocked AudioCraft
- Test `_check_audiocraft_available()` import detection
- Test output file path generation

### 2C — Routing Integration Tests

**`tests/unit/test_task_classifier_new_categories.py`**
- Test that "create a video of a sunset" classifies as VIDEO_GEN
- Test that "compose a jazz piano track" classifies as MUSIC_GEN
- Test that "create a word document summarizing" classifies as DOCUMENT_GEN
- Test that "do a deep research on quantum computing" classifies as RESEARCH
- Test that "write a poem" still classifies as CREATIVE (not DOCUMENT_GEN)
- Test that "explain video compression" does NOT classify as VIDEO_GEN (it's reasoning)
- Test that TTS keywords ("text to speech", "read aloud") do NOT match MUSIC_GEN

**`tests/unit/test_llm_classifier_new_categories.py`**
- Verify the classifier prompt includes all new categories
- Verify category-to-model mapping exists for all new categories in router_rules.json

### 2D — Router Rules Validation Test

**`tests/unit/test_router_rules_completeness.py`**
- Load `router_rules.json`
- Verify every workspace has a model and fallback
- Verify every classifier category maps to a model
- Verify every regex rule has valid regex syntax
- Verify no classifier category is missing from the workspaces

**Verification after Task 2:**
```bash
make test
# New test count should be baseline + ~45-55 new tests. All passing.
```

---

## AGENT TASK 3: Documentation Accuracy Pass

**Goal:** Every document in the repo accurately reflects the state of the code after Tasks 1 and 2.

### 3A — PORTAL_HOW_IT_WORKS.md Corrections

1. **Section 12 (MCP/Tool Layer):** Verify every listed MCP server port matches `docker-compose.yml` and the actual `__main__` defaults
2. **Section 6 (Feature Guide):** Add "I want to download generated files" subsection documenting `GET /v1/files` endpoint
3. **Section 6 (Documents):** Add download URL example: `http://localhost:8081/v1/files/{filename}`
4. **Section 6 (Orchestration):** Add "I want to do a multi-step task" subsection explaining how multi-step prompts trigger the orchestrator

### 3B — PORTAL_ROADMAP.md Corrections

1. **Section 1:** Change "Portal 1.4.6" → "Portal 1.4.7" and add new capabilities to the list
2. **Section 7:** Add run 20 verification findings (new test count, new module count)
3. **Footer:** Update "Last updated" line

### 3C — ARCHITECTURE.md Update

1. Add `portal.core.orchestrator` to the component table
2. Add file delivery endpoint to WebInterface route table
3. Add new MCP servers (video, music, documents, sandbox) to MCP Layer section
4. Update architecture diagram to include orchestrator in AgentCore box

### 3D — README.md Capability Overview

Add a "Capabilities" section between "What It Is" and "Hardware" that lists all capability verticals:
- Text generation & chat
- Code generation & debugging
- Image generation (ComfyUI / mflux)
- Video generation (ComfyUI + video models)
- Music generation (AudioCraft/MusicGen)
- TTS & voice cloning (CosyVoice)
- Speech-to-text (Whisper)
- Document creation (Word, PowerPoint, Excel)
- Red team / offensive security
- Blue team / SIEM analysis
- Creative writing
- Deep reasoning & research
- Code execution sandbox
- Multi-step task orchestration

### 3E — CLAUDE.md Update

1. Verify version says 1.4.7
2. Verify no LMStudio references remain
3. Add orchestrator to "Actively used" list
4. Add new MCP servers to project layout

### 3F — .env.example Completeness Check

Verify every new config var is documented with comments:
- `VIDEO_MCP_PORT` / `VIDEO_MODEL`
- `MUSIC_MCP_PORT`
- `DOCUMENTS_MCP_PORT`
- `SANDBOX_MCP_PORT` / `SANDBOX_ENABLED` / `SANDBOX_TIMEOUT`
- `PORTAL_EMBEDDING_MODEL`
- `GENERATED_FILES_DIR`

---

## AGENT TASK 4: Verification & Audit

**Goal:** Run a full verification pass and produce an updated audit report confirming everything works.

### 4A — Full CI Verification

```bash
cd /Users/chris/portal
source .venv/bin/activate
pip install -e ".[all,dev,test]" -q

# Gate 1: Lint
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/

# Gate 2: Type check
python3 -m mypy src/portal

# Gate 3: Full test suite
python3 -m pytest tests/ -v --tb=short -q

# Gate 4: Module imports (all new modules must import cleanly)
python3 -c "from portal.core.orchestrator import TaskOrchestrator; print('orchestrator OK')"
python3 -c "from portal.tools.media_tools.video_generator import generate_video; print('video_gen OK')"
python3 -c "from portal.tools.media_tools.music_generator import generate_music; print('music_gen OK')"

# Gate 5: Router rules validation
python3 -c "
import json
rules = json.load(open('src/portal/routing/router_rules.json'))
ws = rules['workspaces']
cats = rules['classifier']['categories']
print(f'Workspaces: {len(ws)} — {list(ws.keys())}')
print(f'Categories: {len(cats)} — {list(cats.keys())}')
print(f'Regex rules: {len(rules[\"regex_rules\"])}')
assert len(ws) == 11, f'Expected 11 workspaces, got {len(ws)}'
assert len(cats) == 12, f'Expected 12 categories, got {len(cats)}'
print('Router rules: PASS')
"
```

### 4B — Update PORTAL_AUDIT_REPORT.md

Regenerate the audit report with:
- Updated test count (should be ~960-975)
- New module count (should be ~75+)
- New MCP server count (8 total)
- Tool count (should be ~30)
- Confirm 0 lint, 0 mypy errors
- List all new components instantiated
- Health score should remain 10/10

### 4C — Docker Compose Validation

```bash
docker compose config --quiet  # must not error
docker compose config --services  # list all services
# Verify: ollama, ollama-model-init, redis, qdrant, portal-api, portal-router,
#          open-webui, whisper, comfyui, mcp-filesystem, mcp-shell, mcp-web,
#          mcp-comfyui, mcp-whisper, mcp-video, mcp-music, mcp-documents, mcp-sandbox
```

### 4D — Feature Verification Checklist

After all code and doc changes, verify each row of the HOW_IT_WORKS Capability Matrix by confirming:

| Capability | Code Exists | MCP Exists | Workspace Exists | Routing Works | Tests Pass | Docs Accurate |
|---|---|---|---|---|---|---|
| Text chat | ✓ pre-existing | n/a | auto | ✓ | ✓ | ✓ |
| Code generation | ✓ pre-existing | n/a | auto-coding | ✓ | ✓ | ✓ |
| Image gen (ComfyUI) | ✓ image_generator.py | ✓ comfyui_mcp.py | auto-multimodal | ✓ | verify | verify |
| Image gen (mflux) | ✓ image_generator.py | n/a | n/a (direct tool) | ✓ | ✓ | verify |
| Video generation | ✓ video_generator.py | ✓ video_mcp.py | auto-video | verify routing | **NEEDS TESTS** | verify |
| Music generation | ✓ music_generator.py | ✓ music_mcp.py | auto-music | verify routing | **NEEDS TESTS** | verify |
| TTS / voice clone | ✓ audio_generator.py | n/a (direct tool) | n/a | ✓ | ✓ | verify |
| Speech-to-text | ✓ audio_transcriber.py | ✓ whisper_mcp.py | n/a | ✓ | ✓ | verify |
| Documents | ✓ word/ppt/excel tools | ✓ document_mcp.py | auto-documents | verify routing | **NEEDS TESTS** | verify |
| Red team | ✓ pre-existing | n/a | auto-security | ✓ | ✓ | ✓ |
| Blue team | ✓ pre-existing | n/a | auto-reasoning | ✓ | ✓ | ✓ |
| Creative writing | ✓ pre-existing | n/a | auto-creative | ✓ | ✓ | ✓ |
| Code sandbox | n/a | ✓ code_sandbox_mcp.py | n/a (tool call) | n/a | **NEEDS TESTS** | verify |
| RAG/knowledge | ✓ knowledge tools | n/a | auto-research | verify routing | verify config | verify |
| Orchestration | ✓ orchestrator.py | n/a | n/a (auto-detect) | **NEEDS WIRING** | ✓ (14 tests) | verify |
| File delivery | **NEEDS ENDPOINT** | n/a | n/a | n/a | **NEEDS TESTS** | **NEEDS DOCS** |
| Web search | ✓ web_scrape_mcp | n/a | n/a | ✓ | ✓ | ✓ (note: internet req) |

---

## Priority Execution Order

| Order | Task | What It Does | Estimated Effort |
|---|---|---|---|
| 1 | 1B | File delivery endpoint (unblocks docs/video/music delivery) | 1-2 hours |
| 2 | 1A | Orchestrator wiring into AgentCore | 2-3 hours |
| 3 | 1C | KnowledgeConfig wiring | 30 min |
| 4 | 1D | Launch script updates for new MCPs | 1 hour |
| 5 | 1E | Sandbox code path fix | 30 min |
| 6 | 1F | media_tools init fix | 5 min |
| 7 | 2A-2D | All new tests | 3-4 hours |
| 8 | 3A-3F | All documentation updates | 2-3 hours |
| 9 | 4A-4D | Full verification and audit | 1-2 hours |

**Total estimated:** 12-16 hours of agent work across 2-3 sessions.

---

## Non-Negotiable Constraints

- All existing 919+ tests must continue to pass
- No cloud dependencies
- No external AI frameworks (no LangChain, no CrewAI)
- OpenAI-compatible API contract unchanged
- Lint and mypy must stay at zero
- Every new feature must have unit tests
- Commit convention: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`

---

## Files That Need Changes (Complete List)

### Must Modify
| File | Task | Change |
|---|---|---|
| `src/portal/core/agent_core.py` | 1A | Import + initialize orchestrator, add multi-step detection |
| `src/portal/interfaces/web/server.py` | 1B | Add /v1/files and /v1/files/{filename} routes |
| `src/portal/tools/knowledge/knowledge_base_sqlite.py` | 1C | Consume KnowledgeConfig instead of os.getenv |
| `src/portal/tools/knowledge/local_knowledge.py` | 1C | Consume KnowledgeConfig instead of os.getenv |
| `mcp/generation/launch_generation_mcps.sh` | 1D | Add video_mcp and music_mcp launch lines |
| `mcp/execution/code_sandbox_mcp.py` | 1E | Fix run_python/run_node/run_bash to use file mount |
| `src/portal/tools/media_tools/__init__.py` | 1F | Update docstring to reflect implemented tools |
| `launch.sh` | 1D | Add stop commands for new MCPs in `down`, health checks in `doctor` |
| `PORTAL_HOW_IT_WORKS.md` | 3A | File delivery docs, orchestration docs, port verification |
| `PORTAL_ROADMAP.md` | 3B | Version fix, run 20 verification |
| `docs/ARCHITECTURE.md` | 3C | Orchestrator, file delivery, new MCPs |
| `README.md` | 3D | Capabilities section |
| `CLAUDE.md` | 3E | Orchestrator, new MCPs in layout |
| `.env.example` | 3F | Verify all new vars documented |
| `PORTAL_AUDIT_REPORT.md` | 4B | Full refresh with new metrics |

### Must Create
| File | Task | Purpose |
|---|---|---|
| `tests/unit/test_agent_core_orchestrator.py` | 1A | Orchestrator integration tests |
| `tests/integration/test_file_delivery.py` | 1B | File endpoint tests |
| `tests/unit/mcp/__init__.py` | 2A | Test package init |
| `tests/unit/mcp/test_video_mcp.py` | 2A | Video MCP tests |
| `tests/unit/mcp/test_music_mcp.py` | 2A | Music MCP tests |
| `tests/unit/mcp/test_document_mcp.py` | 2A | Document MCP tests |
| `tests/unit/mcp/test_code_sandbox_mcp.py` | 2A | Sandbox MCP tests |
| `tests/unit/tools/test_video_generator.py` | 2B | Video tool tests |
| `tests/unit/tools/test_music_generator.py` | 2B | Music tool tests |
| `tests/unit/test_task_classifier_new_categories.py` | 2C | New routing category tests |
| `tests/unit/test_router_rules_completeness.py` | 2D | Router rules structural validation |
| `mcp/documents/launch_document_mcp.sh` | 1D | Bare-metal document MCP launcher |
| `mcp/execution/launch_sandbox_mcp.sh` | 1D | Bare-metal sandbox MCP launcher |

---

*This document is the authoritative action plan for taking Portal from "scaffolding complete" to "verifiably working end-to-end."*
