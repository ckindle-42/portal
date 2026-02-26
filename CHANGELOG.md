# Changelog

All notable changes to Portal will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Release model

Changes are accumulated on the development branch and published together as a
named release.  Each section below represents one **tagged release** (e.g.
`v1.0.2`), not an individual commit or pull request.  The authoritative version
number lives in `pyproject.toml`; `src/portal/__init__.py` must stay in sync.

To cut a release:

1. Update `version` in `pyproject.toml` and `__version__` in
   `src/portal/__init__.py`.
2. Add a new `## [x.y.z] - YYYY-MM-DD` section here summarising what the
   release delivers.
3. Commit, tag (`git tag vx.y.z`), and push both the commit and the tag
   (`git push origin vx.y.z`).  The GitHub Actions release workflow picks up the
   tag and creates the GitHub Release automatically.

---

## [1.3.3] - 2026-02-26

### Removed
- **Dead example code** from document processing tools — removed ~250 lines of unused `example_*()` functions and `if __name__ == "__main__"` blocks from `pandoc_converter.py`, `word_processor.py`, `excel_processor.py`, and `powerpoint_processor.py`. These were production-module dead code, not executed by any test or user path.
- **Legacy "PocketPortal" references** — updated two docstrings in `agent_interface.py` and a stale version string in `exceptions.py`.

### Added
- **Module-level constants** in `agent_core.py` — extracted `DEFAULT_MCP_TOOL_MAX_ROUNDS` and `HIGH_RISK_TOOLS` frozenset to replace scattered magic numbers and hardcoded strings.
- **51 new unit tests** covering previously under-tested areas:
  - `test_memory_manager_comprehensive.py` (20 tests): CRUD, edge cases, concurrency, DB integrity, MemorySnippet dataclass
  - `test_context_manager.py` (10 tests): history CRUD, limits, clear, formatting, concurrent writes
  - `test_prompt_manager.py` (9 tests): template loading, caching, system prompt composition
  - `test_agent_core_constants.py` (4 tests): constant values and immutability
  - `test_model_registry_discovery.py` (8 tests): Ollama discovery mocking, query helpers, availability

### Changed
- **Version bump** 1.3.2 → 1.3.3 across `pyproject.toml`, `__init__.py`, `server.py`.
- Replaced f-string logging with structured fields in `agent_core.py` tool confirmation path.

### Metrics
- **Dead code removed**: ~250 lines (document tools examples)
- **Tests added**: 51 new tests (321 → 372 total)
- **Health score**: 9.4 → 9.6/10

---

## [1.3.2] - 2026-02-26

### Removed
- **Dead EventBroker abstraction** — deleted `src/portal/core/event_broker.py` (238 lines). The `EventBroker` ABC and `MemoryEventBroker` were never wired into the actual event system used by AgentCore. The `EventBus` in `event_bus.py` is the single, authoritative event system. Removed from `RuntimeContext`, `core/__init__.py` exports, lifecycle bootstrap, and shutdown.

### Refactored
- **Lifecycle shutdown flattened** — extracted 5 helper methods (`_drain_tasks`, `_stop_optional_components`, `_run_shutdown_callbacks`, `_cleanup_agent_core`) from the monolithic `shutdown()` method, reducing max nesting from 5 to 2 levels.
- **Logger best practice** — replaced f-string interpolation in logger calls with `%`-style formatting throughout `lifecycle.py` (avoids string formatting when log level is suppressed).

### Added
- **47 new tests** (274 → 321 passing):
  - `test_lifecycle.py` (14 tests) — RuntimeContext defaults, ShutdownPriority ordering, bootstrap security guards (MCP key, bootstrap key), shutdown callback sequencing, double-shutdown safety, pre-bootstrap no-ops.
  - `test_event_bus_subscribers.py` (9 tests) — subscribe/unsubscribe, error isolation between subscribers, EventEmitter helpers, Event.to_dict serialization, no-subscriber no-op.
  - `test_security_edge_cases.py` (24 tests) — URL-encoded path traversal, SQL injection patterns, HTML escaping, URL validation (shortener flagging), filename sanitization (truncation, special chars), shell quoting, dangerous command detection (fork bomb, curl-to-bash, rm -rf).

