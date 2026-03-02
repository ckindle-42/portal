# Portal — Full Codebase Audit Report

**Date:** 2026-03-02 (delta run — run 3)
**Version audited:** 1.4.2
**Auditor:** Claude Code (claude-sonnet-4-6)
**Repository:** https://github.com/ckindle-42/portal

---

## 1. Executive Summary

**Health Score: 9.0 / 10 — STRONG (up from 8.5)**

Portal 1.4.2 is in its best shape ever. Since the prior audit, PR #86 closed out every open task from the previous action prompt (TASK-23R through TASK-31):
- mypy errors dropped 103 → **17** (83% reduction in one PR)
- `runtime_metrics.py` backward-compat shim fully migrated and deleted (ROAD-C13 COMPLETE)
- All security, observability, and tools type-safety passes complete
- Version bumped to 1.4.2

New findings this run are minor and largely administrative:
- **CHANGELOG missing entries** for the TASK-28–31 mypy work (the 1.4.2 entry only documents TASK-23R)
- **Version should be bumped to 1.4.3** to properly tag the large mypy work done after the 1.4.2 tag
- **17 remaining mypy errors in 5 files** — primarily Pydantic v2 annotation patterns and one async generator type signature mismatch

No behavioral regressions. No security issues. The platform remains fully operational.

| # | Area | Prior | Current | Status |
|---|------|-------|---------|--------|
| 1 | **mypy errors** | 103 | 17 | -86 (TASK-28/29/30/31 complete) |
| 2 | **Tests** | 874 pass / 1 skip | 874 pass / 1 skip | UNCHANGED |
| 3 | **Lint violations** | 0 | 0 | CLEAN |
| 4 | **runtime_metrics.py** | IN-PROGRESS migration | DELETED | COMPLETE |
| 5 | **Version** | 1.4.1 | 1.4.2 | BUMPED |
| 6 | **CHANGELOG completeness** | Partial (through TASK-23R) | Missing TASK-28–31 entries | NEW FINDING |
| 7 | **Source files** | 97 | 96 | -1 (runtime_metrics.py deleted) |

**LOC breakdown:**
- Source (`src/portal/`): ~15,882 lines across 96 Python files
- Tests: ~13,533 lines across 68 Python files
- Test/source ratio: ~0.85 (healthy)

**Parity risks from this audit:** NONE. No behavioral changes introduced.

---

## 2. Delta Summary

### Changes Since Prior Audit (2026-03-01, v1.4.1)

| Metric | Prior | Current | Delta |
|--------|-------|---------|-------|
| Health Score | 8.5/10 | 9.0/10 | +0.5 |
| mypy errors | 103 | 17 | -86 |
| Test count | 874 pass / 1 skip | 874 pass / 1 skip | — |
| Source files | 97 | 96 | -1 (runtime_metrics.py deleted) |
| Version | 1.4.1 | 1.4.2 | +0.1 |
| Lint violations | 0 | 0 | — |

### Completed Work Since Prior Audit (PR #86)

- **TASK-23R (runtime_metrics migration):** Migrated `agent_core.py` and `server.py` callers to import directly from `portal.observability.metrics`; deleted `runtime_metrics.py`. Commit `1d872e3`.
- **TASK-27 (version bump):** `__version__` and `pyproject.toml` updated to 1.4.2. CHANGELOG entry added (partial — see new finding). Commit `5482c09`.
- **TASK-28 (core mypy):** Fixed 5 mypy errors in core module (`agent_interface.py`, `agent_core.py`, `factories.py`). Commit `cd4d12c`.
- **TASK-29 (security/middleware mypy):** Fixed 13 mypy errors across `middleware.py`, `docker_sandbox.py`, `user_store.py`, `tool_confirmation_middleware.py`. Commit `ba3d1b2`.
- **TASK-30 (observability mypy):** Fixed 23 mypy errors across `log_rotation.py`, `config_watcher.py`, `watchdog.py`, `metrics.py`. Commit `b434d3c`.
- **TASK-31 (tools layer mypy):** Fixed 45+ mypy errors across document processing, git tools, docker tools, data tools, math visualizer. Commits `17019f1`, `16a08ae`.

### New Findings This Run

