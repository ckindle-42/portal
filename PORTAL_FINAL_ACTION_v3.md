# Portal — Final Gap Analysis, Action Tasks & Updated Agent Prompts

**Generated:** 2026-03-02
**Reviewed commit:** ff2ea62 (feat: Task 4 - Full verification and audit)
**Purpose:** Close the last mile. Fix critical bugs. Ensure self-documenting verification. Align web search intent.

---

## 1. What Changed Since Last Review

The coding agent executed Tasks 1–4 from the v2 action prompt. Here's what landed:

**Wired in:** Orchestrator integrated into `agent_core.py` with multi-step detection. File delivery endpoint at `/v1/files` and `/v1/files/{filename}`. KnowledgeConfig consumed by `knowledge_base_sqlite.py`. Sandbox code path fixed to use file mount. Launch scripts updated for video/music MCPs. Document and sandbox launch scripts created. New tests for orchestrator, router rules, task classifier categories, video gen, music gen.

**Still broken or missing — 3 categories:**

---

## 2. Critical Bug: Orchestrator Multi-Step Detection Is Too Aggressive

**This needs to be fixed before anything else.** The `_is_multi_step()` function in `agent_core.py` will hijack normal single-turn requests.

**Problem:** The word "first" is in the multi-step markers list. "Write a function that generates CSV files" has 2 action verbs (write + generates) and triggers the orchestrator. "First, let me explain why..." triggers it. "Find and summarize the key points" triggers it. These are all single-turn prompts that should NOT go through the orchestrator.

**The orchestrator with `build_plan(message)` and no explicit steps creates a single LLM step anyway** — so it's not catastrophic — but it bypasses context history, workspace routing, tool dispatch, streaming, and saves with `model_used="orchestrator"` which breaks metrics and model attribution.

**Fix:**

```python
def _is_multi_step(self, message: str) -> bool:
    """Detect ONLY explicitly structured multi-step requests.

    Conservative: only trigger when the user clearly wants sequential tasks.
    False negatives are fine (normal processing handles it).
    False positives break context, routing, streaming, and metrics.
    """
    message_lower = message.lower()

    # Only match very explicit multi-step structure
    explicit_patterns = [
        r"step\s*1\b.*step\s*2\b",           # "step 1... step 2..."
        r"first\b.*\bthen\b.*\b(then|finally)\b",  # "first X, then Y, then/finally Z"
        r"(?:do|perform)\s+both\b",            # "do both X and Y"
        r"\b1\)\s.*\b2\)\s",                   # "1) X 2) Y"
    ]
    import re
    for pattern in explicit_patterns:
        if re.search(pattern, message_lower, re.DOTALL):
            return True

    return False
```

This is conservative by design — single-turn is the safe default. The orchestrator should only activate when the user's intent is unambiguously multi-step.

**Tests needed:**
- "Write a Python function that generates and creates CSV files" → False
- "First, let me explain quantum computing" → False
- "Find and summarize the key points" → False
- "Step 1: research quantum computing. Step 2: create a presentation about it" → True
- "First research X, then write a report, then create slides" → True
- "Do both: write the code and create the documentation" → True

---

## 3. Missing: launch.sh `down` and `doctor` Not Updated

**Problem:** `launch.sh stop_all()` only kills `comfyui_mcp` and `whisper_mcp`. The 4 new MCPs (video, music, document, sandbox) are orphaned when you run `launch.sh down`.

**Fix — add to `stop_all()` after line 664:**
```bash
pkill -f "video_mcp" 2>/dev/null && echo "[video_mcp] stopped" || true
pkill -f "music_mcp" 2>/dev/null && echo "[music_mcp] stopped" || true
pkill -f "document_mcp" 2>/dev/null && echo "[document_mcp] stopped" || true
pkill -f "code_sandbox_mcp" 2>/dev/null && echo "[code_sandbox_mcp] stopped" || true
```

