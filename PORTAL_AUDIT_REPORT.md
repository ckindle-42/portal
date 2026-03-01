# Portal v1.3.8 — Comprehensive Audit Report

**Generated:** 2026-03-01
**Branch:** `claude/audit-ci-hardening-6qD0L`
**Auditor:** Claude Code (claude-sonnet-4-6)
**Mandate:** Full codebase audit — remediate defects, identify evolution targets

---

## Executive Summary

**Health Score: 7.5 / 10 — STRONG**

Portal 1.3.8 is a well-architected, production-suitable local AI platform. The codebase
demonstrates engineering maturity: Pydantic v2 validation, async-first design, circuit
breakers, structured logging, and strong startup-time secret validation. The test suite
is large (847 tests), high-value, and correctly behaviorally focused.

**Top 5 Remediation Findings:**

| # | Finding | Severity | File(s) |
|---|---------|----------|---------|
| R1 | 20 bare `except Exception:` handlers masking real errors | HIGH | Scattered (11 files) |
| R2 | `os.getenv()` scattered in `web/server.py` instead of Settings | HIGH | `interfaces/web/server.py` |
| R3 | `print()` statements in production tool code (not CLI) | MEDIUM | `tools/knowledge/local_knowledge.py` ✅ fixed |
| R4 | CORS origin parsing lacks URL validation | MEDIUM | `interfaces/web/server.py:74-80` |
| R5 | `aiohttp` dual-client alongside `httpx` | MEDIUM | `routing/model_backends.py` |

**Top 5 Evolution Findings:**

| # | Finding | Priority | Effort |
|---|---------|----------|--------|
| E1 | Backend wiring is hardcoded in `ExecutionEngine.__init__()` — not pluggable | P2-HIGH | 1 day |
| E2 | Workspace routing split between `router.py` (proxy) and `IntelligentRouter` (AgentCore) | P2-HIGH | 1 day |
| E3 | No async task queue — long inference (30–120s) blocks HTTP requests | P3-MEDIUM | 2-3 days |
| E4 | 5 missing contract tests for OpenAI API surface | P2-HIGH | 2 hours |
| E5 | Documentation drift: 6 stale entries across CLAUDE.md, ARCHITECTURE.md, CONTRIBUTING.md | P3-MEDIUM | ✅ fixed |

**LOC Breakdown:**

| Layer | Files | LOC |
|-------|-------|-----|
| Core (agent, config, context, factories, types) | 14 | 2,011 |
| Interfaces (web, telegram, slack) | 7 | 1,425 |
| Routing (engine, router, backends, registry) | 8 | 1,551 |
| Security (middleware, sandbox, auth, rate limiter) | 9 | 1,217 |
| Observability (health, metrics, watchdog, log rotation) | 6 | 1,091 |
| Tools (all categories) | 37 | 5,034 |
| Memory & Persistence | 3 | 313 |
| Protocols/MCP | 3 | 213 |
| Middleware | 2 | 352 |
| CLI & Lifecycle | 2 | 486 |
| **TOTAL** | **96** | **14,816** |

---

## Baseline Status

```
BASELINE STATUS
---------------
Tests:    PASS=844  FAIL=0  SKIP=3  ERROR=0
Lint:     VIOLATIONS=0
API routes confirmed:
  POST /v1/chat/completions    → interfaces/web/server.py:296
  GET  /v1/models              → interfaces/web/server.py:308
  GET  /health                 → interfaces/web/server.py:448, observability/health.py:136
Proceed: YES
```

**CI Fixes Applied (committed to branch):**

| Fix | File | Reason |
|-----|------|--------|
| Guard `telegram` import with `BaseException` | `tests/unit/test_router.py` | `pyo3_runtime.PanicException` not caught by `except Exception:` in broken env |
| Guard `pypdf` import with `BaseException` | `tests/unit/tools/test_document_tools.py` | Same env issue with broken `cryptography` native module |
| Fix websocket error assertion | `tests/integration/test_websocket.py` | Message format changed to include character count; test was stale |

---

## Public Surface Inventory