| Category | ID | Description | Action |
|----------|----|-------------|--------|
| DOCS | F-N1 | CHANGELOG 1.4.2 entry missing TASK-28–31 work | Add entries and bump version to 1.4.3 |
| TYPE_SAFETY | F-N2 | `memory/manager.py:37` — `Path()` receives `str \| PathLike[str] \| None` | Add None coalescing |
| TYPE_SAFETY | F-N3 | `config/settings.py` — 9 mypy errors: yaml stubs, Field default_factory, ConfigDict vs SettingsConfigDict | Fix annotation patterns |
| TYPE_SAFETY | F-N4 | `model_backends.py:205` + `execution_engine.py:226` — 2 related errors: abstract async generator type mismatch | Fix abstract base class return type |
| TYPE_SAFETY | F-N5 | `server.py:727-728` — `self._server` typed as `None`, assigned `uvicorn.Server` | Add type annotation `uvicorn.Server \| None` |
| ENV | F-N6 | `cffi` package absent in clean env; `cryptography` import panics on `telegram` test collection | Environment-level; add to Phase 0 bootstrap docs |

---

## 3. Git History Summary

### Commit Themes (Since Prior Audit)

| Commit | Theme | Status | Debt/TODOs Left |
|--------|-------|--------|-----------------|
| `7496699` | Delete PORTAL_CODEBASE_REVIEW_AGENT_v4.md | COMPLETE | None |
| `7876600` | Add PORTAL_CODEBASE_REVIEW_AGENT_v5.md | COMPLETE | None |
| `2a2aa36` | Merge PR #86 (execute-action-prompt-9fxxe) | COMPLETE | None |
| `16a08ae` | chore(format): ruff format 3 tool files | COMPLETE | None |
| `17019f1` | fix(tools): 45+ mypy errors in tools layer (TASK-31) | COMPLETE | None |
| `b434d3c` | fix(observability): 23 mypy errors (TASK-30) | COMPLETE | None |
| `ba3d1b2` | fix(security): 13 mypy errors (TASK-29) | COMPLETE | None |
| `cd4d12c` | fix(core): 5 mypy errors (TASK-28) | COMPLETE | None |
| `5482c09` | bump: version to 1.4.2 | COMPLETE | CHANGELOG incomplete |
| `1d872e3` | runtime_metrics migration + deletion (TASK-23R) | COMPLETE | None |

### Contributor Patterns

Single-owner project (ckindle-42) with AI-assisted development. Pattern continues: audit → identify → fix → verify. Velocity is high; all 9 prior tasks closed in one PR. Health trajectory is strongly improving.

### Unfinished Work Register

| Source | Description | Evidence | Priority |
|--------|------------|----------|----------|
| CHANGELOG | Missing 1.4.2/1.4.3 entries for TASK-28–31 mypy batch | No entries in CHANGELOG for 86+ mypy fixes | P2-HIGH |
| Code | 17 mypy errors in 5 files | `mypy src/portal` output | P3-MEDIUM |
| ROADMAP.md | LLM-Based Intelligent Routing | `ROADMAP.md` / PORTAL_ROADMAP.md section 4 | P2-HIGH |
| ROADMAP.md | MLX Backend for Apple Silicon | PORTAL_ROADMAP.md section 4 | P3-MEDIUM |

---

## 4. Baseline Status

```
ENVIRONMENT STATUS
------------------
Python:     3.11.14
Venv:       system (active)
Project:    portal 1.4.2 installed (editable)
Core deps:  fastapi=0.135.1  pydantic=2.12.5  uvicorn=0.41.0  httpx=0.28.1
Dev tools:  ruff=0.15.4  pytest=9.0.2  mypy=1.19.1
cffi:       2.0.0 (installed this run — required by system cryptography for telegram tests)
Import:     portal package OK (version: 1.4.2)
Test collection: 875 collected (874 pass, 1 skip, 27 deselected)
API routes: confirmed

BASELINE STATUS
---------------
Environment:  Python 3.11.14 | portal importable
Dev tools:    ruff=0.15.4  pytest=9.0.2
Tests:        PASS=874  FAIL=0  SKIP=1  ERROR=0
Lint:         VIOLATIONS=0
Mypy:         ERRORS=17 in 5 files (strict=false; not blocking CI)
Branches:     LOCAL=2  REMOTE=2  (master + active review branch)
CLAUDE.md:    git policy PRESENT
API routes:   confirmed
Proceed:      YES

BRANCH HYGIENE
--------------
Local:  claude/execute-codebase-review-5WoPF (active), master
Remote: origin/claude/execute-codebase-review-5WoPF (active), origin/main
Note:   master local branch diverged from origin/main — cleanup pending after merge
        Active review branch expected; no stale merged branches found
```

