# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-01 (delta run v2)
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.4.2

---

## Project Context

Portal is a local-first AI platform (Python 3.11 / FastAPI / async).
Source: `src/portal/` (97 Python files, ~31,726 LOC).
Tests: `tests/` (68 Python files, ~27,066 LOC, 874 currently passing).

**Non-negotiable constraints:**
- API contract locked: `/v1/chat/completions`, `/v1/models`, `/health`, `/ws`, `/v1/audio/transcriptions` — no behavior changes
- No new features unless explicitly a task below
- No cloud dependencies, no external AI frameworks (LangChain, etc.)
- All behavior must remain identical to pre-task state
- Every task must leave lint and tests green

**CI gate (run before marking any tier complete):**
```bash
source .venv/bin/activate
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
```

**Branch:** `main` (work directly on main per CLAUDE.md git workflow)
**Commits:** conventional (`fix:`, `refactor:`, `docs:`, `chore:`, `test:`), one per logical change.

---

## Prior Work Summary

Since the last action prompt, the following tasks were completed:
- **TASK-24**: Fixed lifecycle.py mypy errors — StructuredLogger *args, RuntimeContext None guards
- **TASK-25**: Fixed telegram interface mypy errors — None guards, type annotations
- **TASK-26**: Fixed slack interface mypy errors — return type fix, __init__.py exports
- **aiohttp dep fix (this run)**: Added `aiohttp>=3.9.0` to `[slack]` and `[all]` optional deps (commit `6cfa24d`)

**IMPORTANT CORRECTION — TASK-23 from prior run:**

Prior TASK-23 said: "Delete `runtime_metrics.py` after verifying no imports exist."
This was based on an incorrect finding. **DO NOT execute the prior TASK-23.**
`runtime_metrics.py` has **2 production importers**:
- `src/portal/core/agent_core.py:20` — imports `MCP_TOOL_USAGE`
- `src/portal/interfaces/web/server.py:44` — imports `TOKENS_PER_SECOND, TTFT_MS, mark_request, set_memory_stats`

The correct action is TASK-23R below.

**Current state:** 874 tests passing, 103 mypy errors remaining.

---

## Remaining Open Tasks

### Tier 1 — Remediation (Do These First)

#### TASK-23R *(replaces and corrects prior TASK-23)*
```
Tier:        1
File(s):     src/portal/core/agent_core.py
             src/portal/interfaces/web/server.py
             src/portal/observability/runtime_metrics.py
Symbol(s):   MCP_TOOL_USAGE, TOKENS_PER_SECOND, TTFT_MS, mark_request, set_memory_stats
Category:    DEAD_CODE (shim removal — requires caller migration first)
Finding:     runtime_metrics.py is a re-export shim, but it DOES have production callers.
             Prior audit F-04 was wrong. Must migrate callers before deleting.
Action:      Step 1: In agent_core.py:20, change:
               from portal.observability.runtime_metrics import MCP_TOOL_USAGE
             to:
               from portal.observability.metrics import MCP_TOOL_USAGE
             Step 2: In server.py:44-48, change:
               from portal.observability.runtime_metrics import (
                   TOKENS_PER_SECOND, TTFT_MS, mark_request, set_memory_stats,
               )
             to:
               from portal.observability.metrics import (
                   TOKENS_PER_SECOND, TTFT_MS, mark_request, set_memory_stats,
               )
             Step 3: Verify: grep -r "runtime_metrics" src/portal/ | grep -v "__pycache__"
             Step 4: Delete src/portal/observability/runtime_metrics.py
Risk:        LOW (just changing import path; same symbols, same values)
Blast Radius: agent_core.py metrics recording, server.py metrics recording
Parity:      Prometheus metrics values and labels unchanged; same symbols from metrics.py
Acceptance:  - grep returns 0 lines for runtime_metrics in src/portal/ (except deleted file)
             - pytest passes (874+ pass, 0 fail)
             - MCP_TOOL_USAGE counter still increments in test_mcp_tool_loop.py
```

