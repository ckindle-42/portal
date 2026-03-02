# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-02 (delta run v10)
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.4.5 (documentation cleanup)

---

## Project Context

Portal is a local-first AI platform (Python 3.11+ / FastAPI / async).
Source: `src/portal/` (97 Python files, ~16,100 LOC).
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

All tasks through TASK-52 are COMPLETE:
- TASK-48 through TASK-52: Documentation updates complete
- MLX Backend: Fully implemented in PR #99
- PR #99 and PR #100 merged to main

**Current state:** 890 tests passing, 0 mypy errors, 0 lint violations.

Remaining open work is documentation cleanup only.

---

## Open Tasks

### TASK-53
```
Tier:        2
File(s):     src/portal/interfaces/web/server.py
Symbol(s):   WebInterface class
Category:    BUG
Finding:     register_health_endpoints() is defined in observability/health.py but never
             called from WebInterface._build_app(). The /health/live and /health/ready
             K8s probe endpoints return 404. The function exists at health.py:125 but
             no code path wires it up.

Action:      In src/portal/interfaces/web/server.py, add a call to register_health_endpoints()
             in the _build_app() method after health checks are configured.

             The call should look something like:
             from portal.observability.health import register_health_endpoints
             # ... in _build_app():
             register_health_endpoints(app, self.health_check_system)

             Or add to the health setup block around line 270-280 where agent_core is configured.

Risk:        MEDIUM — adds new endpoint registration; could conflict with existing /health
Blast Radius: Only affects WebInterface health endpoints
Parity:      Existing /health endpoint behavior preserved; adds /health/live and /health/ready
Acceptance:  Start portal, curl localhost:8081/health/live returns 200 OK
             curl localhost:8081/health/ready returns 200 OK
```

---

### TASK-54
```
Tier:        1
File(s):     docs/ARCHITECTURE.md
Symbol(s):   Line 298
Category:    DOCS
Finding:     Metrics endpoint documented as `:9090/metrics` but actually served on `:8081/metrics`
             (the portal API port, not a separate metrics port).
Action:      Change line 298:
               "`:9090/metrics`"
               → "`:8081/metrics`"

Risk:        NONE (docs only)
Blast Radius: docs/ARCHITECTURE.md only
Parity:      No code change
Acceptance:  grep -n "9090" docs/ARCHITECTURE.md → no output for metrics
```

---

### TASK-55
```
Tier:        1
File(s):     .env.example
Symbol(s):   End of file (additions)
Category:    CONFIG_HARDENING
Finding:     MLX env vars documented in ROADMAP.md (lines 122-128) but not present in .env.example.
             New operators cannot discover MLX configuration without reading the roadmap.

Action:      Add to .env.example (after existing # --- Advanced / Internal --- section):

             # --- MLX Backend (Apple Silicon) ---
             # MLX server port (default: 8800)
             # MLX_SERVER_PORT=8800
             # Default MLX model (default: mlx-community/Qwen2.5-7B-Instruct-4bit)
             # MLX_DEFAULT_MODEL=mlx-community/Qwen2.5-7B-Instruct-4bit

Risk:        NONE (docs only)
Blast Radius: .env.example only
Parity:      No code change
Acceptance:  grep "MLX_SERVER_PORT\|MLX_DEFAULT_MODEL" .env.example → matches
```

---

### TASK-56
```
Tier:        1
File(s):     .env.example
Symbol(s):   End of file (additions)
Category:    CONFIG_HARDENING
Finding:     KNOWLEDGE_BASE_DIR and ALLOW_LEGACY_PICKLE_EMBEDDINGS are used in code
             (knowledge_base_sqlite.py:212, local_knowledge.py:33) but not documented
             in .env.example.

Action:      Add to .env.example:

             # --- Knowledge Base ---
             # Directory for knowledge base data (default: data)
             # KNOWLEDGE_BASE_DIR=data
             # Allow legacy pickle embeddings (default: false)
             # ALLOW_LEGACY_PICKLE_EMBEDDINGS=false

Risk:        NONE (docs only)
Blast Radius: .env.example only
Parity:      No code change
Acceptance:  grep "KNOWLEDGE_BASE_DIR\|ALLOW_LEGACY_PICKLE" .env.example → matches
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
TASK-54 → TASK-55 → TASK-56    (doc updates — commit together as docs:)
TASK-53                       (code change — commit as fix: or feat:)
```

All tasks except TASK-53 are Tier 1 (documentation-only). TASK-53 is Tier 2 (structural/fix).
Commit with appropriate prefixes. Work on main per CLAUDE.md git policy.
