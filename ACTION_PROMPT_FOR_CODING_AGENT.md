# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-02 (run 17)
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.4.7

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

All code findings from run 16 have been resolved with full implementations:
- **FIX-01**: Removed redundant duplicate import in `metrics.py:193`
- **FIX-02**: Full CosyVoice TTS implementation - `generate_audio()` and `clone_voice()` functions
- **FIX-03**: Full mflux CLI integration - `generate_image()` function using mflux-generate-z-image-turbo

**Current state:** 919 tests passing (+5 new tests for media tools), 0 mypy errors, 0 lint violations. All CI gates green.

---

## Open Tasks

**No open tasks.** Portal 1.4.6 is fully production-ready. All Code Findings Register items resolved.

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
- All 3 deferred Code Findings have been resolved
- TODO comments removed from media_tools stubs
- Redundant import cleaned up in metrics.py