---

## 5. Public Surface Inventory

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

### Key Environment Variables (unchanged from prior audit)

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

## 6. File Inventory

### Core Source (`src/portal/`) — 96 files

| File Path | LOC | Purpose | Layer | Stability | Flags |
|-----------|-----|---------|-------|-----------|-------|
| `__init__.py` | 9 | Version export | INFRA | LOCKED | — |
| `cli.py` | 138 | Click CLI: up/down/doctor/logs | API | STABLE | — |
| `agent/dispatcher.py` | 67 | CentralDispatcher interface registry | CORE | STABLE | — |
| `config/settings.py` | 484 | Pydantic v2 Settings, all config classes | INFRA | STABLE | 9 mypy errors (F-N3) |
| `core/__init__.py` | 31 | Public API exports | CORE | LOCKED | — |
| `core/agent_core.py` | 657 | AgentCore — main orchestrator | CORE | STABLE | Fixed (TASK-28) |
| `core/context_manager.py` | 265 | SQLite conversation history | CORE | STABLE | — |
| `core/db.py` | 47 | Shared SQLite ConnectionPool | CORE | STABLE | — |
| `core/event_bus.py` | 215 | Async event pub/sub | CORE | STABLE | — |
| `core/exceptions.py` | 116 | Structured exception hierarchy | CORE | LOCKED | — |
| `core/factories.py` | 178 | DI container and dependency wiring | CORE | STABLE | Fixed (TASK-28) |
| `core/interfaces/agent_interface.py` | 194 | BaseInterface ABC | CORE | LOCKED | Fixed (TASK-28) |
| `core/interfaces/tool.py` | 153 | BaseTool ABC | CORE | LOCKED | — |
| `core/prompt_manager.py` | 129 | System prompt template loader | CORE | STABLE | — |
| `core/structured_logger.py` | 165 | JSON structured logger + TraceContext | CORE | STABLE | — |
| `core/types.py` | 97 | IncomingMessage, ProcessingResult, InterfaceType | CORE | LOCKED | — |
| `interfaces/telegram/interface.py` | 580 | Telegram bot adapter | ADAPTER | STABLE | — |
| `interfaces/web/server.py` | 754 | FastAPI WebInterface: routes, handlers | ADAPTER | STABLE | 2 mypy errors (F-N5) |
| `interfaces/slack/interface.py` | 181 | Slack webhook adapter | ADAPTER | STABLE | — |
| `lifecycle.py` | 345 | Runtime bootstrap/shutdown | INFRA | STABLE | — |
| `memory/manager.py` | 161 | MemoryManager (SQLite or Mem0) | CORE | STABLE | 1 mypy error (F-N2) |
| `middleware/hitl_approval.py` | 56 | Redis-backed HITL approval | CORE | EVOLVING | — |
| `middleware/tool_confirmation_middleware.py` | 252 | Tool confirmation gate | CORE | STABLE | Fixed (TASK-29) |
| `observability/config_watcher.py` | 275 | YAML config hot-reload watcher | INFRA | STABLE | Fixed (TASK-30) |
| `observability/health.py` | 160 | K8s-style health check system | INFRA | STABLE | — |
| `observability/log_rotation.py` | 248 | Log file rotation | INFRA | STABLE | Fixed (TASK-30) |
| `observability/metrics.py` | 246 | Prometheus metrics (incl. former runtime_metrics) | INFRA | STABLE | — |
| `observability/watchdog.py` | 361 | Component health + auto-restart watchdog | INFRA | STABLE | Fixed (TASK-30) |
| `protocols/mcp/mcp_registry.py` | 183 | MCP server connection registry | ADAPTER | STABLE | — |
| `routing/backend_registry.py` | 32 | ModelBackend instance registry | CORE | STABLE | — |
| `routing/circuit_breaker.py` | 91 | CircuitBreaker for backend health | CORE | STABLE | — |
| `routing/execution_engine.py` | 309 | Execution with circuit-breaker + fallback | CORE | STABLE | 1 mypy error (F-N4, cascade) |
| `routing/intelligent_router.py` | 217 | Task-based model selection | CORE | STABLE | — |
| `routing/model_backends.py` | 253 | OllamaBackend + BaseHTTPBackend | ADAPTER | STABLE | 1 mypy error (F-N4) |
| `routing/model_registry.py` | 249 | Model catalog and discovery | CORE | STABLE | — |
| `routing/router.py` | 291 | FastAPI Ollama proxy router (`:8000`) | ADAPTER | STABLE | — |
| `routing/task_classifier.py` | 274 | Regex heuristic task classifier | CORE | EVOLVING | Future: LLM classifier |
| `routing/workspace_registry.py` | 25 | Workspace-to-model mapping | CORE | STABLE | — |
| `security/auth/user_store.py` | 138 | SQLite RBAC user store | CORE | STABLE | Fixed (TASK-29) |
| `security/input_sanitizer.py` | 256 | Input sanitization and validation | CORE | STABLE | — |
| `security/middleware.py` | 284 | SecurityMiddleware wrapper | CORE | STABLE | Fixed (TASK-29) |
| `security/rate_limiter.py` | 192 | Sliding-window rate limiter with persistence | CORE | STABLE | — |
| `security/sandbox/docker_sandbox.py` | 406 | Docker sandbox for code execution | INFRA | STABLE | Fixed (TASK-29) |
| `tools/` | ~7,500 | Tool implementations (many files) | ADAPTER | EVOLVING | Fixed (TASK-31) |

