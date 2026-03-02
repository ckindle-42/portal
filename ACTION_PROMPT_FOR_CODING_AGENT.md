# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-02 (delta run v11)
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.4.5 (all tasks complete)

---

## Project Context

Portal is a local-first AI platform (Python 3.11+ / FastAPI / async).
Source: `src/portal/` (97 Python files, ~16,100 LOC).
Tests: `tests/` (69 Python files, 914 currently passing).

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
   python3 -m pytest tests/ -v --tb=short   # expect 914 PASS
   python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2  # expect 0 errors
   ```

---

## Prior Work Summary

All tasks are COMPLETE:
- TASK-53: K8s health probes wired (commit 94ae694)
- TASK-54: Metrics port corrected to :8081 (commit 94ae694)
- TASK-55: MLX env vars added to .env.example (commit 94ae694)
- TASK-56: Knowledge base env vars added to .env.example (commit 94ae694)

**Current state:** 914 tests passing, 0 mypy errors, 0 lint violations.

**There are no open tasks. Portal is fully production-ready.**

---

## Open Tasks

**NONE** — All tasks complete. Portal 1.4.5 is fully production-ready with zero open findings.

---

## CI Gate (run before any task)

```bash
source .venv/bin/activate 2>/dev/null || true
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2
```

---

## Execution

No tasks to execute. The codebase is complete and ready for production use.
