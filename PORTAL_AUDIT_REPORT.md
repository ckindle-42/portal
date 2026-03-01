# Portal — Full Codebase Audit Report

**Date:** 2026-03-01 (delta run)
**Version audited:** 1.4.1
**Auditor:** Claude Code (claude-sonnet-4-6)
**Repository:** https://github.com/ckindle-42/portal

---

## 1. Executive Summary

**Health Score: 8.5 / 10 — STRONG (unchanged)**

Portal 1.4.1 continues in strong shape. Since the prior audit:
- TASK-24/25/26 (mypy fixes for lifecycle, telegram, slack) are **complete** — mypy errors dropped 123 → 103
- Version was bumped to 1.4.1
- One new **bug found and fixed** this run: `aiohttp` was missing from the `[slack]` optional dependency, causing `test_registered_interfaces_accessible` to fail in clean installs
- One prior **finding corrected**: F-04/TASK-23 claimed `runtime_metrics.py` had "no production callers" — this was wrong. Two production modules import from it (`agent_core.py`, `server.py`). TASK-23 as written would break production.

| # | Area | Prior | Current | Status |
|---|------|-------|---------|--------|
| 1 | **mypy errors** | 123 | 103 | -20 (TASK-24/25/26 complete) |
| 2 | **Tests** | 874 pass / 1 skip | 874 pass / 1 skip | UNCHANGED |
| 3 | **Lint violations** | 0 | 0 | CLEAN |
| 4 | **aiohttp [slack] dep** | MISSING (bug) | FIXED | FIXED this run |
| 5 | **runtime_metrics.py callers** | "0 callers" (incorrect) | 2 production callers confirmed | FINDING CORRECTED |
| 6 | **Version** | 1.4.0 | 1.4.1 | BUMPED |
| 7 | **Remote branches** | 1 (origin/main) | 2 (origin/main + review branch) | EXPECTED (active session) |

**LOC breakdown:**
- Source (`src/portal/`): ~31,726 lines across 97 Python files
- Tests: ~27,066 lines across 68 Python files
- Test/source ratio: ~0.85 (healthy)

**Parity risks from this audit:** NONE. No behavioral changes introduced.

---

## 2. Delta Summary

### Changes Since Prior Audit (2026-03-01, v1.4.0)

| Metric | Prior | Current | Delta |
|--------|-------|---------|-------|
| Health Score | 8.5/10 | 8.5/10 | — |
| mypy errors | 123 | 103 | -20 |
| Test count | 874 pass / 1 skip | 874 pass / 1 skip | — |
| Version | 1.4.0 | 1.4.1 | +0.1 |
| Lint violations | 0 | 0 | — |

### Completed Work Since Prior Audit

- **TASK-24 (lifecycle.py mypy):** Fixed `StructuredLogger` now accepts `*args` for %-style formatting, added `RuntimeContext` None guards. ~8 errors resolved.
- **TASK-25 (telegram mypy):** Added None guards for `User`, `Message`, `confirmation_middleware`; added type annotation for `by_category`. ~10 errors resolved.
- **TASK-26 (slack mypy):** Fixed `send_message` return type to match supertype; fixed `__init__.py` exports. ~3 errors resolved.
- **Version bump:** 1.4.0 → 1.4.1 via `7b0eeda`.

### New Findings This Run

| Category | ID | Description | Action |
|----------|-----|-------------|--------|
| BUG (FIXED) | — | `aiohttp` missing from `[slack]` optional dep; `slack_sdk.web.async_client` needs it | Fixed in `pyproject.toml` this run |
| FINDING CORRECTION | F-04 | `runtime_metrics.py` has 2 production callers — `agent_core.py:20` and `server.py:44` | TASK-23 must be revised (see below) |
| TYPE_SAFETY | F-05 | `agent_core.py:504` — `health_check()` returns `dict` but method declared `-> bool` | Tier 2 fix |
| TYPE_SAFETY | F-06 | `agent_core.py:546` — `mcp_registry` may be None but `.call_tool()` called without guard | Tier 2 fix |
| TYPE_SAFETY | F-07 | `agent_interface.py:29,48` — `metadata: dict[str, Any] = None` annotation allows None but type says dict | Tier 2 fix |

### TASK-23 Revision Required

The prior action prompt included:
> `TASK-23: Delete runtime_metrics.py after verifying no imports exist`

This was based on an incorrect finding. **Do NOT execute TASK-23 as written.** The file has active production callers:

