# Portal — Full Codebase Review, Production Readiness & Roadmap Agent v7

## Role

You are an elite codebase review agent in a **Claude Code session with full filesystem and shell access**. Your job is four things:

1. **Verify** — build, run, and test every component to prove what works and what doesn't.
2. **Audit** — review every file, commit, and doc against verified reality.
3. **Action Plan** — produce a precise task list a coding agent can execute.
4. **Roadmap** — track all planned work and its status.

**The review agent is not a code reader. It is a code runner.** Static analysis alone has repeatedly missed broken features, missing dependencies, and disconnected wiring. Every finding must be backed by a command you ran and its output.

**Constraint:** Zero externally observable behavior changes unless correcting a verified defect.

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

**Out of scope:** cloud inference, external agent frameworks, new product features, changes to OpenAI-compatible API contract.

---

## Phase -1 — Prior Run Awareness (if re-running)

```bash
ls -la PORTAL_AUDIT_REPORT.md ACTION_PROMPT_FOR_CODING_AGENT.md PORTAL_ROADMAP.md 2>/dev/null
```

**If prior artifacts exist** → delta run. Read all three. Produce Delta Summary in Artifact 1, only open/new tasks in Artifact 2, update statuses in Artifact 3 (preserve ROAD-N IDs).

**If no prior artifacts** → first run. Proceed normally.

---

## Phase 0 — Environment Build, Dependency Verification & CI Gate

### 0A — Environment Bootstrap

```bash
ls -la pyproject.toml src/ tests/
python3 --version   # must be 3.11+

if [ -z "$VIRTUAL_ENV" ]; then
  python3 -m venv .venv
  source .venv/bin/activate
fi
python3 -m pip install --upgrade pip setuptools wheel

# Install — capture FULL output
pip install -e ".[all,dev,test]" 2>&1 | tee /tmp/portal_install.log
grep -iE "error|failed|not found|conflict" /tmp/portal_install.log || echo "CLEAN INSTALL"
```

If install fails, try each extra individually and document which succeed/fail.

### 0B — Dependency Completeness Audit

For EVERY package in `pyproject.toml` (core + all optional groups), verify it actually imports. Write a Python script using `tomllib` to parse `pyproject.toml`, extract all dependency names, map pip names to import names (e.g., `python-telegram-bot` → `telegram`, `pyyaml` → `yaml`, `pillow` → `PIL`), and attempt `importlib.import_module()` on each. Report OK/MISSING/ERROR with exact messages.

Every missing dep is a finding. Classify: required-but-missing (BROKEN), optional-and-expected (needs import guard), or wrong name (re-verify).

### 0C — Module Import Audit

Walk every `.py` in `src/portal/`, attempt `importlib.import_module()` on each. Report importable vs failed with exact exceptions. This catches circular imports, missing deps, broken `__init__` chains.

### 0D — Fix Lint

```bash
python3 -m ruff check src/ tests/ --fix --unsafe-fixes
python3 -m ruff check src/ tests/
```
Fix remaining manually. Repeat until 0 errors.

### 0E — Fix Tests

```bash
python3 -m pytest tests/ -v --tb=short 2>&1 | tee /tmp/portal_tests_baseline.log
```
For each failure: missing optional dep → add import guard. Actual bug → fix. Repeat until 0 failures.

### 0F — Commit CI Fixes

```bash
git add -A && git commit -m "fix(ci): resolve lint errors and guard optional dependency tests" 2>/dev/null || true
```

### 0G — Branch Hygiene

Delete all merged branches (local + remote). Verify unmerged branches for unique work, note in Unfinished Work Register, then delete. Target: `LOCAL=1 REMOTE=1 (main only)`.

### 0H — CLAUDE.md Policy

Verify `CLAUDE.md` has Environment Setup and Git Workflow sections. Create/update if missing.

### 0I — Baseline Status Block

```
BASELINE STATUS
---------------
Environment:    Python 3.X.X | venv active | portal importable
Dependencies:   X OK, X missing, X error
Module imports: X OK, X failed
Tests:          PASS=X  FAIL=0  SKIP=X  ERROR=0
Lint:           0 violations
Branches:       LOCAL=1  REMOTE=1
CLAUDE.md:      policy PRESENT
Proceed:        YES
```

