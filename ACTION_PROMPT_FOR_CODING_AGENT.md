# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-02 (delta run v3)
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.4.3

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
   ```

3. Install cffi if telegram test collection fails:
   ```bash
   python3 -m pytest tests/unit/test_telegram_interface.py --collect-only 2>&1 | grep -q "PanicException" && pip install cffi || true
   ```
   The system `cryptography` package requires `cffi` — a missing cffi causes a `pyo3_runtime.PanicException`
   during collection. This is an environment issue, not a code bug.

4. Verify baseline:
   ```bash
   python3 -m ruff check src/ tests/    # expect 0 violations
   python3 -m pytest tests/ -v --tb=short  # expect 874+ PASS, 0 FAIL
   python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -3  # expect 17 errors
   ```

Environment must be verified before TASK-32 begins.

---

## Prior Work Summary

The prior action prompt (2026-03-01 delta run v2) had TASK-23R through TASK-31.
**All tasks are now COMPLETE** (PR #86, merged 2026-03-02):

- **TASK-23R**: Migrated runtime_metrics callers → deleted shim (commit `1d872e3`)
- **TASK-27**: Version bump to 1.4.2 (commit `5482c09`) — PARTIAL: CHANGELOG incomplete, see TASK-32
- **TASK-28**: Core module mypy fixes — 5 errors resolved (commit `cd4d12c`)
- **TASK-29**: Security/middleware mypy fixes — 13 errors resolved (commit `ba3d1b2`)
- **TASK-30**: Observability mypy fixes — 23 errors resolved (commit `b434d3c`)
- **TASK-31**: Tools layer mypy batch fix — 45+ errors resolved (commits `17019f1`, `16a08ae`)

**mypy progression:** 170 → 124 → 103 → **17** (over multiple audit cycles)

**Current state:** 874 tests passing, 17 mypy errors remaining (in 5 files).

---

## Remaining Open Tasks

### Tier 1 — Remediation

#### TASK-32 *(new — version bump and CHANGELOG completeness)*
```
Tier:        1
File(s):     src/portal/__init__.py
             pyproject.toml
             CHANGELOG.md
Symbol(s):   __version__, version
Category:    DOCS
Finding:     The 1.4.2 CHANGELOG entry only covers the aiohttp dependency fix
             and TASK-23R (runtime_metrics removal). TASK-27 through TASK-31 —
             which resolved 86+ mypy errors across 6 files — are not documented.
             The version bump to 1.4.2 was tagged BEFORE these commits were made.
Action:      1. Update src/portal/__init__.py: __version__ = "1.4.3"
             2. Update pyproject.toml: version = "1.4.3"
             3. Add to CHANGELOG.md at the top:

             ## [1.4.3] - 2026-03-02 — Type Safety Batch (TASK-28 through TASK-31)

             ### Fixed
             - **TASK-28**: Resolved 5 mypy errors in core module:
               - agent_interface.py metadata field annotation (dict|None)
               - agent_core.py health_check() return type (bool|dict)
               - agent_core.py mcp_registry None guard
               - factories.py MCPRegistry type annotation
             - **TASK-29**: Resolved 13 mypy errors in security/middleware modules:
               - security/middleware.py None list, re.search, RateLimitError patterns
               - security/sandbox/docker_sandbox.py docker client None guards (7 errors)
               - security/auth/user_store.py Path() with str|None
               - middleware/tool_confirmation_middleware.py Event None annotation
             - **TASK-30**: Resolved 23 mypy errors in observability module:
               - log_rotation.py: logger.info() structured kwargs → extra={} pattern
               - config_watcher.py: yaml/toml import-untyped suppression
               - watchdog.py: component type guards
             - **TASK-31**: Resolved 45+ mypy errors in tools layer:
               - document_processing: metadata extractor, word processor fixes
               - data_tools: math visualizer, text transformer, file compressor fixes
               - git_tools: _base.py, git_tool.py fixes
               - docker_tools: docker_tool.py None guards
               - automation_tools/shell_safety.py fix

             ### Metrics
             - mypy errors: 103 → 17 (83% reduction across TASK-28–31)
             - Source files: 97 → 96 (runtime_metrics.py deleted in 1.4.2)

             4. Commit: `bump: version to 1.4.3`
Risk:        LOW
Blast Radius: Version string in /health response
Parity:      None
Acceptance:  python3 -c "import portal; assert portal.__version__ == '1.4.3'"
             pytest passes (874+ pass, 0 fail)
