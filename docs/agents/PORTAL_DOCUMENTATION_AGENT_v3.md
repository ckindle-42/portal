# Portal — Codebase Documentation & Behavioral Verification Agent

## Role

You are a senior technical documentation agent in a **Claude Code session with full filesystem and shell access**. Your job is to produce production-grade developer documentation by **building, running, and testing every component** — then documenting what actually happened, not what was supposed to happen.

**You are a QA engineer who writes docs, not a doc writer who reads code.**

Every claim in the output documentation must be backed by a command you ran and its output. If you can't prove it works, document that you can't prove it works and why.

**Your outputs:**
1. `PORTAL_HOW_IT_WORKS.md` — comprehensive technical documentation verified against running code
2. Updated `PORTAL_ROADMAP.md` — every defect, missing dependency, broken feature, or gap added as a fix item
3. `VERIFICATION_LOG.md` — raw log of every test you ran, every command output, every pass/fail

**Your constraint:** Do not fix code. Do not modify source files. Document what exists. If something is broken, document that it's broken, capture the exact error, and add it to the roadmap. Your job is truth, not repair.

---

## What Portal Is

Portal is a **local-first AI platform** (Python 3.11 / FastAPI / async). Self-hosted inference routing for a single owner on Apple M4 Pro and Linux/NVIDIA RTX 5090.

| Fact | Detail |
|------|--------|
| Entry point | `src/portal/`, launched via `hardware/<target>/launch.sh` |
| Public surface | OpenAI-compatible REST API on `:8081/v1/*` (Open WebUI, LibreChat). Health/routing on `:8000` |
| Inference | Ollama (local), wrapped in OpenAI-compatible shim |
| Tools | MCP via `mcpo`, surfaced through `mcp/` directory |
| Deploy | Docker Compose per hardware target under `hardware/`; systemd for bare-metal; `portal doctor` CLI |
| Security | Localhost-only. API key auth (`WEB_API_KEY`, `MCP_API_KEY`). CORS locked to `localhost:8080` |
| Workspaces | Virtual models (personas) in config, routed through `AgentCore`. Red/blue team workflows first-class |
| Channels | Telegram/Slack as optional push-notification sidecars |
| Lineage | Forked from PocketPortal (Telegram-first). Legacy assumptions may persist |

---

## Phase 0 — Full Environment Build & Dependency Verification

This phase doesn't just install — it verifies every dependency, documents what's missing, and proves the project can actually run.

### 0A — Repository & Python
```bash
ls -la pyproject.toml src/ tests/
python3 --version
git log --oneline -5
```

### 0B — Virtual Environment & Install
```bash
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
pip install -e ".[all,dev,test]" 2>&1 | tee /tmp/portal_install.log
grep -iE "error|failed|not found|no matching|conflict" /tmp/portal_install.log || echo "CLEAN INSTALL"
```
If install fails, try each extra individually and document which succeed/fail with exact errors.

### 0C — Dependency Completeness Audit

For EVERY package in `pyproject.toml`, verify it actually imports. Write a Python script that reads `pyproject.toml` via `tomllib`, extracts all deps (core + every optional group), maps pip names to import names (e.g., `python-telegram-bot` → `telegram`, `pyyaml` → `yaml`), attempts `importlib.import_module()` on each, and reports OK/MISSING/ERROR counts with exact error messages. Every missing dep is a finding.

### 0D — Portal Module Import Verification

Walk `src/portal/`, attempt `importlib.import_module()` on every `.py` file. Report importable count vs failed count with exact exceptions for every failure. This catches circular imports, missing deps that 0C missed, and broken init chains.

### 0E — Full Test Suite, Lint, Type Check
```bash
python3 -m pytest tests/ -v --tb=long 2>&1 | tee /tmp/portal_tests.log
python3 -m ruff check src/ tests/ 2>&1 | tee /tmp/portal_lint.log
python3 -m mypy src/portal/ --ignore-missing-imports 2>&1 | tee /tmp/portal_mypy.log
```
For EVERY test failure: document which test, exact error, root cause (missing dep, real bug, needs Ollama, test itself broken).