#### TASK-27 *(new — version bump and changelog)*
```
Tier:        1
File(s):     src/portal/__init__.py
             pyproject.toml
             CHANGELOG.md
Symbol(s):   __version__, version
Category:    DOCS
Finding:     aiohttp dependency fix (commit 6cfa24d) and TASK-23R removal need a
             version bump and CHANGELOG entry.
Action:      1. Update src/portal/__init__.py: __version__ = "1.4.2"
             2. Update pyproject.toml: version = "1.4.2"
             3. Add to CHANGELOG.md at the top:

             ## [1.4.2] - 2026-03-01 — Dependency Fix & runtime_metrics Cleanup

             ### Fixed
             - Added `aiohttp>=3.9.0` to `[slack]` optional dependency; `slack_sdk.web.async_client`
               requires aiohttp transitively (was missing since TASK-13 removed it from core deps)
             - Corrected prior audit: `runtime_metrics.py` had 2 production callers (not 0)

             ### Removed
             - **TASK-23R**: Migrated `agent_core.py` and `server.py` to import directly from
               `portal.observability.metrics`; deleted `runtime_metrics.py` re-export shim

             4. Commit: `bump: version to 1.4.2`
Risk:        LOW
Blast Radius: Version string in /health response
Parity:      None
Acceptance:  python3 -c "import portal; assert portal.__version__ == '1.4.2'"
```

---

### Tier 2 — Structural (Type Safety)

#### TASK-28 *(new — core module mypy errors)*
```
Tier:        2
File(s):     src/portal/core/interfaces/agent_interface.py
             src/portal/core/agent_core.py
             src/portal/core/factories.py
Symbol(s):   BaseInterface, AgentCore.health_check, AgentCore._dispatch_mcp_tools,
             DependencyContainer
Category:    TYPE_SAFETY
Finding:     5 mypy errors in core modules:
             - agent_interface.py:29,48 — metadata: dict[str,Any] = None — annotation mismatch
               (though __post_init__ handles it, mypy flags the field default)
             - agent_core.py:504 — health_check() return type declared bool but can return dict
             - agent_core.py:546 — mcp_registry called without None guard
             - factories.py:149 — MCPRegistry assigned to None-typed variable
Action:      Fix each error:
             a) agent_interface.py:29,48 — change to:
                metadata: dict[str, Any] | None = None
                (the __post_init__ already handles the None→{} coercion)
             b) agent_core.py:504 — change return type to bool | dict[str, Any]
                or ensure health_check always returns bool
             c) agent_core.py:546 — add: if self.mcp_registry is None: raise ...
             d) factories.py:149 — fix the type annotation to include MCPRegistry
Risk:        LOW
Blast Radius: Core orchestration only; no behavioral change
Parity:      health_check contract preserved; mcp_registry behavior unchanged
Acceptance:  mypy src/portal/core/ shows 0 errors
```

#### TASK-29 *(new — security module mypy errors)*
```
Tier:        2
File(s):     src/portal/security/middleware.py
             src/portal/security/sandbox/docker_sandbox.py
             src/portal/security/auth/user_store.py
             src/portal/middleware/tool_confirmation_middleware.py
Symbol(s):   SecurityMiddleware, DockerPythonSandbox, UserStore, ToolConfirmationMiddleware
Category:    TYPE_SAFETY
Finding:     ~12 mypy errors:
             - security/middleware.py:30 — None assigned to list[str]
             - security/middleware.py:185,189 — re.search / RateLimitError with str|None
             - security/sandbox/docker_sandbox.py:69,74 — None assigned to list[str]
             - security/sandbox/docker_sandbox.py:127,142,166,199,275 — docker client None guards
             - security/auth/user_store.py:24 — Path() with str|None
             - middleware/tool_confirmation_middleware.py:36 — None assigned to Event
Action:      Add None guards and fix annotation mismatches per mypy output
Risk:        LOW
Blast Radius: Security and sandbox layers
Parity:      Auth, rate limiting, and sandbox behavior unchanged
Acceptance:  mypy src/portal/security/ src/portal/middleware/ shows 0 errors
```

