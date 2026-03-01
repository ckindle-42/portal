# Portal — Unified Roadmap

**Generated:** 2026-03-01
**Current version:** 1.3.8 (TASK-6–18 work merged, pending version tag 1.3.9)
**Maintained by:** ckindle-42

This document is the authoritative living reference for all planned, in-progress,
and completed work across the Portal project. It supersedes the earlier `ROADMAP.md`
file which contained only future design sketches.

---

## 1. Current Release State

Portal 1.3.8 is fully operational for its stated purpose:

- **OpenAI-compatible REST API** at `:8081/v1/*` — works with Open WebUI and LibreChat
- **Ollama proxy router** at `:8000` — workspace routing, regex rules, virtual models
- **Telegram interface** — polling mode, per-user auth, HITL confirmation, rate limiting
- **Slack interface** — webhook events, channel whitelist, streaming replies
- **MCP tool dispatch** — via mcpo proxy (openapi transport) and streamable-http
- **Circuit breaker** — per-backend failure isolation and automatic recovery
- **Prometheus metrics** — at `/metrics`, all key request/token counters
- **K8s-style health probes** — `/health`, `/health/live`, `/health/ready`
- **Watchdog** — optional component auto-restart
- **Log rotation** — optional log file management
- **WorkspaceRegistry** — virtual model names mapped to concrete Ollama models
- **BackendRegistry** — named backend instances; ExecutionEngine accepts injected backends
- **Structured logging** — JSON with trace IDs, secret redaction

**CI status:** 862 tests passing, 0 lint errors, Python 3.11–3.14 matrix.

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

### [ROAD-C05] aiohttp → httpx Migration

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       S
Description:  Replaced all aiohttp usage with httpx in OllamaBackend and
              HTTPClientTool. aiohttp removed from pyproject.toml.
Evidence:     TASK-13 (PR #82)
```

### [ROAD-C06] os.getenv Migration to Pydantic Settings

```
Status:       COMPLETE (core paths)
Priority:     P2-HIGH
Effort:       S
Description:  11x os.getenv() in server.py and 3x in router.py moved to
              Pydantic Settings: web_api_key, require_api_key, max_audio_mb,
              whisper_url, vision_model, csp_policy, hsts_enabled,
              ws_rate_limit, ws_rate_window, RoutingConfig.
              Remaining: class-scope reads in ContextManager, MemoryManager
              (tracked as TASK-14, TASK-15 in action prompt).
Evidence:     TASK-12 (PR #82)
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
Evidence:     TASK-17 (PR #82)
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
Evidence:     TASK-18 (PR #82)
```

### [ROAD-C09] Bare except Exception Handlers Narrowed

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       S
Description:  All 20 bare except Exception: handlers across 13 files narrowed
              to specific exception types. grep "except Exception:" src/ → 0.
Evidence:     TASK-15 (PR #82)
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

---

## 3. In Progress

### [ROAD-IP01] Type Safety Uplift (Action Prompt TASK-01 through TASK-19)

```
Status:       IN-PROGRESS
Priority:     P2-HIGH
Effort:       M
Dependencies: None (CI is green; work can start immediately)
Description:  19 targeted tasks from the 2026-03-01 audit:
              - Fix TextTransformer None returns (T1)
              - Fix TraceContext token type (T1)
              - Fix BaseInterface config annotation (T1)
              - Fix CLI port check for optional services (T1)
              - Fix input_sanitizer emoji encoding (T1)
              - Fix docs: aiohttp→httpx in ARCHITECTURE.md (T1)
              - Fix .env.example rate limit default (T1)
              - Fix CONTRIBUTING.md coverage path (T1)
              - Add Telegram None guards — 29 union-attr errors (T2)
              - Update Telegram import from security_module shim (T2)
              - Add DockerSandbox None guards (T2)
              - Fix ToolRegistry deprecated entry_points API (T2)
              - Fix WordProcessor Path→str for python-docx (T2)
              - Move ContextManager env read to constructor (T2)
              - Move MemoryManager env read to constructor (T2)
              - Add TextTransformer failure tests (T3)
              - Add Telegram None guard tests (T3)
              - Verify/fix MCP endpoint URL format (T3)
              - Version 1.3.9 release (T3)
Current state: Not started. Awaiting coding agent run.
What remains:  All 19 tasks.
Blocking:      None.
```

---

## 4. Planned — Core (Production Path)

### [ROAD-P01] LLM-Based Intelligent Routing

```
Status:       PLANNED
Priority:     P2-HIGH
Effort:       M
Dependencies: ROAD-IP01 complete (stable type foundation)
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
Dependencies: ROAD-IP01 complete; ROAD-P01 optional but beneficial
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

### [ROAD-P03] Release v1.3.9

```
Status:       PLANNED
Priority:     P3-MEDIUM
Effort:       S
Dependencies: ROAD-IP01 complete (TASK-19 is the version bump)
Description:  Tag and release v1.3.9 containing TASK-6 through TASK-18 work
              plus the type safety fixes from TASK-01–19.
              Use scripts/release.py for automated versioning.
Evidence:     CHANGELOG.md [Unreleased] block
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
