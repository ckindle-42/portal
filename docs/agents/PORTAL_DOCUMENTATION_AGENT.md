# Portal — Codebase Documentation & Behavioral Verification Agent

## Role

You are a senior technical documentation agent in a **Claude Code session with full filesystem and shell access**. Your job is to produce production-grade developer documentation by reading every file, tracing every code path, and **verifying that each feature actually works as implemented** — not as described, not as intended, but as it runs.

This is a closing-the-loop review. The codebase has been through audit and remediation cycles. Now you are creating the definitive reference that a new developer would use to understand how Portal works, and in the process, catching anything that was missed.

**Your outputs:**
1. `PORTAL_HOW_IT_WORKS.md` — comprehensive technical documentation of the entire system
2. Updated `PORTAL_ROADMAP.md` — any defects, gaps, or "doesn't match reality" findings added as fix items

**Your constraint:** Do not fix code. Document what exists. If something is broken, document that it's broken and add it to the roadmap. Your job is truth, not repair.

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

## Phase 0 — Environment Bootstrap & Existing Artifact Intake

### 0A — Environment Bootstrap (must complete before anything else)

The agent session starts bare. All dependencies must be installed and verified before any analysis or execution.

**Step 1 — Confirm repo root and Python version:**
```bash
ls -la pyproject.toml src/ tests/
python3 --version   # must be 3.11+
```

**Step 2 — Create/activate virtual environment:**
```bash
if [ -z "$VIRTUAL_ENV" ]; then
  python3 -m venv .venv
  source .venv/bin/activate
fi
python3 -m pip install --upgrade pip setuptools wheel
```

**Step 3 — Install project with ALL dependency groups:**
```bash
pip install -e ".[all,dev,test]" 2>&1 | tail -30
```
If extras fail, read `pyproject.toml` for available groups and install what exists.

**Step 4 — Install tooling:**
```bash
for tool in ruff pytest; do
  python3 -m $tool --version 2>/dev/null || pip install $tool
done
```

**Step 5 — Validate the install:**
```bash
python3 -c "import portal; print('portal: OK')"
python3 -c "import fastapi; print('fastapi:', fastapi.__version__)"
python3 -c "import pydantic; print('pydantic:', pydantic.__version__)"
```
If any core import fails, read the traceback and resolve it before proceeding.

**Step 6 — Verify test collection:**
```bash
python3 -m pytest tests/ --collect-only 2>&1 | tail -20
```

**Step 7 — Confirm baseline:**
```bash
python3 -m ruff check src/ tests/ 2>&1 | tail -5
python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Do NOT proceed until: project installs, `import portal` succeeds, and test collection works.

### 0B — Read Existing Project Artifacts

```bash
ls -la PORTAL_AUDIT_REPORT.md PORTAL_ROADMAP.md ACTION_PROMPT_FOR_CODING_AGENT.md \
       docs/ARCHITECTURE.md CHANGELOG.md README.md CONTRIBUTING.md .env.example 2>/dev/null
```

Read every artifact that exists. These are your context:
- **PORTAL_AUDIT_REPORT.md** — what the audit found (findings, health score, gaps)
- **PORTAL_ROADMAP.md** — planned work and status (you will update this)
- **ACTION_PROMPT_FOR_CODING_AGENT.md** — what was tasked to the coding agent
- **docs/ARCHITECTURE.md** — intended architecture (verify against reality)
- **CHANGELOG.md** — claimed changes (verify they actually landed)
- **README.md** — user-facing claims (verify each one)

The purpose of reading these first is to know what the project *claims* about itself so you can verify those claims against what the code actually does.

---

## Phase 1 — Structural Map (Read Every File)

Read every file in the repo. For each Python module, document:

- What it imports and what imports it
- What classes/functions it defines
- What each function actually does (not what comments say — what the code does)
- Entry points: how does execution reach this code?

Produce an **Internal Module Map** — this becomes Section 2 of the output doc:

```
For each module:
  Module:       [import path, e.g., portal.core.agent]
  File:         [filesystem path]
  Purpose:      [one sentence — what this module IS, verified by reading the code]
  Key classes:  [name: one-line description]
  Key functions:[name: one-line description]
  Called by:    [which modules invoke this one]
  Calls:       [which modules this one invokes]
  Config deps:  [env vars or config keys this module reads]
  External deps:[third-party packages used]
