# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-02 (delta run v8 — documentation cleanup)
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.4.5 (no code changes; docs only)

---

## Project Context

Portal is a local-first AI platform (Python 3.11+ / FastAPI / async).
Source: `src/portal/` (97 Python files, ~16,095 LOC).
Tests: `tests/` (69 Python files, ~13,724 LOC, 890 currently passing).

**Non-negotiable constraints:**
- API contract locked: no behavior changes to existing endpoints
- No new features unless explicitly requested
- No cloud dependencies, no external AI frameworks
- Regex fallback must always be preserved (LLM classifier unavailability is expected)

---

## Session Bootstrap — Run Before Any Task

Do not read or modify any source file until this bootstrap completes successfully.

1. Activate or create the virtual environment:
   ```bash
   if [ -d .venv ]; then
     source .venv/bin/activate
   else
     python3 -m venv .venv && source .venv/bin/activate
     pip install --upgrade pip setuptools wheel
   fi
   ```

2. Install project and all dependency groups:
   ```bash
   pip install -e ".[all,dev]" 2>&1 | tail -10
   ```

3. Verify core imports and tooling:
   ```bash
   python3 -c "import portal; print('portal:', portal.__version__)"
   python3 -m ruff --version
   python3 -m pytest --version
   python3 -m mypy --version
   ```

4. Verify tests can be collected:
   ```bash
   python3 -m pytest tests/ --collect-only 2>&1 | tail -5
   ```

5. Run baseline verification:
   ```bash
   python3 -m ruff check src/ tests/        # expect 0 violations
   python3 -m pytest tests/ -v --tb=short   # expect 890 PASS
   python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2  # expect 0 errors
   ```

---

## Prior Work Summary

All tasks through TASK-47 are COMPLETE. ROAD-P01 is fully implemented.

- TASK-36 through TASK-40 (lint, mypy, tests, ROUTING_LLM_MODEL, proxy router async): **COMPLETE**
- TASK-41 (IntelligentRouter.route() async + LLMClassifier): **COMPLETE** (commit 620d0a4)
- TASK-42 (router_rules.json classifier block): **COMPLETE**
- TASK-43 (version 1.4.5 + CHANGELOG): **COMPLETE**
- TASK-44 (pyproject.toml version sync): **COMPLETE** (commit b6f0671)
- TASK-45 (ARCHITECTURE.md version sync): **COMPLETE** (commit b6f0671)
- TASK-46 (stream_classify dead code removal): **COMPLETE** (commit fa8e5ae)
- TASK-47 (router.py → create_classifier()): **COMPLETE** (commit 4ac58c8)

**Current state:** 890 tests passing, 0 mypy errors, 0 lint violations.
All production paths use dual LLMClassifier + TaskClassifier routing.
Remaining work is documentation cleanup only.

---

## Open Tasks

### TASK-48
```
Tier:        1
File(s):     docs/ARCHITECTURE.md
Symbol(s):   Lines 142, 144, 149
Category:    DOCS
Finding:     ARCHITECTURE.md describes both routing paths using only regex/TaskClassifier,
             which was accurate before TASK-40 and TASK-41. Now:
             - Proxy Router (line 142): uses LLMClassifier as primary, regex as fallback
             - IntelligentRouter (line 144): uses dual LLMClassifier + TaskClassifier
             - Line 149: "Future unification is a Track B opportunity" — ROAD-P01 is complete

Action:      1. Line 142: change
               "regex-based model selection via router_rules.json"
               → "LLM classifier (qwen2.5:0.5b via router_rules.json) with regex fallback"
             2. Line 144: change
               "uses TaskClassifier (100+ regex patterns) to classify task complexity and category"
               → "uses dual classification: LLMClassifier (async Ollama call) for category
                  plus TaskClassifier (regex) for complexity metadata"
             3. Line 149: remove or update
               "Future unification is a Track B opportunity (see ROADMAP.md for LLM-based
               Intelligent Routing)."
               → "LLM-based routing is now complete in both paths (see ROAD-P01 in PORTAL_ROADMAP.md)."

Risk:        NONE (docs only)
Blast Radius: docs/ARCHITECTURE.md only
Parity:      No code change
Acceptance:  grep -n "TaskClassifier (100+ regex\|Track B opportunity" docs/ARCHITECTURE.md → no output
             grep -n "LLMClassifier\|llm_classifier\|dual classification" docs/ARCHITECTURE.md → matches
```

---

### TASK-49
```
Tier:        1
File(s):     CHANGELOG.md
Symbol(s):   [1.4.5] section
Category:    DOCS
Finding:     The [1.4.5] section was written before PR #96 merged. It describes only the
             initial LLMClassifier module (commit f6ed8dd) and proxy router integration.
             PR #96 (commits b6f0671, fa8e5ae, 4ac58c8, 620d0a4, 0038dc5) added:
             - IntelligentRouter.route() made async with dual classification (TASK-41)
             - pyproject.toml version sync (TASK-44)
             - docs/ARCHITECTURE.md version sync (TASK-45)
             - stream_classify() dead code removed (TASK-46)
             - router.py changed to use create_classifier() (TASK-47)
             None of these appear in the changelog.

Action:      Append a "### Also in 1.4.5 (PR #96)" subsection to the [1.4.5] entry:

             ### Also in 1.4.5 (PR #96)
             - IntelligentRouter.route() made async; dual LLMClassifier + TaskClassifier
               classification for all AgentCore chat requests (TASK-41)
             - router.py changed to use create_classifier() — ROUTING_LLM_MODEL env var
               now respected (TASK-47)
             - stream_classify() dead code and AsyncIterator import removed from
               llm_classifier.py (TASK-46)
             - Version 1.4.5 synced in pyproject.toml and docs/ARCHITECTURE.md (TASK-44, TASK-45)

Risk:        NONE (docs only)
Blast Radius: CHANGELOG.md only
Parity:      No code change
Acceptance:  grep "TASK-41\|IntelligentRouter.*async" CHANGELOG.md → matches in [1.4.5] section
```