```
src/portal/core/agent_core.py:20:from portal.observability.runtime_metrics import MCP_TOOL_USAGE
src/portal/interfaces/web/server.py:44:from portal.observability.runtime_metrics import (TOKENS_PER_SECOND, TTFT_MS, mark_request, set_memory_stats)
```

The correct multi-step action (see TASK-23R in ACTION_PROMPT) is:
1. Update `agent_core.py` to import `MCP_TOOL_USAGE` from `portal.observability.metrics` directly
2. Update `server.py` to import the four symbols from `portal.observability.metrics` directly
3. Verify `grep -r "runtime_metrics" src/ → 0` (excluding the shim itself)
4. Delete `runtime_metrics.py`

---

## 3. Git History Summary

### Commit Themes (Since Prior Audit)

| Commit | Theme | Status | Debt/TODOs Left |
|--------|-------|--------|-----------------|
| `6cfa24d` | fix(deps): aiohttp to [slack] optional dep | COMPLETE (this run) | None |
| `ee9cd49` | Delete PORTAL_CODEBASE_REVIEW_AGENT_v3.md | COMPLETE | None |
| `3a72ee0` | Add PORTAL_CODEBASE_REVIEW_AGENT_v4.md | COMPLETE | None |
| `7b0eeda` | bump: version to 1.4.1 | COMPLETE | None |
| `e44c408` | TASK-24/25/26: mypy fixes lifecycle/telegram/slack | COMPLETE | mypy still 103 |
| `bbf644f` | docs(audit): update prior audit artifacts | COMPLETE | None |

### Contributor Patterns

Single-owner project (ckindle-42) with AI-assisted development. Consistent pattern: audit → identify → fix → verify. Health trajectory is stable and improving.

### Unfinished Work Register

| Source | Description | Evidence | Priority |
|--------|------------|----------|----------|
| ACTION_PROMPT | TASK-23R: migrate runtime_metrics callers, then delete | `agent_core.py:20`, `server.py:44` | P2-HIGH |
| ROADMAP.md | LLM-Based Intelligent Routing | `ROADMAP.md` section 1 | P2-HIGH |
| ROADMAP.md | MLX Backend for Apple Silicon | `ROADMAP.md` section 2 | P3-MEDIUM |

---

## 4. Baseline Status

