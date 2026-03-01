# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-01
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.4.0 (next release)

---

## Project Context

Portal is a local-first AI platform (Python 3.11 / FastAPI / async).
Source: `src/portal/` (98 Python files, ~15,800 LOC).
Tests: `tests/` (67 Python files, ~14,000 LOC, 874 currently passing).

**Non-negotiable constraints:**
- API contract locked: `/v1/chat/completions`, `/v1/models`, `/health`, `/ws`, `/v1/audio/transcriptions` — no behavior changes
- No new features unless explicitly a task below
- No cloud dependencies, no external AI frameworks (LangChain, etc.)
- All behavior must remain identical to pre-task state
- Every task must leave lint and tests green

**CI gate (run before marking any tier complete):**
```bash
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
```

**Branch:** `main` (work directly on main per CLAUDE.md git workflow)
**Commits:** conventional (`fix:`, `refactor:`, `docs:`, `chore:`, `test:`), one per logical change.

---

## Prior Work Summary

All 19 tasks from the previous action prompt (TASK-01 through TASK-19) have been completed:
- Type safety fixes: TextTransformer, TraceContext, BaseInterface, Telegram guards, DockerSandbox, ToolRegistry, WordProcessor
- Config hardening: ContextManager and MemoryManager env reads moved to constructors
- Documentation fixes: ARCHITECTURE.md, .env.example, CONTRIBUTING.md
- Testing: TextTransformer failure tests, Telegram None guard tests added
- Release: Version bumped to 1.3.9, CHANGELOG updated

**Current state:** 874 tests passing, 124 mypy errors remaining (down from 170).

---

## Current Findings

The codebase is in excellent shape. The remaining issues are low-priority type safety improvements:

| Category | Count | Notes |
|----------|-------|-------|
| mypy errors | 124 | In lifecycle.py, telegram interface, agent_core |
| security_module.py shim | 1 file | Still used by middleware.py |

No bugs, security issues, or behavioral defects identified.

---

## Recommended Work (Optional)

If additional improvement is desired, consider:

1. **Continue mypy cleanup** — Reduce errors from 124 to under 30
   - Focus on lifecycle.py (8 errors)
   - Focus on telegram interface (10 errors)
   - Focus on agent_core (5 errors)

2. **Remove security_module.py shim** — Update middleware.py to import directly from rate_limiter and input_sanitizer

These are optional quality improvements, not blockers. The platform is production-ready.

---

## CI Gate (run before any changes)

```bash
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
```

Expected output:
- ruff check: 0 violations
- pytest: 874+ PASS, 0 FAIL, 0 ERROR