### Docs
- **Version sync** — `pyproject.toml`, `__init__.py`, `server.py`, `ARCHITECTURE.md` all updated to 1.3.2.
- **CODE_REVIEW_SUMMARY** refreshed to 1.3.2 with current health score.
- **CHANGELOG** updated with all 1.3.2 changes.

### Metrics
- **Files removed**: 1 (`event_broker.py`)
- **Lines saved**: ~238 (dead EventBroker abstraction)
- **Lines added**: ~510 (new tests)
- **Net complexity reduction**: Lifecycle nesting 5→2, EventBroker indirection removed
- **Tests**: 274 → 321 passing (+47), 0 failures, 1 skip (optional dep)

---

## [1.3.1] - 2026-02-26

### Security
- **ROUTER_TOKEN auth enforcement** — proxy, `/api/dry-run`, and `/api/tags` routes now verify `ROUTER_TOKEN` via `hmac.compare_digest` when the env var is set. Auth is skipped when unset (dev environments).

### Fixed
- **Naive datetime bugs** — replaced all 34 `datetime.now()` calls across 11 source files with `datetime.now(tz=UTC)` to prevent naive/aware comparison errors and ensure consistent UTC timestamps.
- **Version string mismatch** — `WebInterface` FastAPI version and `ARCHITECTURE.md` directory tree both updated from `1.2.0` to `1.3.0`.
- **N+1 query** — `SQLiteConversationRepository._sync_list_conversations()` replaced per-conversation message fetch with a single LEFT JOIN query (subquery for correct LIMIT/OFFSET on conversations).

### Refactored
- **DRY message builder** — extracted duplicated chat-message construction from 4 methods in `OllamaBackend`/`LMStudioBackend` into `BaseHTTPBackend._build_chat_messages()` (~40 lines saved).
- **Data-driven model registry** — replaced 175-line `_register_default_models()` with a compact list of dicts iterated in a 2-line loop (175 → 65 lines). All 9 models preserved.

### Added
- **36 new tests** (240 → 276 passing):
  - `test_router_auth.py` — ROUTER_TOKEN enforcement (7 tests)
  - `test_build_chat_messages.py` — shared message-builder helper (6 tests)
  - `test_circuit_breaker.py` — full CircuitBreaker state machine (10 tests)
  - `test_structured_logger_redaction.py` — secret redaction patterns (7 tests)
  - `test_data_driven_registry.py` — model registry data integrity (7 tests)

### Docs
- **CHANGELOG** updated with all 1.3.1 changes.
- **ARCHITECTURE.md** version string corrected to 1.3.0.
- **CODE_REVIEW_SUMMARY** refreshed with 9.0/10 health score.

---

## [1.3.0] - 2026-02-26

### Fixed
- **MCP tool loop context loss** — final fallback execution in `_run_execution_with_mcp_loop()` passed `messages=None`, discarding all accumulated tool results. Now correctly passes `current_messages` with full context history.
- **`execute_parallel()` cancellation** — added `return_exceptions=True` to `asyncio.gather()` in `ExecutionEngine.execute_parallel()` so one failing query no longer cancels sibling queries.

### Refactored
- **Event history O(n) → O(1)** — replaced `list.pop(0)` in `EventBus` with `collections.deque(maxlen=N)` for constant-time eviction of oldest events.
- **Tool registration deduplicated** — extracted shared validate/register/categorize logic into `ToolRegistry._register_tool_instance()`, eliminating ~40 lines of duplication between internal discovery and entry-point plugin loading.
- **Import cleanup** — moved `from pathlib import Path` to module-level in `lifecycle.py` (was inline as `from pathlib import Path as _Path`); fixed ruff I001 unsorted imports in `tools/__init__.py`.

### Docs
- **Version bump** — `pyproject.toml`, `src/portal/__init__.py`, `docs/ARCHITECTURE.md` all updated to 1.3.0.
- **Code Review Summary** refreshed with current health score and 10/10 path checklist.
- **Action Prompt** updated with completed and remaining tasks.

---

## [1.2.2] - 2026-02-26