| Endpoint | Method | Auth Required | File:Line | Notes |
|----------|--------|---------------|-----------|-------|
| `/v1/chat/completions` | POST | Yes (if `WEB_API_KEY` set) | `server.py:296` | Streaming + non-streaming; SSE or JSON |
| `/v1/models` | GET | Yes (if `WEB_API_KEY` set) | `server.py:308` | OpenAI-compatible model list |
| `/v1/audio/transcriptions` | POST | Yes (if `WEB_API_KEY` set) | `server.py:302` | Forwards to Whisper at `WHISPER_URL` |
| `/health` | GET | No | `server.py:448` | Returns version, status, agent_core state |
| `/health/live` | GET | No | `health.py:128` | Liveness probe |
| `/health/ready` | GET | No | `health.py:132` | Readiness probe |
| `/ws` | WebSocket | Yes (query param `api_key`) | `server.py:481` | Real-time streaming; rate-limited |
| `/metrics` | GET | No | `metrics.py` | Prometheus metrics |
| Router proxy | All | Token (if set) | `routing/router.py:8000` | Ollama proxy with workspace routing |

---

## File Inventory Table

| File Path | LOC | Purpose | Layer | Stability | Flags |
|-----------|-----|---------|-------|-----------|-------|
| `src/portal/__init__.py` | 10 | Version metadata | CORE | LOCKED | None |
| `src/portal/cli.py` | 139 | CLI: up/down/doctor/logs | API | STABLE | None |
| `src/portal/lifecycle.py` | 347 | Runtime bootstrap & graceful shutdown | CORE | STABLE | Strong secret validation |
| `src/portal/config/__init__.py` | 1 | Empty init | CORE | STABLE | Dead export file |
| `src/portal/config/settings.py` | 454 | Pydantic v2 settings with validators | CORE | LOCKED | Best-in-codebase |
| `src/portal/core/__init__.py` | 32 | Public API exports | CORE | LOCKED | None |
| `src/portal/core/agent_core.py` | 657 | Main orchestrator (process_message, MCP loop) | CORE | EVOLVING | 2× bare `except Exception:` |
| `src/portal/core/event_bus.py` | 215 | Async pub/sub system | CORE | STABLE | None |
| `src/portal/core/exceptions.py` | 117 | Structured error codes | CORE | STABLE | None |
| `src/portal/core/context_manager.py` | 265 | Conversation history (SQLite) | CORE | STABLE | None |
| `src/portal/core/db.py` | ~40 | SQLite connection pool | CORE | STABLE | None |
| `src/portal/core/factories.py` | 110 | Dependency injection container | CORE | STABLE | None |
| `src/portal/core/prompt_manager.py` | ~120 | Prompt template management | CORE | STABLE | None |
| `src/portal/core/structured_logger.py` | 165 | Structured logging with trace IDs | CORE | STABLE | None |
| `src/portal/core/types.py` | 97 | Core type definitions | CORE | LOCKED | None |
| `src/portal/core/interfaces/tool.py` | ~60 | BaseTool ABC | CORE | LOCKED | None |
| `src/portal/core/interfaces/agent_interface.py` | ~40 | AgentInterface ABC | CORE | LOCKED | None |
| `src/portal/interfaces/web/server.py` | 695 | FastAPI web server (primary interface) | ADAPTER | EVOLVING | 5× bare except; 11× os.getenv; CORS lacks validation |
| `src/portal/interfaces/telegram/interface.py` | 549 | Telegram bot interface | ADAPTER | STABLE | None |
| `src/portal/interfaces/slack/interface.py` | 181 | Slack bot interface | ADAPTER | STABLE | None |
| `src/portal/protocols/mcp/mcp_registry.py` | 183 | MCP server registry & tool dispatch | ADAPTER | STABLE | None |
| `src/portal/middleware/hitl_approval.py` | ~100 | HITL approval (Redis) | ADAPTER | STABLE | Optional feature |
| `src/portal/middleware/tool_confirmation_middleware.py` | 252 | Tool execution confirmation | ADAPTER | STABLE | None |
| `src/portal/agent/dispatcher.py` | 68 | Interface registry (decorator pattern) | CORE | STABLE | None |
| `src/portal/routing/router.py` | 277 | Ollama proxy with workspace routing | INFRA | EVOLVING | 3× os.getenv; workspace not shared with IntelligentRouter |
| `src/portal/routing/execution_engine.py` | 308 | Model execution + circuit breaker | CORE | STABLE | Backend hardcoded at init |
| `src/portal/routing/intelligent_router.py` | 186 | Routing strategy selection | CORE | STABLE | No workspace concept |
| `src/portal/routing/task_classifier.py` | 274 | Task classification (heuristic) | CORE | CANDIDATE | Prototype for planned LLM classifier |
| `src/portal/routing/model_registry.py` | 249 | Model metadata & discovery | CORE | STABLE | TODO: aiohttp→httpx noted |
| `src/portal/routing/model_backends.py` | 257 | Ollama backend (BaseHTTPBackend) | CORE | EVOLVING | aiohttp; TODO(Track B) noted |
| `src/portal/routing/circuit_breaker.py` | ~80 | Circuit breaker pattern | CORE | STABLE | None |
| `src/portal/security/middleware.py` | 284 | Security middleware wrapper | CORE | STABLE | None |
| `src/portal/security/input_sanitizer.py` | 245 | Input validation & sanitization | CORE | STABLE | None |
| `src/portal/security/rate_limiter.py` | 192 | Request rate limiting (JSON persistence) | CORE | STABLE | Not Redis-backed |
| `src/portal/security/sandbox/docker_sandbox.py` | 406 | Docker sandbox for code execution | INFRA | STABLE | 1× bare except |
| `src/portal/security/security_module.py` | ~80 | Security aggregator | CORE | STABLE | None |
| `src/portal/security/auth/user_store.py` | ~100 | User auth & bootstrap | CORE | STABLE | None |
| `src/portal/observability/health.py` | 160 | Component health check system | INFRA | STABLE | `print()` in CLI function (intentional) |
| `src/portal/observability/metrics.py` | 247 | Prometheus metrics | INFRA | STABLE | 1× bare except |
| `src/portal/observability/watchdog.py` | 361 | Health watchdog with restart capability | INFRA | STABLE | 1× bare except |
| `src/portal/observability/log_rotation.py` | 248 | Log file rotation & compression | INFRA | STABLE | `print()` to stderr in error path (acceptable) |
| `src/portal/observability/config_watcher.py` | 275 | Config hot-reload | INFRA | STABLE | `print()` in docstring example only |
| `src/portal/memory/manager.py` | 163 | Long-term memory (Mem0 or SQLite) | CORE | EVOLVING | type: ignore on Mem0 |
| `src/portal/tools/knowledge/local_knowledge.py` | 302 | Local knowledge base (JSON/RAG) | INFRA | STABLE | ✅ print→logger fixed |
| `src/portal/tools/knowledge/knowledge_base_sqlite.py` | 502 | SQLite knowledge store | INFRA | STABLE | Complex; lacks logger |
| `src/portal/tools/document_processing/excel_processor.py` | 404 | Excel file operations | INFRA | STABLE | None |
| `src/portal/tools/document_processing/word_processor.py` | 356 | Word document operations | INFRA | STABLE | None |
| `src/portal/tools/document_processing/powerpoint_processor.py` | 350 | PowerPoint operations | INFRA | STABLE | None |
| `src/portal/tools/document_processing/pandoc_converter.py` | 289 | Pandoc document conversion | INFRA | STABLE | 1× bare except at module level |
| `src/portal/tools/document_processing/document_metadata_extractor.py` | 330 | Document metadata extraction | INFRA | STABLE | None |
| `src/portal/tools/git_tools/git_tool.py` | 359 | Git operations | INFRA | STABLE | 1× bare except |
| `src/portal/tools/data_tools/text_transformer.py` | ~120 | Text transformation tools | INFRA | STABLE | 2× bare except |
| `src/portal/tools/web_tools/http_client.py` | ~80 | HTTP client wrapper | INFRA | STABLE | aiohttp; 1× bare except |
| `src/portal/tools/docker_tools/docker_tool.py` | 228 | Docker operations | INFRA | STABLE | None |
| `src/portal/tools/dev_tools/python_env_manager.py` | ~130 | Python venv manager | INFRA | STABLE | subprocess.run (non-async context; OK) |