```

---

### Tier 2 — Structural (Type Safety)

#### TASK-33 *(new — resolve remaining 17 mypy errors in 5 files)*
```
Tier:        2
File(s):     src/portal/memory/manager.py
             src/portal/config/settings.py
             src/portal/routing/model_backends.py
             src/portal/routing/execution_engine.py
             src/portal/interfaces/web/server.py
Symbol(s):   MemoryManager.__init__, Settings, ModelBackend.generate_stream,
             OllamaBackend.generate_stream, WebInterface._server
Category:    TYPE_SAFETY
Finding:     17 mypy errors across 5 files remain after TASK-28–31:

             GROUP A — memory/manager.py:37 (1 error):
               Path() receives str|PathLike[str]|None but accepts only str|PathLike[str]
               Fix: add `or Path("data/memory.db")` coalescing before passing to Path()

             GROUP B — config/settings.py (9 errors):
               B1. Line 14: import yaml — add # type: ignore[import-untyped]
               B2. Lines 331-337: Field(default_factory=BackendsConfig) etc. —
                   change to Field(default_factory=lambda: BackendsConfig()) for
                   all 6 sub-config fields (BackendsConfig, SecurityConfig,
                   InterfacesConfig, ToolsConfig, ContextConfig, LoggingConfig,
                   RoutingConfig)
               B3. Line 345: ConfigDict(env_prefix=..., env_nested_delimiter=...) —
                   import SettingsConfigDict from pydantic_settings and use it
                   instead of ConfigDict from pydantic
               B4. Lines 384 (cascade): missing argument errors are caused by B3;
                   fixing B3 should resolve these cascade errors

             GROUP C — model_backends.py:205 + execution_engine.py:226 (2 errors):
               The abstract base class ModelBackend declares:
                 async def generate_stream(...) -> AsyncGenerator[str, None]: pass
               This is a coroutine (no yield), so mypy infers actual return type as
                 Coroutine[Any, Any, AsyncGenerator[str, None]]
               OllamaBackend.generate_stream uses yield (is an actual async generator),
               returning AsyncGenerator[str, None] — mypy sees this as a return type
               mismatch.
               Fix: Change abstract base class return type to AsyncIterator[str]:
                 from typing import AsyncIterator
                 async def generate_stream(...) -> AsyncIterator[str]: pass
               AsyncIterator[str] is satisfied by both the coroutine-and-yield approach
               and the actual async generator. The cascade error in execution_engine
               (line 226 "not async iterable") will also be resolved.

             GROUP D — server.py:727-728 (2 errors):
               self._server = None (line 150) is typed as None
               Line 727: self._server = uvicorn.Server(config) — type mismatch
               Fix: Add explicit type annotation at declaration:
                 import uvicorn  (at top of file, or within the method with TYPE_CHECKING)
                 self._server: uvicorn.Server | None = None

Action:      Fix each group independently. Run mypy after each group.
             After all fixes: python3 -m mypy src/portal --ignore-missing-imports
             should report 0 errors.
Risk:        LOW
Blast Radius: Settings (runtime behavior unchanged — Pydantic still validates the same),
             model_backends streaming (behavior unchanged), server (behavior unchanged)
Parity:      Settings validation unchanged. Streaming behavior unchanged (AsyncIterator
             is a supertype, not a different type). Server start/stop behavior unchanged.
Acceptance:  python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2
             should show "Found 0 errors in N files"
             pytest passes (874+ pass, 0 fail)
```

---

### Tier 3 — Hardening

No Tier 3 tasks currently. Codebase is in excellent shape.

---

## CI Gate (run before starting)

```bash
python3 -m ruff check src/ tests/            # 0 violations expected
python3 -m ruff format --check src/ tests/   # 0 violations expected
python3 -m pytest tests/ -v --tb=short       # 874+ PASS, 0 FAIL expected
python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -3  # 17 errors expected
```

---

## CI Gate (run after Tier 1 completion)

```bash
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
python3 -c "import portal; assert portal.__version__ == '1.4.3', portal.__version__"
```

---

## CI Gate (run after Tier 2 completion)

```bash
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -3  # expect 0 errors
```

---

## Execution Order

1. **TASK-32** — version bump to 1.4.3, complete CHANGELOG. Run CI after.
2. **TASK-33** — fix remaining 17 mypy errors in 5 files. Run `mypy src/portal --ignore-missing-imports` after each group; run full CI after all groups.
3. Final CI gate: full test suite green, mypy 0 errors.