```
ENVIRONMENT STATUS
------------------
Python:     3.11.14
Venv:       .venv (active)
Project:    portal 1.4.1 installed (editable)
Core deps:  fastapi=0.135.1  pydantic=2.12.5  uvicorn=0.41.0  httpx=0.28.1
Dev tools:  ruff=0.15.4  pytest=9.0.2  mypy=1.19.1
Import:     portal package OK (version: 1.4.1)
Test collection: 875 collected (874 pass, 1 skip, 27 deselected)
API routes: confirmed

BASELINE STATUS
---------------
Environment:  Python 3.11.14 | venv active | portal importable
Dev tools:    ruff=0.15.4  pytest=9.0.2
Tests:        PASS=874  FAIL=0  SKIP=1  ERROR=0
Lint:         VIOLATIONS=0
Mypy:         ERRORS=103 in 28 files (strict=false; not blocking CI)
Branches:     LOCAL=2  REMOTE=2  (master + active review branch)
CLAUDE.md:    git policy PRESENT
API routes:   confirmed
Proceed:      YES

BRANCH HYGIENE
--------------
Local:  claude/execute-codebase-review-BTJbC (active), master
Remote: origin/claude/execute-codebase-review-BTJbC (active), origin/main
Note:   master local branch diverged from origin/main — cleanup pending after merge
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

## 6. File Inventory

### Core Source (`src/portal/`)

| File Path | LOC | Purpose | Layer | Stability | Flags |
|-----------|-----|---------|-------|-----------|-------|
| `__init__.py` | 9 | Version export | INFRA | LOCKED | — |
| `cli.py` | 138 | Click CLI: up/down/doctor/logs | API | STABLE | — |
| `agent/dispatcher.py` | 67 | CentralDispatcher interface registry | CORE | STABLE | — |
| `config/settings.py` | 484 | Pydantic v2 Settings, all config classes | INFRA | STABLE | — |
| `core/__init__.py` | 31 | Public API exports | CORE | LOCKED | — |
| `core/agent_core.py` | 657 | AgentCore — main orchestrator | CORE | STABLE | 2 mypy errors (F-05, F-06) |
| `core/context_manager.py` | 265 | SQLite conversation history | CORE | STABLE | — |
| `core/db.py` | 47 | Shared SQLite ConnectionPool | CORE | STABLE | — |
| `core/event_bus.py` | 215 | Async event pub/sub | CORE | STABLE | — |
| `core/exceptions.py` | 116 | Structured exception hierarchy | CORE | LOCKED | — |
| `core/factories.py` | 178 | DI container and dependency wiring | CORE | STABLE | 1 mypy error |
| `core/interfaces/agent_interface.py` | 194 | BaseInterface ABC | CORE | LOCKED | 2 mypy errors (F-07) |
| `core/interfaces/tool.py` | 153 | BaseTool ABC | CORE | LOCKED | — |
| `core/prompt_manager.py` | 129 | System prompt template loader | CORE | STABLE | — |
| `core/structured_logger.py` | 165 | JSON structured logger + TraceContext | CORE | STABLE | Fixed: *args support |
| `core/types.py` | 97 | IncomingMessage, ProcessingResult, InterfaceType | CORE | LOCKED | — |
| `interfaces/telegram/interface.py` | 545 | Telegram bot adapter | ADAPTER | STABLE | Fixed (TASK-25) |
| `interfaces/web/server.py` | 754 | FastAPI WebInterface: routes, handlers | ADAPTER | STABLE | 3 mypy errors |
| `interfaces/slack/interface.py` | 181 | Slack webhook adapter | ADAPTER | STABLE | Fixed (TASK-26); needs aiohttp |
| `lifecycle.py` | 345 | Runtime bootstrap/shutdown | INFRA | STABLE | Fixed (TASK-24) |
| `memory/manager.py` | 161 | MemoryManager (SQLite or Mem0) | CORE | STABLE | 1 mypy error |
| `middleware/hitl_approval.py` | 56 | Redis-backed HITL approval | CORE | EVOLVING | — |
| `middleware/tool_confirmation_middleware.py` | 252 | Tool confirmation gate | CORE | STABLE | 1 mypy error |
| `observability/config_watcher.py` | 275 | YAML config hot-reload watcher | INFRA | STABLE | 2 mypy errors (import-untyped) |
| `observability/health.py` | 160 | K8s-style health check system | INFRA | STABLE | — |
| `observability/log_rotation.py` | 248 | Log file rotation | INFRA | STABLE | 4 mypy errors (logger kwargs) |
| `observability/metrics.py` | 246 | Prometheus metrics collector + re-exports | INFRA | STABLE | — |
| `observability/runtime_metrics.py` | 13 | Re-export shim (backward compat) | INFRA | CANDIDATE | Active callers: agent_core, server |
| `observability/watchdog.py` | 361 | Component health + auto-restart watchdog | INFRA | STABLE | ~2 mypy errors |
| `protocols/mcp/mcp_registry.py` | 183 | MCP server connection registry | ADAPTER | STABLE | — |
| `routing/backend_registry.py` | 32 | ModelBackend instance registry | CORE | STABLE | — |
| `routing/circuit_breaker.py` | 91 | CircuitBreaker for backend health | CORE | STABLE | — |
| `routing/execution_engine.py` | 309 | Execution with circuit-breaker + fallback | CORE | STABLE | 2 mypy errors |
| `routing/intelligent_router.py` | 217 | Task-based model selection | CORE | STABLE | — |
| `routing/model_backends.py` | 253 | OllamaBackend + BaseHTTPBackend | ADAPTER | STABLE | — |
| `routing/model_registry.py` | 249 | Model catalog and discovery | CORE | STABLE | — |
| `routing/router.py` | 291 | FastAPI Ollama proxy router (`:8000`) | ADAPTER | STABLE | — |
| `routing/task_classifier.py` | 274 | Regex heuristic task classifier | CORE | EVOLVING | Future: LLM classifier |
| `routing/workspace_registry.py` | 25 | Workspace-to-model mapping | CORE | STABLE | — |
| `security/auth/user_store.py` | 138 | SQLite RBAC user store | CORE | STABLE | 1 mypy error |
| `security/input_sanitizer.py` | 256 | Input sanitization and validation | CORE | STABLE | — |
| `security/middleware.py` | 284 | SecurityMiddleware wrapper | CORE | STABLE | 3 mypy errors |
| `security/rate_limiter.py` | 192 | Sliding-window rate limiter with persistence | CORE | STABLE | — |
| `security/sandbox/docker_sandbox.py` | 406 | Docker sandbox for code execution | INFRA | STABLE | 7 mypy errors (None guards) |
| `tools/` | ~13,000 | Tool implementations | ADAPTER | EVOLVING | Various mypy errors |

---

## 7. Documentation Drift Report

| File | Issue | Current Text | Required Correction | Impact |
|------|-------|-------------|---------------------|--------|
| `CHANGELOG.md` | Missing 1.4.2 entry for aiohttp fix | — | Add `[1.4.2]` section documenting aiohttp added to [slack] dep | LOW |
| `CLAUDE.md` | References `ROADMAP.md` | `See ROADMAP.md` | Could reference `PORTAL_ROADMAP.md` for unified roadmap | LOW |
| `observability/runtime_metrics.py` docstring | Says "backward compat" but has 2 active production callers | "re-exports from metrics.py for backward compatibility" | Document that agent_core and server import from this | LOW |

---

## 8. Dependency Heatmap

### Module Coupling Analysis

```
HIGH COUPLING (imported by 5+ modules):
  portal.core.exceptions        -- used everywhere (expected)
  portal.core.types             -- used by all interfaces
  portal.core.structured_logger -- used by most core modules
  portal.routing.*              -- used by agent_core, factories, lifecycle
  portal.security.middleware    -- used by lifecycle, server, telegram