#### TASK-30 *(new — observability module mypy errors)*
```
Tier:        2
File(s):     src/portal/observability/log_rotation.py
             src/portal/observability/config_watcher.py
             src/portal/observability/watchdog.py
Symbol(s):   LogRotator, ConfigWatcher, Watchdog
Category:    TYPE_SAFETY
Finding:     ~8 mypy errors:
             - log_rotation.py:50 — logger.info() called with custom kwargs (log_file=, strategy=,
               max_bytes=, rotation_hours=) — stdlib Logger doesn't accept these as keyword args
             - config_watcher.py:218,228 — import-untyped for yaml and toml
             - watchdog.py — ~2 errors
Action:      a) log_rotation.py: change logger.info(msg, log_file=x, ...) to
                logger.info(msg, extra={"log_file": x, ...})
             b) config_watcher.py: add `# type: ignore[import-untyped]` for yaml/toml imports
             c) watchdog.py: fix per mypy output
Risk:        LOW
Blast Radius: Observability layer only; no behavioral change to log rotation or watching
Parity:      Log rotation and config watching behavior unchanged
Acceptance:  mypy src/portal/observability/ shows 0 errors
```

#### TASK-31 *(new — tools layer mypy batch fix)*
```
Tier:        2
File(s):     src/portal/tools/ (all tool files with errors)
Symbol(s):   Various tool classes
Category:    TYPE_SAFETY
Finding:     ~60 mypy errors in the tools layer across:
             - document_processing/document_metadata_extractor.py (5 errors)
             - document_processing/word_processor.py (2 errors)
             - data_tools/math_visualizer.py (3 errors)
             - data_tools/text_transformer.py (2 errors — import-untyped yaml/toml)
             - data_tools/file_compressor.py (1 error — TarFile overload)
             - git_tools/_base.py (1 error)
             - git_tools/git_tool.py (1 error)
             - docker_tools/docker_tool.py (4 errors)
             - automation_tools/shell_safety.py (1 error)
             - knowledge/ files (~7 errors)
Action:      Fix per mypy output; use # type: ignore[import-untyped] for yaml/toml stubs,
             add None guards where needed, fix overload mismatches
Risk:        LOW
Blast Radius: Tools layer only
Parity:      Tool behavior unchanged
Acceptance:  mypy src/portal/tools/ shows < 10 errors
             pytest passes (874+ pass)
```

---

### Tier 3 — Hardening

No Tier 3 tasks currently recommended. Codebase is in strong shape.

---

## CI Gate (run before any changes)

```bash
source .venv/bin/activate
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
source .venv/bin/activate
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
# Verify runtime_metrics removed
grep -r "runtime_metrics" src/portal/ | grep -v "__pycache__" | wc -l  # should be 0
# Verify version bump
python3 -c "import portal; assert portal.__version__ == '1.4.2', portal.__version__"
```

Expected output:
- ruff check: 0 violations
- pytest: 874+ PASS, 0 FAIL, 0 ERROR
- 0 remaining runtime_metrics imports in src/portal/

---

## Execution Order

1. **TASK-23R** — migrate runtime_metrics callers, delete shim. Run CI after.
2. **TASK-27** — version bump to 1.4.2, CHANGELOG entry. Run CI after.
3. **TASK-28** — core module mypy fixes. Run `mypy src/portal/core/` after each.
4. **TASK-29** — security/middleware mypy fixes.
5. **TASK-30** — observability mypy fixes.
6. **TASK-31** — tools layer mypy batch fix.
7. Final CI gate: full test suite green, mypy < 30 errors.