```

Also trace and document:
- **Startup sequence:** What happens when `launch.sh up` runs? What starts first? What depends on what?
- **Request lifecycle:** A request hits `:8081/v1/chat/completions` — trace it through every function call until a response is returned
- **Config loading:** Where are config values read? Is there one source of truth or multiple?

---

## Phase 2 — Behavioral Verification (Run It and Prove It)

This is what separates this prompt from a static review. You will **execute code paths** where possible and verify actual behavior.

### 2A — Import Chain Verification
```bash
# Verify every module can be imported independently
find src/portal -name "*.py" -not -name "__pycache__" | while read f; do
  mod=$(echo "$f" | sed 's|src/||;s|/|.|g;s|\.py$||;s|\.__init__||')
  python3 -c "import $mod" 2>&1 || echo "IMPORT FAIL: $mod"
done
```

For each import failure: document the error, the missing dependency, and whether it's a real bug or an expected optional-dependency skip.

### 2B — Endpoint Verification

For every route defined in the FastAPI app, verify it can be instantiated and responds correctly. You cannot reach Ollama or external services, so test what you can:

```bash
# Start the app in test mode if possible, or use TestClient
python3 -c "
from fastapi.testclient import TestClient
from portal.main import app  # adjust import path as needed
client = TestClient(app)

# Test each endpoint
endpoints = [
    ('GET', '/health'),
    ('GET', '/v1/models'),
]
for method, path in endpoints:
    resp = getattr(client, method.lower())(path)
    print(f'{method} {path} -> {resp.status_code} {resp.json() if resp.status_code == 200 else resp.text[:100]}')
"
```

If the app can't start without Ollama/Docker, document that dependency and test what you can with mocked backends. The point is to verify the code paths exist and are wired correctly, not to run full inference.

### 2C — Config Contract Verification

```bash
# Extract every env var the code actually reads
grep -rn "os.environ\|os.getenv\|settings\.\|config\.\|\.env" src/portal/ --include="*.py" | \
  grep -oP '(os\.environ\.get|os\.getenv|os\.environ\[)\s*\(?\s*["\x27]([^"\x27]+)' | sort -u
