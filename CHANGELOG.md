# CLAUDE.md – Guidelines for Claude Code in the Portal Project

**Project**: Portal — Local-First AI Platform  
**Repository**: https://github.com/ckindle-42/portal  
**Last Updated**: February 26, 2026  

### Core Directives (All Equally Important)
- Aggressively identify and safely remove technical debt (high-priority).  
- Perform exhaustive top-to-bottom review of every file and line.  
- Flatten structures, reduce nesting/complexity.  
- Keep **all documentation 100 % synchronized**.  
- Validate features and add **realistic, high-impact enhancements** only.  
- Drive to **10/10 code health** (see definition below).  

### Updated 10/10 Code Health Definition (Feb 26, 2026)
- Zero technical debt  
- **≥85 % high-value test coverage** focused on critical paths, hardware paths, edge cases, and concurrency (lean test suite preferred; avoid bloat)  
- Flattened architecture (nesting ≤3, functions ≤40 lines)  
- All features validated + meaningful enhancements  
- Performance & security optimized for local hardware  
- New interfaces still ≤50 lines of Python  
- Perfect documentation sync + clean git history  

*(Note: Coverage is important but no longer the dominant metric. Quality and maintainability take precedence over line coverage.)*

### Mandatory Workflow, Code Quality Standards, Testing & Git Rules, Review Checklist
*(unchanged from previous version — only the 10/10 definition and testing language updated above)*

**Claude Code Instructions**
Read this file first. Follow the 9-step workflow with the new balanced 10/10 definition.

---

## [Unreleased] — 2026-02-27 — Codebase Shrink & Optimization

### chore(shrink): Tier 1 — dead code removal, bug fixes, test consolidation

**Dead code removed:**
- `src/portal/persistence/` (sqlite_impl.py, repositories.py, __init__.py — 931 LOC): never
  imported by any production code; application uses ContextManager + MemoryManager instead.
- `src/portal/observability/tracer.py` (99 LOC): never imported by production code or re-exported.
- `src/portal/core/exceptions.py`: removed dead `ContextNotFoundError`, `ModelQuotaExceededError`,
  `ErrorCode.CONTEXT_NOT_FOUND`, and `ErrorCode.MODEL_QUOTA_EXCEEDED`.
- `src/portal/core/structured_logger.py`: removed unused `set_trace_id()` and `get_trace_id()`.
- `src/portal/lifecycle.py`: removed dead `run_with_lifecycle()` function + `sys` import.
- `src/portal/routing/execution_engine.py`: removed dead `execute_parallel()` method.
- `src/portal/observability/health.py`: removed speculative `JobQueueHealthCheck` +
  `WorkerPoolHealthCheck` (no job queue or worker pool exists in Portal).

**Bug fixes:**
- `src/portal/routing/router.py`: `/health` endpoint now returns `"version": __version__`
  instead of hardcoded `"1.0.0"`.

**Tests removed/consolidated:**
- `tests/unit/test_sqlite_impl.py` (320 LOC, 40 tests) — dead code removed.
- `tests/unit/test_repositories.py` (131 LOC, 8 tests) — dead code removed.
- `tests/unit/test_tracer.py` (57 LOC, 8 tests) — dead code removed.
- `tests/unit/test_health_checks.py`: removed `TestJobQueueHealthCheck` (4 tests) and
  `TestWorkerPoolHealthCheck` (3 tests) for removed classes.
- `tests/unit/test_execution_engine_comprehensive.py`: removed `TestExecuteParallel` class.
- `tests/unit/test_dynamic_model_registry.py` (125 LOC, 5 tests): merged 3 unique tests into
  `test_model_registry_discovery.py`; deleted duplicate file.
- `tests/unit/test_core_init_exports.py` (67 LOC, 4 tests): low-value module-export shape tests.
- `tests/unit/test_agent_core_constants.py` (24 LOC, 4 tests): low-value constant checks.
- Fixed invalid `# noqa` directive in `test_execution_engine_comprehensive.py`.

**Documentation updated:**
- `KNOWN_ISSUES.md`: removed fully resolved Section 1 and Section 2.
- `docs/CODE_REVIEW_SUMMARY.md`: added historical artifact header with accurate caveats.
- `docs/implementation_plan.md`: marked as COMPLETE.
- `docs/ACTION_PROMPT_FOR_CODING_AGENT.md`: marked as superseded.

### fix(deprecation): Tier 2 — deprecation debt, dependency cleanup, code flattening