---

## Documentation Drift Table

| File | Issue | Current Text | Required Correction | Impact | Status |
|------|-------|--------------|---------------------|--------|--------|
| `CLAUDE.md:33` | Python upper bound stale | `3.11+ required, <3.13` | `3.11+ required` (no upper bound) | HIGH | ✅ Fixed |
| `docs/ARCHITECTURE.md:443` | Version number stale | `version = "1.3.4"` | `version = "1.3.8"` | LOW | ✅ Fixed |
| `CONTRIBUTING.md:11` | Install command includes unnecessary extras | `pip install -e ".[all,dev]"` | `pip install -e ".[dev]"` | LOW | ✅ Fixed |
| `CONTRIBUTING.md:37` | Deprecated mypy flag | `mypy src/portal --ignore-missing-imports` | `mypy src/portal` | LOW | ✅ Fixed |
| `README.md` | `/ws` endpoint not documented | — | Add WebSocket endpoint to public surface table | MED | Open |
| `README.md` | `/v1/audio/transcriptions` not documented | — | Add audio transcription endpoint to public surface | MED | Open |
| `.env.example` | `ALLOW_LEGACY_PICKLE_EMBEDDINGS` missing | Not present | Add with `false` default and description | LOW | Open |
| `QUICKSTART.md:21,79` | Pins python3.11 specifically | `brew install ... python@3.11` | Note that 3.12+ also supported | MED | Open |
| `docs/ARCHITECTURE.md:157` | MLX backend section misleads readers | "MLXBackend is a separate in-process backend" | Clarify MLX is planned (ROADMAP.md), not current | MED | Open |