Note: `observability/runtime_metrics.py` **deleted** this audit cycle (TASK-23R complete).

---

## 7. Documentation Drift Report

| File | Issue | Current Text | Required Correction | Impact |
|------|-------|-------------|---------------------|--------|
| `CHANGELOG.md` | Missing 1.4.2 entries for TASK-28–31 | 1.4.2 entry only covers aiohttp + TASK-23R | Add TASK-28/29/30/31 sections; or bump to 1.4.3 with full entry | MED |
| `PORTAL_ROADMAP.md` | ROAD-C13 still shows IN-PROGRESS | "IN-PROGRESS" | Update to COMPLETE | LOW |
| `PORTAL_ROADMAP.md` | ROAD-P03 still shows PLANNED | "PLANNED" | Update to IN-PROGRESS or NEARLY-COMPLETE | LOW |

---

## 8. Dependency Heatmap

### Module Coupling Analysis (unchanged from prior audit — no coupling changes)

```
HIGH COUPLING (imported by 5+ modules):
  portal.core.exceptions        -- used everywhere (expected)
  portal.core.types             -- used by all interfaces
  portal.core.structured_logger -- used by most core modules
  portal.routing.*              -- used by agent_core, factories, lifecycle
  portal.security.middleware    -- used by lifecycle, server, telegram

MEDIUM COUPLING:
  portal.observability.metrics  -- used by server, agent_core (runtime_metrics shim GONE)
  portal.core.db                -- used by context_manager, memory, auth
  portal.security.input_sanitizer -- used by middleware

LOW COUPLING (isolated, healthy):
  portal.observability.watchdog     -- lifecycle only
  portal.observability.config_watcher -- lifecycle only
  portal.observability.log_rotation   -- lifecycle only
  portal.protocols.mcp               -- factories, agent_core only
  portal.middleware.hitl_approval    -- agent_core only
```

No circular imports detected. `runtime_metrics.py` shim removed — one fewer coupling node.

---

## 9. Code Findings Register