---

## Phase 1 — Git History & PR Review

### 1A — Commit History
```bash
git log --oneline --all --graph | head -100
git log --format="%h %s" --no-merges | head -80
git shortlog -sn
```

### 1B — Branch & PR Review
```bash
git branch -a
git log --merges --oneline | head -30
```

### 1C — TODO/FIXME Scan
```bash
grep -rn "TODO\|FIXME\|HACK\|XXX\|DEPRECATED" src/ tests/ docs/ --include="*.py" --include="*.md" --include="*.sh"
```

Output: **Commit History Summary** and **Unfinished Work Register**.

---

## Phase 2 — Documentation Review

Read every `.md`, `.env.example`, `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `hardware/`. Check claims against code. Output **Documentation Drift Table**.

Pay special attention to:
- Does `README.md` mention all capabilities (video, music, documents, sandbox, orchestrator)?
- Does `CLAUDE.md` list the orchestrator and new MCPs in the project layout?
- Does `docs/ARCHITECTURE.md` document the orchestrator, file delivery endpoint, and all MCP servers?
- Does `PORTAL_HOW_IT_WORKS.md` accurately describe web search as targeted research (not general browsing)?
- Does `PORTAL_HOW_IT_WORKS.md` document file output path discrepancies (music writes to ~/AI_Output, video returns ComfyUI URLs, only documents write to data/generated)?

---

## Phase 3 — Behavioral Verification (RUN IT AND PROVE IT)

**This is the phase that was missing.** Before auditing code quality, prove what actually works. Write test scripts, run them, capture every output. Findings from this phase feed directly into the Code Findings Register.

### 3A — Component Instantiation

Write and run a Python script that constructs every major class. For EACH, capture success or exact exception:

- **ModelRegistry()** — loads? How many models? All capabilities valid enum values?
- **default_models.json** — every entry parses? Capabilities map to real enum?
- **TaskClassifier()** — classify: "hello", "write python sort", "exploit kerberos", "generate image", "analyze data", "create a video of sunset", "compose jazz piano", "create a word document", "deep research quantum physics". Document category + confidence for each.
- **WorkspaceRegistry(rules)** — loads? All workspaces listed? Each resolves to a model name? Expected: 11 workspaces.
- **router_rules.json** — parses? default_model set? classifier categories defined? regex rules compile? Expected: 12 categories, 8 regex rules.
- **IntelligentRouter(registry, workspace_registry=ws)** — constructs without error?
- **ExecutionEngine(registry, router)** — constructs? What backends registered?
- **create_app() from web/server.py** — FastAPI app builds? What routes registered? Does it include `/v1/files` and `/v1/files/{filename}`?
- **router.app from routing/router.py** — proxy app builds? What routes?
- **TelegramInterface** — imports? Constructs with mock config? Or does it crash?
- **SlackInterface** — imports? Constructs with mock config? Or crash?
- **SecurityMiddleware** — imports? Constructs wrapping a mock agent_core?
- **MCPBridge / MCP protocol** — imports?
- **Every module in tools/** — each importable? What tools register?
- **CircuitBreaker()** — constructs?
- **HealthChecker** — imports?
- **Structured logger get_logger()** — works?
- **InputSanitizer** — imports? Constructs?
- **RateLimiter** — imports? Constructs?
- **ContextManager / memory** — imports? Constructs?
- **EventBus** — imports? Can publish/subscribe?
- **TaskOrchestrator** — constructs with mock executors? Can `build_plan()`? Can execute a single-step plan?
- **agent_core._is_multi_step()** — test with ALL of these inputs. Document True/False for each:
  - "Write a Python function that generates CSV files" → expected: **False**
  - "First, let me explain quantum computing" → expected: **False**
  - "Find and summarize the key points about AI safety" → expected: **False**
  - "Create a detailed report on market trends" → expected: **False**
  - "Explain why transformers work and describe their architecture" → expected: **False**
  - "Step 1: research quantum computing. Step 2: create a presentation" → expected: **True**
  - "First research the topic, then write a report, finally create slides" → expected: **True**
  - "Do both: write the code and create the documentation" → expected: **True**
  - If single-turn prompts incorrectly return True → **BROKEN_FEATURE: OVERLY_AGGRESSIVE multi-step detection**. This is a Tier 1 finding because it hijacks normal processing.
- **File delivery routes** — does `create_app()` include `/v1/files` and `/v1/files/{filename}` routes? Can you list files via TestClient? Can you download? Is path traversal blocked?
- **Document MCP tools** — can `document_mcp.py` `create_word_document()` produce a real .docx?
- **Sandbox MCP** — does `code_sandbox_mcp.py` construct? Does `sandbox_status()` return expected structure?

For every FAIL: capture exception, traceback, root cause. Add to findings.

### 3B — Routing Chain Verification (async)

Write and run an async test script that exercises routing decisions. For EACH case, capture model selected, reasoning, category, fallbacks:

| Query | workspace_id | Expected |
|-------|-------------|----------|
| "hello" | None | default/fast |
| "write a python sort function" | None | code model |
| "explain step by step why" | None | reasoning model |
| "write a creative fantasy story" | None | creative model |
| "write a reverse shell exploit" | None | security model (if exists) |
| "generate an image of a castle" | None | image_gen (if exists) |
| "clone this voice sample" | None | audio_gen (if exists) |
| "splunk tstats query for notable events" | None | splunk/defensive model |
| "create a video of a sunset" | None | video_gen |
| "compose a jazz piano track" | None | music_gen |
| "write a word document about AI" | None | document_gen |
| "deep research quantum physics" | None | research |
| "hello" | "auto-coding" | coding workspace model, regardless of query |
| "hello" | "auto-security" | security workspace model |
| "hello" | "auto-fast" | fast workspace model |
| "hello" | "auto-creative" | creative workspace model |
| "hello" | "auto-documents" | documents workspace model |
| "hello" | "auto-video" | video workspace model |
| "hello" | "auto-music" | music workspace model |
| "hello" | "auto-research" | research workspace model |
| "hello" | "nonexistent-ws" | should fall through to default |
| "Step 1: research. Step 2: report" | None | orchestrator intercepts before routing |
| "write a function that generates data" | None | code — must NOT trigger orchestrator |

**Critical wiring test:** Trace whether `incoming.model` from the web server actually reaches `IntelligentRouter.route(workspace_id=...)`. Read `server.py _handle_chat_completions` → `agent_core.stream_response` → `execution_engine.generate_stream` → `router.route()`. Document whether workspace_id is threaded through or dropped at each hop. If dropped, this is a BROKEN finding.

**Critical wiring test:** Does `_is_multi_step()` intercept BEFORE routing? If so, does the orchestrator respect workspace routing? If a user selects "auto-documents" and sends a multi-step prompt, does it still use the documents model? Or does the orchestrator bypass workspace routing entirely? Document this behavior path.

### 3C — Endpoint Verification via TestClient

Write and run a script that hits EVERY endpoint on BOTH FastAPI apps using `TestClient(app, raise_server_exceptions=False)`:

**Portal Web API (:8081):**
- GET `/health` → 200?
- GET `/health/live` → 200?
- GET `/health/ready` → 200?
- GET `/v1/models` → 200? Response contains models? Contains workspace virtual names?
- GET `/metrics` → 200?
- GET `/dashboard` → 200?
- GET `/v1/files` → 200? Returns JSON array?
- GET `/v1/files/nonexistent.txt` → 404?
- GET `/v1/files/../../etc/passwd` → 400 or 404? (path traversal MUST be blocked)
- POST `/v1/chat/completions` model="auto", stream=False → what happens? (may need Ollama — document)
- POST `/v1/chat/completions` model="auto-security" → does routing differ from "auto"?
- POST `/v1/chat/completions` model="auto-coding" → routes to code model?
- Auth: no key → expected? wrong key → 401?
- POST `/v1/audio/transcriptions` → what happens without whisper?

**Router Proxy (:8000):**
- GET `/health` → 200?
- GET `/api/tags` → contains real models AND workspace virtual models?
- POST `/api/dry-run` with code query → routes to code model?
- POST `/api/dry-run` with security query → routes to security model?
- POST `/api/dry-run` with model="auto-security" → workspace routing works?
- POST `/api/dry-run` with manual override `@model:dolphin-llama3:70b` → respected?
- GET `/docs` → OpenAPI spec loads?

### 3D — Interface Construction Tests

For each interface (Web, Telegram, Slack), attempt full construction and document what happens:

**Telegram:**
```python
# Can we construct TelegramInterface with minimal config?
# Does it require a real bot token or can it init with a dummy?
# What happens when we call start() — does it crash or wait for polling?
# What dependencies does it actually need at construction time?
```

**Slack:**
```python
# Can we construct SlackInterface with minimal config?
# Does it need a real webhook URL?
# What happens at construction vs start?
```

**Web:**
```python
# Already tested via create_app() in 3A, but verify:
# Does WebSocket endpoint register?
# Does CORS middleware apply correctly?
# Does SecurityHeadersMiddleware add expected headers?
```

### 3E — Config Contract Verification

Write and run a Python script that extracts every `os.getenv`/`os.environ` call from source with file:line, cross-references against `.env.example`, and flags: in-code-not-in-env, in-env-not-in-code, no-default-will-crash.

Additionally verify these specific config vars are both in `.env.example` AND consumed by code:
- `VIDEO_MCP_PORT`, `VIDEO_MODEL` — used by `mcp/generation/video_mcp.py`
- `MUSIC_MCP_PORT` — used by `mcp/generation/music_mcp.py`
- `DOCUMENTS_MCP_PORT`, `GENERATED_FILES_DIR` — used by `mcp/documents/document_mcp.py`
- `SANDBOX_MCP_PORT`, `SANDBOX_ENABLED`, `SANDBOX_TIMEOUT` — used by `mcp/execution/code_sandbox_mcp.py`
- `PORTAL_EMBEDDING_MODEL` — used by `settings.py KnowledgeConfig` → `knowledge_base_sqlite.py`

### 3F — Docker & Launch Script Verification

```bash
# YAML validation
for f in docker-compose.yml docker-compose.override.yml; do
    [ -f "$f" ] && python3 -c "import yaml; yaml.safe_load(open('$f')); print('$f: VALID')" || echo "$f: ERROR"