---

## Dependency Heatmap

| Module | Inbound Deps | Outbound Deps | Blast Radius | Risk |
|--------|-------------|---------------|--------------|------|
| `core/types.py` | 12 | 0 | **CRITICAL** — breaks everything if changed | LOCKED |
| `core/interfaces/tool.py` | 37 (all tools) | 1 | HIGH — changing BaseTool breaks all tools | LOCKED |
| `config/settings.py` | 8 | 2 | HIGH — all components depend on Settings | LOCKED |
| `core/factories.py` | 3 | 8 | HIGH — wires all components together | STABLE |
| `core/agent_core.py` | 4 (interfaces) | 7 | HIGH — central orchestrator | EVOLVING |
| `routing/execution_engine.py` | 2 | 3 | MED — change affects routing layer | STABLE |
| `routing/model_backends.py` | 1 (execution_engine) | 1 (aiohttp) | MED — isolated; adding backends needs ExecutionEngine edit | EVOLVING |
| `security/middleware.py` | 3 | 3 | MED — security stack | STABLE |
| `interfaces/web/server.py` | 0 (entry point) | 6 | LOW — changes don't cascade | EVOLVING |

---

## Code Findings Register

### Category: BUG / ERROR_HANDLING

| ID | File | Lines | Category | Finding | Action | Risk | Blast Radius |
|----|------|-------|----------|---------|--------|------|--------------|
| B1 | `interfaces/web/server.py` | 211 | BUG | `except Exception: pass` suppresses agent warmup errors silently | Log at WARNING level: `logger.warning("Agent warmup failed", exc_info=True)` | LOW | None — warmup continues regardless |
| B2 | `interfaces/web/server.py` | 420 | BUG | `except Exception:` on Ollama model list — falls back to hardcoded `["auto"]` | Narrow to `httpx.ConnectError, httpx.TimeoutException` | LOW | None — fallback is correct |
| B3 | `interfaces/web/server.py` | 469,476 | BUG | `except Exception:` on health check — returns `degraded` without logging | Add `logger.warning("Health check error", exc_info=True)` | LOW | None |
| B4 | `interfaces/web/server.py` | 567 | BUG | `except Exception: pass` on WebSocket error send — swallows send errors | `except (RuntimeError, WebSocketDisconnect): pass` (correct types) | LOW | None |
| B5 | `core/agent_core.py` | 98 | BUG | `except Exception:` on Redis HITL init — already logs at WARNING; OK as fallback | Narrow to `ConnectionError, OSError, ImportError` | LOW | None |
| B6 | `core/agent_core.py` | 507 | BUG | `except Exception: return False` on health check | Narrow to `Exception` → already specific enough; add `exc_info=True` log | LOW | None |
| B7 | `routing/model_backends.py` | 244 | BUG | `except Exception:` on aiohttp streaming — swallows parse errors | Narrow to `aiohttp.ClientError, json.JSONDecodeError` | MEDIUM | Execution engine error handling |
| B8 | `observability/watchdog.py` | 293 | BUG | `except Exception:` in watchdog loop — prevents crash but hides errors | Narrow to `asyncio.CancelledError` (re-raise) + log others | LOW | Watchdog continues |
| B9 | `observability/metrics.py` | 47 | BUG | `except Exception:` on metrics registration — metric silently absent | Narrow to `ValueError` (duplicate registration) | LOW | Metrics dashboard missing gauge |
| B10 | `tools/document_processing/pandoc_converter.py` | 31 | BUG | `except Exception:` at module level on pandoc version check | Narrow to `FileNotFoundError, subprocess.SubprocessError` | LOW | Tool marks pandoc unavailable |