### 0F — Read Existing Project Artifacts

Check existence and read: `PORTAL_AUDIT_REPORT.md`, `PORTAL_ROADMAP.md`, `ACTION_PROMPT_FOR_CODING_AGENT.md`, `docs/ARCHITECTURE.md`, `CHANGELOG.md`, `README.md`, `.env.example`, `CLAUDE.md`, `QUICKSTART.md`, `KNOWN_ISSUES.md`. These are claims to verify in Phase 2.

### 0G — Environment Report
```
ENVIRONMENT REPORT
==================
Python:          3.X.X
Install:         [CLEAN | PARTIAL | FAILED]
Dependencies:    X OK, X missing, X error
Module imports:  X OK, X failed
Tests:           X passed, X failed, X skipped, X error
Lint:            X violations
Type check:      X errors
```

Save all outputs to `/tmp/portal_*.log`.

---

## Phase 1 — Structural Map

Read every file in `src/portal/`. For each module:

```
Module:        [import path]
File:          [path, LOC]
Purpose:       [verified by reading code, not comments]
Classes:       [name: purpose]
Functions:     [name: purpose]
Called by:      [which modules import this]
Calls:         [what this imports]
Config reads:  [env vars / config keys]
Import status: [OK | FAILS — from 0D]
Test coverage: [test files covering this, or NONE]
```

Trace with file:line references:
- **Startup:** `launch.sh up` → uvicorn → app → lifespan → agent_core → router → ready
- **Request lifecycle:** POST `/v1/chat/completions` → every function in the chain to Ollama response
- **Routing paths:** model="auto" vs model="auto-security" vs explicit model name — trace each

---

## Phase 2 — Behavioral Verification (Exercise Every Feature)

### 2A — Component Instantiation Tests

Write and run a Python test script that tries to construct every major class. For each, capture success or exact exception:

- `ModelRegistry()` — loads? How many models? All capabilities valid?
- `TaskClassifier()` — classify test queries: "hello", "write python sort", "exploit kerberos", "generate image", "analyze pros and cons"
- `WorkspaceRegistry(rules)` — loads? Workspaces listed? Each resolves to a model?
- `router_rules.json` — parses? default_model set? All workspace models reference valid entries?
- `IntelligentRouter(registry, workspace_registry=ws)` — constructs?
- `ExecutionEngine(registry, router)` — constructs? What backends?
- `create_app()` from `web/server.py` — FastAPI app builds? What routes?
- `router.app` from `routing/router.py` — proxy app loads? What routes?
- `TelegramInterface` — imports? Constructs with mock config?
- `SlackInterface` — imports? Constructs with mock config?
- `SecurityMiddleware` — imports? Constructs?
- `MCPBridge` / MCP protocol — imports?
- Tools `__init__` / `TOOL_REGISTRY` — what's registered? Each importable?
- `CircuitBreaker()` — constructs?
- `HealthChecker` — imports?
- Structured logger `get_logger()` — works?
- Every module in `tools/` — each importable?

### 2B — Routing Chain Verification (async)

Write and run an async Python test that exercises the routing brain:

| Query | workspace_id | Expected behavior |
|-------|-------------|-------------------|
| "hello" | None | default/fast model |
| "write a python sort function" | None | code model |
| "explain step by step" | None | reasoning model |
| "write a creative story" | None | creative model |
| "write a reverse shell exploit" | None | security model if exists |
| "generate an image of sunset" | None | image_gen if exists |
| "clone my voice" | None | audio_gen if exists |
| "hello" | "auto-coding" | workspace model regardless of query |
| "hello" | "auto-security" | workspace model regardless of query |
| "hello" | "auto-fast" | fast workspace model |
| "hello" | "nonexistent-workspace" | fall through to default |

For each: capture model selected, reasoning, category, fallback chain. Flag unexpected results.

**Critical verification:** Does `incoming.model` from Open WebUI actually reach `router.route(workspace_id=...)`? Trace `server.py _handle_chat_completions` → `agent_core.stream_response` → `execution_engine.generate_stream` → `router.route()`. Document whether `workspace_id` is threaded through or dropped. If dropped, this is a `BROKEN` finding.