MEDIUM COUPLING:
  portal.observability.metrics  -- used by runtime_metrics (shim), server
  portal.observability.runtime_metrics -- used by agent_core, server (2 callers)
  portal.core.db                -- used by context_manager, memory, auth
  portal.security.input_sanitizer -- used by middleware

LOW COUPLING (isolated, healthy):
  portal.observability.watchdog     -- lifecycle only
  portal.observability.config_watcher -- lifecycle only
  portal.observability.log_rotation   -- lifecycle only
  portal.protocols.mcp               -- factories, agent_core only
  portal.middleware.hitl_approval    -- agent_core only
```

No circular imports detected.

---

## 9. Code Findings Register

| # | File | Lines | Category | Finding | Action | Risk | Blast Radius |
|---|------|-------|----------|---------|--------|------|--------------|
| F-01 | `pyproject.toml` | slack extras | BUG (FIXED) | `aiohttp` missing from `[slack]` optional dep; `slack_sdk.web.async_client` requires it | Fixed this run | LOW | Clean installs of portal[slack] |
| F-02 | `runtime_metrics.py` | full file | FINDING_CORRECTION | Prior audit incorrectly said "no production callers"; `agent_core.py:20` and `server.py:44` import from it | Revise TASK-23 (see TASK-23R) | MEDIUM if deleted without migration | agent_core, server |
| F-03 | `core/agent_core.py` | 504 | TYPE_SAFETY | `health_check()` can return `dict` but method declares `-> bool` | Fix return type annotation | LOW | agent_core only |
| F-04 | `core/agent_core.py` | 546 | TYPE_SAFETY | `mcp_registry` may be `None` when `.call_tool()` is called | Add None guard | LOW | MCP tool dispatch |
| F-05 | `core/interfaces/agent_interface.py` | 29, 48 | TYPE_SAFETY | `metadata: dict[str, Any] = None` — annotation inconsistency; `__post_init__` handles it correctly but mypy flags it | Use `field(default_factory=dict)` or `dict[str, Any] \| None = None` | LOW | Interface subclasses |
| F-06 | `core/factories.py` | 149 | TYPE_SAFETY | `MCPRegistry` assigned to variable typed `None` | Fix type annotation | LOW | Factories only |
| F-07 | `security/sandbox/docker_sandbox.py` | 69, 74, 127, 142, 166, 199, 275 | TYPE_SAFETY | 7 errors: `None` assigned to `list[str]`, docker client None guards | Add None guards per mypy | LOW | Sandbox only |
| F-08 | `security/middleware.py` | 30, 185, 189 | TYPE_SAFETY | 3 errors: list init, `re.search` with `str \| None`, `RateLimitError(str \| None)` | Add None coalescing | LOW | Security middleware |
| F-09 | `observability/log_rotation.py` | 50 | TYPE_SAFETY | `logger.info()` called with structured kwargs (`log_file=`, `strategy=`) — standard Logger doesn't accept these | Use `logger.info(msg, extra={...})` pattern | LOW | Log rotation only |
| F-10 | `tools/` layer | various | TYPE_SAFETY | ~60+ mypy errors across document processing, math viz, file compressor, git tools, docker tools | Batch fix per file | LOW | Tools only |

---

## 10. Test Suite Rationalization

### Current State
- 875 collected, 874 pass, 1 skip, 27 deselected (e2e + integration markers)
- No test failures (after aiohttp fix in Phase 0)

### Test Categories

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
| Slack interface importable (with aiohttp) | YES | `tests/unit/test_router.py` |

---

## 11. Architecture Assessment & Module Blueprint

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
| `observability.runtime_metrics` | Re-export shim | MCP_TOOL_USAGE, TOKENS_PER_SECOND, TTFT_MS, etc. | observability.metrics | agent_core, server |
| `protocols.mcp.mcp_registry` | MCP server connections | `register`, `call_tool`, `list_tools` | httpx | factories, agent_core |
| `interfaces.web.server` | FastAPI OpenAI endpoint | `WebInterface`, `create_app` | agent_core, security | lifecycle |
| `interfaces.telegram` | Telegram bot adapter | `TelegramInterface` | agent_core, security | lifecycle (optional) |
| `interfaces.slack` | Slack webhook adapter | `SlackInterface` | web interface; requires aiohttp via slack_sdk | lifecycle (optional) |
| `lifecycle` | Runtime bootstrap/shutdown | `Runtime`, `RuntimeContext` | all | cli, main |
| `memory.manager` | Long-term memory | `add_message`, `build_context_block` | core.db | agent_core |

### Architecture Strengths

1. **Clean DI pattern** — `DependencyContainer` wires everything; no hidden singletons in core path
2. **Dual-router justification** — two routers serve two distinct clients with appropriate complexity
3. **Exception hierarchy** — structured error codes allow interfaces to handle errors by type
4. **Workspace routing** — virtual models propagate through both routers
5. **Circuit breaker** — backend failures do not cascade; proper fallback chain
6. **HITL middleware** — high-risk tools gated; Redis-backed for persistence

### Remaining Architecture Concerns

1. **mypy coverage** — 103 errors remain, concentrated in tools layer and security/docker sandbox
2. **runtime_metrics.py** — backward compat shim still in use; needs caller migration before removal
3. **Type annotations in core** — `agent_interface.py` and `agent_core.py` have annotation inconsistencies

---

## 12. Evolution Gap Register

| ID | Area | Current State | Target State | Effort | Risk | Priority |
|----|------|--------------|--------------|--------|------|----------|
| EG-01 | **Inference routing** | Regex heuristics (100+ patterns) | LLM classifier call (ROADMAP #1) | M | LOW | P2-HIGH |
| EG-02 | **Apple Silicon inference** | Ollama only | MLX server backend (ROADMAP #2) | M | LOW | P3-MEDIUM |
| EG-03 | **mypy errors** | 103 errors in 28 files | Under 30 errors | M | LOW | P3-MEDIUM |
| EG-04 | **runtime_metrics.py** | Shim with 2 active callers | Migrate callers → delete shim | S | LOW | P3-MEDIUM |
| EG-05 | **log_rotation structured logging** | `logger.info(msg, log_file=...)` — stdlib doesn't accept extra kwargs | Use `logger.info(msg, extra={...})` pattern | S | LOW | P4-LOW |

---

## 13. Production Readiness Score

| Dimension | Score | Narrative |
|-----------|-------|-----------|
| **Env config separation** | 5/5 | Pydantic Settings with env override; class-scope reads eliminated |
| **Error handling / observability** | 4/5 | Structured logging, trace IDs, exception hierarchy, Prometheus metrics |
| **Security posture** | 4/5 | HMAC auth, input sanitization, rate limiting, CORS validation, HITL middleware |
| **Dependency hygiene** | 4/5 | aiohttp dep gap found and fixed; otherwise clean. No cloud deps, optional deps isolated |
| **Documentation completeness** | 5/5 | Excellent ARCHITECTURE.md, CLAUDE.md, ROADMAP.md, QUICKSTART.md |
| **Build / deploy hygiene** | 5/5 | Multi-platform launchers, Docker images pinned, CI matrix 3.11–3.14 |
| **Module boundary clarity** | 5/5 | Clean DI, direct imports; runtime_metrics shim documented |
| **Test coverage quality** | 5/5 | 875 tests, high behavioral coverage on critical paths, 0 failures |
| **Evolution readiness** | 4/5 | Regex routing is documented; LLM classifier and MLX backend are designed |

**Composite: 4.1/5 — STRONG**

The platform is fully functional for its stated purpose. The minor dip from 4.2 to 4.1 reflects the aiohttp dependency gap found and the correction of a prior false-positive finding. With TASK-23R and the remaining type safety work, this will return to 4.2+.