### Category: SECURITY

| ID | File | Lines | Category | Finding | Action | Risk | Blast Radius |
|----|------|-------|----------|---------|--------|------|--------------|
| S1 | `interfaces/web/server.py` | 74-80 | SECURITY | CORS origin parsing splits on comma with no URL validation | Validate each origin with `urllib.parse.urlparse()` or `pydantic.HttpUrl` | MEDIUM | Could accept malformed CORS origin |
| S2 | `interfaces/web/server.py` | 147-156 | SECURITY | `WEB_API_KEY` read from `os.getenv()` not from Settings — bypasses validation | Move to `SecurityConfig` in `settings.py` | MEDIUM | Scattered config source |
| S3 | `routing/router.py` | ~20 | SECURITY | `ROUTER_TOKEN` read from `os.getenv()` not Settings | Move to `RoutingConfig` in `settings.py` | LOW | Proxy auth only |
| S4 | `observability/log_rotation.py` | 232,236 | SECURITY | `print()` to stderr in log rotation error path | Acceptable — logger may be unavailable during rotation | IGNORE | — |

### Category: LEGACY_ARTIFACT / TECHNICAL DEBT

| ID | File | Lines | Category | Finding | Action | Risk | Blast Radius |
|----|------|-------|----------|---------|--------|------|--------------|
| L1 | `routing/model_backends.py` | 13, 88-92 | LEGACY_ARTIFACT | `aiohttp.ClientSession` used while `httpx` is already a core dep | Migrate to `httpx.AsyncClient` (see TODO(Track B) comment) | MEDIUM | Must update ExecutionEngine session handling |
| L2 | `tools/web_tools/http_client.py` | 31 | LEGACY_ARTIFACT | `aiohttp` imported conditionally — second use of aiohttp in tools | Migrate to `httpx` | LOW | Tool-local change |
| L3 | `interfaces/web/server.py` | 147+ | LEGACY_ARTIFACT | 11× `os.getenv()` calls should be centralized in Settings | Move `WEB_API_KEY`, `WEB_PORT`, `PORTAL_MAX_AUDIO_MB`, `WHISPER_URL`, etc. to `settings.py` | MEDIUM | All server config reads change |

### Category: TYPE_SAFETY

| ID | File | Category | Finding | Action | Risk |
|----|------|----------|---------|--------|------|
| T1 | Multiple | TYPE_SAFETY | 244 occurrences of `Any` in type hints — primarily in config dicts and tool params | Create TypedDict for `DependencyContainer`, `ExecutionConfig`; use Literal for enums | LOW |
| T2 | `routing/router.py` | TYPE_SAFETY | `call_next` parameter in `dispatch()` lacks type annotation | Add `from starlette.types import ASGIApp` annotation | LOW |
| T3 | `memory/manager.py` | TYPE_SAFETY | `# type: ignore` on Mem0 import | Add conditional TYPE_CHECKING import | LOW |

