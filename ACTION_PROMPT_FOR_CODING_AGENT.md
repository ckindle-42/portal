# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-02 (run 24)
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.5.0

---

## Project Context

Portal is a local-first AI platform (Python 3.11+ / FastAPI / async).
Source: `src/portal/` (100+ Python modules).
Tests: `tests/` (986 tests passing, 13 skipped).

**Non-negotiable constraints:**
- API contract locked: no behavior changes to existing endpoints
- No new features unless explicitly requested
- No cloud dependencies, no external AI frameworks

---

## Prior Work Summary

All deferred items have been resolved:
- **ROAD-FIX-01 (RESOLVED)**: Metrics module import failure - now imports cleanly

**Current state:** 986 tests passing, 0 mypy errors, 0 lint violations. All CI gates green. Health score 10/10.

---

## Open Tasks

**No open tasks.** Portal 1.5.0 is fully production-ready.

---

## Session Bootstrap

```bash
# Verify environment
cd /Users/chris/portal
source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev,test]" -q

# Verify CI gates (all should pass)
python3 -m ruff check src/ tests/           # expect 0 violations
python3 -m ruff format --check src/ tests/  # expect no changes needed
python3 -m mypy src/portal                  # expect 0 errors
python3 -m pytest tests/ -v --tb=short      # expect 986 PASSED, 13 SKIPPED
```

---

## Notes

- No action required — Portal is production-ready
- All Code Findings Register items resolved
- ROAD-FIX-01 fixed in prior commits (metrics import now works)
- Health score: 10/10 — FULLY PRODUCTION-READY
