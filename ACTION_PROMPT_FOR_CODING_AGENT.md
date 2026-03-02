# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-02 (delta run v4)
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.4.4

---

## Project Context

Portal is a local-first AI platform (Python 3.11 / FastAPI / async).
Source: `src/portal/` (96 Python files, ~15,882 LOC).
Tests: `tests/` (68 Python files, ~13,533 LOC, 874 currently passing).

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
python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2
```

**Branch:** `main` (work directly on main per CLAUDE.md git workflow)
**Commits:** conventional (`fix:`, `refactor:`, `docs:`, `bump:`, `chore:`), one per logical change.

---

## Session Bootstrap — Run Before Any Task

Do not read or modify any source file until this bootstrap completes successfully.

1. Install project and all dependency groups:
   ```bash
   pip install -e ".[all,dev]" 2>&1 | tail -10
   ```
   If install errors remain, resolve them before proceeding.

2. Verify core imports and tooling:
   ```bash
   python3 -c "import portal; print('portal:', portal.__version__)"
   python3 -m ruff --version
   python3 -m pytest --version
   python3 -m mypy --version
   ```

3. Install cffi if telegram test collection fails:
   ```bash
   python3 -m pytest tests/unit/test_telegram_interface.py --collect-only 2>&1 | grep -q "PanicException" && pip install cffi || true
   ```
   The system `cryptography` package requires `cffi` — a missing cffi causes a `pyo3_runtime.PanicException`
   during collection. This is an environment issue, not a code bug.

4. Verify baseline:
   ```bash
   python3 -m ruff check src/ tests/                           # expect 0 violations
   python3 -m pytest tests/ -v --tb=short                      # expect 874+ PASS, 0 FAIL
   python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2  # expect 0 errors
   ```

Environment must be verified before TASK-34 begins.

---

## Prior Work Summary

The prior action prompt (2026-03-02 delta run v3) had TASK-32 and TASK-33.
**All tasks are now COMPLETE** (PR #88, merged 2026-03-02):

- **TASK-32**: Version bumped to 1.4.3; CHANGELOG updated with retroactive TASK-28–31 entries (commit `4a07a7b`)
- **TASK-33**: All 17 remaining mypy errors resolved across 5 files — mypy now reports 0 errors in 96 files (commit `8e1ebaf`)

**mypy progression:** 170 → 124 → 103 → 17 → **0** (over multiple audit cycles — fully clean)

**Current state:** 874 tests passing, 0 mypy errors, 0 lint violations.

---

## Remaining Open Tasks

### Tier 1 — Remediation

#### TASK-34 *(new — CHANGELOG completion and version bump to 1.4.4)*
```
Tier:        1
File(s):     CHANGELOG.md
             src/portal/__init__.py
             pyproject.toml
Symbol(s):   __version__, version
Category:    DOCS
Finding:     The CHANGELOG 1.4.3 entry (added by TASK-32) documents TASK-28–31
             (retroactive — the 103→17 mypy reduction). However, TASK-33 — which
             fixed the remaining 17 errors and brought mypy to 0 — was committed
             INTO 1.4.3 AFTER the CHANGELOG entry was written and is not documented.
             The 1.4.3 metric "mypy errors: 103 → 17" is also misleading; the
             current state after 1.4.3 is 0 errors.
