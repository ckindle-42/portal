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
- security_module.py shim: middleware.py updated to import directly (tests still use shim)

**Current state:** 874 tests passing, 124 mypy errors remaining.

---

## Current Findings

### New This Run

| Category | Count | Notes |
|----------|-------|-------|
| Orphan remote branches | 11 | 5 AI agent branches + 6 dependabot branches |
| Test import cleanup | 13 files | Still import from security_module.py |
| mypy errors | 124 | In lifecycle.py, telegram interface, agent_core |

---

## Recommended Work

### Tier 1 — Remediation (Critical)

#### TASK-20
```
Tier:        1
File(s):     tests/unit/test_security_middleware.py, tests/unit/test_security.py, tests/unit/test_stream_security.py, tests/unit/test_data_integrity.py, tests/integration/test_websocket.py
Symbol(s):   RateLimiter, InputSanitizer imports
Category:    LEGACY_IMPORT
Finding:     13 test files still import RateLimiter/InputSanitizer from security_module.py shim
Action:      Update all test imports to import directly from portal.security.rate_limiter and portal.security.input_sanitizer
Risk:        LOW
Blast Radius: Tests only - no production impact
Parity:      Test behavior unchanged
Acceptance:  grep -r "from portal.security.security_module" tests/ returns nothing
```

#### TASK-21
```
Tier:        1
File(s):     src/portal/security/security_module.py
Symbol(s):   security_module.py
Category:    DEAD_CODE_CANDIDATE
Finding:     After TASK-20, security_module.py is unused and can be deleted
Action:      Delete src/portal/security/security_module.py after test imports are updated
Risk:        LOW
Blast Radius: None after test cleanup
Parity:      All imports updated to direct modules
Acceptance:  File deleted, tests still pass
```

#### TASK-22
```
Tier:        1
File(s):     remote branches
Symbol(s):   origin/claude/*, origin/codex/*, origin/dependabot/*
Category:    ORPHAN_BRANCH
Finding:     11 orphan remote branches (5 AI agent + 6 dependabot) not merged to main
Action:      Delete all orphan remote branches:
             git push origin --delete fix-code-review-issues-YbiiZ fix-codex-review-issues-in-pr-#17 fix-high-priority-bugs-from-codex-review fix-path-traversal-security-issues perform-comprehensive-code-review-gr3qbw
             git push origin --delete docker_compose/deploy/web-ui/librechat/mongo-8.2 docker_compose/deploy/web-ui/openwebui/caddy-2.11-alpine github_actions/actions/checkout-6 github_actions/actions/setup-python-6 pip/python-telegram-bot-gte-21.0-and-lt-23.0
Risk:        LOW
Blast Radius: Git history only - no production impact
Parity:      No active branches affected
Acceptance:  git branch -r shows only origin/main and origin/HEAD
```

---

### Tier 2 — Structural (Optional)

#### TASK-23
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

#### TASK-24
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

---

## CI Gate (run after Tier 1 completion)

```bash
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
git branch -r | grep -v "origin/main\|origin/HEAD" | wc -l  # should be 0
grep -r "from portal.security.security_module" tests/ | wc -l  # should be 0
```

Expected output:
- ruff check: 0 violations
- pytest: 874+ PASS, 0 FAIL, 0 ERROR
- 0 orphan remote branches
- 0 imports from security_module in tests

---

## Version Bump (after all tasks complete)

After Tier 1 tasks are complete, bump version:

1. Update `src/portal/__init__.py`: `__version__ = "1.4.0"`
2. Update `pyproject.toml`: `version = "1.4.0"`
3. Update `CHANGELOG.md`: Add `[1.4.0]` section with today's date
4. Commit with: `bump: version to 1.4.0`