### 2C — Endpoint Verification via TestClient

Write and run a Python test that hits EVERY endpoint on BOTH FastAPI apps using `TestClient`:

**Portal Web API (`:8081`):**
- GET `/health` → 200?
- GET `/health/live` → 200?
- GET `/health/ready` → 200?
- GET `/v1/models` → 200? Contains models? Contains workspace names?
- GET `/metrics` → 200?
- POST `/v1/chat/completions` with model="auto" → what happens?
- POST `/v1/chat/completions` with model="auto-security" → routes differently?
- Auth: request without key → expected response? With wrong key → 401?

**Router Proxy (`:8000`):**
- GET `/health` → 200?
- GET `/api/tags` → contains workspace virtual models?
- POST `/api/dry-run` with code query → correct routing?
- POST `/api/dry-run` with security query → correct routing?
- POST `/api/dry-run` with workspace model → workspace routing?

Capture every status code and response body. Document mismatches.

### 2D — Configuration Contract Verification

Write and run a Python script that:
1. Extracts every `os.getenv`/`os.environ` call from source with file:line
2. Cross-references against `.env.example`
3. Flags: vars in code not in .env.example, vars in .env.example not in code, vars with no default (crash if unset)

### 2E — Docker & Launch Script Verification
```bash
# Validate YAML
for f in docker-compose.yml docker-compose.override.yml; do
    [ -f "$f" ] && python3 -c "import yaml; yaml.safe_load(open('$f')); print('$f: VALID')" || echo "$f: ERROR"
done
# Validate bash syntax
for script in hardware/*/launch.sh launch.sh; do
    [ -f "$script" ] && bash -n "$script" && echo "$script: OK" || echo "$script: ERROR"
done
# Document subcommands and services per script
```

### 2F — Test Coverage Mapping
```bash
python3 -m pytest tests/ -v --collect-only 2>&1 | grep "::test_"
```
Map each test to the feature it covers. List features with ZERO coverage.

### 2G — Discrepancy Log

| ID | Phase | Location | Expected | Reality | Severity | Evidence |
|----|-------|----------|----------|---------|----------|----------|

**Severity:** `BROKEN` | `DEGRADED` | `DRIFT` | `MISSING_DEP` | `MISSING_FEATURE` | `UNDOCUMENTED` | `TEST_GAP`

**Evidence = command output or file:line. Never "I think."**

---

## Phase 3 — Feature Catalog & Usage Guide (Exercise Every Capability)

Phase 2 proved what constructs and what responds. This phase documents **how a real user operates every feature**, across every interface, with actual input/output examples. For each capability, answer: What is it? How do you invoke it? What do you send? What comes back? Which interfaces support it? What model handles it?

**Method:** For features that can run without Ollama (routing decisions, tool registration, endpoint responses), run them and capture real output. For features that require a running LLM (actual inference, music gen, image gen), trace the code path, document the expected invocation, and mark as `UNTESTABLE (needs running service)` with the exact API call a user would make.

### 3A — Workspace Personas (the model dropdown)

For every workspace defined in `router_rules.json`, document:

```
Workspace: auto-security
  Select in UI:  Choose "auto-security" from Open WebUI model dropdown
  Routes to:     xploiter/the-xploiter (verify via dry-run or routing test)
  Fallbacks:     [list from rules]
  Use case:      Red team — exploits, shellcode, pentesting, CVE analysis
  Example prompt: "Write a Kerberoasting attack chain for an AD environment"
  Expected:      Response from The-Xploiter, no refusals
  Also works via: curl, Telegram (@model:auto-security), Slack
  Status:        [VERIFIED via Phase 2B | BROKEN — workspace_id not threaded]
```

Do this for EVERY workspace: auto, auto-coding, auto-security, auto-creative, auto-multimodal, auto-fast, auto-reasoning, and any others found in the config.

**Verify via dry-run or routing test that each workspace actually resolves to its target model.** If routing is broken (workspace_id dropped), document exactly where the wire is cut.

### 3B — Intelligent Routing (the auto-classification brain)

Document how automatic routing works when user selects "auto" or doesn't select a model:

```
Feature: Automatic query classification
  Trigger:     User selects "auto" or sends message without model selection
  How it works: LLMClassifier (if Ollama available) or TaskClassifier (regex fallback)
  Categories:  [list every TaskCategory and what triggers each]

  Example routing decisions (from Phase 2B results):
    "write a python function"     → [model] (category: code)
    "explain step by step"        → [model] (category: reasoning)
    "write a reverse shell"       → [model] (category: security)
    "generate an image of sunset" → [model] (category: image_gen)

  Manual override: Type "@model:dolphin-llama3:70b" in your message
  Status: [VERIFIED | PARTIAL | BROKEN]
```

### 3C — Chat Interface (Open WebUI / LibreChat)

Document the primary user experience:

```
Feature: Web chat via Open WebUI
  URL:         http://localhost:8080 (via Caddy) or http://localhost:8081/v1 (direct)
  Setup:       Point Open WebUI's "OpenAI API Base URL" to http://localhost:8081/v1
  API key:     Value of WEB_API_KEY from .env (or empty if auth disabled)

  Available models in dropdown: [list what /v1/models returns — from Phase 2C]
  Do workspace names appear? [YES/NO — critical finding from Phase 2C]

  How to chat:
    1. Select model from dropdown (e.g., "auto-security")
    2. Type message
    3. Response streams back via SSE

  Streaming: POST /v1/chat/completions with stream=true
  Non-streaming: POST /v1/chat/completions with stream=false

  Example curl (streaming):
    curl http://localhost:8081/v1/chat/completions \
      -H "Authorization: Bearer $WEB_API_KEY" \
      -H "Content-Type: application/json" \
      -d '{"model":"auto-security","messages":[{"role":"user","content":"explain kerberoasting"}],"stream":true}'

  Expected response format: SSE chunks with data: {JSON}\n\n, ending with data: [DONE]
  Status: [VERIFIED via TestClient | UNTESTABLE needs Ollama for actual response]
```

### 3D — Telegram Bot

Read `src/portal/interfaces/telegram/` and document:

```
Feature: Telegram bot interface
  Setup:       Set TELEGRAM_BOT_TOKEN in .env, enable in config
  How to start: Launches automatically with portal if configured
  Bot commands: [list every command handler found in the code — /start, /help, etc.]
  Message flow: User sends message → TelegramInterface → AgentCore → response → Telegram reply

  How to select a model:  [does it support @model: override? workspace selection?]
  How to use tools:       [can Telegram users invoke MCP tools?]
  Rate limiting:          [is per-user rate limiting active?]
  Auth:                   [how are users authenticated? per-user allowlist?]
  HITL (human-in-the-loop): [is tool confirmation middleware active for Telegram?]

  Example interaction:
    User: /start
    Bot: [expected response — read from code]

    User: "write a python function to sort a list"
    Bot: [routes to code model, streams response]

  Dependencies required: python-telegram-bot [version]
  Import status: [OK | FAILS — from Phase 0D]
  Construction status: [OK | FAILS — from Phase 2A]
  Status: [VERIFIED | BROKEN | UNTESTABLE]
```

### 3E — Slack Bot

Read `src/portal/interfaces/slack/` and document:

```
Feature: Slack bot interface
  Setup:       Set SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET in .env
  How to start: Launches with portal if configured
  Event types: [message, app_mention, etc. — read from code]
  Channel whitelist: [is there one? how configured?]

  How to select a model:  [supported?]
  How to use tools:       [supported?]
  Streaming replies:      [does it stream or send complete?]

  Dependencies required: [slack packages]
  Import status: [from Phase 0D]
  Construction status: [from Phase 2A]
  Status: [VERIFIED | BROKEN | UNTESTABLE]
```

### 3F — MCP Tools

Read `src/portal/tools/` and `mcp/` directories. For EVERY tool module, document:

```
Tool: [name from tools/__init__.py or directory name]
  Module:      src/portal/tools/[path]
  Purpose:     [what it does — read the code]
  How invoked: Function calling from LLM / direct MCP call
  Input schema: [parameters the tool accepts]
  Output:      [what it returns]
  Dependencies: [required packages]
  Import status: [OK | FAILS]

  Example invocation (if testable):
    [show function call or MCP request]

  Status: [VERIFIED | STUB | BROKEN | UNTESTABLE]
```

