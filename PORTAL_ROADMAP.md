# Portal — Unified Roadmap

**Generated:** 2026-03-02 (delta update — run 3)
**Current version:** 1.4.2 (1.4.3 pending TASK-32)
**Maintained by:** ckindle-42

This document is the authoritative living reference for all planned, in-progress,
and completed work across the Portal project. It supersedes the earlier `ROADMAP.md`
file which contained only future design sketches.

---

## Changelog

- **2026-03-02 (run 3):** All TASK-23R through TASK-31 confirmed complete (PR #86). mypy errors reduced 103 → 17. ROAD-C13 (runtime_metrics migration) COMPLETE. ROAD-C15 (TASK-28–31 type safety batch) added as COMPLETE. ROAD-P03 updated to NEARLY-COMPLETE (17 errors remain). Health score 8.5 → 9.0/10. New TASK-32 (version bump + CHANGELOG) and TASK-33 (final 17 mypy errors) added.
- **2026-03-01 (run 2):** aiohttp dep gap found and fixed (pyproject.toml). ROAD-C13 status updated: runtime_metrics.py has 2 production callers — caller migration required before deletion (TASK-23R). TASK-24/25/26 confirmed complete. ROAD-C14 (aiohttp dep fix) added. ROAD-C15 (core mypy fixes) added. Health score stable at 8.5/10.
- **2026-03-01:** Version bumped to 1.4.0 then 1.4.1. ROAD-C12 (security_module cleanup) COMPLETE. All TASK-20-26 completed (20-22 prior run; 24-26 this delta).
- **2026-03-01 (prior):** Added ROAD-C12 (security_module cleanup — in progress). Updated TASK-20, TASK-21, TASK-22 in action prompt.

---

## 1. Current Release State

Portal 1.4.2 is fully operational for its stated purpose:

- **OpenAI-compatible REST API** at `:8081/v1/*` — works with Open WebUI and LibreChat
- **Ollama proxy router** at `:8000` — workspace routing, regex rules, virtual models
- **Telegram interface** — polling mode, per-user auth, HITL confirmation, rate limiting
- **Slack interface** — webhook events, channel whitelist, streaming replies; requires aiohttp
- **MCP tool dispatch** — via mcpo proxy (openapi transport) and streamable-http
- **Circuit breaker** — per-backend failure isolation and automatic recovery
- **Prometheus metrics** — at `/metrics`, all key request/token counters
- **K8s-style health probes** — `/health`, `/health/live`, `/health/ready`
- **Watchdog** — optional component auto-restart
- **Log rotation** — optional log file management
- **WorkspaceRegistry** — virtual model names mapped to concrete Ollama models
- **BackendRegistry** — named backend instances; ExecutionEngine accepts injected backends
- **Structured logging** — JSON with trace IDs, secret redaction
- **No backward-compat shims** — both `security_module.py` and `runtime_metrics.py` fully removed

**CI status:** 874 tests passing, 0 lint errors, Python 3.11–3.14 matrix.
**Type safety:** 17 mypy errors (down from 103 in prior audit — 83% reduction in one PR).
**Dependency note:** `[slack]` extra includes `aiohttp>=3.9.0` (required by slack_sdk async client).

---

## 2. Completed Work

### [ROAD-C01] Foundation & Architecture

```
Status:       COMPLETE
Priority:     P1-CRITICAL
Effort:       XL
Description:  Complete rewrite from PocketPortal (Telegram-first) to Portal
              (web-first, multi-interface). FastAPI, Pydantic v2, DI via
              DependencyContainer, dual-router architecture.
Evidence:     PR #46–#66 (2026-02-27 to 2026-02-28)
```

### [ROAD-C02] Security Hardening

```
Status:       COMPLETE
Priority:     P1-CRITICAL
Effort:       M
Description:  CORS origin validation, rate limiting with persistence, input
              sanitization, WebSocket auth, HMAC-based API key auth,
              HITL approval middleware (Redis-backed), Docker sandbox.
Evidence:     PR #59, #77, #78, #79; TASK-14 (CORS urlparse validation)
```

### [ROAD-C03] Dead Code Removal

```
Status:       COMPLETE
Priority:     P1-CRITICAL
Effort:       M
Description:  Removed: persistence/ module, tracer.py, dead exception types,
              dead RPC functions, LMStudioBackend, MLXBackend stub, dead config
              fields. All removals evidence-based with import tracing.
Evidence:     PR #51–#64; CHANGELOG 1.3.4–1.3.5; CLAUDE.md removed list
```

### [ROAD-C04] Modularization Round 1

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       M
Description:  CircuitBreaker extracted to own module. security_module.py split
              into rate_limiter.py + input_sanitizer.py. metrics consolidated.
              Web server handlers extracted to class methods. Lifecycle
              bootstrap decomposed into named phases.
Evidence:     PR #66 (2026-02-28)
```

### [ROAD-C05] aiohttp → httpx Migration (Core)

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       S
Description:  Replaced all aiohttp usage with httpx in OllamaBackend and
              HTTPClientTool. aiohttp removed from pyproject.toml CORE dependencies.
              Note: aiohttp remains required by slack_sdk[asyncio] for the Slack
              interface (see ROAD-C14 for the dep declaration fix).
Evidence:     TASK-13 (PR #82); CHANGELOG 1.3.9
```

### [ROAD-C06] os.getenv Migration to Pydantic Settings

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       S
Description:  11x os.getenv() in server.py and 3x in router.py moved to
              Pydantic Settings: web_api_key, require_api_key, max_audio_mb,
              whisper_url, vision_model, csp_policy, hsts_enabled,
              ws_rate_limit, ws_rate_window, RoutingConfig.
              Also: ContextManager and MemoryManager env reads moved to constructors.
Evidence:     TASK-12, TASK-14, TASK-15 (PR #84)
```

### [ROAD-C07] BackendRegistry (TASK-17)

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       S
Description:  BackendRegistry added to routing/. ExecutionEngine accepts
              pre-built backends dict. Factories wire OllamaBackend through
              BackendRegistry. Enables MLX backend addition without changing
              ExecutionEngine.__init__.
Evidence:     TASK-17 (PR #84)
```

### [ROAD-C08] WorkspaceRegistry (TASK-18)

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       S
Description:  WorkspaceRegistry added to routing/. IntelligentRouter.route()
              accepts workspace_id. Proxy router uses registry for virtual
              model resolution. Both routing layers now use shared workspace
              logic. DependencyContainer wires it.
Evidence:     TASK-18 (PR #84)
```

### [ROAD-C09] Bare except Exception Handlers Narrowed

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       S
Description:  All 20 bare except Exception: handlers across 13 files narrowed
              to specific exception types. grep "except Exception:" src/ → 0.
Evidence:     TASK-15 (PR #84)
```

### [ROAD-C10] CI Hardening

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       S
Description:  Python 3.13 + 3.14 added to CI matrix. Docker images pinned to
              version tags. Dependabot configured. Security scanning (pip-audit
              + Docker Scout) added.
Evidence:     PR #70 (v1.3.8)
```

### [ROAD-C11] Type Safety Uplift (TASK-1 through TASK-26)

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       L
Description:  26 targeted type safety and hardening tasks completed:
              - T1-T19: TextTransformer, TraceContext, BaseInterface, CLI port checks,
                input sanitizer, documentation, Telegram None guards, DockerSandbox,
                ToolRegistry, WordProcessor, ContextManager, MemoryManager fixes.
                mypy errors reduced: 170 → 124
              - T20-22: security_module.py import cleanup + deletion. 13 test files
                updated. 10 orphan remote branches pruned.
              - T24-26: lifecycle.py StructuredLogger *args, Telegram None guards
                and type annotations, Slack return type + __init__.py exports.
                mypy errors reduced: 124 → 103
Evidence:     PR #84 (v1.3.9); commits e407996, e44c408, 7b0eeda (v1.4.0-1.4.1)
```

### [ROAD-C12] security_module.py Cleanup

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       S
Description:  Remove security_module.py re-export shim:
              - middleware.py updated to import directly (prior run)
              - 13 test files updated to import directly (TASK-20)
              - security_module.py file deleted (TASK-21)
Evidence:     e407996 (middleware.py update); TASK-20/21 (test files + deletion)
```

### [ROAD-C13] runtime_metrics.py Caller Migration and Removal

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       XS
Description:  observability/runtime_metrics.py backward-compat re-export shim.
              Prior audit incorrectly identified it as dead code (TASK-23).
              Correct action (TASK-23R) migrated callers then deleted the file:
              1. agent_core.py:20 migrated to import MCP_TOOL_USAGE from metrics.py
              2. server.py:44-48 migrated to import 4 symbols from metrics.py
              3. runtime_metrics.py deleted
              All former re-exports now consolidated in metrics.py (with comment).
Evidence:     commit 1d872e3 (2026-03-02, PR #86); no remaining runtime_metrics
              imports in src/portal/ (verified this audit run)
```

### [ROAD-C14] aiohttp Dependency Declaration Fix

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       XS
Description:  TASK-13 (v1.3.9) removed aiohttp from core dependencies when httpx
              was adopted for OllamaBackend and HTTPClientTool. However, slack_sdk's
              AsyncWebClient has a transitive dependency on aiohttp that was not
              accounted for. This caused test_registered_interfaces_accessible to
              fail in clean installs. Fixed by adding aiohttp>=3.9.0 to [slack]
              and [all] optional extras.
Evidence:     commit 6cfa24d (2026-03-01)
```

### [ROAD-C15] Type Safety Batch (TASK-28 through TASK-31)

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       M
Description:  Large batch of mypy fixes across 4 modules, reducing errors 103 → 17:
              - TASK-28: core module — agent_interface.py metadata field, agent_core.py
                health_check() return type + mcp_registry None guard, factories.py
                MCPRegistry annotation. 5 errors resolved.
              - TASK-29: security/middleware — middleware.py None list + re.search
                patterns, docker_sandbox.py docker client None guards (7 errors),
                user_store.py Path() annotation, tool_confirmation_middleware.py
                Event None annotation. 13 errors resolved.
              - TASK-30: observability — log_rotation.py logger.info kwargs → extra
                pattern, config_watcher.py yaml/toml import-untyped suppression,
                watchdog.py component type guards. 23 errors resolved.
              - TASK-31: tools layer batch — document_processing, data_tools, git_tools,
                docker_tools, automation_tools. 45+ errors resolved.
Evidence:     commits cd4d12c, ba3d1b2, b434d3c, 17019f1, 16a08ae (PR #86)
              mypy errors: 103 → 17 (83% reduction)
```

---

## 3. In Progress

No tasks currently in progress. All prior open tasks were completed in PR #86.

---

## 4. Planned — Core (Production Path)

### [ROAD-P01] LLM-Based Intelligent Routing

```
Status:       PLANNED
Priority:     P2-HIGH
Effort:       M
Dependencies: None (type safety foundation complete)
Description:  Replace regex-based task classification with a small LLM
              classifier call. Both routing layers (proxy router at :8000
              and IntelligentRouter at :8081) use the same new classifier.

              Architecture:
              - New src/portal/routing/llm_classifier.py — async function
                that calls a small Ollama model (qwen2.5:0.5b) with a
                structured prompt; returns one of: general, code, reasoning,
                splunk, creative (configurable)
              - Update router.py::resolve_model() — replace regex_rules step
                with classifier call; keep @model: and workspace overrides
              - Update intelligent_router.py — replace TaskClassifier with
                classifier (keep TaskClassifier as zero-latency fallback)
              - Update router_rules.json schema to replace regex_rules with
                classifier config block
              - LRU cache on classifier to avoid reclassifying identical prompts

              Performance: adds ~100-300ms (already-loaded 0.5B model).
              Invisible relative to 2-30s generation time.

              See: ROADMAP.md section 1 for full design spec.
Evidence:     ROADMAP.md section 1 (designed 2026-02-28)
```

### [ROAD-P02] MLX Backend for Apple Silicon

```
Status:       PLANNED
Priority:     P3-MEDIUM
Effort:       M
Dependencies: ROAD-P01 optional but beneficial
Description:  Add MLXServerBackend(BaseHTTPBackend) targeting mlx_lm.server
              HTTP endpoint on :8800. Same pattern as OllamaBackend — Portal
              stays a thin orchestration layer; no in-process model loading.

              Architecture:
              - New MLXServerBackend in model_backends.py (~100 lines)
              - ExecutionEngine: conditionally register mlx backend when
                COMPUTE_BACKEND=mps
              - hardware/m4-mac/launch.sh: start mlx_lm.server on :8800
              - default_models.json: add MLX model entries
              - .env.example: add MLX_SERVER_PORT, MLX_DEFAULT_MODEL
              - launch.sh doctor: check MLX server health

              See: ROADMAP.md section 2 for full design spec.
Evidence:     ROADMAP.md section 2 (designed 2026-02-28)
```

### [ROAD-P03] mypy Error Reduction to Zero

```
Status:       NEARLY-COMPLETE (was PLANNED)
Priority:     P3-MEDIUM
Effort:       XS (was M)
Dependencies: ROAD-C15 COMPLETE (provides foundation)
Description:  17 mypy errors remain across 5 files after TASK-28–31:
              - memory/manager.py:37 (1 error): Path() with str|None
              - config/settings.py (9 errors): yaml stubs, Field default_factory
                pattern, ConfigDict vs SettingsConfigDict, cascade errors
              - routing/model_backends.py:205 (1 error): abstract async generator
                return type mismatch
              - routing/execution_engine.py:226 (1 error): cascade from above
              - interfaces/web/server.py:727-728 (2 errors): _server None typing

              Full details and fix instructions in TASK-33 (ACTION_PROMPT).
Evidence:     2026-03-02 audit — mypy: 17 errors in 5 files
```

---

## 5. Planned — Future Evolution

### [ROAD-F01] Per-Workspace ACLs

```
Status:       DISCUSSED
Priority:     P3-MEDIUM
Effort:       M
Dependencies: WorkspaceRegistry (COMPLETE), UserStore (COMPLETE)
Description:  Extend WorkspaceRegistry to associate ACL rules with workspaces.
              Validate user role against workspace ACL during routing.
              Would allow "reasoning" workspace to be restricted to admin users
              while "general" workspace is open.
Evidence:     Security section of ARCHITECTURE.md; WorkspaceRegistry design
```

### [ROAD-F02] Streaming Memory Context

```
Status:       DISCUSSED
Priority:     P3-MEDIUM
Effort:       S
Dependencies: MemoryManager (COMPLETE)
Description:  Currently memory context is prepended to the message as a text
              block. Improve injection: pass memory snippets as a dedicated
              system message segment rather than concatenated to user message.
              Better handles long-context edge cases.
Evidence:     agent_core.py _persist_user_context()
```

### [ROAD-F03] MCP Tool Permission Scoping

```
Status:       DISCUSSED
Priority:     P3-MEDIUM
Effort:       M
Dependencies: MCPRegistry (COMPLETE), WorkspaceRegistry (COMPLETE)
Description:  Allow different workspaces to have different MCP tool access.
              e.g., "red-team" workspace has access to security tools;
              "assistant" workspace does not.
              Implement as a workspace → allowed_tools list in config.
Evidence:     HITL approval middleware; workspace system
```

### [ROAD-F04] WebSocket Token Auth Improvement

```
Status:       DISCUSSED
Priority:     P3-MEDIUM
Effort:       S
Dependencies: None
Description:  Current WebSocket auth requires the first message to contain
              the Bearer token. Consider moving to WS query param or
              subprotocol-based auth for compatibility with more WS clients.
Evidence:     WebInterface._handle_websocket()
```

### [ROAD-F05] Structured Config Hot-Reload

```
Status:       DISCUSSED
Priority:     P4-LOW
Effort:       M
Dependencies: ConfigWatcher (COMPLETE)
Description:  ConfigWatcher detects file changes but currently just logs them.
              Full implementation would reload settings and propagate to
              AgentCore, routers, and interfaces without restart.
Evidence:     observability/config_watcher.py
```

### [ROAD-F06] HITL Non-Redis Fallback

```
Status:       DISCUSSED
Priority:     P4-LOW
Effort:       S
Dependencies: HITLApprovalMiddleware (COMPLETE)
Description:  HITL approval requires Redis. Add an in-memory fallback for
              deployments without Redis that is single-instance safe.
              Would make HITL available in --minimal mode.
Evidence:     middleware/hitl_approval.py
```

---

## 6. Explicitly Deferred / Out of Scope

### [ROAD-D01] LMStudio Backend

```
Status:       DEFERRED
Description:  LMStudioBackend was removed in v1.3.5 — it was a dead stub from
              PocketPortal with no production callers. LMStudio is not part
              of the current hardware target configuration.
Why deferred: No current need; adding it would be speculative code that
              becomes dead code again.
```

### [ROAD-D02] Cloud Inference (OpenAI, Anthropic, etc.)

```
Status:       DEFERRED
Description:  Portal is explicitly local-first. Cloud inference would add
              external dependencies, API key management, usage costs, and
              privacy concerns that contradict the core value proposition.
Why deferred: Out of scope by design. Will not be implemented.
```

### [ROAD-D03] External Agent Frameworks (LangChain, LlamaIndex, etc.)

```
Status:       DEFERRED
Description:  Portal's AgentCore is intentionally lightweight and framework-free.
              External agent frameworks add large dependency trees and impose
              architectural patterns that conflict with Portal's DI design.
Why deferred: Out of scope by design.
```

### [ROAD-D04] Multi-User / Multi-Tenant

```
Status:       DEFERRED
Description:  Portal targets a single owner on personal hardware. Multi-tenant
              would require per-user model isolation, resource accounting,
              and billing concerns that are incompatible with the local-first model.
Why deferred: Out of scope for the hardware target and ownership model.
```

### [ROAD-D05] Web Admin UI

```
Status:       DEFERRED
Description:  Portal uses Open WebUI or LibreChat as the primary web interface.
              Building a separate admin UI would duplicate existing functionality
              already covered by the `portal doctor` CLI and existing health endpoints.
Why deferred: Not needed; existing CLI + third-party UIs cover the use case.
```

---

*This roadmap is maintained as part of the Portal source tree. Update it whenever a
significant item is completed, started, or added.*

*Last updated: 2026-03-02 (run 3) — PR #86 complete: all TASK-23R through TASK-31 done.
mypy: 103 → 17 errors. ROAD-C13 (runtime_metrics) COMPLETE. ROAD-C15 (TASK-28–31 type
safety batch) COMPLETE. ROAD-P03 NEARLY-COMPLETE (17 errors remain — TASK-33 pending).
Health score 8.5 → 9.0/10.*