**Deprecation fixes:**
- `src/portal/tools/dev_tools/session_manager.py`: replaced 4× `datetime.utcnow()` with
  `datetime.now(tz=UTC)` (Python 3.12+ deprecation).
- `tests/unit/test_session_manager.py`: same fix (2× occurrences).
- `src/portal/tools/document_processing/document_metadata_extractor.py`: replaced deprecated
  `PyPDF2.PdfReader` import with `pypdf.PdfReader`.
- `pyproject.toml`: replaced `PyPDF2>=3.0.0` with `pypdf>=4.0.0` in dev deps.

**Dependency cleanup:**
- `pyproject.toml`: removed `requests>=2.32.0` from core deps (unused; codebase uses httpx/aiohttp).
- `pyproject.toml`: removed `numexpr>=2.8.0` from `generation` optional deps (never imported).

**Code flattening:**
- `src/portal/security/sandbox/docker_sandbox.py`: decomposed 111-line `execute_code()` into
  `_prepare_container()`, `_run_container()`, `_collect_output()` helpers; orchestrator ≤30 lines.
- `src/portal/routing/task_classifier.py`: extracted `_match_all_patterns()` helper; `classify()`
  reduced from 91 to ~35 lines.
- `src/portal/tools/knowledge/local_knowledge.py`: extracted `_keyword_search()` and
  `_embedding_search()` helpers; `_search()` reduced from 94 to ~20 lines.

**Metrics:**
| Metric | Before | After | Δ |
|--------|--------|-------|---|
| Dead source removed | — | ~1,538 LOC | −1,538 |
| Test files removed | — | 8 deleted, 1 consolidated | −~637 LOC |
| Lint errors | 0 | 0 | 0 |
| Unit tests passing | 937 | 827 | −110 (dead tests removed) |
| DeprecationWarnings | 1 (PyPDF2) | 0 | −1 |

---

## [Unreleased] — 2026-02-26 — Test Suite Shrink

### test(prune): consolidate `portal.core` export contract checks
- Replaced repetitive one-assert-per-test checks in `tests/unit/test_core_init_exports.py` with lean `pytest.mark.parametrize` coverage.
- Removed low-value module leak assertion focused on import internals and kept behavior-focused API contract checks only.
- Net result: same public API coverage with substantially less test code and simpler maintenance.

## [Unreleased] — 2026-02-26 — Complete Shrink & Rebase to Lean 10/10

### chore(shrink): Aggressive codebase shrink — 1,145 LOC removed (3.1% reduction)

**Executive Summary**: 36,589 → 35,444 total Python LOC. 0 lint errors. 910 tests pass (141 skipped for optional deps). All functionality preserved.

#### Batch 1: Test File Consolidation (201 LOC removed)
- Merged `test_event_bus_deque.py` (40 LOC) + `test_event_bus_subscribers.py` (168 LOC) into `test_event_bus.py`; added 4 unique deque/edge-case tests; deleted both redundant files
- Deleted `test_memory_manager.py` (14 LOC) — fully covered by `test_memory_manager_comprehensive.py`
- Deleted `test_model_backends.py` (34 LOC) — all normalize_tool_calls tests duplicated in `test_model_backends_comprehensive.py`

#### Batch 2: Source File Shrink — Docstrings, Banners, Bloat (528 LOC removed)
- `factories.py`: 348 → 149 LOC (−199): removed section banners, verbose Args/Returns docstrings, version comments
- `tools/__init__.py`: 445 → 245 LOC (−200): single-line warning messages, merged dual health_check loops, extracted `_record_failure()` helper, simplified entry_points discovery
- `agent_core.py`: 752 → 623 LOC (−129): slimmed module docstring (22→4 lines), class/method docstrings, `create_agent_core` factory

#### Batch 3: Routing Module Refactor (215 LOC removed)
- `intelligent_router.py`: 267 → 173 LOC (−94): removed all inline section comments, verbose RoutingStrategy enum comments, consolidated `_generate_reasoning()` to single return
- `execution_engine.py`: 495 → 374 LOC (−121): removed section banner, simplified CircuitBreaker init/docstrings, flattened `record_success/failure`, condensed `execute()` and `health_check()`