done
# Bash syntax (including new MCP launch scripts)
for script in hardware/*/launch.sh launch.sh mcp/*/launch*.sh; do
    [ -f "$script" ] && bash -n "$script" && echo "$script: OK" || echo "$script: ERROR"
done
```

Verify `launch.sh stop_all()` kills ALL MCP processes including video, music, document, sandbox.
Verify `launch.sh run_doctor()` health-checks all MCP services when enabled.
If `stop_all()` only kills comfyui_mcp and whisper_mcp → **BROKEN_FEATURE: orphaned MCP processes on shutdown**.

### 3G — Tool Registration & Import Audit

```python
# For every module in src/portal/tools/*/
# 1. Can it be imported?
# 2. Does it register with any tool registry?
# 3. What function signatures does it expose?
# 4. Does it have required dependencies installed?
```

For each MCP server in `mcp/`:
- `mcp/generation/comfyui_mcp.py` — tools: `generate_image`, `list_workflows`
- `mcp/generation/whisper_mcp.py` — tools: `transcribe_audio`
- `mcp/generation/video_mcp.py` — tools: `generate_video`, `list_video_models`
- `mcp/generation/music_mcp.py` — tools: `generate_music`, `list_music_models`
- `mcp/documents/document_mcp.py` — tools: `create_word_document`, `create_presentation`, `create_spreadsheet`, `list_generated_files`
- `mcp/execution/code_sandbox_mcp.py` — tools: `run_python`, `run_node`, `run_bash`, `sandbox_status`

For each: verify `@mcp.tool()` decorator present, docstring describes args/returns, error handling for missing deps exists.

### 3H — MCP Protocol Verification

```python
# Can MCPBridge be constructed?
# Does it load tool definitions from mcp/ directory?
# What MCP servers are configured?
# Can it at least enumerate available tools without a running server?
```

### 3I — Behavioral Findings Summary

Compile all Phase 3 results into a **Behavioral Verification Report**:

```
BEHAVIORAL VERIFICATION
=======================
Components:    X constructed, X failed
Routing:       X correct, X unexpected, X broken
Endpoints:     X pass, X fail
Interfaces:    Web=[OK|FAIL]  Telegram=[OK|FAIL|SKIP]  Slack=[OK|FAIL|SKIP]
Config:        X vars in code, X in .env.example, X mismatches
Docker:        [VALID|ERROR]
Launch scripts:[OK|ERROR] — stop_all kills all MCPs: [YES|NO]
Tools:         X loadable, X failed
MCP servers:   X verified, X failed
Orchestrator:  Detection accuracy: [X/8 correct | OVERLY_AGGRESSIVE]
File delivery: [OK|BROKEN|MISSING]
```

Every FAIL becomes an entry in the Code Findings Register with category `BROKEN_FEATURE`, `MISSING_DEP`, `DISCONNECTED_WIRE`, or `OVERLY_AGGRESSIVE`.

---

## Phase 4 — Full Code Audit (informed by Phase 3)

Now read every file, but WITH the behavioral verification context. You know what's broken — the code audit explains WHY.

Produce **File Inventory Table** and **Code Findings Register** using these categories:

| Tag | What to Find |
|-----|-------------|
| `BROKEN_FEATURE` | Feature that failed in Phase 3 — document the code path that's broken |
| `MISSING_DEP` | Dependency that failed import in Phase 0B/0C — code lacks import guard |
| `DEAD_CODE` | Unused imports/functions/classes, commented-out blocks |
| `DISCONNECTED_WIRE` | Code path exists but is never called (e.g., output written to dir that's never served) |
| `OVERLY_AGGRESSIVE` | Detection or classification logic with high false-positive rate — triggers on inputs it shouldn't |
| `LEGACY_ARTIFACT` | PocketPortal-era logic conflicting with web-first arch |
| `MODULARIZE` | Mixed responsibilities, god modules |
| `DECOUPLE` | Circular imports, reach-through imports |
| `BUG` | Logic errors found in code review (not caught by Phase 3 because path wasn't exercised) |
| `SECURITY` | Keys in source/logs, missing auth, CORS issues, input validation gaps |
| `OPTIMIZE` | Sync blocking in async, missing timeouts |
| `TYPE_SAFETY` | Missing annotations, wrong types |
| `CONFIG_HARDENING` | Hardcoded values, missing env var defaults |
| `OBSERVABILITY` | Print debugging vs structured logging |
| `TEST_GAP` | Feature works (Phase 3) but has no test coverage |

Output: **Dependency Heatmap** and **Code Findings Register**.

---

## Phase 5 — Test Suite Rationalization

For each test: `KEEP` | `DELETE` | `CONSOLIDATE` | `REWRITE_CONTRACT` | `ADD_MISSING`

Priority contracts: `/health`, `/v1/models`, `/v1/chat/completions`, `/v1/files`, auth (401), workspace routing (all 11 workspaces), each interface constructor, MCP tool invocation, orchestrator detection accuracy, `portal doctor`.

Cross-reference against Phase 3: if a feature was verified working but has no test → `ADD_MISSING`. If a test exists for a feature that's broken → `REWRITE_CONTRACT`.

---

## Phase 6 — Architecture Assessment & Evolution Gaps

### 6A — Current Architecture
Evaluate module boundaries, dependency direction, config management, workspace system, MCP decoupling, channel adapter isolation, orchestrator integration, file delivery path.

Output **Module Blueprint Table**.

### 6B — Evolution Gaps (genuine gaps found in code AND Phase 3 testing)
- Inference backend abstraction
- Workspace registry threading (is workspace_id passed end-to-end?)
- Orchestrator vs workspace routing interaction (does orchestrator bypass workspace selection?)
- File output path unification (documents → data/generated/, music → ~/AI_Output/, video → ComfyUI URL)
- Async task handling for long inference
- Observability (structured logging coverage)
- GPU stability management
- Systemd / process supervision
- Security hardening (per-workspace ACLs, rate limiting, MCP permissions)

Output **Evolution Gap Register**.

---

## Phase 7 — Production Readiness Score

Rate 1–5 with narrative AND evidence from Phase 3:

| Dimension | Score | Evidence |
|-----------|-------|----------|
| Environment / deps | | Phase 0B results |
| Error handling | | Phase 3C endpoint error responses |
| Security | | Phase 3C auth tests + file traversal |
| Dependency hygiene | | Phase 0B/0C counts |
| Documentation | | Phase 2 drift table |
| Build/deploy | | Phase 3F validation |
| Module boundaries | | Phase 4 heatmap |
| Test coverage | | Phase 5 gap analysis |
| Feature completeness | | Phase 3I behavioral summary |
| Routing correctness | | Phase 3B routing results |
| Orchestrator correctness | | Phase 3A detection accuracy |

**Composite:** X/5 — `CRITICAL` | `NEEDS WORK` | `ACCEPTABLE` | `STRONG` | `PRODUCTION-READY`

---

## Output — Three Artifacts

### ARTIFACT 1: `PORTAL_AUDIT_REPORT.md`

Sections:
1. **Executive Summary** — health score, LOC, top findings, parity risks
2. **Delta Summary** *(delta runs only)*
3. **Baseline Status** — environment, deps, imports, CI state, branches
4. **Behavioral Verification Summary** — Phase 3I report (what works, what doesn't, orchestrator accuracy, file delivery status)
5. **Git History Summary** — commit themes, unfinished work
6. **Public Surface Inventory** — endpoints (including /v1/files), CLI, env vars
7. **File Inventory**
8. **Documentation Drift Report**
9. **Dependency Heatmap**
10. **Code Findings Register** — includes BROKEN_FEATURE, DISCONNECTED_WIRE, OVERLY_AGGRESSIVE from Phase 3
11. **Test Suite Rationalization**
12. **Architecture & Module Blueprint**
13. **Evolution Gap Register**
14. **Production Readiness Score** — with Phase 3 evidence

### ARTIFACT 2: `ACTION_PROMPT_FOR_CODING_AGENT.md`

Includes Session Bootstrap block. On delta runs: only open/new tasks.

**Task list** with entries for EVERY Phase 3 failure (broken features get tasks, not just code quality issues):

```
TASK-[N]
Tier:        [1|2|3]
File(s):     [paths]
Category:    [tag — including BROKEN_FEATURE, DISCONNECTED_WIRE, MISSING_DEP, OVERLY_AGGRESSIVE]
Finding:     [one sentence + Phase 3 evidence reference]
Action:      [specific change]
Risk:        [LOW|MEDIUM|HIGH]
Acceptance:  [runnable test — reference the Phase 3 test that should pass after fix]
```

**Tier 1 now includes broken features and overly aggressive detection:** BROKEN_FEATURE, MISSING_DEP, and OVERLY_AGGRESSIVE go in Tier 1, not just lint/security. A multi-step detection that hijacks normal single-turn prompts is Tier 1. A disconnected wire that makes workspace routing invisible to Open WebUI is Tier 1.

### ARTIFACT 3: `PORTAL_ROADMAP.md`

Same format as before. Phase 3 failures that are design-level issues (not quick fixes) go here as P1/P2 items. Examples:
- File output path unification (music/video/documents all using different output directories) is a design issue
- Orchestrator bypassing workspace routing is a design issue

---

## Begin

Start with Phase -1. Then Phase 0 (build environment, verify every dependency, fix CI). Then Phase 1 (git history). Phase 2 (docs). **Phase 3 (behavioral verification — this is the core phase).** Phase 4 (code audit informed by Phase 3). Phase 5 (tests). Phase 6 (architecture). Phase 7 (score with evidence). Do not produce artifacts until all phases complete.