**Fix — add to `run_doctor()` for optional MCP health checks:**
```bash
check_optional "mcp-video" "http://localhost:${VIDEO_MCP_PORT:-8911}/health"
check_optional "mcp-music" "http://localhost:${MUSIC_MCP_PORT:-8912}/health"
check_optional "mcp-documents" "http://localhost:${DOCUMENTS_MCP_PORT:-8913}/health"
check_optional "mcp-sandbox" "http://localhost:${SANDBOX_MCP_PORT:-8914}/health"
```

---

## 4. Missing: No Tests for File Delivery or Orchestrator Integration

**File delivery endpoint** (`/v1/files`, `/v1/files/{filename}`) has zero test coverage. This is a new public API surface.

**Orchestrator integration** (`_is_multi_step`, `_handle_orchestrated_request`) has zero integration test coverage. The orchestrator unit tests only test the standalone `TaskOrchestrator` class, not the wiring into `agent_core`.

**New MCP servers** (video_mcp, music_mcp, document_mcp, code_sandbox_mcp) have zero test coverage.

Required tests detailed in Agent Task section below.

---

## 5. Missing: Documentation Not Updated

These docs reference the old state and don't mention orchestrator, file delivery, or new MCPs:

- `docs/ARCHITECTURE.md` — no orchestrator, no `/v1/files`, no new MCP servers
- `README.md` — no capabilities overview section
- `CLAUDE.md` — no orchestrator in "Actively used" list, no new MCPs in project layout
- `PORTAL_HOW_IT_WORKS.md` — web search description should clarify it's for targeted research when the model needs current/updated information, not general internet browsing

---

## 6. Clarification: Web Search / Crawl Intent

Per your direction: the web crawl (scrapling + DuckDuckGo fallback) is specifically for **when you need to research something the model doesn't know or needs more current information on**. It is NOT general internet browsing for fun.

**Current docs say:** "PARTIAL (needs internet)" — this is misleading. It implies the feature is incomplete.

**Should say:** "READY — requires internet connection. Designed for targeted research queries when the LLM needs current or specialized information not in its training data. Not intended for general web browsing."

Update in:
- `PORTAL_HOW_IT_WORKS.md` capability matrix and Section 6 feature guide
- Any doc agent output that discusses web search

---

## 7. Agent Task List (For Coding Agent)

### TASK-1: Fix Orchestrator Multi-Step Detection (CRITICAL)

**File:** `src/portal/core/agent_core.py`
**Problem:** `_is_multi_step()` triggers on 16 common English words and 2+ verbs from a list of 17 common verbs. This catches most normal prompts.
**Action:** Replace with regex-based explicit multi-step structure detection per Section 2 above.
**Tests:** Create `tests/unit/test_multi_step_detection.py` with at minimum:
- 5 prompts that SHOULD trigger orchestrator (explicitly structured multi-step)
- 10 prompts that SHOULD NOT trigger (normal single-turn with action verbs, "first" in casual use, etc.)
**Acceptance:** `make test` passes. No existing tests broken.

### TASK-2: Update launch.sh Down and Doctor

**File:** `launch.sh`
**Problem:** `stop_all()` orphans 4 new MCP processes. `run_doctor()` doesn't check them.
**Action:** Per Section 3 above.
**Acceptance:** `bash -n launch.sh` passes. New MCPs stop on `down` and get health-checked on `doctor`.

### TASK-3: File Delivery Tests

**File:** Create `tests/integration/test_file_delivery.py`
**Tests:**
- `GET /v1/files` returns JSON list (empty when no generated files)
- `GET /v1/files` returns files after one is created in `data/generated/`
- `GET /v1/files/{filename}` returns 200 with correct content-type for .docx, .pptx, .xlsx, .wav
- `GET /v1/files/{filename}` returns 404 for nonexistent file
- `GET /v1/files/../../etc/passwd` returns 400 (path traversal blocked)
- `GET /v1/files/..%2F..%2Fetc%2Fpasswd` returns 400 (encoded traversal blocked)
**Acceptance:** All pass. `make test` green.

