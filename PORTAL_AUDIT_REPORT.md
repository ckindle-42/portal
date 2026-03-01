# Portal — Full Codebase Audit Report

**Date:** 2026-03-01
**Version audited:** 1.3.8
**Auditor:** Claude Code (claude-sonnet-4-6)
**Repository:** https://github.com/ckindle-42/portal

---

## 1. Executive Summary

**Health Score: 7.5 / 10 — ACCEPTABLE (trending toward STRONG)**

Portal 1.3.8 is a well-structured, actively maintained local-first AI platform. The codebase has
undergone multiple systematic refactor rounds (shrink-and-optimize, modularization, security hardening)
and shows clear intentional design. CI is fully green. Lint is clean. Test coverage is broad.

The project's biggest remaining exposure areas are:

| # | Area | Severity |
|---|------|----------|
| 1 | **mypy: 170 errors in 34 files** — type unsafety concentrated in Telegram interface and tool layer | MEDIUM |
| 2 | **Telegram interface union-attr gaps** — 29 `union-attr` errors that represent real NoneType dereference risks | MEDIUM |
| 3 | **os.getenv at class/module scope** — `ContextManager._MAX_AGE_DAYS` and `MemoryManager._MAX_AGE_DAYS` read env vars eagerly at import time, not at construction | LOW |
| 4 | **Documentation drift (minor)** — `ARCHITECTURE.md` references `aiohttp` after TASK-13 replaced it with `httpx` | LOW |
| 5 | **MCP endpoint format unverified** — `mcp_registry.py` note acknowledges mcpo URL format needs live verification | LOW |
| 6 | **TextTransformer returns None where str required** — two mypy errors that are actual return-type bugs | LOW |
| 7 | **CHANGELOG `[Unreleased]` block should be versioned** — recent TASK work is unreleased | INFO |

**LOC breakdown:**
- Source (src/portal): ~15,800 lines across 98 Python files
- Tests: ~13,300 lines across 67 Python files
- Test/source ratio: ~0.84 (healthy)

**Parity risks from this audit:** NONE. No behavioral changes recommended in this audit.

---

## 2. Git History Summary

### Commit Themes

| Commit Range | Theme | Status | Debt/TODOs Left |
|-------------|-------|--------|-----------------|
| TASK-6 to TASK-18 (2026-03-01) | Modularization, security hardening, TASK completion | COMPLETE | `[Unreleased]` changelog needs versioning |
| PR #79/#78/#77 (2026-02-28) | Security hardening: CORS, WebSocket, rate limiting, aiohttp consolidation | COMPLETE | None |
| PR #70 (1.3.8, 2026-02-28) | CI improvements, Docker pin, Dependabot, Python 3.13/14 CI matrix | COMPLETE | None |
| PR #69 (1.3.7) | `switch-ui` and `reset` commands | COMPLETE | None |
| PR #68 (1.3.6) | ROADMAP.md, launch.sh hardening | COMPLETE | None |
| PR #67 (1.3.5) | Dead backend removal (LMStudio, MLX stub), config cleanup | COMPLETE | MLX backend is future work (ROADMAP) |
| PR #66 | Modularization round 1: CircuitBreaker extraction, security split, metrics consolidation | COMPLETE | `security_module.py` shim still used by Telegram |
| PR #65 | QUICKSTART.md validation | COMPLETE | None |
| PR #60-64 | Shrink/refactor: boilerplate elimination, flatten nesting, consolidate tools | COMPLETE | None |
| PR #54-59 | Security hardening, CI fixes | COMPLETE | None |

### Contributor Patterns

Single-owner project (ckindle-42) with AI-assisted development. Clear pattern of
problem-identification → audit → targeted refactor → test verification.

### Unfinished Work Register

| Source | Description | Evidence | Priority |
|--------|------------|----------|----------|
| ROADMAP.md | LLM-Based Intelligent Routing | `ROADMAP.md` section 1 | P2-HIGH |
| ROADMAP.md | MLX Backend for Apple Silicon | `ROADMAP.md` section 2 | P3-MEDIUM |
| CHANGELOG `[Unreleased]` | Version TASK-6–18 work needs a release tag | `CHANGELOG.md` line 1 | P3-MEDIUM |
| `mcp_registry.py:163` | mcpo endpoint URL format note needs live verification | comment in `call_tool()` | P2-HIGH |

---

## 3. Baseline Status

