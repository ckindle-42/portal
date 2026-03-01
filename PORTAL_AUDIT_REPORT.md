# Portal — Full Codebase Audit Report

**Date:** 2026-03-01
**Version audited:** 1.4.0
**Auditor:** Claude Code (claude-sonnet-4-6)
**Repository:** https://github.com/ckindle-42/portal

---

## 1. Executive Summary

**Health Score: 8.5 / 10 — STRONG (unchanged from prior)**

Portal 1.4.0 is in excellent shape. All Tier 1 tasks from the previous action prompt have been completed: security_module.py shim removed, tests updated to import directly, orphan branches pruned, and version bumped. Remaining work is primarily type safety (mypy) in lifecycle and telegram interfaces.

| # | Area | Prior | Current | Status |
|---|------|-------|---------|--------|
| 1 | **mypy errors** | 124 | 123 | UNCHANGED |
| 2 | **security_module.py** | shim removed, tests using it | FILE DELETED, tests updated | COMPLETE |
| 3 | **Version** | 1.3.9 | 1.4.0 | BUMPED |
| 4 | **Tests** | 874 | 875 | +1 |
| 5 | **Lint violations** | 0 | 0 | CLEAN |
| 6 | **Remote branches** | 11 orphans | 1 (origin/main only) | CLEAN |

**LOC breakdown:**
- Source (src/portal): ~15,800 lines across 97 Python files
- Tests: ~14,000 lines across 67 Python files
- Test/source ratio: ~0.89 (healthy)

**Parity risks from this audit:** NONE. No behavioral changes recommended in this audit.

---

## 2. Delta Summary

### Changes Since Prior Audit (2026-03-01)

| Metric | Prior | Current | Delta |
|--------|-------|---------|-------|
| Health Score | 8.5/10 | 8.5/10 | — |
| mypy errors | 124 | 123 | -1 |
| Test count | 874 | 875 | +1 |
| Version | 1.3.9 | 1.4.0 | +0.1 |
| Lint violations | 0 | 0 | — |
| Remote branches | 11 | 1 | -10 |

### Completed Work

- **TASK-20 (security_module.py import cleanup):** Updated 13 test files to import RateLimiter and InputSanitizer directly from `portal.security.rate_limiter` and `portal.security.input_sanitizer` instead of the shim.
- **TASK-21 (security_module.py deletion):** Deleted `src/portal/security/security_module.py` after confirming all imports were updated.
- **TASK-22 (orphan branch cleanup):** Pruned 10 stale remote tracking branches (5 AI agent + 5 dependabot branches).
- **Version bump:** Bumped to 1.4.0 in `__init__.py` and `pyproject.toml`.

### New Findings

| Category | Count | Notes |
|----------|-------|-------|
| mypy errors | 123 | lifecycle.py (~8), telegram interface (~10), slack interface (2), misc |
| Documentation sync | Minor | CLAUDE.md references ROADMAP.md; PORTAL_ROADMAP.md exists separately |

---

## 3. Git History Summary

### Commit Themes (Since Prior Audit)

| Commit Range | Theme | Status | Debt/TODOs Left |
|-------------|-------|--------|-----------------|
| 4b8a98a | Version bump to 1.4.0 | COMPLETE | None |
| ed6181a | docs(audit): update audit report | COMPLETE | None |
| e407996 | refactor(security): remove security_module.py shim | COMPLETE | None |

### Contributor Patterns

Single-owner project (ckindle-42) with AI-assisted development. Clear pattern of problem-identification → audit → targeted refactor → test verification.

### Unfinished Work Register

| Source | Description | Evidence | Priority |
|--------|------------|----------|----------|
| ROADMAP.md | LLM-Based Intelligent Routing | `ROADMAP.md` section 1 | P2-HIGH |
| ROADMAP.md | MLX Backend for Apple Silicon | `ROADMAP.md` section 2 | P3-MEDIUM |

---

## 4. Baseline Status