### Category: OBSERVABILITY

| ID | File | Lines | Category | Finding | Action |
|----|------|-------|----------|---------|--------|
| O1 | `tools/knowledge/local_knowledge.py` | 67,242,261,274,294-302 | OBSERVABILITY | 8× `print()` in production I/O paths | ✅ **Fixed** — replaced with `logger.*` calls |
| O2 | `tools/knowledge/knowledge_base_sqlite.py` | Multiple | OBSERVABILITY | No logger setup; uses no structured logging | Add `logger = logging.getLogger(__name__)` |

---

## Test Suite Rationalization

**Summary:** 847 tests collected, all behavioral contracts. Zero tests to DELETE. Zero
tests that check constants or module structure.

| Decision | Count | Notes |
|----------|-------|-------|
| KEEP | 847 | All test behavioral contracts |
| DELETE | 0 | No dead tests found |
| CONSOLIDATE | 0 | No significant duplication |
| ADD_MISSING | 5 | See below |

### Missing Contract Tests (ADD_MISSING)

| ID | Contract | Gap | File to Add | Priority |
|----|----------|-----|-------------|----------|
| TC1 | `GET /v1/models` Ollama fallback | No test verifies `/v1/models` returns list when Ollama unreachable | `tests/integration/test_web_interface.py` | HIGH |
| TC2 | `POST /v1/chat/completions` usage field | Non-streaming response `usage` field not validated | `tests/integration/test_web_interface.py` | HIGH |
| TC3 | `POST /v1/audio/transcriptions` success schema | No positive test for successful transcription response schema | `tests/integration/test_web_interface.py` | MED |
| TC4 | WebSocket rate limit violation | Rate limiter fires after N messages per connection | `tests/integration/test_websocket.py` | MED |
| TC5 | `@model:name` routing override | Manual model override in message content not tested | `tests/integration/test_routing.py` | MED |

### Critical Contract Coverage — Current State

| Contract | Status | File |
|----------|--------|------|
| `GET /health` 200 response | ✅ Covered | `test_web_interface.py:56-109` |
| `GET /health` security headers | ✅ Covered | `test_web_interface.py:118-129` |
| `GET /v1/models` OpenAI schema | ✅ Covered | `test_web_interface.py:138-149` |
| `GET /v1/models` 401 without key | ✅ Covered | `test_web_interface.py:176-204` |
| `POST /v1/chat/completions` streaming SSE | ✅ Covered | `test_web_interface.py:263-282` |
| `POST /v1/chat/completions` non-streaming JSON | ✅ Covered | `test_web_interface.py:286-307` |
| `POST /v1/chat/completions` 503 during warmup | ✅ Covered | `test_web_interface.py:348-382` |
| `POST /v1/chat/completions` SSE usage block | ✅ Covered | `test_stream_response.py:157-179` |
| `POST /v1/audio/transcriptions` 413 oversized | ✅ Covered | `test_web_interface.py:37-67` |
| WebSocket auth | ✅ Covered | `test_websocket.py:55-100` |
| Auth middleware 401 | ✅ Covered | `test_web_interface.py:176-204` |
| MCP tool loop | ✅ Covered | `test_mcp_tool_loop.py` |
| Workspace/intelligent routing | ✅ Covered | `test_intelligent_router.py` |
| Circuit breaker | ✅ Covered | `test_circuit_breaker.py` |
| Slack HMAC validation | ✅ Covered | `test_slack_hmac.py` |
| HITL approval middleware | ✅ Covered | `test_human_in_loop_middleware.py` |

---

## Architecture Assessment & Module Blueprint

### Current Architecture Evaluation

**Module Boundaries:** GOOD — layers are well-defined. Clean separation between
API (interfaces), Core (agent, context, types), Adapter (MCP, memory), Infra (security,
observability, routing), Tools.

**Dependency Direction:** GOOD — API → Core → Adapter → Infra. No reverse dependencies
detected. No circular imports.