```
BASELINE STATUS
---------------
Tests:    PASS=862  FAIL=0  SKIP=3  ERROR=0
Lint:     VIOLATIONS=0 (ruff check passes)
Mypy:     ERRORS=170 in 34 files (strict=false; not blocking CI)
API routes confirmed: YES
  - POST /v1/chat/completions  (server.py:359)
  - GET  /v1/models            (server.py:371)
  - GET  /health               (server.py:507)
  - WS   /ws                   (server.py:541)
  - POST /v1/audio/transcriptions (server.py:365)
  - GET  /health (router)      (router.py:138)
Python:   3.11.14
Proceed: YES
```

---

## 4. Public Surface Inventory

### HTTP API (`:8081` — WebInterface)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/v1/chat/completions` | Bearer (`WEB_API_KEY`) | OpenAI-compatible chat, streaming SSE + non-streaming |
| `GET` | `/v1/models` | Bearer | Virtual model list from Ollama router |
| `POST` | `/v1/audio/transcriptions` | Bearer | Whisper audio transcription proxy |
| `WS` | `/ws` | Bearer (first message) | WebSocket streaming chat |
| `GET` | `/health` | None | System health — version, agent_core, MCP status |
| `GET` | `/metrics` | None | Prometheus metrics |
| `GET` | `/dashboard` | None | Simple HTML dashboard |

### HTTP API (`:8000` — Proxy Router)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Ollama connectivity health |
| `POST` | `/api/dry-run` | Bearer (`ROUTER_TOKEN`) | Routing decision without execution |
| `GET` | `/api/tags` | Bearer | Ollama models + virtual workspace models |
| `*` | `/{path:path}` | Bearer | Catch-all Ollama proxy |

### CLI (`portal` command)

| Command | Description |
|---------|-------------|
| `portal up [--minimal] [--profile]` | Start the Portal stack |
| `portal down` | Stop the Portal stack |
| `portal doctor` | Health check all components |
| `portal logs [service]` | Tail log files |

