# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-02 (delta run v5)
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.4.5 (if needed)

---

## Project Context

Portal is a local-first AI platform (Python 3.11+ / FastAPI / async).
Source: `src/portal/` (96 Python files, ~15,882 LOC).
Tests: `tests/` (68 Python files, ~13,533 LOC, 874 currently passing).

**Non-negotiable constraints:**
- API contract locked: no behavior changes
- No new features unless explicitly requested
- No cloud dependencies, no external AI frameworks

---

## Session Bootstrap — Run Before Any Task

1. Install project and all dependency groups:
   ```bash
   pip install -e ".[all,dev]" 2>&1 | tail -10
   ```

2. Verify core imports and tooling:
   ```bash
   python3 -c "import portal; print('portal:', portal.__version__)"
   python3 -m ruff --version
   python3 -m pytest --version
   python3 -m mypy --version
   ```

3. Verify baseline:
   ```bash
   python3 -m ruff check src/ tests/                           # expect 0
   python3 -m pytest tests/ -v --tb=short                      # expect 874+ PASS
   python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2  # expect 0
   ```

---

## Prior Work Summary

All tasks from prior runs are COMPLETE:
- TASK-32 (version 1.4.3): COMPLETE
- TASK-33 (mypy 17→0): COMPLETE
- TASK-34 (version 1.4.4 + CHANGELOG): COMPLETE
- TASK-35 (ARCHITECTURE.md version): COMPLETE

**Current state:** 874 tests passing, 0 mypy errors, 0 lint violations, version 1.4.4.

---

## Remaining Open Tasks

### No open tasks

The codebase is fully production-ready. All prior findings have been resolved.

---

## CI Gate (run before starting)

```bash
python3 -m ruff check src/ tests/                            # 0 violations
python3 -m ruff format --check src/ tests/                   # 0 violations
python3 -m pytest tests/ -v --tb=short                       # 874+ PASS, 0 FAIL
python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2  # 0 errors
```

---

## Execution Notes

Portal 1.4.4 is fully production-ready with:
- 0 mypy errors in 96 source files
- 0 lint violations
- 874 tests passing
- Health score 10/10

No remediation tasks required. The codebase is clean.