---

### TASK-50
```
Tier:        1
File(s):     ROADMAP.md
Symbol(s):   Line 10 (Status field, Item 1)
Category:    DOCS
Finding:     ROADMAP.md Item 1 "LLM-Based Intelligent Routing" shows Status: Planned.
             This feature is now fully complete in both routing paths.
Action:      Change line 10:
               Status: Planned
               → Status: Complete (both proxy router and IntelligentRouter — as of 2026-03-02)
Risk:        NONE (docs only)
Blast Radius: ROADMAP.md only
Parity:      No code change
Acceptance:  grep "Status:" ROADMAP.md | head -1 → "Status: Complete"
```

---

### TASK-51
```
Tier:        1
File(s):     .env.example
Symbol(s):   N/A (additions only)
Category:    CONFIG_HARDENING
Finding:     12 env vars are read via os.getenv() in production code but have no entry
             (even commented-out) in .env.example. A new operator cannot discover them
             without reading source code.

             Vars absent from .env.example (with their source locations):
             - REDIS_URL            → agent_core.py:94, middleware/hitl_approval.py:34
             - MEM0_API_KEY         → memory/manager.py:55
             - PORTAL_AUTH_DB       → security/auth/user_store.py:24
             - PORTAL_BOOTSTRAP_USER_ID → security/auth/user_store.py:124
             - PORTAL_BOOTSTRAP_USER_ROLE → security/auth/user_store.py:125
             - RATE_LIMIT_DATA_DIR  → security/rate_limiter.py:28
             - PORTAL_VRAM_USAGE_MB → observability/metrics.py:245
             - PORTAL_UNIFIED_MEMORY_USAGE_MB → observability/metrics.py:246
             - PORTAL_ENV           → lifecycle.py:131
             - TELEGRAM_USER_ID     → interfaces/telegram/interface.py:120 (legacy singular)
             - PORTAL_MEMORY_DB     → memory/manager.py:37
             - PORTAL_MEMORY_PROVIDER → memory/manager.py:39

Action:      Add a commented-out section to .env.example for advanced/optional vars.
             Each entry should include a brief description of what it controls and when to set it.
             Do NOT change defaults in code — only document in .env.example.

             Suggested additions (all commented out, showing defaults):
             # --- Advanced / Internal ---
             # Redis URL for HITL approval state storage (default: redis://localhost:6379/0)
             # REDIS_URL=redis://localhost:6379/0
             # Mem0 cloud API key (optional; only if PORTAL_MEMORY_PROVIDER=mem0cloud)
             # MEM0_API_KEY=
             # Path to Portal auth SQLite DB (default: data/auth.db)
             # PORTAL_AUTH_DB=data/auth.db
             # Bootstrap user identity for first Open WebUI user (default: open-webui)
             # PORTAL_BOOTSTRAP_USER_ID=open-webui
             # Bootstrap user role (default: user)
             # PORTAL_BOOTSTRAP_USER_ROLE=user
             # Directory for rate limit persistence (default: data)
             # RATE_LIMIT_DATA_DIR=data
             # Reported VRAM usage in MB for metrics (default: 0; set externally by GPU monitor)
             # PORTAL_VRAM_USAGE_MB=0
             # Reported unified memory usage in MB for metrics (default: 0)
             # PORTAL_UNIFIED_MEMORY_USAGE_MB=0
             # Runtime environment tag (default: production)
             # PORTAL_ENV=production
             # Legacy singular Telegram user ID (prefer TELEGRAM_USER_IDS for multiple users)
             # TELEGRAM_USER_ID=
             # Path to Portal memory SQLite DB (default: data/memory.db)
             # PORTAL_MEMORY_DB=data/memory.db
             # Memory provider: auto | sqlite | mem0cloud (default: auto)
             # PORTAL_MEMORY_PROVIDER=auto

Risk:        NONE (docs only)
Blast Radius: .env.example only
Parity:      No code change; no default changes
Acceptance:  grep "REDIS_URL\|MEM0_API_KEY\|PORTAL_AUTH_DB\|PORTAL_ENV" .env.example → matches
```

---

### TASK-52
```
Tier:        1
File(s):     local git state
Symbol(s):   master branch
Category:    BRANCH
Finding:     A local `master` branch exists with 0 unique commits vs origin/main.
             It is a stale orphan from the initial repo setup.
Action:      Delete the local stale branch:
               git branch -d master
Risk:        NONE — 0 unique commits; fully merged
Blast Radius: Local git state only; no remote impact
Parity:      N/A
Acceptance:  git branch | grep master → no output
```

---

## CI Gate (run after every task, before starting the next)

```bash
source .venv/bin/activate 2>/dev/null || true
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2
```

## Execution Order

```
TASK-52             (branch cleanup — no CI needed, just git)
TASK-48 → TASK-49 → TASK-50  (doc updates — commit together as docs:)
TASK-51             (env.example additions — commit as docs(config):)
```

All tasks are Tier 1, documentation-only. No CI risk. Commit with `docs:` prefix.
Work on main per CLAUDE.md git policy.