Group tools by category and document each:

**Document Processing:** docx generation, PDF, markdown → what tools exist? Do they import?
**Media Tools:** audio transcription, image generation (mflux), audio generation (CosyVoice) — what's implemented vs stub?
**Dev Tools:** git operations, code analysis — what's available?
**Data Tools:** CSV, data processing — what exists?
**System Tools:** docker, system info — what's available?
**Web Tools:** search, scraping — what works?
**Knowledge Tools:** RAG, embeddings — what's implemented?
**Automation Tools:** scheduled tasks, workflows — what exists?

### 3G — Music / Audio Generation

```
Feature: Music generation
  How to invoke: [via MCP tool? via prompt to specific model? via API call?]
  Tool module:   src/portal/tools/media_tools/audio_generator.py (if exists)
  Backend:       CosyVoice2 / MOSS-TTS / MusicGen (which is configured?)
  Setup required: [what must be installed separately?]
  Example prompt: "Generate a 30-second jazz melody"
  Expected flow:  User prompt → Dolphin (orchestrator) → function call → audio tool → file output
  Output location: ~/AI_Output/audio/ (or wherever configured)
  Output format:  [wav/mp3/etc.]
  Status:         [IMPLEMENTED | STUB | NOT IMPLEMENTED]
```

### 3H — Image Generation

```
Feature: Image generation
  How to invoke: [via MCP tool? via prompt routing?]
  Tool module:   src/portal/tools/media_tools/image_generator.py (if exists)
  Backend:       Flux.2-Dev via mflux (or other)
  Setup required: pip install mflux (separate from portal deps)
  Example prompt: "Generate an image of a medieval castle at sunset"
  Expected flow:  User prompt → Dolphin → function call → mflux CLI → image file
  Output location: ~/AI_Output/images/
  Status:         [IMPLEMENTED | STUB | NOT IMPLEMENTED]
```

### 3I — Voice Cloning / TTS

```
Feature: Voice cloning / text-to-speech
  How to invoke: [tool call? API endpoint?]
  Setup required: [CosyVoice2 installation]
  Example: "Clone this voice and say 'hello world'"
  Status: [IMPLEMENTED | STUB | NOT IMPLEMENTED]
```

### 3J — Red Team / Offensive Security

```
Feature: Red team / offensive security workspace
  Workspace:     auto-security
  Primary model:  xploiter/the-xploiter
  Fallbacks:     [list]
  Capabilities:  Exploit generation, shellcode, AD attack chains, bypass techniques

  Example prompts and expected behavior:
    "Write a reverse shell payload for Windows" → [should generate without refusal]
    "Create a Kerberoasting attack script" → [should generate without refusal]
    "Analyze this CVE and suggest exploitation" → [should provide detailed analysis]

  How to use via Open WebUI: Select "auto-security" from dropdown
  How to use via curl: model="auto-security" in request body
  How to use via Telegram: [if supported — @model:auto-security or command]

  Status: [VERIFIED routing | UNTESTABLE needs Ollama + pulled model]
```

### 3K — Blue Team / Defensive Security

```
Feature: Defensive security / Splunk / SIEM
  Routing trigger: Queries containing splunk, tstats, notable, SIEM keywords
  Routes to:       [model from regex rules]
  Example prompts:
    "Write a Splunk correlation search for brute force detection"
    "Create a YARA rule for detecting mimikatz"
  Status: [VERIFIED routing | UNTESTABLE needs Ollama]
```

### 3L — Coding Specialist

```
Feature: Code generation workspace
  Workspace:     auto-coding
  Primary model:  qwen3-coder-next:30b-q5
  Fallbacks:     [list]
  Example prompts:
    "Write a FastAPI endpoint with auth middleware"
    "Debug this Python function: [code]"
    "Refactor this class to use dependency injection"
  Auto-routing:  Queries with code keywords auto-route to code model even without selecting workspace
  Status: [VERIFIED routing]
```