### Key Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `MCP_API_KEY` | YES (production) | — | MCP server API key; refuses start if changeme |
| `PORTAL_BOOTSTRAP_API_KEY` | YES (production) | — | Bootstrap API key; refuses start if unset/default |
| `WEB_API_KEY` | Recommended | "" | Bearer token for /v1/* auth |
| `ROUTER_TOKEN` | Optional | "" | Bearer token for proxy router |
| `OLLAMA_HOST` | Optional | `http://localhost:11434` | Ollama URL |
| `PORTAL_ENV` | Optional | `production` | Controls bootstrap key validation |
| `PORTAL_CONTEXT_RETENTION_DAYS` | Optional | `30` | Context pruning age |
| `PORTAL_MEMORY_RETENTION_DAYS` | Optional | `90` | Memory pruning age |
| `PORTAL_MEMORY_PROVIDER` | Optional | `auto` | `auto`/`mem0`/`sqlite` |
| `PORTAL_BOOTSTRAP_USER_ID` | Optional | `open-webui` | Bootstrap user ID |
| `PORTAL_BOOTSTRAP_USER_ROLE` | Optional | `user` | Bootstrap user role |
| `PORTAL_AUTH_DB` | Optional | `data/auth.db` | Auth database path |
| `PORTAL_MEMORY_DB` | Optional | `data/memory.db` | Memory database path |
| `REDIS_URL` | Optional | — | Redis URL for HITL approval middleware |
| `MEM0_API_KEY` | Optional | — | Mem0 API key for cloud memory provider |

---

## 5. File Inventory

### Core Source (`src/portal/`)

| File Path | LOC | Purpose | Layer | Stability | Flags |
|-----------|-----|---------|-------|-----------|-------|
| `__init__.py` | 9 | Version export | INFRA | LOCKED | — |
| `cli.py` | 138 | Click CLI: up/down/doctor/logs | API | STABLE | Minor: redis/qdrant ports checked on `up` but not required |
| `agent/dispatcher.py` | 67 | CentralDispatcher interface registry | CORE | STABLE | — |
| `config/settings.py` | 484 | Pydantic v2 Settings, all config classes | INFRA | STABLE | — |
| `core/__init__.py` | 31 | Public API exports | CORE | LOCKED | — |
| `core/agent_core.py` | 657 | AgentCore — main orchestrator | CORE | STABLE | `os.getenv("REDIS_URL")` at runtime OK |
| `core/context_manager.py` | 265 | SQLite conversation history | CORE | STABLE | `_MAX_AGE_DAYS` reads env at import |
| `core/db.py` | 47 | Shared SQLite ConnectionPool | CORE | STABLE | — |
| `core/event_bus.py` | 215 | Async event pub/sub | CORE | STABLE | — |
| `core/exceptions.py` | 116 | Structured exception hierarchy | CORE | LOCKED | — |
| `core/factories.py` | 178 | DI container and dependency wiring | CORE | STABLE | — |
| `core/interfaces/agent_interface.py` | 194 | BaseInterface ABC | CORE | LOCKED | 2 mypy errors |
| `core/interfaces/tool.py` | 153 | BaseTool ABC | CORE | LOCKED | — |
| `core/prompt_manager.py` | 129 | System prompt template loader | CORE | STABLE | — |
| `core/structured_logger.py` | 165 | JSON structured logger + TraceContext | CORE | STABLE | 2 mypy token type errors |
| `core/types.py` | 97 | IncomingMessage, ProcessingResult, InterfaceType | CORE | LOCKED | — |
| `interfaces/telegram/interface.py` | 545 | Telegram bot adapter | ADAPTER | EVOLVING | 29 mypy union-attr, still imports security_module shim |
| `interfaces/web/server.py` | 754 | FastAPI WebInterface: routes, handlers | ADAPTER | STABLE | — |
| `interfaces/slack/interface.py` | 181 | Slack webhook adapter | ADAPTER | STABLE | — |
| `lifecycle.py` | 345 | Runtime bootstrap/shutdown | INFRA | STABLE | — |
| `memory/manager.py` | 161 | MemoryManager (SQLite or Mem0) | CORE | STABLE | `_MAX_AGE_DAYS` reads env at import |
| `middleware/hitl_approval.py` | 56 | Redis-backed HITL approval | CORE | EVOLVING | — |
| `middleware/tool_confirmation_middleware.py` | 252 | Tool confirmation gate | CORE | STABLE | — |
| `observability/config_watcher.py` | 275 | YAML config hot-reload watcher | INFRA | STABLE | — |
| `observability/health.py` | 160 | K8s-style health check system | INFRA | STABLE | — |
| `observability/log_rotation.py` | 248 | Log file rotation | INFRA | STABLE | 3 mypy false positives (StructuredLogger kwargs) |
| `observability/metrics.py` | 246 | Prometheus metrics collector + re-exports | INFRA | STABLE | — |
| `observability/runtime_metrics.py` | 13 | Re-export shim for backward compat | INFRA | CANDIDATE | Could be removed when all callers updated |
| `observability/watchdog.py` | 361 | Component health + auto-restart watchdog | INFRA | STABLE | — |
| `protocols/mcp/mcp_registry.py` | 183 | MCP server connection registry | ADAPTER | EVOLVING | mcpo endpoint URL format unverified |
| `routing/backend_registry.py` | 32 | ModelBackend instance registry (TASK-17) | CORE | STABLE | — |
| `routing/circuit_breaker.py` | 91 | CircuitBreaker for backend health | CORE | STABLE | — |
| `routing/execution_engine.py` | 309 | Execution with circuit-breaker + fallback | CORE | STABLE | — |
| `routing/intelligent_router.py` | 217 | Task-based model selection | CORE | STABLE | — |
| `routing/model_backends.py` | 253 | OllamaBackend + BaseHTTPBackend | ADAPTER | STABLE | — |
| `routing/model_registry.py` | 249 | Model catalog and discovery | CORE | STABLE | — |
| `routing/router.py` | 291 | FastAPI Ollama proxy router (`:8000`) | ADAPTER | STABLE | 3 `os.getenv` fallbacks (acceptable — module-level init) |
| `routing/task_classifier.py` | 274 | Regex heuristic task classifier | CORE | EVOLVING | Future: replace with LLM classifier |
| `routing/workspace_registry.py` | 25 | Workspace-to-model mapping (TASK-18) | CORE | STABLE | — |
| `security/auth/user_store.py` | 138 | SQLite RBAC user store | CORE | STABLE | 1 mypy Path error |
| `security/input_sanitizer.py` | 256 | Input sanitization and validation | CORE | STABLE | Warning emoji chars appear as UTF-8 sequences |
| `security/middleware.py` | 284 | SecurityMiddleware wrapper | CORE | STABLE | — |
| `security/rate_limiter.py` | 192 | Sliding-window rate limiter with persistence | CORE | STABLE | — |
| `security/sandbox/docker_sandbox.py` | 406 | Docker sandbox for code execution | INFRA | EVOLVING | 6 mypy errors (docker client None checks) |
| `security/security_module.py` | 5 | Re-export shim (RateLimiter, InputSanitizer) | CANDIDATE | Stable shim | Still imported by telegram/interface.py |
| `tools/` | ~4200 | Tool implementations (git, docker, data, etc.) | ADAPTER | EVOLVING | Tool layer has highest mypy error density |

---

## 6. Documentation Drift Report

| File | Issue | Current Text | Required Correction | Impact |
|------|-------|-------------|---------------------|--------|
| `docs/ARCHITECTURE.md` | References `aiohttp` after TASK-13 replaced it with `httpx` | "Shared aiohttp session management; base class for OllamaBackend" | Replace `aiohttp` with `httpx`; update `BaseHTTPBackend` description | LOW |
| `docs/ARCHITECTURE.md` | "LMStudio planned" in ExecutionEngine table | "(lmstudio and mlx planned)" | Say "lmstudio: deferred; mlx: planned (see ROADMAP.md)" | LOW |
| `CHANGELOG.md` | `[Unreleased]` block at top for TASK-6–18 work | `## [Unreleased] - 2026-03-01` | Should become `## [1.3.9] - YYYY-MM-DD` when released | LOW |
| `CHANGELOG.md` | Second `[Unreleased]` block (older modularization work) | `## [Unreleased] — 2026-02-28` | Already superseded by 1.3.8 entry; relabel or merge | LOW |
| `KNOWN_ISSUES.md` | Section 3 references MLX memory pressure | `M4 Mac Memory Pressure (MLX)` | Add note that MLX backend is not yet implemented | LOW |
| `.env.example` | `RATE_LIMIT_PER_MINUTE=60` but Settings default is `max_requests_per_minute=20` | `RATE_LIMIT_PER_MINUTE=60` | Change to `RATE_LIMIT_PER_MINUTE=20` or document the discrepancy | MEDIUM |
| `CONTRIBUTING.md` | Coverage report path | `pytest --cov=portal` | `pytest --cov=src/portal --cov-report=term-missing` | LOW |

---

## 7. Dependency Heatmap

### Module Coupling Analysis

```
HIGH COUPLING (imported by 5+ modules):
  portal.core.exceptions        -- used everywhere (expected)
  portal.core.types             -- used by all interfaces
  portal.core.structured_logger -- used by most core modules
  portal.routing.*              -- used by agent_core, factories, lifecycle
  portal.security.security_module (shim) -- telegram still uses it

MEDIUM COUPLING:
  portal.observability.metrics  -- used by runtime_metrics (shim), server
  portal.core.db                -- used by context_manager, memory, auth
  portal.security.middleware    -- used by lifecycle, server, telegram

LOW COUPLING (isolated, healthy):
  portal.observability.watchdog     -- lifecycle only
  portal.observability.config_watcher -- lifecycle only
  portal.observability.log_rotation   -- lifecycle only
  portal.protocols.mcp               -- factories, agent_core only
  portal.middleware.hitl_approval    -- agent_core only
```

No circular imports detected. All `TYPE_CHECKING` guards properly used.

---

## 8. Code Findings Register

| # | File | Lines | Category | Finding | Action | Risk | Blast Radius |
|---|------|-------|----------|---------|--------|------|--------------|
| F-01 | `core/structured_logger.py` | 135-142 | TYPE_SAFETY | `self.token = None` but `_trace_id_var.set()` returns non-None Token; `_trace_id_var.reset(self.token)` called with wrong type | Annotate `self.token` as `Token[str \| None] \| None`; guard `.reset()` | LOW | None |
| F-02 | `interfaces/telegram/interface.py` | 291-500 | TYPE_SAFETY | 29 `union-attr` mypy errors — `update.callback_query`, `update.message` accessed without None checks in handlers | Add `if update.callback_query is None: return` guards at top of each handler | MEDIUM | Telegram interface stability |
| F-03 | `tools/data_tools/text_transformer.py` | 103-106 | BUG | `_serialize()` returns `None` when format is unrecognized or serialization fails; return type annotated as `str` | Return `""` or raise `ValueError` instead of `None` | LOW | TextTransformer tool output |
| F-04 | `core/context_manager.py` | 52 | CONFIG_HARDENING | `_MAX_AGE_DAYS = int(os.getenv(...))` at class level — read at import time | Move to `__init__` accepting constructor arg or from config | LOW | Context pruning interval |
| F-05 | `memory/manager.py` | 35-40 | CONFIG_HARDENING | Same pattern — `_MAX_AGE_DAYS` and `PORTAL_MEMORY_DB` read at class/constructor scope via `os.getenv` | Move to constructor params with defaults | LOW | Memory pruning interval |
| F-06 | `routing/router.py` | 24-35 | CONFIG_HARDENING | Module-level `os.getenv` fallbacks that run even when RoutingConfig import fails | Acceptable for FastAPI module-level init; document as intentional | NONE | None |
| F-07 | `protocols/mcp/mcp_registry.py` | 163-173 | BUG | `call_tool()` has comment "mcpo endpoint format (needs live verification)" | Verify against live mcpo instance; remove comment or fix URL construction | MEDIUM | MCP tool dispatch in production |
| F-08 | `security/input_sanitizer.py` | 46-47 | OBSERVABILITY | Warning strings contain raw UTF-8 emoji sequences rendering as mojibake in some terminals | Replace with ASCII `[WARNING]` or proper Unicode literal `\u26a0\ufe0f` | LOW | Log readability |
| F-09 | `security/sandbox/docker_sandbox.py` | 69,74,119,158,191 | TYPE_SAFETY | Docker client initialized as `None` but accessed without None checks in multiple methods | Add `if self.client is None: raise RuntimeError(...)` guards | LOW | Docker sandbox operations |
| F-10 | `tools/__init__.py` | 140 | TYPE_SAFETY | `importlib.metadata.get()` called with `list[Never]` — deprecated API usage | Use `importlib.metadata.entry_points(group=...)` instead | LOW | Plugin discovery |
| F-11 | `tools/document_processing/word_processor.py` | 182+ | TYPE_SAFETY | `python-docx` expects `str \| IO[bytes]` but `Path` objects passed to `Document.save()` | Use `str(path)` to convert Path objects | LOW | Word processor tool |
| F-12 | `core/interfaces/agent_interface.py` | 29,48 | TYPE_SAFETY | `self.config = None` overrides `dict[str, Any]` annotation | Use `self.config: dict[str, Any] = {}` as default | LOW | BaseInterface subclasses |
| F-13 | `docs/ARCHITECTURE.md` | — | DOCUMENTATION | `BaseHTTPBackend` description says `aiohttp` (replaced by `httpx` in TASK-13) | Update to `httpx` | LOW | Docs accuracy |
| F-14 | `.env.example` | — | DOCUMENTATION | `RATE_LIMIT_PER_MINUTE=60` conflicts with Settings default of 20 | Align default to 20 | MEDIUM | Operator expectations |
| F-15 | `observability/runtime_metrics.py` | all | DEAD_CODE | Pure re-export shim; all callers could import from `metrics.py` directly | Keep for now (backward compat shim); schedule for removal | NONE | None |
| F-16 | `security/security_module.py` | all | DEAD_CODE | Re-export shim still used by `telegram/interface.py` | After F-02 fix, update Telegram to import from `security.rate_limiter` directly | LOW | Import resolution |
| F-17 | `tools/data_tools/file_compressor.py` | 86 | TYPE_SAFETY | `zipfile.ZipFile` constructor overload mismatch | Narrow argument types | LOW | ZipFile tool |
| F-18 | `cli.py` | 54-57 | BUG | `portal up` checks ports 6379 (redis) and 6333 (qdrant) even though these are optional deps not started by default | Remove redis/qdrant from default port check; only check when those services are configured | LOW | Fresh installs without Redis/Qdrant |

---

## 9. Test Suite Rationalization

### Current State
- 892 collected, 865 selected (27 deselected: e2e + integration markers)
- 862 PASS, 3 SKIP (optional dependencies), 0 FAIL

### Test Categories

| Category | Tests | Verdict | Notes |
|----------|-------|---------|-------|
| Unit — core | ~250 | KEEP | Good behavioral coverage |
| Unit — routing | ~80 | KEEP | Comprehensive router/engine tests |
| Unit — security | ~50 | KEEP | Good middleware/auth coverage |
| Unit — tools | ~200 | KEEP | Solid tool-level tests |
| Unit — observability | ~80 | KEEP | Watchdog, health, metrics |
| Integration — web | 22 | KEEP | Mocked httpx; no live Ollama needed |
| Integration — websocket | ~30 | KEEP | WebSocket protocol tests |
| E2E — observability | ~5 | KEEP (deselected by default) | Needs full stack |

### Critical Contract Coverage

| Contract | Covered? | Test Location |
|----------|----------|--------------|
| `GET /health` | YES | `tests/unit/test_web_interface.py` |
| `GET /v1/models` | YES | `tests/integration/test_web_interface.py` |
| `POST /v1/chat/completions` | YES | `tests/integration/test_web_interface.py` |
| Auth middleware (401) | YES | `tests/unit/test_security_middleware.py` |
| Workspace routing | YES | `tests/unit/test_workspace_registry.py` |
| MCP tool invocation | YES | `tests/unit/test_mcp_tool_loop.py` |
| `portal doctor` | YES | `tests/e2e/test_cli_commands.py` |
| Audio transcription | YES | `tests/unit/test_web_interface.py` |
| `/v1/models` Ollama-unreachable fallback | YES | `tests/integration/test_web_interface.py` |
| OpenAI `usage` field | YES | `tests/integration/test_web_interface.py` |

### Missing Coverage (ADD_MISSING)

| Priority | Contract | Recommended Test |
|----------|----------|-----------------|
| P2 | `TextTransformer` returns `""` on serialization failure (F-03 fix) | Unit test after fix |
| P2 | Telegram None guard coverage (F-02 fix) | Unit test for callback_query=None path |
| P3 | `WorkspaceRegistry` round-trip via proxy router | Integration |
| P3 | HITL approval approval/denial cycle | Unit with mock Redis |

---

## 10. Architecture Assessment & Module Blueprint

### Module Blueprint

| Module | Responsibility | Public API | Depends On | Used By |
|--------|----------------|-----------|-----------|---------|
| `core.agent_core` | Orchestrate all AI ops | `process_message`, `stream_response`, `health_check`, `execute_tool` | routing, context, events, tools, memory | lifecycle, web, telegram, slack |
| `core.factories` | DI wiring | `DependencyContainer`, `create_dependencies` | routing, core.* | lifecycle, cli |
| `core.context_manager` | Conversation history | `add_message`, `get_history`, `get_formatted_history` | core.db | agent_core |
| `core.event_bus` | Async pub/sub | `publish`, `subscribe` | — | agent_core |
| `core.exceptions` | Error hierarchy | All exception classes | — | everywhere |
| `routing.intelligent_router` | Task classification + model selection | `route(query, workspace_id)` | model_registry, task_classifier, workspace_registry | execution_engine, agent_core |
| `routing.execution_engine` | LLM execution + circuit breaker | `execute`, `generate_stream` | model_backends, circuit_breaker, backend_registry | agent_core |
| `routing.router` | Ollama proxy with workspace routing | FastAPI app on `:8000` | workspace_registry | standalone service |
| `routing.backend_registry` | Named backend registry | `register`, `get`, `available` | model_backends | factories, execution_engine |
| `routing.workspace_registry` | Workspace-to-model mapping | `get_model`, `list_workspaces` | — | intelligent_router, router, factories |
| `security.middleware` | Input sanitization + rate limiting wrapper | `process_message` | security.rate_limiter, security.input_sanitizer | interfaces |
| `security.auth.user_store` | RBAC SQLite store | `authenticate`, `add_tokens` | core.db | web interface |
| `observability.health` | K8s health probes | `HealthCheckSystem`, `register_health_endpoints` | — | lifecycle, web |
| `observability.watchdog` | Auto-restart monitoring | `Watchdog`, `register_component` | health | lifecycle |
| `protocols.mcp.mcp_registry` | MCP server connections | `register`, `call_tool`, `list_tools` | httpx | factories, agent_core |
| `interfaces.web.server` | FastAPI OpenAI endpoint | `WebInterface`, `create_app` | agent_core, security | lifecycle |
| `interfaces.telegram` | Telegram bot adapter | `TelegramInterface` | agent_core, security | lifecycle (optional) |
| `interfaces.slack` | Slack webhook adapter | `SlackInterface` | web interface | lifecycle (optional) |
| `lifecycle` | Runtime bootstrap/shutdown | `Runtime`, `RuntimeContext` | all | cli, main |
| `memory.manager` | Long-term memory | `add_message`, `build_context_block` | core.db | agent_core |

### Architecture Strengths

1. **Clean DI pattern** — `DependencyContainer` wires everything; no hidden singletons in core path
2. **Dual-router justification** — two routers serve two distinct clients with appropriate complexity
3. **Exception hierarchy** — structured error codes allow interfaces to handle errors by type
4. **Workspace routing** — virtual models propagate through both routers (post TASK-18)
5. **Circuit breaker** — backend failures do not cascade; proper fallback chain
6. **HITL middleware** — high-risk tools gated; Redis-backed for persistence

### Architecture Weaknesses

1. **TaskClassifier** — 100+ compiled regex patterns; fragile for semantic routing
2. **Telegram interface** — 29 union-attr mypy errors represent real runtime NoneType risks
3. **Module-scope env reads** — prevents testability and dynamic reconfiguration

---

## 11. Evolution Gap Register

| ID | Area | Current State | Target State | Effort | Risk | Priority |
|----|------|--------------|--------------|--------|------|----------|
| EG-01 | **Inference routing** | Regex heuristics (100+ patterns) | LLM classifier call (ROADMAP #1) | M | LOW | P2-HIGH |
| EG-02 | **Apple Silicon inference** | Ollama only | MLX server backend (ROADMAP #2) | M | LOW | P3-MEDIUM |
| EG-03 | **Telegram type safety** | 29 union-attr mypy errors | All None checks; 0 mypy errors in file | S | LOW | P2-HIGH |
| EG-04 | **Type safety (mypy)** | 170 errors in 34 files | Under 20 errors (tools layer uses external libs) | M | LOW | P2-HIGH |
| EG-05 | **os.getenv at import** | Class-level env reads in ContextManager, MemoryManager | Constructor params with env fallback | S | LOW | P3-MEDIUM |
| EG-06 | **MCP endpoint format** | Comment says "needs live verification" | Verified and comment removed | S | MEDIUM | P2-HIGH |
| EG-07 | **TextTransformer return type** | Returns `None` on failure (bug) | Returns `""` or raises ValueError | S | LOW | P2-HIGH |
| EG-08 | **CLI port check** | Checks redis/qdrant ports even when not required | Only check configured services | S | LOW | P3-MEDIUM |
| EG-09 | **CHANGELOG versioning** | `[Unreleased]` block for TASK-6–18 | Tagged release 1.3.9 | S | NONE | P3-MEDIUM |
| EG-10 | **security_module.py shim** | Re-export shim still imported by Telegram | Remove after Telegram import update | S | LOW | P4-LOW |

---

## 12. Production Readiness Score

| Dimension | Score | Narrative |
|-----------|-------|-----------|
| **Env config separation** | 4/5 | Pydantic Settings with env override; a few `os.getenv` at class scope remain |
| **Error handling / observability** | 4/5 | Structured logging, trace IDs, exception hierarchy, Prometheus metrics; emoji encoding glitch in sanitizer |
| **Security posture** | 4/5 | HMAC auth, input sanitization, rate limiting, CORS validation. Weak: CSP has unsafe-inline (documented), MCP endpoint unverified |
| **Dependency hygiene** | 5/5 | No cloud deps, pinned in uv.lock, Dependabot configured, aiohttp removed, all optional deps isolated |
| **Documentation completeness** | 4/5 | Excellent ARCHITECTURE.md, CLAUDE.md, ROADMAP.md, QUICKSTART.md. Minor drift: aiohttp ref, rate limit default mismatch |
| **Build / deploy hygiene** | 4/5 | Multi-platform launchers, Docker images pinned, CI matrix 3.11–3.14, security scanning, release script |
| **Module boundary clarity** | 4/5 | Clean DI, good separation. Two re-export shims (runtime_metrics, security_module) lingering |
| **Test coverage quality** | 4/5 | 862 tests, high behavioral coverage on critical paths. Tool layer mypy errors not covered by tests |
| **Evolution readiness** | 3/5 | Regex routing is documented fragility; LLM classifier and MLX backend are designed but not started |

**Composite: 3.8/5 — ACCEPTABLE (strong on foundations; next step is type safety and routing evolution)**

The platform is fully functional for its stated purpose. Remaining gaps are concentrated in the optional
tool layer type safety and the evolution roadmap, not in the critical inference path.