```
BASELINE STATUS
---------------
Tests:    PASS=874  FAIL=0  SKIP=1  ERROR=0  (875 collected, 27 deselected)
Lint:     VIOLATIONS=0 (ruff check passes)
Mypy:     ERRORS=123 in ~20 files (strict=false; not blocking CI)
API routes confirmed: YES
  - POST /v1/chat/completions  (server.py:359)
  - GET  /v1/models            (server.py:371)
  - GET  /health               (server.py:507)
  - WS   /ws                   (server.py:541)
  - POST /v1/audio/transcriptions (server.py:365)
  - GET  /health (router)      (router.py:138)
Python:   3.14.3
Proceed: YES
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
| `core/agent_core.py` | 657 | AgentCore — main orchestrator | CORE | STABLE | ~5 mypy errors |
| `core/context_manager.py` | 265 | SQLite conversation history | CORE | STABLE | — |
| `core/db.py` | 47 | Shared SQLite ConnectionPool | CORE | STABLE | — |
| `core/event_bus.py` | 215 | Async event pub/sub | CORE | STABLE | — |
| `core/exceptions.py` | 116 | Structured exception hierarchy | CORE | LOCKED | — |
| `core/factories.py` | 178 | DI container and dependency wiring | CORE | STABLE | ~2 mypy errors |
| `core/interfaces/agent_interface.py` | 194 | BaseInterface ABC | CORE | LOCKED | Fixed: config default |
| `core/interfaces/tool.py` | 153 | BaseTool ABC | CORE | LOCKED | — |
| `core/prompt_manager.py` | 129 | System prompt template loader | CORE | STABLE | — |
| `core/structured_logger.py` | 165 | JSON structured logger + TraceContext | CORE | STABLE | Fixed: token type |
| `core/types.py` | 97 | IncomingMessage, ProcessingResult, InterfaceType | CORE | LOCKED | — |
| `interfaces/telegram/interface.py` | 545 | Telegram bot adapter | ADAPTER | EVOLVING | ~10 mypy errors |
| `interfaces/web/server.py` | 754 | FastAPI WebInterface: routes, handlers | ADAPTER | STABLE | ~3 mypy errors |
| `interfaces/slack/interface.py` | 181 | Slack webhook adapter | ADAPTER | STABLE | 2 mypy errors |
| `lifecycle.py` | 345 | Runtime bootstrap/shutdown | INFRA | STABLE | ~8 mypy errors |
| `memory/manager.py` | 161 | MemoryManager (SQLite or Mem0) | CORE | STABLE | Fixed: env in constructor |
| `middleware/hitl_approval.py` | 56 | Redis-backed HITL approval | CORE | EVOLVING | — |
| `middleware/tool_confirmation_middleware.py` | 252 | Tool confirmation gate | CORE | STABLE | — |
| `observability/config_watcher.py` | 275 | YAML config hot-reload watcher | INFRA | STABLE | — |
| `observability/health.py` | 160 | K8s-style health check system | INFRA | STABLE | — |
| `observability/log_rotation.py` | 248 | Log file rotation | INFRA | STABLE | — |
| `observability/metrics.py` | 246 | Prometheus metrics collector + re-exports | INFRA | STABLE | — |
| `observability/runtime_metrics.py` | 13 | Re-export shim for backward compat | INFRA | CANDIDATE | Could be removed |
| `observability/watchdog.py` | 361 | Component health + auto-restart watchdog | INFRA | STABLE | 2 mypy errors |
| `protocols/mcp/mcp_registry.py` | 183 | MCP server connection registry | ADAPTER | STABLE | Fixed: NOTE removed |
| `routing/backend_registry.py` | 32 | ModelBackend instance registry | CORE | STABLE | — |
| `routing/circuit_breaker.py` | 91 | CircuitBreaker for backend health | CORE | STABLE | — |
| `routing/execution_engine.py` | 309 | Execution with circuit-breaker + fallback | CORE | STABLE | 1 mypy error |
| `routing/intelligent_router.py` | 217 | Task-based model selection | CORE | STABLE | — |
| `routing/model_backends.py` | 253 | OllamaBackend + BaseHTTPBackend | ADAPTER | STABLE | — |
| `routing/model_registry.py` | 249 | Model catalog and discovery | CORE | STABLE | — |
| `routing/router.py` | 291 | FastAPI Ollama proxy router (`:8000`) | ADAPTER | STABLE | — |
| `routing/task_classifier.py` | 274 | Regex heuristic task classifier | CORE | EVOLVING | Future: LLM classifier |
| `routing/workspace_registry.py` | 25 | Workspace-to-model mapping | CORE | STABLE | — |
| `security/auth/user_store.py` | 138 | SQLite RBAC user store | CORE | STABLE | 1 mypy error |
| `security/input_sanitizer.py` | 256 | Input sanitization and validation | CORE | STABLE | Fixed: emoji encoding |
| `security/middleware.py` | 284 | SecurityMiddleware wrapper | CORE | STABLE | Fixed: direct imports |
| `security/rate_limiter.py` | 192 | Sliding-window rate limiter with persistence | CORE | STABLE | — |
| `security/sandbox/docker_sandbox.py` | 406 | Docker sandbox for code execution | INFRA | STABLE | Fixed: None guards |
| `tools/` | ~4200 | Tool implementations | ADAPTER | EVOLVING | Various mypy errors |

---

## 7. Documentation Drift Report

| File | Issue | Current Text | Required Correction | Impact |
|------|-------|-------------|---------------------|--------|
| CLAUDE.md | References ROADMAP.md | `ROADMAP.md` | Could reference `PORTAL_ROADMAP.md` for unified roadmap | LOW |
| `runtime_metrics.py` | Backward compat shim | Re-exports from metrics | Could be removed (no production callers) | LOW |

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
  portal.core.db                -- used by context_manager, memory, auth
  portal.security.input_sanitizer -- used by middleware

LOW COUPLING (isolated, healthy):
  portal.observability.watchdog     -- lifecycle only
  portal.observability.config_watcher -- lifecycle only
  portal.observability.log_rotation   -- lifecycle only
  portal.protocols.mcp               -- factories, agent_core only
  portal.middleware.hitl_approval    -- agent_core only
```

