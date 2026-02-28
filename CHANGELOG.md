# Changelog

All notable changes to Portal are documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/).

---

## [1.3.4] — 2026-02-27 — Codebase Shrink & Optimization (Round 1 + Round 2)

### Summary

Dead-code removal, test consolidation, nesting reduction, and one bug fix across two rounds. No new features or architectural changes. All removals were evidence-verified via import tracing before deletion.

**Round 1 Metrics**: ~500 src LOC removed, ~40 test LOC net reduction, 0 lint errors.

**Round 2 Addendum (2026-02-28)**: Additional dead-code removal, 5 unused pip dependencies removed, 2 brittle tests deleted, QUAL-/ARCH- review tags cleaned, and context_manager.Message renamed to ContextMessage to eliminate name collision. ~570 src LOC removed (session_manager.py + user_store methods + validate_tool_parameters), 193 test LOC removed (test_session_manager.py). 0 lint errors, 818 tests passing (1 skipped).

### Removed

- Unused core dependencies: `tiktoken`, `tenacity`, `rich`, `python-jose`
- Stale documentation: `PULL_REQUEST.md`, `docs/ACTION_PROMPT_FOR_CODING_AGENT.md`, `docs/CODE_REVIEW_SUMMARY.md`, `docs/implementation_plan.md`
- `src/portal/interfaces/base.py` re-export shim; both consumers (`slack/interface.py`, `web/server.py`) updated to import directly from `portal.core.interfaces.agent_interface`
- Uncalled methods: `PortalError.user_message()`, `BaseTool.safe_execute()`, `TraceContext.get_current_trace_id()`, `ModelRegistry.get_models_by_capability()`, `RateLimiter.get_remaining()`
- `ToolExecutionStats` dataclass and `tool_stats` tracking dict from `ToolRegistry`; five uncalled methods removed: `record_execution()`, `get_tool_stats()`, `get_all_stats()`, `get_failed_tools()`, `get_tools_by_category()`
- Dead Jupyter scaffolding from `session_manager.py`: `_init_jupyter_session()`, `_execute_jupyter()`, and all `elif backend == "jupyter"` branches
- Trivial/structural tests: `test_hitl_import_guard.py`, enum member-count tests, `hasattr`-only structural tests, and duplicate coverage consolidated into primary test files

### Fixed

- Unbounded `_seen_users` growth in `runtime_metrics.py` — set now capped at 10,000 entries via `_MAX_SEEN_USERS` guard

### Refactored

- Dispatch tables replace `if/elif` chains in `word_processor.py`, `powerpoint_processor.py`, `document_metadata_extractor.py`
- Extracted helpers to reduce nesting: `_rerank_with_embeddings()` from `knowledge_base_sqlite._search()`, `_detect_category()` from `task_classifier.classify()`, `_attempt_recovery()` from `watchdog._check_component()`
- `BaseTool.validate_parameters()` uses `_TYPE_VALIDATORS`/`_TYPE_MESSAGES` class dicts instead of `if/elif` chain
- `ToolRegistry.get_tool()` return type tightened from `Any | None` to `BaseTool | None`
- Consolidated test files: security edge-cases → `test_security.py`; MCP context preservation → `test_mcp_tool_loop.py`; pickle gating → `test_mcp_registry.py`
- Parametrized repetitive tests in `test_intelligent_router.py`, `test_model_backends_comprehensive.py`, `test_watchdog.py`

### Documentation

- Removed internal review tags (`QUAL-3`, `ARCH-3`) from `ARCHITECTURE.md`
- Updated README hardware table entry to "Apple M4 Mac Mini Pro (64–128GB)"

---

### Round 2 Addendum — 2026-02-28

#### Removed (Round 2)

- `src/portal/tools/dev_tools/session_manager.py` (337 LOC) — `SessionManager` never subclassed `BaseTool`, never imported in production
- `tests/unit/test_session_manager.py` (193 LOC) — tests for the removed module
- Unused pip dependencies: `websockets` (pulled transitively by uvicorn), `cryptography` (orphaned by prior jose removal), `opentelemetry-api`, `opentelemetry-sdk`, `mcp` (all zero imports in src/)
- Uncalled `UserStore` methods: `create_api_key()`, `get_tokens()`, `_ConnectionPool.close_all()`
- Uncalled `ToolRegistry.validate_tool_parameters()` (tool validation handled by `BaseTool.validate_parameters()`)
- `Message` and `Response` unused re-exports from `src/portal/interfaces/__init__.py`