### TASK-4: Orchestrator Integration Tests

**File:** Create `tests/unit/test_agent_core_orchestrator.py`
**Tests:**
- `_is_multi_step("hello")` returns False
- `_is_multi_step("write a Python sort function")` returns False
- `_is_multi_step("first, let me explain")` returns False
- `_is_multi_step("Step 1: research. Step 2: write report")` returns True
- `_handle_orchestrated_request()` returns ProcessingResult with model_used="orchestrator"
- If orchestrator raises, `process_message()` falls back to normal processing
**Acceptance:** All pass.

### TASK-5: MCP Server Tests

**File:** Create `tests/unit/mcp/test_document_mcp.py`
**Tests:**
- `create_word_document()` produces a .docx file that exists on disk
- `create_presentation()` produces a .pptx file
- `create_spreadsheet()` produces a .xlsx file
- `list_generated_files()` returns file list after creation
- Invalid input handling (empty title, etc.)

**File:** Create `tests/unit/mcp/test_code_sandbox_mcp.py`
**Tests (mocked Docker):**
- `run_python()` with mock subprocess returns stdout/stderr
- Timeout case returns `timed_out: True`
- Docker not found returns clear error
- `sandbox_status()` returns expected structure

**Note:** Video and music MCP tests already exist. Document and sandbox need them.

### TASK-6: Documentation Updates

**Files:** `docs/ARCHITECTURE.md`, `README.md`, `CLAUDE.md`, `PORTAL_HOW_IT_WORKS.md`
**Action:**
- ARCHITECTURE.md: Add orchestrator to AgentCore component table. Add `/v1/files` to WebInterface route table. Add video/music/documents/sandbox MCP servers to MCP Layer section.
- README.md: Add "Capabilities" section between "What It Is" and "Hardware" listing all verticals.
- CLAUDE.md: Add orchestrator to "Actively used" list. Add new MCPs to project layout. Verify version is 1.4.7.
- PORTAL_HOW_IT_WORKS.md: Update web search description per Section 6 above. Add orchestration usage example. Verify `/v1/files` download URL is documented in documents section.
**Acceptance:** `grep -c orchestrator docs/ARCHITECTURE.md` > 0. `grep -c "v1/files" docs/ARCHITECTURE.md` > 0.

### TASK-7: Run Full Verification

After all tasks complete:
```bash
make lint && make typecheck && make test
```
All must pass. Update `PORTAL_AUDIT_REPORT.md` with new test count and module count.

---

## 8. Updated Agent Prompts

The existing Documentation Agent v3 and Codebase Review Agent v6 are strong prompts. They need targeted additions, not rewrites. Here are the specific changes:

### 8A — Documentation Agent v3 Additions

Add to **Phase 3 (Feature Catalog)** after Section 3R:

```markdown
### 3S — Multi-Step Task Orchestration

```
Feature: Task Orchestrator
  Module:      portal.core.orchestrator.TaskOrchestrator
  Wired into:  agent_core.py → _is_multi_step() → _handle_orchestrated_request()
  Trigger:     User sends explicitly multi-step prompt (e.g., "Step 1: X. Step 2: Y")
  Behavior:    Decomposes into sequential steps, executes each, passes context forward
  Constraints: Max 8 steps. Linear chains only. Falls back to normal processing on failure.
  VERIFY:      Does _is_multi_step() correctly identify multi-step vs single-turn?
               Test with: "write a function" (should NOT trigger), "Step 1: X. Step 2: Y" (SHOULD trigger)
  Status:      [VERIFIED | BROKEN — document which prompts trigger incorrectly]