No circular imports detected. All `TYPE_CHECKING` guards properly used.

---

## 9. Code Findings Register

| # | File | Lines | Category | Finding | Action | Risk | Blast Radius |
|---|------|-------|----------|---------|--------|------|--------------|
| F-01 | `lifecycle.py` | 88, 160, 162, 204, 332, 335, 341 | TYPE_SAFETY | ~8 errors: StructuredLogger kwargs, RuntimeContext None checks | Future iteration | LOW | Lifecycle only |
| F-02 | `interfaces/telegram/interface.py` | 171, 175, 222, 272, 293, 381, 468, 474, 483 | TYPE_SAFETY | ~10 remaining errors: User.id, Message.reply_text, process_message args | Future iteration | LOW | Telegram only |
| F-03 | `interfaces/slack/interface.py` | 171, __init__ | TYPE_SAFETY | 2 errors: send_message signature, __init__ assignment | Future iteration | LOW | Slack only |
| F-04 | `observability/runtime_metrics.py` | full file | DEAD_CODE_CANDIDATE | Backward compat shim, no production callers | Consider removal | LOW | None if removed |

---

## 10. Test Suite Rationalization

### Current State
- 875 collected, 874 pass, 1 skip, 27 deselected (e2e + integration markers)

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
| `/v1/models` Ollama-unreachable fallback | YES | `tests/integration/test_web_interface.py` |
| OpenAI `usage` field | YES | `tests/integration/test_web_interface.py` |

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
4. **Workspace routing** — virtual models propagate through both routers
5. **Circuit breaker** — backend failures do not cascade; proper fallback chain
6. **HITL middleware** — high-risk tools gated; Redis-backed for persistence

### Remaining Improvements

1. **mypy coverage** — 123 errors remain in lifecycle.py, telegram, slack
2. **runtime_metrics.py** — backward compat shim could be removed
3. **Branch cleanup** — completed (1 remote branch remains: origin/main)

---

## 12. Evolution Gap Register

| ID | Area | Current State | Target State | Effort | Risk | Priority |
|----|------|--------------|--------------|--------|------|----------|
| EG-01 | **Inference routing** | Regex heuristics (100+ patterns) | LLM classifier call (ROADMAP #1) | M | LOW | P2-HIGH |
| EG-02 | **Apple Silicon inference** | Ollama only | MLX server backend (ROADMAP #2) | M | LOW | P3-MEDIUM |
| EG-03 | **mypy errors** | 123 errors in ~20 files | Under 30 errors | M | LOW | P3-MEDIUM |
| EG-04 | **runtime_metrics.py** | Kept for backward compat | Consider removal | S | LOW | P4-LOW |

---

## 13. Production Readiness Score

| Dimension | Score | Narrative |
|-----------|-------|-----------|
| **Env config separation** | 5/5 | Pydantic Settings with env override; class-scope reads eliminated |
| **Error handling / observability** | 4/5 | Structured logging, trace IDs, exception hierarchy, Prometheus metrics |
| **Security posture** | 4/5 | HMAC auth, input sanitization, rate limiting, CORS validation, HITL middleware |
| **Dependency hygiene** | 5/5 | No cloud deps, pinned in uv.lock, Dependabot configured, all optional deps isolated |
| **Documentation completeness** | 5/5 | Excellent ARCHITECTURE.md, CLAUDE.md, ROADMAP.md, QUICKSTART.md |
| **Build / deploy hygiene** | 5/5 | Multi-platform launchers, Docker images pinned, CI matrix 3.11–3.14 |
| **Module boundary clarity** | 5/5 | Clean DI, direct imports, security_module shim removed |
| **Test coverage quality** | 5/5 | 875 tests, high behavioral coverage on critical paths |
| **Evolution readiness** | 4/5 | Regex routing is documented; LLM classifier and MLX backend are designed |

**Composite: 4.2/5 — STRONG (unchanged from 8.5/10)**

The platform is fully functional for its stated purpose. Remaining gaps are concentrated in type safety (mypy) and minor cleanup items — not in the critical inference path.