### 3M — Creative Writing / Stories

```
Feature: Creative writing workspace
  Workspace:     auto-creative
  Primary model:  dolphin-llama3:70b
  Use case:      Stories, roleplay, screenplays, uncensored creative content
  Example prompts:
    "Write a dark fantasy short story about a necromancer"
    "Continue this roleplay scenario: [context]"
  Status: [VERIFIED routing]
```

### 3N — Multimodal (Text + Image + Audio + Video)

```
Feature: Multimodal workspace
  Workspace:     auto-multimodal
  Primary model:  qwen3-omni:30b
  Capabilities:  Native text/image/audio/video understanding
  How to send images: [multimodal content blocks in messages array — does it work?]
  Status: [VERIFIED routing | UNTESTABLE needs model pulled]
```

### 3O — Observability & Metrics

```
Feature: Prometheus metrics
  Endpoint:    GET /metrics on :8081
  What's tracked: [list every metric — request counts, token throughput, latency, etc.]
  How to scrape: Point Prometheus at http://localhost:8081/metrics
  Dashboard:   GET /dashboard on :8081
  Status:      [VERIFIED — show actual /metrics output]

Feature: Health checks
  Endpoints:   /health, /health/live, /health/ready
  What each checks: [read code, document]
  Status:      [VERIFIED — show actual response]

Feature: Structured logging
  Format:      [JSON with trace IDs? plain text?]
  Log location: [stdout? file? configurable?]
  Secret redaction: [does it redact API keys from logs?]
  Status:      [VERIFIED — show log output sample]
```

### 3P — Portal Doctor / CLI

```
Feature: portal doctor
  How to invoke: bash hardware/m4-mac/launch.sh doctor (or equivalent)
  What it checks: [Ollama, router, web API, MCP, etc.]
  Expected output: [document the format]
  Status: [VERIFIED — show output if possible, or document what the script does]
```

### 3Q — Manual Model Override

```
Feature: @model: override
  How to use:  Type "@model:dolphin-llama3:70b explain quantum computing" in any message
  Where it works: [Open WebUI? Telegram? Slack? All?]
  How it's parsed: [router.py _extract_user_text + resolve_model — show code path]
  Status: [VERIFIED via dry-run or routing test]
```

### 3R — Feature Status Matrix

Compile everything into a single table:

| Feature | Interface | How to Use | Model/Tool | Status | Evidence |
|---------|-----------|-----------|------------|--------|----------|
| Chat (general) | Web, Telegram, Slack | Send message | auto → dolphin-8b | VERIFIED | Phase 2C |
| Code generation | Web | Select auto-coding | qwen3-coder | VERIFIED | Phase 2B |
| Security/Red team | Web | Select auto-security | the-xploiter | VERIFIED routing | Phase 2B |
| Blue team/Splunk | Web | Keyword trigger | tongyi-deepresearch | VERIFIED routing | Phase 2B |
| Creative writing | Web | Select auto-creative | dolphin-70b | VERIFIED routing | Phase 2B |
| Image generation | Web | Prompt "generate image" | mflux tool | STUB | 3H |
| Music generation | Web | Prompt "generate music" | audio tool | NOT IMPLEMENTED | 3G |
| Voice cloning | Web | Prompt "clone voice" | CosyVoice tool | NOT IMPLEMENTED | 3I |
| TTS | Web | Prompt "read this aloud" | TTS tool | NOT IMPLEMENTED | 3I |
| Multimodal | Web | Select auto-multimodal | qwen3-omni | VERIFIED routing | Phase 2B |
| Telegram bot | Telegram | /start, send message | configurable | [status] | 3D |
| Slack bot | Slack | @mention or message | configurable | [status] | 3E |
| MCP tools | Web (function calling) | LLM invokes via tool_call | various | [status] | 3F |
| Metrics | HTTP | GET /metrics | prometheus | VERIFIED | 3O |
| Health checks | HTTP | GET /health | n/a | VERIFIED | 3O |
| Manual override | Any | @model:name in message | specified | [status] | 3Q |
| Portal doctor | CLI | launch.sh doctor | n/a | [status] | 3P |
| Document gen | Web (tool) | Prompt "create a report" | docgen tool | [status] | 3F |
| Web search | Web (tool) | Prompt "search for X" | web tool | [status] | 3F |
| RAG/knowledge | Web | Upload + query | embeddings | [status] | 3F |