#### Fixed (Round 2)

- `context_manager.Message` renamed to `ContextMessage` to eliminate name collision with `agent_interface.Message`

#### Refactored (Round 2)

- `powerpoint_processor._add_slide()`: extracted `_fill_body_placeholder()` helper to reduce nesting from 6 → 3

#### Documentation (Round 2)

- Removed `QUAL-` and `ARCH-` review tags from `mcp_registry.py` and `test_bootstrap.py`
- Removed brittle `test_default_model_count` (breaks on model list changes) and trivial `test_processing_result_defaults`
- Applied ruff format to entire codebase (pre-existing formatting backlog cleared)

---

### Round 3 Addendum — 2026-02-28 — Final Polish

#### Removed (Round 3)

- `PortalRuntime.wait_for_shutdown()` from `lifecycle.py` — zero callers confirmed via grep
- Stale `setup_telemetry` try/except block from `tests/e2e/test_observability.py` — `setup_telemetry` was removed when opentelemetry deps were deleted; block always hit the except branch

#### Refactored (Round 3)

- `observability/__init__.py`: replaced 71-LOC eager barrel import with 8-line docstring; all consumers already import directly from submodules
- `_ConnectionPool` deduplicated: private copies in `context_manager.py` and `user_store.py` replaced with shared `portal.core.db.ConnectionPool` (configurable pragmas)
- `routing/model_registry.py`: 9-model hardcoded catalog (~155 LOC) moved to `default_models.json`; `_register_default_models()` replaced with 10-line JSON loader
- 9 functions flattened from nesting=5 to nesting≤4 using early-return and dispatch-table patterns across 8 tool files (`csv_analyzer`, `text_transformer`, `file_compressor`, `local_knowledge`, `excel_processor`, `word_processor`, `powerpoint_processor`, `tools/__init__`)
- Verification: `mcp_registry.list_tools()` intentionally remains at nesting=5 (data-shape-driven traversal)

---

## [Unreleased] — 2026-02-27 — Security Hardening & Reliability

### Summary

**Security hardening** (Tier 1), **reliability improvements** (Tier 2), and **targeted enhancements** (Tier 3) for real-world portal usage. All findings were confirmed via code analysis before implementation. No architectural changes; no speculative features.

**Metrics**: +41 tests added (869 passing, 1 skipped), 0 lint errors. Net +~180 src LOC.

### refactor(tools): Consolidate git tool boilerplate [R4]

All 9 git tool files (`git_branch`, `git_clone`, `git_commit`, `git_diff`, `git_log`,
`git_merge`, `git_pull`, `git_push`, `git_status`) repeated an identical 5-line try/except
GitPython import block, a `GIT_AVAILABLE` guard, and a `Repo()`/bare-check/`InvalidGitRepositoryError`
handler. Centralized in `src/portal/tools/git_tools/_base.py`. Each tool now imports
`GIT_AVAILABLE`, `GitCommandError`, and `open_repo()` from the shared module. Test patch
targets updated from per-tool `XXX.Repo` to `_base.Repo` (correct call site).
Net LOC reduction: ~100 lines.

### refactor(tools): Consolidate docker tool boilerplate [R5]

4 of 5 docker SDK tools (`docker_ps`, `docker_logs`, `docker_run`, `docker_stop`) repeated an
identical 4-line try/except Docker import block. Centralized in
`src/portal/tools/docker_tools/_base.py`. Each SDK tool imports `DOCKER_AVAILABLE` and `docker`
from the shared module. `docker_compose.py` is unchanged (subprocess-based, no SDK dependency).
Net LOC reduction: ~30 lines.

---

### security(web): Gate SSE streaming through SecurityMiddleware [S1]

The streaming path (`stream: true`) was calling `agent_core.stream_response()` directly, bypassing `SecurityMiddleware`. Both input sanitization (dangerous command detection) and rate limiting are now applied to streaming requests identically to non-streaming ones. Uses `isinstance(secure_agent, SecurityMiddleware)` guard so mocked agents in tests are unaffected.

