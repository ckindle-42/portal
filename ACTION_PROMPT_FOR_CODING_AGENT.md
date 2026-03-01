# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-01
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.4.1 (next release)

---

## Project Context

Portal is a local-first AI platform (Python 3.11 / FastAPI / async).
Source: `src/portal/` (97 Python files, ~15,800 LOC).
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

All Tier 1 tasks from the previous action prompt (TASK-20 through TASK-22) have been completed:
- TASK-20: Updated 13 test files to import directly from rate_limiter and input_sanitizer
- TASK-21: Deleted security_module.py after confirming test imports were updated
- TASK-22: Pruned 10 orphan remote branches

**Current state:** 874 tests passing, 123 mypy errors remaining.

---

## Current Findings

### New This Run

| Category | Count | Notes |
|----------|-------|-------|
| mypy errors | 123 | In lifecycle.py (~8), telegram interface (~10), slack interface (2) |
| runtime_metrics.py | 1 file | Backward compat shim, no production callers |
| Documentation | Minor | CLAUDE.md could reference PORTAL_ROADMAP.md |

---

## Recommended Work

### Tier 1 — Remediation (Critical)

#### TASK-23
```
Tier:        1
File(s):     src/portal/observability/runtime_metrics.py
Symbol(s):   runtime_metrics.py
Category:    DEAD_CODE_CANDIDATE
Finding:     runtime_metrics.py is a backward compatibility shim that re-exports from metrics.py but has no production callers
Action:      Delete src/portal/observability/runtime_metrics.py after verifying no imports exist
Risk:        LOW
Blast Radius: None if verified no callers
Parity:      All production code imports from metrics.py directly
Acceptance:  grep -r "runtime_metrics" src/portal/ returns nothing (except this file itself)
```

---

### Tier 2 — Structural (Optional)

#### TASK-24
```
Tier:        2
File(s):     src/portal/lifecycle.py
Symbol(s):   RuntimeContext, StructuredLogger
Category:    TYPE_SAFETY
Finding:     ~8 mypy errors related to StructuredLogger kwargs and RuntimeContext None checks
Action:      Add type annotations and None guards per mypy output
Risk:        LOW
Blast Radius: Lifecycle only
Parity:      Runtime behavior unchanged
Acceptance:  mypy src/portal/lifecycle.py shows reduced errors
```

#### TASK-25
```
Tier:        2
File(s):     src/portal/interfaces/telegram/interface.py
Symbol(s):   TelegramInterface
Category:    TYPE_SAFETY
Finding:     ~10 remaining mypy errors: User.id, Message.reply_text, process_message args
Action:      Add type annotations and None guards per mypy output
Risk:        LOW
Blast Radius: Telegram interface only
Parity:      Telegram bot behavior unchanged
Acceptance:  mypy src/portal/interfaces/telegram/interface.py shows reduced errors
```

#### TASK-26
```
Tier:        2
File(s):     src/portal/interfaces/slack/interface.py, src/portal/interfaces/slack/__init__.py
Symbol(s):   SlackInterface
Category:    TYPE_SAFETY
Finding:     2 errors: send_message signature incompatible with supertype, __init__ assignment
Action:      Fix send_message return type to match BaseInterface, fix __init__.py assignment
Risk:        LOW
Blast Radius: Slack interface only
Parity:      Slack bot behavior unchanged
Acceptance:  mypy src/portal/interfaces/slack/interface.py shows 0 errors
```

---

### Tier 3 — Hardening (Future)

No Tier 3 tasks currently recommended. The codebase is in strong shape.

---

## CI Gate (run before any changes)

```bash
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
```

Expected output:
- ruff check: 0 violations
- ruff format: 0 violations
- pytest: 874+ PASS, 0 FAIL, 0 ERROR

---

## CI Gate (run after Tier 1 completion)

```bash
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
grep -r "runtime_metrics" src/portal/ | grep -v "__pycache__" | wc -l  # should be 0
```

Expected output:
- ruff check: 0 violations
- ruff format: 0 violations
- pytest: 874+ PASS, 0 FAIL, 0 ERROR
- 0 imports from runtime_metrics in production code

---

## Version Bump (after all tasks complete)

After Tier 1 tasks are complete, bump version:

1. Update `src/portal/__init__.py`: `__version__ = "1.4.1"`
2. Update `pyproject.toml`: `version = "1.4.1"`
3. Update `CHANGELOG.md`: Add `[1.4.1]` section with today's date
4. Commit with: `bump: version to 1.4.1`