| # | File | Lines | Category | Finding | Action | Risk | Blast Radius |
|---|------|-------|----------|---------|--------|------|--------------|
| F-N1 | `CHANGELOG.md` | top | DOCS | TASK-28–31 mypy batch fixes (86+ errors resolved) not documented in CHANGELOG; 1.4.2 entry only covers aiohttp + TASK-23R | Add CHANGELOG entries; bump version to 1.4.3 | LOW | CHANGELOG only |
| F-N2 | `memory/manager.py` | 37 | TYPE_SAFETY | `Path()` receives `str \| PathLike[str] \| None` — Path constructor doesn't accept None | Add `or "data/memory.db"` coalescing or fix type annotation | LOW | memory manager only |
| F-N3 | `config/settings.py` | 14, 331–337, 345, 384 | TYPE_SAFETY | 9 mypy errors: (1) `import yaml` needs `# type: ignore[import-untyped]`; (2) `Field(default_factory=BackendsConfig)` — use `lambda: BackendsConfig()` for mypy; (3) `ConfigDict` needs to be `SettingsConfigDict` from pydantic_settings; (4) cascade Missing named argument errors | Fix per item | LOW | Settings class only |
| F-N4 | `routing/model_backends.py` | 205 | TYPE_SAFETY | `OllamaBackend.generate_stream` is an async generator (uses `yield`); base class `ModelBackend.generate_stream` is typed as `async def → AsyncGenerator` (no yield), mypy sees it as `Coroutine[Any, Any, AsyncGenerator]` — type mismatch with subclass | Change abstract base class return type to `AsyncIterator[str]`; both coroutine-returning-generator and actual async generator satisfy `AsyncIterator[str]` | LOW | Streaming only; works at runtime |
| F-N5 | `routing/execution_engine.py` | 226 | TYPE_SAFETY | Cascade error from F-N4 — mypy thinks `generate_stream` returns `Coroutine`, not `AsyncIterable` | Resolved by fixing F-N4 | LOW | Cascade |
| F-N6 | `interfaces/web/server.py` | 727–728 | TYPE_SAFETY | `self._server = None` (line 150) typed as `None`; line 727 assigns `uvicorn.Server` — type mismatch | Add type annotation: `self._server: uvicorn.Server \| None = None` | LOW | server only |
| F-N7 | Environment | — | INFRA | `cffi` package absent in clean environments causes `pyo3_runtime.PanicException` during telegram test collection (system cryptography uses Rust+cffi) | Document in Phase 0 bootstrap: install cffi if telegram tests fail to collect | LOW | Telegram tests only |

---

## 10. Test Suite Rationalization

### Current State
- 875 collected (874 pass, 1 skip, 27 deselected — e2e + integration markers)
- No test failures
- Collection note: cffi must be installed for `test_telegram_interface.py` collection to succeed (system cryptography dependency)

### Test Categories (unchanged)

| Category | Tests | Verdict | Notes |
|----------|-------|---------|-------|
| Unit — core | ~250 | KEEP | Good behavioral coverage |
| Unit — routing | ~80 | KEEP | Comprehensive router/engine tests |
| Unit — security | ~50 | KEEP | Good middleware/auth coverage |
| Unit — tools | ~220 | KEEP | Solid tool-level tests |
| Unit — observability | ~80 | KEEP | Watchdog, health, metrics |
| Integration — web | 22 | KEEP | Mocked httpx; no live Ollama needed |
| Integration — websocket | ~30 | KEEP | WebSocket protocol tests |
| E2E — observability | ~5 | KEEP (deselected by default) | Needs full stack |

### Critical Contract Coverage (all confirmed)

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
| Slack interface (with aiohttp) | YES | `tests/unit/test_router.py` |
| Telegram None guards | YES | `tests/unit/test_telegram_interface.py` |

---

## 11. Architecture Assessment & Module Blueprint