### security(web): WebSocket shares HTTP rate limiter state [S2]

The WebSocket handler used its own per-connection rate limiter (`message_timestamps: list[float]`). A user could exhaust their HTTP limit and reconnect via WebSocket to bypass it. The handler now uses `SecurityMiddleware.rate_limiter` when available, with the per-connection limiter as a fallback when no real `SecurityMiddleware` is present.

### security(telegram): Mask bot token in startup log [S3]

`logger.info("  Bot token: %s...", self.bot_token[:20])` logged the first 20 characters of the bot token (including the secret portion). Replaced with `Bot ID: <id> (token masked)` — only the numeric bot ID (safe to log) is emitted.

### security(web): Add file size limit to audio upload endpoint [S4]

`/v1/audio/transcriptions` read the entire uploaded file into memory with no size check. Added a configurable limit via `PORTAL_MAX_AUDIO_MB` (default: 25 MB). Oversized uploads return HTTP 413.

### security(security): Fix eager f-string in rate limiter warning [S5]

`logger.warning(f"Rate limit exceeded for user {user_id} ...")` was eagerly formatting the string even when WARNING level is disabled. Converted to lazy `%`-style formatting.

### feat(registry): Auto-discover Ollama models at startup [R1]

`ModelRegistry.discover_from_ollama()` was fully implemented but never called. Added a call in `Runtime.bootstrap()` after `create_agent_core()`. Discovery errors are swallowed as warnings so startup is not blocked when Ollama is unreachable. The `PORTAL_BACKENDS_OLLAMA_URL` setting is forwarded to the discovery call.

### feat(context): Add TTL-based message pruning [R2]

The `conversations` SQLite table grew unbounded. Added `_sync_prune_old_messages()` which deletes messages older than `PORTAL_CONTEXT_RETENTION_DAYS` (default: 30 days). Pruning is triggered every 100 inserts via an in-memory counter. Uses the new thread-local connection pool (see E4).

### feat(memory): Add TTL-based memory pruning [R3]

The `memories` SQLite table grew unbounded. Added `_prune_old_memories()` which deletes entries older than `PORTAL_MEMORY_RETENTION_DAYS` (default: 90 days). Pruning is triggered every 100 inserts via an in-memory counter.

### fix(web): Source FastAPI version from portal.__version__ [R4]

`FastAPI(version="1.3.3")` was hardcoded and would drift on every release. Replaced with `from portal import __version__` and `FastAPI(version=__version__)`.

### refactor(web): Share httpx client across model/audio endpoints [R5]

`/v1/models` and `/v1/audio/transcriptions` each created a new `httpx.AsyncClient`, made one request, then closed it — incurring connection setup overhead per request. A shared `self._ollama_client` is now initialized in the lifespan and closed on shutdown.

### feat(web): Add SSE usage block to streaming responses [E1]

The final SSE chunk was missing the `usage` field required by the OpenAI streaming spec. Clients (Open WebUI, Continue, Cursor) use this for token accounting. The final chunk now includes `{"usage": {"prompt_tokens": 0, "completion_tokens": N, "total_tokens": N}}` where N is the number of tokens streamed.

### feat(web): Add startup readiness gate (503 during warmup) [E2]

Portal accepted chat completion requests immediately, even before the agent warmup completed. Requests would fail with cryptic errors if Ollama was unreachable. Added a readiness check: `/v1/chat/completions` now returns `503 Service Unavailable` with `Retry-After: 5` while `_agent_ready` is not set.

### feat(web): Add X-Request-Id tracing to HTTP responses [E3]

Added `X-Request-Id` header in `SecurityHeadersMiddleware`. If the client provides `X-Request-Id`, it is echoed back. If not, a 8-character UUID fragment is generated. Allows correlation of client requests with internal Portal logs across Ollama and MCP.

### refactor(context): Add thread-local SQLite connection pool [E4]

Every `ContextManager` sync helper was calling `sqlite3.connect(self.db_path)` — creating a new connection per call. Adopted the same `_ConnectionPool` pattern used by `UserStore`: thread-local connection caching with WAL mode enabled on first use. Eliminates connection setup overhead on high-frequency context reads/writes.

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