**Config Management:** GOOD — Pydantic v2 with env overrides. One gap: `os.getenv()`
scattered in `web/server.py` and `router.py` should be in Settings.

**Workspace System:** WEAK — Workspaces exist only in the Ollama proxy (`router.py`).
The `IntelligentRouter` in `AgentCore` has no workspace concept. Telegram/Slack/WebSocket
callers cannot use workspace routing.

**MCP Decoupling:** GOOD — `MCPRegistry` is a clean adapter. AgentCore doesn't know
about MCP protocol internals.

**Channel Adapter Isolation:** GOOD — Each interface (Web, Telegram, Slack) is a
standalone module that self-registers via `@CentralDispatcher.register()`.

### Module Blueprint Table (Proposed Improvements)

| Module (Proposed) | Responsibility | Public API | Depends On | Used By |
|-------------------|---------------|-----------|-----------|---------|
| `routing/backend_registry.py` | Backend registration & discovery | `register(name, backend)`, `get(name)` | `model_backends.py` | `execution_engine.py` |
| `routing/workspace_registry.py` | Centralized workspace→model mapping | `get_workspace(id)`, `list_workspaces()` | `config/settings.py` | `router.py`, `intelligent_router.py` |
| `config/settings.py` ← add `WEB_API_KEY` | Move all scattered `os.getenv()` calls here | `settings.security.web_api_key` | `pydantic-settings` | `server.py`, `router.py` |

---

## Evolution Gap Register

| ID | Area | Current State | Target State | Effort | Risk | Priority |
|----|------|---------------|-------------|--------|------|----------|
| EG1 | Backend abstraction | `OllamaBackend` hardcoded in `ExecutionEngine.__init__()` line 45; adding new backend requires source edit | `BackendRegistry.register(name, backend)` called from `factories.py`; backends configured via Settings | 1 day | MED | **P2-HIGH** |
| EG2 | Workspace routing | Split: proxy router (port 8000) has workspaces; IntelligentRouter (AgentCore) has none | `WorkspaceRegistry` shared by both; single source of truth | 1 day | MED | **P2-HIGH** |
| EG3 | Missing contract tests | 5 API surface contracts untested | All contracts tested including Ollama fallback and usage fields | 2 hours | LOW | **P2-HIGH** |
| EG4 | aiohttp→httpx migration | `model_backends.py` and `tools/web_tools/http_client.py` use aiohttp; rest uses httpx | Consolidate on httpx; remove aiohttp dependency | 0.5 day | LOW | **P3-MEDIUM** |
| EG5 | Settings centralization | 11× `os.getenv()` in `server.py`, 3× in `router.py` | All config via Settings (zero scattered `os.getenv`) | 0.5 day | LOW | **P3-MEDIUM** |
| EG6 | CORS validation | Origin strings split on comma, no URL format check | Validate each origin with `urllib.parse` | 2 hours | LOW | **P3-MEDIUM** |
| EG7 | Bare except narrowing | 20× `except Exception:` across 11 files | Specific exception types; preserve logging | 0.5 day | LOW | **P3-MEDIUM** |
| EG8 | knowledge_base_sqlite.py logger | No logger; uses no structured logging | Add `logger = logging.getLogger(__name__)` | 1 hour | LOW | **P4-LOW** |
| EG9 | Async task queue | Long inference blocks HTTP request (no polling) | Optional asyncio queue for background generation | 2-3 days | HIGH | **P4-LOW** (not in roadmap) |
| EG10 | README endpoint docs | `/ws` and `/v1/audio/transcriptions` not documented | Add to README and QUICKSTART | 1 hour | LOW | **P3-MEDIUM** |

---

## Production Readiness Score