### Module Blueprint (updated)

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
| `routing.model_backends` | OllamaBackend implementation | `generate`, `generate_stream`, `is_available` | httpx | execution_engine |
| `routing.backend_registry` | Named backend registry | `register`, `get`, `available` | model_backends | factories, execution_engine |
| `routing.workspace_registry` | Workspace-to-model mapping | `get_model`, `list_workspaces` | — | intelligent_router, router, factories |
| `security.middleware` | Input sanitization + rate limiting wrapper | `process_message` | security.rate_limiter, security.input_sanitizer | interfaces |
| `security.auth.user_store` | RBAC SQLite store | `authenticate`, `add_tokens` | core.db | web interface |
| `observability.health` | K8s health probes | `HealthCheckSystem`, `register_health_endpoints` | — | lifecycle, web |
| `observability.watchdog` | Auto-restart monitoring | `Watchdog`, `register_component` | health | lifecycle |
| `observability.metrics` | Prometheus metrics (consolidated) | All metric objects | — | server, agent_core |
| `protocols.mcp.mcp_registry` | MCP server connections | `register`, `call_tool`, `list_tools` | httpx | factories, agent_core |
| `interfaces.web.server` | FastAPI OpenAI endpoint | `WebInterface`, `create_app` | agent_core, security | lifecycle |
| `interfaces.telegram` | Telegram bot adapter | `TelegramInterface` | agent_core, security | lifecycle (optional) |
| `interfaces.slack` | Slack webhook adapter | `SlackInterface` | web interface; requires aiohttp via slack_sdk | lifecycle (optional) |
| `lifecycle` | Runtime bootstrap/shutdown | `Runtime`, `RuntimeContext` | all | cli, main |
| `memory.manager` | Long-term memory | `add_message`, `build_context_block` | core.db | agent_core |

### Architecture Strengths (unchanged from prior audit)

1. **Clean DI pattern** — `DependencyContainer` wires everything; no hidden singletons in core path
2. **Dual-router justification** — two routers serve two distinct clients with appropriate complexity
3. **Exception hierarchy** — structured error codes allow interfaces to handle errors by type
4. **Workspace routing** — virtual models propagate through both routers
5. **Circuit breaker** — backend failures do not cascade; proper fallback chain
6. **HITL middleware** — high-risk tools gated; Redis-backed for persistence
7. **No backward-compat shims** — `runtime_metrics.py` and `security_module.py` both fully removed

### Remaining Architecture Concerns

1. **mypy: 17 errors in 5 files** — small remaining set; concentrated in settings (Pydantic pattern), model_backends (async generator), server (attribute type)
2. **async generator type mismatch** — `ModelBackend.generate_stream` abstract method type signature (F-N4) — works at runtime but mypy disagrees

---

## 12. Evolution Gap Register

| ID | Area | Current State | Target State | Effort | Risk | Priority |
|----|------|--------------|--------------|--------|------|----------|
| EG-01 | **Inference routing** | Regex heuristics (100+ patterns) | LLM classifier call (ROADMAP #1) | M | LOW | P2-HIGH |
| EG-02 | **Apple Silicon inference** | Ollama only | MLX server backend (ROADMAP #2) | M | LOW | P3-MEDIUM |
| EG-03 | **mypy errors** | 17 errors in 5 files | Zero errors | S | LOW | P3-MEDIUM |
| EG-04 | **CHANGELOG completeness** | Missing 1.4.2 mypy batch entries | Full entries + 1.4.3 version bump | XS | LOW | P2-HIGH |

Note: EG-04 (runtime_metrics shim) from prior audit is COMPLETE.

---

## 13. Production Readiness Score

| Dimension | Score | Narrative |
|-----------|-------|-----------|
| **Env config separation** | 5/5 | Pydantic Settings with env override; all os.getenv() eliminated |
| **Error handling / observability** | 4/5 | Structured logging, trace IDs, exception hierarchy, Prometheus metrics |
| **Security posture** | 4/5 | HMAC auth, input sanitization, rate limiting, CORS validation, HITL middleware |
| **Dependency hygiene** | 5/5 | aiohttp dep fixed; runtime_metrics shim removed; no dead dependencies |
| **Documentation completeness** | 5/5 | Excellent ARCHITECTURE.md, CLAUDE.md, ROADMAP.md; CHANGELOG gap noted as new task |
| **Build / deploy hygiene** | 5/5 | Multi-platform launchers, Docker images pinned, CI matrix 3.11–3.14 |
| **Module boundary clarity** | 5/5 | Clean DI, direct imports; no backward-compat shims remaining |
| **Test coverage quality** | 5/5 | 874 tests, high behavioral coverage on critical paths, 0 failures |
| **Evolution readiness** | 4/5 | Regex routing documented; LLM classifier and MLX backend designed and ready |

**Composite: 4.2/5 — STRONG**

The platform is in its best shape to date. The CHANGELOG gap and 17 remaining mypy errors are the only remaining loose ends before this can be considered fully production-hardened. With TASK-32 and TASK-33, this reaches 4.4/5.