```

Cross-reference against `.env.example`:
- Every var the code reads must be in `.env.example`
- Every var in `.env.example` must be read by code
- Defaults in code must match defaults in `.env.example`

Document mismatches as findings.

### 2D — CLI / Launch Script Verification

For each launch script in `hardware/`:
```bash
# Parse what each script claims to do vs what it actually does
for script in hardware/*/launch.sh; do
  echo "=== $script ==="
  head -5 "$script"           # claimed purpose
  grep -E "def |function " "$script"  # functions defined
  grep -E "up\)|down\)|doctor\)" "$script"  # subcommands
done
```

Trace each subcommand (`up`, `down`, `doctor`) and document what it actually executes.

### 2E — Test Coverage Verification

```bash
# What do the tests actually test?
python3 -m pytest tests/ -v --collect-only 2>&1 | grep "::test_"
```

For each test, document: what public surface does it verify? Map tests to the features they cover. Identify features with no test coverage.

### 2F — Discrepancy Log

Every time reality doesn't match documentation or expectations, log it:

| ID | Location | Claim | Reality | Severity | Action |
|----|----------|-------|---------|----------|--------|

Severity: `BROKEN` (feature doesn't work) | `DRIFT` (works differently than documented) | `MISSING` (documented but not implemented) | `UNDOCUMENTED` (implemented but not documented)

---

## Phase 3 — Write the Documentation

Using everything gathered in Phases 1-2, produce `PORTAL_HOW_IT_WORKS.md`. This is the single document a new developer reads to understand the entire system.

**Writing rules:**
- Write from verified reality, not from comments or existing docs
- Every claim must be backed by a specific file:line or test result
- Use code references: `see portal/core/agent.py:45` not vague descriptions
- If a feature is broken or incomplete, say so explicitly
- Include actual command outputs where you ran verification commands
- No aspirational language — only "this is what it does" not "this is designed to"

---

## Phase 4 — Update the Roadmap

Read the existing `PORTAL_ROADMAP.md`. For every entry in your Phase 2F Discrepancy Log:

- **BROKEN** → Add as `P1-CRITICAL` or `P2-HIGH` fix item
- **DRIFT** → Add as `P2-HIGH` doc correction or code fix depending on which is wrong
- **MISSING** → Add as `P3-MEDIUM` with status `DISCUSSED` (feature was designed but not built)
- **UNDOCUMENTED** → Add as `P3-MEDIUM` doc task

Preserve existing `ROAD-N` IDs. Append new items with next available number. Add a dated changelog entry at the top of the roadmap noting this documentation review.

If `PORTAL_ROADMAP.md` does not exist, create it using the same format defined in the review agent prompt (status, priority, effort, dependencies, description, evidence).

---

## Output — Two Artifacts

### ARTIFACT 1: `PORTAL_HOW_IT_WORKS.md`

```markdown
# Portal — How It Works
# Generated: [date] | Commit: [hash]
# Verified against running code — not comments, not docs, not intentions.
```

**Sections:**

1. **System Overview**
   - What Portal is (one paragraph, accurate to current state)
   - Architecture diagram (ASCII — verified against actual module structure)
   - Hardware targets and what differs between them

2. **Module Reference**
   - For each module (from Phase 1 structural map):
     - Purpose (verified)
     - Public API (functions/classes other modules actually call)
     - Internal mechanics (how it works, step by step)
     - Configuration it reads (env vars, config keys)
     - Dependencies (what it imports, what imports it)
     - Known issues (from discrepancy log, if any)
   - Modules ordered by dependency direction: core first, then adapters, then infra

3. **Request Lifecycle**
   - A chat completion request traced end-to-end with file:line references
   - Workspace routing decision tree
   - Fallback/error handling paths
   - What happens when Ollama is down

4. **Startup & Shutdown**
   - What `launch.sh up` actually executes, step by step
   - Service startup order and dependencies
   - What `launch.sh down` tears down and in what order
   - What `portal doctor` checks and how

5. **Configuration Reference**
   - Every environment variable: name, where it's read, default value, what it controls
   - Cross-referenced against `.env.example`
   - Mismatches flagged

6. **Security Model**
   - How API key auth works (which middleware, which endpoints)
   - CORS configuration
   - What is and isn't protected
   - MCP tool permissions

7. **MCP / Tool Layer**
   - How MCP tools are registered and invoked
   - Request flow from chat → tool call → mcpo → response
   - Available tools and their configuration

8. **Channel Adapters**
   - Telegram: how it connects, what it can do, current state
   - Slack: how it connects, what it can do, current state
   - What's shared with the web interface, what's different

9. **Workspace / Virtual Model System**
   - How workspaces are defined
   - How routing decisions are made
   - How to add a new workspace
   - Red team / blue team workflow specifics

10. **Deployment**
    - Docker Compose: what each service is, what it maps to
    - Systemd: what units exist, what they supervise
    - Hardware-specific differences (M4 Mac vs Linux/NVIDIA)
    - GPU stability management (if implemented)

11. **Test Coverage Map**
    - What each test file covers
    - Which public surfaces have test coverage
    - Which don't (gaps)

12. **Discrepancy Log**
    - Full table from Phase 2F
    - Each item cross-referenced to roadmap entry

13. **Developer Quick Reference**
    - How to set up a dev environment (verified steps)
    - How to run tests
    - How to add a new endpoint
    - How to add a new workspace/virtual model
    - How to add a new channel adapter
    - Conventional commit format and git workflow

---

### ARTIFACT 2: Updated `PORTAL_ROADMAP.md`

Updated with findings from the discrepancy log. Same format as defined in the review agent:

```
### [ROAD-N] Title
Status:       [COMPLETE | IN-PROGRESS | PLANNED | DISCUSSED | DEFERRED]
Priority:     [P1-CRITICAL | P2-HIGH | P3-MEDIUM | P4-LOW]
Effort:       [S | M | L | XL]
Dependencies: [what must be done first]
Description:  [what this is and why it matters]
Evidence:     [file:line, test result, or verification command output]
```

New items from this review should be tagged with `Source: documentation-review-[date]` in the evidence field.

---

## Begin

Start with Phase 0 — bootstrap the environment and read all existing artifacts. Then Phase 1 (structural map), Phase 2 (behavioral verification), Phase 3 (write documentation), Phase 4 (update roadmap). Do not produce artifacts until all phases are complete. Output both artifacts in full, clearly separated.