```

### 3T — File Delivery Endpoint

```
Feature: Generated file download
  Endpoints:   GET /v1/files (list), GET /v1/files/{filename} (download)
  Source dir:   data/generated/
  Security:     Path traversal protection (rejects .., /, \)
  Used by:      Document MCP, Music MCP, Video MCP — all write to data/generated/
  VERIFY:       Hit GET /v1/files via TestClient. Create a test file in data/generated/,
                verify it appears in list and can be downloaded.
                Verify path traversal is blocked.
  Status:       [VERIFIED | BROKEN]
```

### 3U — Web Search / Research Tool

```
Feature: Web search for targeted research
  Purpose:     When the LLM needs current or specialized information not in its training data.
               NOT for general internet browsing.
  MCP server:  mcp/scrapling/ (streamable-http on :8900)
  Fallback:    scripts/mcp/web_scrape_mcp_server.py (DuckDuckGo instant answer API)
  Requires:    Internet connection for the specific query
  Use cases:   "What is the latest CVE for Log4j?" — model needs current data
               "Research the current NERC CIP v7 standard changes" — specialized/current info
  NOT for:     "Browse Reddit for me" or "What's trending on Twitter"
  Status:      [VERIFIED — requires internet | document actual behavior]
```
```

Add to **Phase 2B (Routing Chain Verification)** table:

```markdown
| "create a video of a sunset" | None | video_gen category |
| "compose jazz piano music" | None | music_gen category |
| "create a word document" | None | document_gen category |
| "deep research quantum computing" | None | research category |
| "Step 1: research X. Step 2: summarize" | None | should trigger orchestrator |
```

Add to **Phase 3R (Feature Status Matrix)** additional rows:

```markdown
| Orchestration | Web, Telegram, Slack | Multi-step prompt | orchestrator | [status] | 3S |
| File delivery | Web | GET /v1/files | FileResponse | [status] | 3T |
| Video generation | Web (tool) | Prompt "create video" | ComfyUI MCP | [status] | 3H |
| Music generation | Web (tool) | Prompt "compose music" | AudioCraft MCP | [status] | 3G |
| Code sandbox | Web (tool) | Prompt "run this code" | Docker sandbox | [status] | 3F |
| Web search | Web (tool) | Prompt "research X" | scrapling/DDG | READY (internet) | 3U |
```

### 8B — Codebase Review Agent v6 Additions

Add to **Phase 3A (Component Instantiation)**:

```markdown
- **TaskOrchestrator** — constructs? Can build a plan? Can execute a single-step plan?
- **_is_multi_step()** — test with 5 single-turn prompts and 5 multi-step prompts. Document false positive/negative rate.
- **File delivery routes** — do /v1/files endpoints exist in create_app() routes? Return expected responses?
```

Add to **Phase 3B (Routing Chain Verification)** table:

```markdown
| "create a video of a sunset" | None | video_gen |
| "compose a jazz piano track" | None | music_gen |
| "write a word document" | None | document_gen |
| "deep research quantum physics" | None | research |
```

Add to **Phase 4 (Code Audit)** a new finding category:

```markdown
| `OVERLY_AGGRESSIVE` | Detection/classification logic that triggers on too many inputs, causing false positives |
```

Add to **Phase 3E (Config Contract)**:

```markdown
Verify these new config vars are in .env.example AND consumed by code:
- VIDEO_MCP_PORT, VIDEO_MODEL
- MUSIC_MCP_PORT  
- DOCUMENTS_MCP_PORT, GENERATED_FILES_DIR
- SANDBOX_MCP_PORT, SANDBOX_ENABLED, SANDBOX_TIMEOUT
- PORTAL_EMBEDDING_MODEL
```

Add to **Phase 3G (Tool Registration)**:

```markdown
For each MCP server in mcp/:
- comfyui_mcp.py — tools registered? generate_image, list_workflows
- whisper_mcp.py — tools registered? transcribe_audio
- video_mcp.py — tools registered? generate_video, list_video_models
- music_mcp.py — tools registered? generate_music, list_music_models
- document_mcp.py — tools registered? create_word_document, create_presentation, create_spreadsheet, list_generated_files
- code_sandbox_mcp.py — tools registered? run_python, run_node, run_bash, sandbox_status
```