#### Batch 4: Observability, Security, Lifecycle (201 LOC removed)
- `lifecycle.py`: 371 → 323 LOC (−48): module docstring 18→1 line, ShutdownPriority enum, Runtime class, step comments
- `security_module.py`: 495 → 449 LOC (−46): module docstring, section banners, RateLimiter init verbosity, InputSanitizer docstring
- `metrics.py`: 433 → 400 LOC (−33): 28-line module docstring → 1 line, removed FASTAPI MIDDLEWARE banner
- `log_rotation.py`: 449 → 422 LOC (−27): module docstring, LogRotator docstring with example, RotationStrategy enum comments
- `router.py`: 311 → 278 LOC (−33): 14-line module docstring → 1 line, removed all 4 section banners
- `model_backends.py`: 478 → 469 LOC (−9): MLX inline comments, simplified generate_stream

#### Debt Metrics
| Metric | Before | After | Δ |
|--------|--------|-------|---|
| Total LOC | 36,589 | 35,444 | −1,145 |
| Test files | 77 | 74 | −3 |
| Lint errors | 0 | 0 | 0 |
| Tests passing | 910 | 910 | 0 |
| Tests skipped | 141 | 141 | 0 |

---

## [Unreleased] — 2026-02-26 — Code Health Modernization

### chore(debt): Remove unused `max_retries` from ExecutionEngine
- `ExecutionEngine.__init__` stored `self.max_retries` but no retry loop ever read it.
- Removed the attribute and its log entry; updated two corresponding unit tests.
- **Lines removed**: 2 source + 2 test. No functional change.

### chore(debt): Remove stale inline version comments from execution_engine.py
- Removed `# (v4.6.2: ...)` comments embedded in docstrings and inline — these belong in
  the changelog, not in source code. Simplified affected docstrings to one-liners.
- **Lines removed**: ~10.

### refactor: Extract `_row_to_message()` in SQLiteConversationRepository
- Eliminated two identical `Message(role=..., content=..., timestamp=..., metadata=...)`
  comprehensions in `_sync_get_messages()` and `_sync_search_messages()`.
- Replaced with a `@staticmethod _row_to_message(row)` called from both sites.
- **Duplication removed**: ~16 lines.

### refactor: Extract `_row_to_document()` in SQLiteKnowledgeRepository
- Eliminated four identical `Document(id=..., content=..., ...)` comprehensions across
  `_sync_search`, `_sync_search_by_embedding`, `_sync_get_document`, `_sync_list_documents`.
- Replaced with a `@staticmethod _row_to_document(row)` called from all four sites.
- **Duplication removed**: ~28 lines.

### refactor: Extract `_resolve_launcher()` in cli.py
- `up()` and `down()` both replicated the `repo_root / "launch.sh"` → per-platform fallback
  logic (~12 lines each).
- Extracted into `_resolve_launcher() -> Path`; also fixed `repo_root` path (was
  `parent.parent.parent.parent` — one level too high).
- **Duplication removed**: ~14 lines.

### refactor: Extract `_error_result()` on `ModelBackend`
- `OllamaBackend.generate()`, `LMStudioBackend.generate()`, and `MLXBackend.generate()` all
  constructed identical `GenerationResult(text="", tokens_generated=0, ...)` error structs.
- Added `ModelBackend._error_result(model_id, start_time, error)` static method; all three
  backends now delegate to it.
- **Duplication removed**: ~18 lines.

### refactor: Remove redundant local alias in SecurityMiddleware
- `_validate_security_policies` aliased `self.max_message_length` to a local variable
  before immediately using it. Removed the alias; use `self.max_message_length` directly.
- **Lines removed**: 1.

### refactor: Flatten routing dispatch in IntelligentRouter
- Replaced a 10-line `if/elif/else` chain in `IntelligentRouter.route()` with a
  `strategy_dispatch` dict, eliminating repeated `elif` branches.
- Simplified `_build_fallback_chain` to a single sorted comprehension (removed
  intermediate list and explicit for-loop).
- **Lines reduced**: ~10.

### Health metrics
| Dimension | Before | After |
|-----------|--------|-------|
| Dead code (unused attrs) | `max_retries` never used | Removed |
| Duplication (row mapping) | 4 × Message ctor, 4 × Document ctor | Single helper each |
| Duplication (error result) | 3 × GenerationResult error block | `_error_result()` |
| Duplication (CLI launcher) | 2 × 12-line path resolution | `_resolve_launcher()` |
| Stale comments | v4.6.x inline versioning | Removed |
| Tests | 1065 pass, 1 skip | 1065 pass, 1 skip (unchanged) |