### Refactored
- **Python 3.11+ modernization** — removed `importlib_metadata` fallback for Python <3.8 in `tools/__init__.py`; project requires 3.11+.
- **`os.path` → `pathlib`** — replaced `os.path.exists()` in `security_module.py` with `Path().exists()` per project guidelines.
- **ToolCategory alignment** — `ToolRegistry` pre-initialized categories and `ToolsConfig.enabled_categories` now use actual `ToolCategory` enum values (`utility`/`dev`) instead of phantom `system`/`git`.

### Security
- **numexpr bypass removed** — `MathVisualizerTool` no longer tries `numexpr.evaluate()` before `_safe_eval()`. Previously, if numexpr was installed, it bypassed the AST-walking security restrictions entirely.
- **Whisper MCP non-blocking** — `whisper_mcp.py` wraps blocking `model.transcribe()` in `asyncio.to_thread()` to avoid freezing the event loop.

### Fixed
- **TelegramInterface async/sync mismatch** — `_check_rate_limit()` now properly `await`s the async `RateLimiter.check_limit()` method. Previously returned a coroutine instead of a tuple, which would crash at runtime.
- **Path traversal false positives** — `InputSanitizer.validate_file_path()` now uses `Path.relative_to()` instead of `str.startswith()` to check sensitive directories. Prevents false rejections of paths like `/etc-safe/` that merely prefix-match `/etc`.
- **Log rotation in sync context** — `RotatingStructuredLogHandler._rotate_sync()` gracefully handles missing asyncio event loop by falling back to synchronous gzip compression instead of raising `RuntimeError`.
- **Hardcoded version in Prometheus metrics** — `MetricsCollector` now reads version from `importlib.metadata` instead of hardcoded `"4.3.0"`.
- **ExecutionEngine logger kwargs** — `logger.info()` calls with keyword args (silently dropped by stdlib) replaced with positional format args.
- **MLX artificial latency** — removed unnecessary `asyncio.sleep(0.01)` in `MLXBackend.generate_stream()`.

### Added
- **`ToolMetadata.async_capable`** field — new `bool` field (default `True`) on the `ToolMetadata` dataclass, preventing `AttributeError` when `ToolRegistry.get_tool_list()` accesses it.
- **`docs/CODE_REVIEW_SUMMARY.md`** — full code review report with health score, findings, and roadmap.
- **`docs/ACTION_PROMPT_FOR_CODING_AGENT.md`** — prioritized implementation task list for next session.