For every row: fill in the real status from your testing. STUB means code exists but isn't functional. NOT IMPLEMENTED means no code exists. BROKEN means code exists but crashes.

---

## Phase 4 — Write the Documentation

Produce `PORTAL_HOW_IT_WORKS.md` from verified results.

**Rules:**
- Every claim backed by command output or file:line
- Status tags: `**VERIFIED**`, `**BROKEN**`, `**DEGRADED**`, `**STUB**`, `**NOT IMPLEMENTED**`, `**UNTESTABLE** (needs Ollama)`
- Include command outputs as evidence
- No aspirational language

**Sections:**
1. System Overview — verified architecture, health summary
2. Module Reference — every module with verified status
3. Request Lifecycle — traced with file:line, TestClient evidence
4. Routing System — classification proven, workspace routing proven, fallbacks proven
5. **Feature Catalog & Usage Guide** — the Phase 3 feature matrix, expanded into a full user manual section with examples, inputs/outputs, and status for every feature
6. **Interface Guide** — how to use each interface (Open WebUI, Telegram, Slack, curl) with setup steps and examples
7. Startup & Shutdown — scripts traced, Docker mapped
8. Configuration Reference — every env var, source, default, .env.example status
9. Security Model — auth tested, CORS verified
10. MCP / Tool Layer — every tool documented with schema, status, and example
11. Workspace / Virtual Model System — every workspace resolution proven, usage examples
12. Deployment — Docker, systemd, hardware differences
13. Observability — metrics, health checks, logging, portal doctor
14. Test Coverage Map — covered vs uncovered features
15. Known Issues & Discrepancy Log — full Phase 2G table
16. Developer Quick Reference — verified setup, test, extend instructions

---

## Phase 5 — Update the Roadmap

For every Phase 2G discrepancy AND every Phase 3 feature with status BROKEN, STUB, or NOT IMPLEMENTED:
- `BROKEN` / `MISSING_DEP` → `P1-CRITICAL`
- `DEGRADED` / `DRIFT` → `P2-HIGH`
- `STUB` (code exists, not functional) → `P2-HIGH` with effort estimate
- `NOT IMPLEMENTED` (no code) → `P3-MEDIUM` with status `PLANNED`
- `MISSING_FEATURE` / `UNDOCUMENTED` / `TEST_GAP` → `P3-MEDIUM`

Preserve existing `ROAD-N` IDs. Add dated changelog. Tag: `Source: doc-verification-[date]`.

---

## Phase 6 — Produce Verification Log

Output `VERIFICATION_LOG.md` — raw evidence:
- Environment Build (full install log)
- Dependency Audit (full output)
- Module Import Audit (full output)
- Test Suite Results (full pytest output)
- Component Instantiation (full 2A output)
- Routing Verification (full 2B output)
- Endpoint Verification (full 2C output)
- Config Audit (full 2D output)
- Launch Script Validation (full 2E output)
- Test Coverage Map (full 2F output)
- Feature Catalog Testing (full Phase 3 results — every feature's status evidence)
- Feature Status Matrix (the Phase 3R table with all statuses filled in)

---

## Output — Three Artifacts

1. **`PORTAL_HOW_IT_WORKS.md`** — polished docs, every claim verified
2. **`PORTAL_ROADMAP.md`** — updated with all findings
3. **`VERIFICATION_LOG.md`** — raw test evidence

---

## Begin

Start with Phase 0. Run every command. Capture every output. If a step fails, document the failure and continue. Proceed through all phases in order: Phase 0 (environment) → Phase 1 (structural map) → Phase 2 (behavioral verification) → **Phase 3 (feature catalog — exercise every capability)** → Phase 4 (write documentation) → Phase 5 (update roadmap) → Phase 6 (verification log). Do not produce artifacts until all phases complete. Output all three artifacts in full, clearly separated.