| Dimension | Score | Narrative |
|-----------|-------|-----------|
| **Env config separation** | 3/5 | Settings.py is excellent; scattered `os.getenv()` in server.py and router.py undermine it |
| **Error handling & observability** | 4/5 | Structured logging, Prometheus, watchdog, circuit breakers — excellent. 20 bare excepts lose specific context |
| **Security posture** | 4/5 | Startup secret validation, hmac.compare_digest, rate limiting, Docker sandbox. CORS validation gap. |
| **Dependency hygiene** | 4/5 | Clean pyproject.toml with optional extras. Dual aiohttp/httpx client is minor debt. |
| **Documentation completeness** | 3/5 | Core docs accurate; stale version numbers, missing endpoint docs, Python version constraint (fixed) |
| **Build/deploy hygiene** | 5/5 | Dockerfile (non-root, healthcheck), docker-compose variants, Makefile, systemd, hardware-specific launchers |
| **Module boundary clarity** | 4/5 | Clean layers, no circular imports. Workspace routing split is the one architectural seam issue. |
| **Test coverage quality** | 5/5 | 847 behavioral tests, all earning their place; comprehensive API contract coverage |
| **Evolution readiness** | 3/5 | Hardcoded backend wiring; workspace not centralized; aiohttp migration pending |

**Composite Score: 3.9/5 — STRONG**

Portal is production-ready for its current scope (single-backend Ollama, localhost deployment).
The identified gaps are structural improvements for the next growth phase, not blockers.

---

## Prioritized Work Plan

### Tier 1 — Remediation (Do First, Low Risk)

| Task | File(s) | Category | Action |
|------|---------|----------|--------|
| T1-1 | `tests/unit/test_router.py` | BUG | ✅ Guard telegram import with BaseException |
| T1-2 | `tests/unit/tools/test_document_tools.py` | BUG | ✅ Guard pypdf import with BaseException |
| T1-3 | `tests/integration/test_websocket.py` | BUG | ✅ Fix stale error message assertion |
| T1-4 | `tools/knowledge/local_knowledge.py` | OBSERVABILITY | ✅ Replace 8× print() with logger calls |
| T1-5 | `CLAUDE.md`, `docs/ARCHITECTURE.md` | DOCS | ✅ Fix Python version constraint and version number |
| T1-6 | `CONTRIBUTING.md` | DOCS | ✅ Fix install command and mypy flag |
| T1-7 | `interfaces/web/server.py:211` | BUG | Add `logger.warning()` to warmup exception handler |
| T1-8 | `routing/model_backends.py:244` | BUG | Narrow bare except to `aiohttp.ClientError, json.JSONDecodeError` |
| T1-9 | `tools/document_processing/pandoc_converter.py:31` | BUG | Narrow to `FileNotFoundError, subprocess.SubprocessError` |
| T1-10 | Add 5 missing contract tests | TEST | See TC1-TC5 in test rationalization |
| T1-11 | `README.md` | DOCS | Document `/ws` and `/v1/audio/transcriptions` endpoints |

### Tier 2 — Structural Refactors (After Tier 1 Complete)

| Task | File(s) | Category | Action |
|------|---------|----------|--------|
| T2-1 | `config/settings.py` + `interfaces/web/server.py` | CONFIG_HARDENING | Move all scattered `os.getenv()` calls to Settings |
| T2-2 | `routing/model_backends.py` + `tools/web_tools/http_client.py` | LEGACY_ARTIFACT | Migrate aiohttp → httpx |
| T2-3 | `interfaces/web/server.py:74-80` | SECURITY | Add URL validation to CORS origin parsing |
| T2-4 | Remaining bare except handlers (B2-B10) | BUG | Narrow to specific exception types throughout |
| T2-5 | `tools/knowledge/knowledge_base_sqlite.py` | OBSERVABILITY | Add structured logger |

### Tier 3 — Evolution (After Tier 2 Complete)

| Task | File(s) | Category | Action |
|------|---------|----------|--------|
| T3-1 | `routing/backend_registry.py` (new) | ARCHITECTURE | Create pluggable BackendRegistry for multi-backend future |
| T3-2 | `routing/workspace_registry.py` (new) | ARCHITECTURE | Centralize workspace→model mapping; share between proxy and IntelligentRouter |
| T3-3 | `config/settings.py` | TYPE_SAFETY | Add TypedDict for DependencyContainer, ExecutionConfig |

---

*Report generated by full codebase audit on 2026-03-01. All Tier 1 tasks marked ✅ are
already applied to branch `claude/audit-ci-hardening-6qD0L`.*