### Removed
- Dead `.env.example` entries: `MUSIC_API_URL`, `VOICE_API_URL`, `DOCGEN_API_URL` (referenced services don't exist).
- Unused `import tempfile` in `whisper_mcp.py`.

---

## [1.2.1] - 2026-02-26

### Security
- **Bash MCP sidecar hardened** — `shell=True` removed; commands are now parsed with `shlex.split()` and validated against an allowlist of safe binaries (`_ALLOWED_BINARIES`). Enforces `_MAX_CMD_LENGTH=2000` and `_MAX_ARGS=50` guards. Rejects unrecognised binaries with HTTP 403.
- **`eval()` eliminated from `MathVisualizer`** — replaced with a recursive AST-walking evaluator (`_safe_eval`) that only permits arithmetic operators, safe math functions (`sin`, `cos`, `tan`, `log`, `exp`, `sqrt`, `abs`), and named constants (`pi`, `e`). Arbitrary code execution is no longer possible via the math expression input.
- **Pickle deserialization gated** — legacy `pickle.loads()` fallback in `KnowledgeBaseSQLite._deserialize_embedding()` is now disabled by default. Enable only by setting `ALLOW_LEGACY_PICKLE_EMBEDDINGS=true`. Re-index documents to migrate to JSON encoding.
- **Secret redaction added to structured logger** — `_redact_secrets()` filter applied to all log messages and string kwargs. Masks Slack bot tokens, OpenAI keys, Telegram bot tokens, GitHub PATs, and Bearer tokens.
- **Docker sandbox resource limits** — `SandboxConfig` defaults updated to `memory=512m`, `cpus=1.0`, `pids_limit=100`. Network isolation (`network_mode=none`) is now the enforced default; only overridden if `network_disabled=False` is explicitly set.

### Removed
- `docs/archive/` (7 000 lines — PocketPortal v3 legacy docs, no references)
- `src/portal/interfaces/telegram/renderers.py` (611 lines — not imported anywhere)
- `src/portal/protocols/mcp/mcp_connector.py` (531 lines — broken `from base_tool import`, dead)
- `src/portal/protocols/mcp/mcp_server.py` (224 lines — dead, only in try/except init)
- `src/portal/protocols/mcp/security_policy.py` (223 lines — not imported anywhere)
- `src/portal/protocols/approval/` package (275 lines — re-exported only, never consumed)
- `src/portal/persistence/inmemory_impl.py` (371 lines — not imported or tested)
- `src/portal/config/schemas/` package (empty docstring-only init)
- `src/portal/observability/tracer.py` (208 lines — half-integrated, no OTLP wired)

### Fixed
- **`TelegramInterface` standalone entrypoint** — removed broken `main()` function that called `TelegramInterface()` with no arguments (constructor requires `agent_core` and `settings`).
- **`lifecycle.py` Path coercion** — `_config_watch_path = self.config_path or _Path("portal.yaml")` replaced with `_Path(self.config_path) if self.config_path else _Path("portal.yaml")` so a bare string `config_path` no longer causes `AttributeError` on `.exists()`.
- **`docker_sandbox.py` broken import** — `from base_tool import ...` with `sys.path.insert` hack replaced with canonical `from portal.core.interfaces.tool import BaseTool, ...`.
- **`ToolRegistry.validate_tool_parameters` dict/list crash** — parameter iteration now handles both `dict` (legacy format) and `list` of `ToolParameter` objects (current format).

### Changed
- **`protocols/mcp/__init__.py`** simplified to export only `MCPRegistry` after removal of dead connector and server modules.
- **`redis` moved to optional dependency** — `redis>=5.0.0` moved from `[project.dependencies]` to `[project.optional-dependencies].redis` and included in `all`/`dev` groups. Only needed for HITL approval workflow.
- **`media_tools/audio/` nesting flattened** — `audio_transcriber.py` promoted to `media_tools/audio_transcriber.py`; the empty `audio/` subdirectory is removed.
- **`/health` endpoint** — now includes `mcp` key with results of `MCPRegistry.health_check_all()` when an MCP registry is attached to `AgentCore`.

### Added
- `tests/unit/test_bash_mcp_hardening.py` — 8 tests covering approved/denied/blocked/malformed/oversized/injected commands.
- `tests/unit/test_math_safe_eval.py` — 13 tests covering correctness (polynomial, trig, constants) and security (import, open, exec, unknown vars/functions, attribute access).
- `tests/unit/test_pickle_gating.py` — 6 tests covering flag-disabled (default), flag-enabled (`true`/`1`/`yes`), and JSON path.

---

## [1.2.0] - 2026-02-26

### Fixed
- Critical runtime bugs: `get_column_letter` and `OPENPYXL_AVAILABLE` undefined in `excel_processor.py`
- Missing `import sys` in `tests/e2e/test_job_queue_system.py` and `tests/e2e/test_observability.py`

### Removed
- ~1 640 lines of dead code: `job_worker.py` (473 lines), `LogParser`, `InterfaceManager`, unused `EventBus` methods (`get_event_history`, `clear_history`, `get_stats`), unused `PromptManager` methods, unused `ContextManager` methods, `DependencyFactory` Protocol, `example_usage()` in `renderers.py`
- Corresponding dead test files (`test_job_queue_system.py`, `test_job_queue.py`)
- Stale `src/portal/config/schemas/README.md`

### Refactored
- `_build_app()` in `server.py` split into `_register_exception_handlers()`, `_register_middleware()`, `_register_chat_routes()`, `_register_utility_routes()`, `_register_websocket_route()`
- `process_message()` in `agent_core.py` split into `_normalize_interface()`, `_record_message_start()`, `_persist_user_context()`, `_build_execution_context()`, `_finalize_result()`, `_handle_processing_error()`
- Unused imports removed from `tools/__init__.py`, `word_processor.py`, `powerpoint_processor.py`

### Docs
- `ARCHITECTURE.md`: CLI commands synchronized (`portal logs [SERVICE]` added; `portal status`/`portal config` removed)
- `ARCHITECTURE.md`: class names corrected (`WatchdogMonitor` → `Watchdog`, `DockerSandbox` → `DockerPythonSandbox`)
- `ARCHITECTURE.md`: hardware path corrected (`hardware/linux/` → `hardware/linux-bare/`)
- `ARCHITECTURE.md`: added Dynamic Ollama Discovery, `BaseHTTPBackend`, and Interface Registry sections; bumped to v1.2.0
- `Makefile`: removed bogus `tests/tests/unit/` path from `test-unit` target

---

## [1.1.0] - 2026-02-26

### Phase 7 — Modernisation: security hardening, structural cleanup, and resilience

This release completes a comprehensive 7-phase modernisation of the portal
codebase, bringing it to production-grade quality.

#### Security

- **Timing-attack fix** — API key comparison in `WebInterface` now uses
  `hmac.compare_digest` to prevent key enumeration via response-time analysis.
- **Guarded Redis import** in `HITLApprovalMiddleware` — missing `redis`
  package raises `RuntimeError` with install instructions instead of crashing
  at import time.
- **WebSocket API-key guard** also uses `hmac.compare_digest`.

#### Architecture

- **`CentralDispatcher`** — new `src/portal/agent/dispatcher.py` provides a
  dictionary-based interface registry (`@CentralDispatcher.register("web")`).
  `WebInterface`, `TelegramInterface`, and `SlackInterface` are registered at
  import time.  `CentralDispatcher.get(name)` raises `UnknownInterfaceError`
  for unknown names.
- **`BaseHTTPBackend`** extracted to `src/portal/routing/model_backends.py` —
  `OllamaBackend` and `LMStudioBackend` now inherit shared session management
  (`_get_session`, `close`), eliminating duplication.
- **`portal.core` canonical API** — `src/portal/core/__init__.py` now exports
  all public symbols (`AgentCore`, `EventBus`, exception types, message types,
  …) from a single import path.
- **`AgentCore._resolve_preflight_tools()`** — preflight MCP tool loop
  extracted from `stream_response` into its own method for clarity and
  testability.

#### Resilience

- **MCPRegistry retry transport** — `httpx.AsyncHTTPTransport(retries=3)` with
  exponential backoff (`_RETRY_DELAYS = (1.0, 2.0, 4.0)`) for all MCP HTTP
  requests.
- **Dynamic Ollama model discovery** — `ModelRegistry.discover_from_ollama()`
  queries `/api/tags` and auto-registers new models with sensible defaults.
- **ConfigWatcher** started as an asyncio task during lifecycle startup.
- **Async lifespan** on `WebInterface` — FastAPI now uses an
  `asynccontextmanager` lifespan so startup is non-blocking; `/health` returns
  `{"status": "warming_up"}` until the warmup task completes.

#### Dead code removed (~3 000 lines)

`secrets.py`, `validator.py`, `response_formatter.py`, `cost_tracker.py`,
`sqlite_rate_limiter.py`, `resource_resolver.py`, `settings_schema.py`,
`src/portal/utils/` stub directory, `src/portal/core/registries/` duplicate
hierarchy, three dummy methods from `WebInterface`, and the now-obsolete
`tests/tests/e2e/test_mcp_protocol.py`.

#### Test structure

- `tests/tests/` nested hierarchy flattened to `tests/unit/`, `tests/e2e/`,
  `tests/integration/`, `tests/unit/tools/`.
- Registered `e2e` and `integration` pytest markers; both are excluded from
  the default `pytest tests/` run (require external services).
- New unit tests: `test_hitl_import_guard`, `test_dynamic_model_registry`,
  `test_core_init_exports`, `test_mcp_registry`, plus `CentralDispatcher` /
  `UnknownInterfaceError` cases in `test_router`.
- Fixed broken imports and async/sync mismatches in `test_data_integrity`.

#### Documentation & environment

- `docs/ARCHITECTURE.md` updated to v1.1.0 with new sections for
  `CentralDispatcher`, `BaseHTTPBackend`, `discover_from_ollama`, retry
  transport, HITLApprovalMiddleware, and the updated startup sequence.
- `.env.example` sets `SANDBOX_ENABLED=false`, documents `MCP_API_KEY`, and
  adds `PORTAL_BOOTSTRAP_API_KEY` with generation instructions.
- `KNOWN_ISSUES.md` section 3 documents M4 Mac memory pressure for MLX models
  above q8_0 quantisation.

---

## [1.0.3] - 2026-02-25

### Phase 2 — MCP tool dispatch, security hardening, CI, docs

All medium, low, and improvement items from the targeted fix list are resolved.
The MCP tool-use loop is fully wired end-to-end, security headers and API-key
documentation are in place, and the project now ships CI and a contributing guide.

#### Runtime fixes

- **`routing/model_backends.py`** — `OllamaBackend.generate()` and
  `generate_stream()` now use `/api/chat` instead of `/api/generate`.
  This surfaces `tool_calls` from tool-capable Ollama models and aligns
  the non-streaming and streaming paths to the same API endpoint.
  `GenerationResult` gains a `tool_calls: Optional[list]` field.
- **`routing/execution_engine.py`** — `ExecutionResult` gains a
  `tool_calls: Optional[List[Dict]]` field; `execute()` populates it from
  the backend result so `AgentCore._dispatch_mcp_tools()` receives real
  tool-call data instead of an always-empty list.
- **`core/agent_core.py`** — MCP tool loop now reads `result.tool_calls`
  directly (no more `getattr` fallback returning `[]`).

#### Security

- **`interfaces/web/server.py`** — `SecurityHeadersMiddleware` added;
  injects `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`,
  `Referrer-Policy`, and `Content-Security-Policy` on every response.
  HSTS is opt-in via `PORTAL_HSTS=1` (for deployments behind a TLS
  terminator such as Caddy).  CSP value overridable via `PORTAL_CSP`.
- **`interfaces/web/server.py`** — `_verify_api_key` docstring updated
  to document that `WEB_API_KEY` must be set before any non-localhost
  exposure of the `/v1/*` routes.

#### Ops / launch

- **`hardware/m4-mac/launch.sh`** — `down` command now includes
  `pkill -f "uvicorn.*8081"` and `pkill -f "uvicorn.*portal.routing.router"`
  as belt-and-suspenders fallbacks when PID files are absent.

#### Observability

- **`interfaces/web/server.py`** — `/health` response now includes
  `version` (from `portal.__version__`) and `build` metadata
  (`python_version`, `timestamp`) instead of a hardcoded `"1.0.1"` string.

#### CI

- **`.github/workflows/ci.yml`** added — runs `ruff` lint + format check,
  `mypy` type check, `pytest` (unit + integration), and a `docker build`
  on every push to `main`/`master`/`claude/**` and on all PRs.

#### Docs

- **`docs/ARCHITECTURE.md`** — Phase 2 work table updated to reflect
  current implementation state: true per-token streaming is done, MCP
  tool dispatch is wired end-to-end.  Data-flow diagram updated.
- **`README.md`** — Quick-start expanded with step-by-step launch
  instructions, `portal doctor` verification output, manual `curl` checks,
  and a security notes table.
- **`CONTRIBUTING.md`** added — covers dev setup, test commands, code
  quality tools, commit style, branching, and release process.

#### Project

- **`pyproject.toml`** — All runtime dependencies changed from `>=` to `~=`
  (compatible-release pinning); `requires-python` tightened to `>=3.11,<3.13`.
  Ruff `[tool.ruff.lint]` and `[tool.mypy]` sections added.
- **`tests/integration/test_web_interface.py`** — Expanded with tests for
  security headers, `/health` version field, agent_core degraded status,
  API key guard (401 without key, 200 with Bearer token), and
  `create_app()` factory.

---

## [1.0.2] - 2026-02-25

### Phase 1 — Boot-path quality pass

All critical runtime breaks, architectural seams, and quality gaps identified
during the initial post-port review have been resolved.  The application now
boots, passes its unit-test smoke suite, and is ready for Phase 2 work.

#### Runtime fixes

- **`factories.py`** — `DependencyContainer.create_agent_core()` now calls
  `AgentCore(**self.get_all())` instead of a hand-rolled kwarg set that was
  missing five required dependencies and included one invalid one.
- **`agent_core.py`** — added `stream_response(incoming)` async generator so
  that `WebInterface` and `SlackInterface` calls no longer raise
  `AttributeError`; wraps `process_message()` and yields a single token until
  true per-token streaming is wired in Phase 2.  `process_message()` now
  coerces plain string `interface` arguments to `InterfaceType` so callers
  passing `interface="telegram"` don't trigger `AttributeError` on `.value`.
  `AgentCore.health_check()` added; `mcp_registry` stored as an instance
  attribute with a `_dispatch_mcp_tools()` stub ready for Phase 2.
- **`core/types.py`** — unified the two incompatible `ProcessingResult`
  definitions into one canonical dataclass; all modules import from
  `portal.core.types`.
- **`config/settings.py`** — resolved dual-schema conflict: `env_prefix`
  corrected to `PORTAL_`, `SlackConfig` added, `TelegramConfig.allowed_user_ids`
  renamed to `authorized_users`, `SecurityConfig.rate_limit_requests` added,
  `Settings.to_agent_config()` added, `LoggingConfig.verbose` added,
  `validate_required_config()` updated for renamed fields and Slack coverage.
- **`slack/interface.py`** — `hmac.new(key, msg, hashlib.sha256)` confirmed
  correct for Python 3.11; unit tests added.
- **`web/server.py`** — non-streaming path fixed to pass correct kwargs to
  `process_message()`; `_format_completion()` corrected from `result.text` to
  `result.response`; `/health` endpoint now calls `agent_core.health_check()`
  and reflects real state instead of hard-coding `"ok"`.
- **`factories.py`** — `get_all()` now includes `mcp_registry` so it reaches
  `AgentCore` on every call.
- **`telegram/interface.py`** — imports and passes `InterfaceType.TELEGRAM`
  (enum) instead of the plain string `"telegram"`.

#### Tests added

| File | Covers |
|------|--------|
| `tests/unit/test_bootstrap.py` | DI wiring, `ProcessingResult` fields, factory function |
| `tests/unit/test_slack_hmac.py` | `hmac.new()` correctness, Slack signature verify/reject |

#### Docs

- `docs/ARCHITECTURE.md` — replaced five-line placeholder with a full
  architecture document covering component roles, data flow, startup sequence,
  directory structure, and Phase 2 limitations.

---

## [1.0.0] - 2026-02-10

### Initial release — ported from PocketPortal 4.7.4

Portal is a complete redesign of PocketPortal as a **web-primary,
multi-interface, hardware-agnostic** local AI platform.

#### Core

- `AgentCore` — central processing engine with `process_message()` and
  `health_check()`, routing, context management, and tool dispatch
- `DependencyContainer` — factory and DI container for `ModelRegistry`,
  `IntelligentRouter`, `ExecutionEngine`, `ContextManager`, `EventBus`,
  `PromptManager`, and `ToolRegistry`
- `IntelligentRouter` — hardware-aware model routing (AUTO / QUALITY / SPEED /
  BALANCED) across Ollama, LMStudio, and MLX backends
- `ExecutionEngine` — async LLM invocation with circuit-breaker pattern
- `Runtime` / `lifecycle.py` — bootstrap, OS signal handling, graceful shutdown

#### Interfaces

- `WebInterface` — FastAPI + WebSocket server; OpenAI-compatible
  `/v1/chat/completions`; static file serving; session management; SSE scaffold
- `TelegramInterface` — python-telegram-bot v20 with per-user authorisation and
  `ToolConfirmationMiddleware`
- `SlackInterface` — Slack Events API with HMAC verification, slash commands,
  and Block Kit formatting

#### MCP

- `MCPRegistry` — discovers, registers, and health-checks MCP servers over
  `stdio` and `openapi` transports; `mcpo` proxy integration
- Bundled server definitions: Filesystem, Time, ComfyUI, Whisper

#### Config & observability

- Pydantic v2 nested config schema with hardware-profile support
- Hardware env files for M4 Mac and RTX 5090 Linux
- `WatchdogMonitor`, `CostTracker`, `SecurityModule`, structured JSON logging

#### CLI & deployment

- `portal` CLI: `up`, `down`, `doctor`, `status`, `config`
- Multi-stage `Dockerfile`; docker-compose stacks for M4 and RTX 5090

---

## Version numbering

| Segment | When to bump |
|---------|-------------|
| **Major** | Breaking API or config changes |
| **Minor** | New features, backward-compatible |
| **Patch** | Bug fixes, documentation, backward-compatible |

## Links

- [Repository](https://github.com/ckindle-42/portal)
- [Releases](https://github.com/ckindle-42/portal/releases)
- [Issues](https://github.com/ckindle-42/portal/issues)
