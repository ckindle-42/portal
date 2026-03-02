# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-02 (delta run v16)
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.4.6 (all CI gates already green)

---

## Project Context

Portal is a local-first AI platform (Python 3.11+ / FastAPI / async).
Source: `src/portal/` (100 Python files).
Tests: `tests/` (915 tests currently selected; 914 passing, 1 skipped).

**Non-negotiable constraints:**
- API contract locked: no behavior changes to existing endpoints
- No new features unless explicitly requested
- No cloud dependencies, no external AI frameworks

---

## Prior Work Summary

All previously audited tasks from run 15 are complete:
- **TASK-57**: Fixed `test_all_models_available_by_default` to exempt `huggingface` backend
- **TASK-58**: Fixed mypy error in `server.py:784` with `# type: ignore[assignment]`

**Current state:** 914 tests passing, 0 mypy errors, 0 lint violations. All CI gates green.

---

## Open Tasks

**No open tasks.** Portal 1.4.6 is fully production-ready. All prior regressions have been resolved.

---

## Verification (for reference)

```bash
# Verify environment
source .venv/bin/activate 2>/dev/null || true
python3 -c "import portal; print('portal:', portal.__version__)"

# Verify CI gates (all should pass)
python3 -m ruff check src/ tests/           # expect 0 violations
python3 -m ruff format --check src/ tests/  # expect no changes needed
python3 -m mypy src/portal                  # expect 0 errors
python3 -m pytest tests/ -v --tb=short      # expect 0 FAILED, 914 PASSED, 1 SKIPPED
```

---

## Notes

- No action required — Portal is production-ready
- Phase 3 behavioral verification confirmed all major components work
- All endpoints respond correctly
- This is a verification-only run; no code changes needed