---

## 9. Self-Documentation Capability

You asked for the project to be able to "document itself." Here's how that works with the two agent prompts:

**The Documentation Agent v3** is the self-documentation engine. When run against the repo in a Claude Code session, it:
1. Builds the environment from scratch
2. Runs every test
3. Instantiates every component
4. Exercises every routing path
5. Hits every endpoint
6. Checks every config var
7. Tests every feature
8. Writes verified documentation based only on what it proved works

**The Codebase Review Agent v6** is the self-auditing engine. When run, it:
1. Does everything the doc agent does (Phase 0–3)
2. Then audits code quality, dead code, disconnected wires
3. Produces an action plan for a coding agent to execute
4. Updates the roadmap with findings

**The workflow is:**
1. Run Code Review Agent v6 → produces audit report + action tasks
2. Coding agent executes the tasks
3. Run Documentation Agent v3 → produces verified HOW_IT_WORKS.md
4. Any discrepancies become new roadmap items

With the additions from Section 8 above, both agents will now cover all new features (orchestrator, file delivery, video/music/doc MCPs, sandbox, web search intent, multi-step detection correctness).

---

## 10. Priority Execution Order

| # | Task | Why | Effort |
|---|---|---|---|
| 1 | TASK-1: Fix multi-step detection | **Critical bug** — currently hijacks normal prompts | 1 hour |
| 2 | TASK-4: Orchestrator integration tests | Prevents regression of fix | 1 hour |
| 3 | TASK-2: launch.sh down/doctor | Orphaned processes on shutdown | 30 min |
| 4 | TASK-3: File delivery tests | New public API with no coverage | 1 hour |
| 5 | TASK-5: MCP server tests | New servers with no coverage | 1.5 hours |
| 6 | TASK-6: Documentation updates | Docs don't reflect current state | 2 hours |
| 7 | TASK-7: Full verification | Prove everything works | 30 min |

**Total: ~8 hours of agent work.**

After TASK-7 completes, run the Documentation Agent v3 (with Section 8A additions) to regenerate PORTAL_HOW_IT_WORKS.md from verified reality. That's the finish line.

---

## 11. Files Summary

### Must Modify
| File | Task | What |
|---|---|---|
| `src/portal/core/agent_core.py` | 1 | Rewrite `_is_multi_step()` to conservative regex |
| `launch.sh` | 2 | Add new MCPs to `stop_all()` and `run_doctor()` |
| `docs/ARCHITECTURE.md` | 6 | Orchestrator, /v1/files, new MCPs |
| `README.md` | 6 | Capabilities section |
| `CLAUDE.md` | 6 | Orchestrator, new MCPs in layout |
| `PORTAL_HOW_IT_WORKS.md` | 6 | Web search clarification, verify all sections current |

### Must Create
| File | Task | What |
|---|---|---|
| `tests/unit/test_multi_step_detection.py` | 1, 4 | Conservative detection tests |
| `tests/unit/test_agent_core_orchestrator.py` | 4 | Integration tests for wiring |
| `tests/integration/test_file_delivery.py` | 3 | File endpoint tests |
| `tests/unit/mcp/test_document_mcp.py` | 5 | Document MCP tests |
| `tests/unit/mcp/test_code_sandbox_mcp.py` | 5 | Sandbox MCP tests |

### Agent Prompt Updates (for your reference, not for coding agent)
| File | What |
|---|---|
| `docs/agents/PORTAL_DOCUMENTATION_AGENT_v3.md` | Add Sections 3S, 3T, 3U + routing + matrix rows per 8A |
| `docs/agents/PORTAL_CODEBASE_REVIEW_AGENT_v6.md` | Add Phase 3A/3B/3E/3G/4 additions per 8B |

---

*This is the final gap between "scaffolding connected" and "verified complete." Fix the multi-step detection first — everything else is test coverage, docs, and operational completeness.*