Action:      1. Update src/portal/__init__.py: __version__ = "1.4.4"
             2. Update pyproject.toml: version = "1.4.4"
             3. Add to CHANGELOG.md between the header line and the [1.4.3] entry:

             ## [1.4.4] - 2026-03-02 — TASK-33 Final mypy Clean

             ### Fixed
             - **TASK-33**: Resolved final 17 mypy errors across 5 files:
               - memory/manager.py:37 — Path() coalescing: `os.getenv("PORTAL_MEMORY_DB") or "data/memory.db"`
                 (two-stage `or` prevents `None` from reaching `Path()`)
               - config/settings.py — four fixes:
                 (a) `import yaml  # type: ignore[import-untyped]`
                 (b) All 7 sub-config Field default_factory changed to `lambda: ClassName()`
                     for mypy compatibility with Pydantic v2 Field inference
                 (c) `model_config` changed from `ConfigDict` to `SettingsConfigDict`
                     (correct type for pydantic-settings BaseSettings subclass)
                 (d) `plugins = ["pydantic.mypy"]` added to `[tool.mypy]` in pyproject.toml
               - routing/model_backends.py — abstract `generate_stream` changed from
                 `async def → AsyncGenerator[str, None]` to `def → AsyncIterator[str]`:
                 abstract generators should not be async; `AsyncIterator[str]` is satisfied
                 by the concrete `OllamaBackend.generate_stream` async generator
               - interfaces/web/server.py — two fixes:
                 (a) `uvicorn` import moved under `TYPE_CHECKING` guard (deferred import)
                 (b) `self._server: uvicorn.Server | None = None` explicit type annotation

             ### Metrics
             - mypy errors: 17 → 0 (FULLY CLEAN — 96 source files, 0 errors)
             - Cumulative across audit cycle: 170 → 0

             4. Also correct the 1.4.3 CHANGELOG metrics line from:
                "mypy errors: 103 → 17 (83% reduction across TASK-28–31)"
                to:
                "mypy errors: 103 → 17 (83% reduction across TASK-28–31; see 1.4.4 for final 17→0)"

             5. Commit: `bump: version to 1.4.4`

Risk:        LOW
Blast Radius: Version string in /health response; CHANGELOG only
Parity:      None
Acceptance:  python3 -c "import portal; assert portal.__version__ == '1.4.4'"
             pytest passes (874+ pass, 0 fail)
```

---

### Tier 2 — Structural (Documentation)

#### TASK-35 *(new — ARCHITECTURE.md version drift)*
```
Tier:        2
File(s):     docs/ARCHITECTURE.md
Symbol(s):   Version string at lines 3 and 443
Category:    DOCS
Finding:     docs/ARCHITECTURE.md shows version 1.3.9 in two places:
             - Line 3:   **Version:** 1.3.9
             - Line 443: │   ├── __init__.py             version = "1.3.9"
             Current version is 1.4.4 (after TASK-34) or 1.4.3 if TASK-34 not yet run.
Action:      Update both occurrences to 1.4.4 (or 1.4.3 if running before TASK-34).
             Prefer: run TASK-34 first, then set to 1.4.4 consistently.
             Simple edit — no functional change.
             Commit: `docs(arch): update version string to 1.4.4`
Risk:        NONE
Blast Radius: Documentation only
Parity:      None
Acceptance:  grep "Version" docs/ARCHITECTURE.md  # shows 1.4.4
             grep "version = " docs/ARCHITECTURE.md  # shows 1.4.4
```

---

### Tier 3 — Hardening

No Tier 3 tasks currently. Codebase is in excellent shape.

---

## CI Gate (run before starting)

```bash
python3 -m ruff check src/ tests/                            # 0 violations expected
python3 -m ruff format --check src/ tests/                   # 0 violations expected
python3 -m pytest tests/ -v --tb=short                       # 874+ PASS, 0 FAIL expected
python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2  # 0 errors expected
```

---

## CI Gate (run after Tier 1 completion)

```bash
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
python3 -c "import portal; assert portal.__version__ == '1.4.4', portal.__version__"
python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2  # 0 errors expected
```

---

## CI Gate (run after Tier 2 completion)

```bash
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
grep "1.4.4" docs/ARCHITECTURE.md  # should return 2 matches
```

---

## Execution Order

1. **TASK-34** — version bump to 1.4.4, complete CHANGELOG with TASK-33 entry. Run CI after.
2. **TASK-35** — update ARCHITECTURE.md version string. Run CI after.
3. Final: full test suite green, mypy 0 errors, docs consistent.
