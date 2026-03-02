# Portal — Unified Roadmap

**Generated:** 2026-03-02 (delta update — run 10)
**Current version:** 1.4.5
**Maintained by:** ckindle-42

This document is the authoritative living reference for all planned, in-progress,
and completed work across the Portal project.

---

## Changelog

- **2026-03-02 (run 10):** MLX backend COMPLETE (PR #99 merged). TASK-48 through TASK-52 (documentation cleanup) all complete. TASK-53 remains open (K8s health probes not wired). TASK-54 partially open (metrics port still :9090 in docs). New findings: MLX env vars missing from .env.example, knowledge base vars undocumented. Health score 9.4/10 maintained.
- **2026-03-02 (run 9):** ROAD-F07 COMPLETE — PORTAL_DOCUMENTATION_AGENT.md executed; PORTAL_HOW_IT_WORKS.md produced. Behavioral verification found 5 discrepancies: D-02 BROKEN (/health/live + /health/ready return 404), D-03 DRIFT (metrics on :8081 not :9090), D-04 UNDOCUMENTED vars. New tasks: TASK-53 (wire K8s probes), TASK-54 (correct metrics port). Health score 9.5 → 9.4/10.
- **2026-03-02 (run 8):** ROAD-P01 FULLY COMPLETE — IntelligentRouter.route() now async with dual LLMClassifier + TaskClassifier. TASK-44–47 complete. All prior tasks resolved. New findings: ARCHITECTURE.md stale, CHANGELOG incomplete, 12 undocumented env vars. Health score 9.3 → 9.5/10. New tasks: TASK-48–52.

---

## 1. Current Release State

Portal 1.4.5 is fully operational for its stated purpose:

- **OpenAI-compatible REST API** at `:8081/v1/*` — works with Open WebUI and LibreChat
- **Ollama proxy router** at `:8000` — workspace routing, LLM classifier, regex fallback
- **IntelligentRouter** at `:8081` — dual LLM + regex routing
- **MLX Backend** at `:8800` — Apple Silicon Neural Engine acceleration (PR #99)
- **Telegram interface** — polling mode, per-user auth, HITL confirmation, rate limiting
- **Slack interface** — webhook events, channel whitelist, streaming replies
- **MCP tool dispatch** — via mcpo proxy (openapi transport) and streamable-http
- **Circuit breaker** — per-backend failure isolation and automatic recovery
- **Prometheus metrics** — at `:8081/metrics`, all key request/token counters
- **K8s-style health probes** — `/health` ✓ (`/health/live` + `/health/ready` pending TASK-53)
- **Watchdog** — optional component auto-restart
- **Log rotation** — optional log file management
- **WorkspaceRegistry** — virtual model names mapped to concrete Ollama models
- **BackendRegistry** — named backend instances (Ollama, MLX)
- **Structured logging** — JSON with trace IDs, secret redaction
- **LLMClassifier** — async Ollama-based query classification with regex fallback (BOTH routers)
- **Fully mypy-clean** — 0 type errors across 97 source files

**CI status:** 890 tests passing (891 collected, 1 skipped), 0 lint violations.
**Type safety:** 0 mypy errors (down from 170 at project start — 100% reduction).

---

## 2. Completed Work

### [ROAD-C01] Foundation & Architecture

```
Status:       COMPLETE
Priority:     P1-CRITICAL
Description:  Complete rewrite from PocketPortal to Portal (web-first, multi-interface)
```

### [ROAD-C02] Security Hardening

```
Status:       COMPLETE
Priority:     P1-CRITICAL
Description:  CORS, rate limiting, input sanitization, HMAC auth, HITL middleware
```

### [ROAD-C03] Dead Code Removal

```
Status:       COMPLETE
Priority:     P1-CRITICAL
Description:  Removed: persistence/, tracer.py, dead exceptions, LMStudioBackend, etc.
```

### [ROAD-C04] Modularization Round 1

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  CircuitBreaker, security_module split, metrics consolidation
```

### [ROAD-C05] aiohttp → httpx Migration

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  All aiohttp replaced with httpx in OllamaBackend and HTTPClientTool
```

### [ROAD-C06] os.getenv Migration to Pydantic Settings

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  11x os.getenv() moved to Pydantic Settings (core path)
```

### [ROAD-C07] BackendRegistry

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  BackendRegistry added; enables MLX backend addition
```

### [ROAD-C08] WorkspaceRegistry

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  WorkspaceRegistry added; virtual model resolution
```

### [ROAD-C09] Bare except Exception Handlers Narrowed

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  All 20 bare except handlers narrowed to specific types
```

### [ROAD-C10] CI Hardening

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  Python 3.13/3.14 added, Docker pins, Dependabot, security scanning
```

### [ROAD-C11] Type Safety Uplift

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  26 tasks; mypy 170 → 103
```

### [ROAD-C12] security_module.py Cleanup

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  security_module.py deleted; direct imports
```

### [ROAD-C13] runtime_metrics.py Removal

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  Caller migration and file deletion
```

### [ROAD-C14] aiohttp Dependency Fix

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  aiohttp added to [slack] extra
```

### [ROAD-C15] Type Safety Batch (TASK-28–31)

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  mypy 103 → 17
```

### [ROAD-C16] Final mypy Clean (TASK-32, TASK-33)

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  mypy 17 → 0 (FULLY CLEAN)
```

### [ROAD-C17] ROAD-P01 Proxy Router Integration (TASK-40)

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  LLMClassifier wired into proxy router resolve_model(). resolve_model()
             made async. LLM classifier fires for requested_model == "auto".
             Regex rules preserved as fallback. router_rules.json classifier block added.
Evidence:     Commit f6ed8dd
```

### [ROAD-C18] ROAD-P01 IntelligentRouter Integration (TASK-41)

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  IntelligentRouter.route() made async. Dual classification added:
             LLMClassifier (async, category override) + TaskClassifier (sync, metadata).
             agent_core.py:322 updated to await self.router.route(query).
             stream_classify() dead code removed. create_classifier() wiring fixed.
             ROUTING_LLM_MODEL env var now respected in proxy router.
Evidence:     PR #96 — commits b6f0671, fa8e5ae, 4ac58c8, 620d0a4, 0038dc5
```

### [ROAD-C19] MLX Backend for Apple Silicon

```
Status:       COMPLETE
Priority:     P3-MEDIUM
Description:  Full MLX backend implementation:
             - MLXServerBackend class in model_backworks.py (same pattern as Ollama)
             - Backend registration in ExecutionEngine factory
             - Three MLX models added to default_models.json (3B, 7B, 14B Qwen2.5)
             - hardware/m4-mac/launch.sh updated with optional MLX server startup
             - Settings in BackendsConfig (mlx_url, enable_mlx)
Evidence:     PR #99 — commits c6c9741, bc42b38, 2b99683, 087ba8e, 6cb8c6a, d24b073, 947501c
```

---

## 3. In Progress

### [ROAD-P04] Documentation Refresh (TASK-53, TASK-54, TASK-55, TASK-56)

```
Status:       IN-PROGRESS
Priority:     P3-MEDIUM
Effort:       S
Dependencies: None
Description:  Final documentation cleanup:
             - TASK-48 through TASK-52: COMPLETE (from run 9)
             - TASK-53 (NEW): Wire /health/live and /health/ready K8s probes —
               call register_health_endpoints() from WebInterface._build_app().
               Both return 404. Severity: BROKEN.
             - TASK-54: Correct metrics port docs — :9090 → :8081
             - TASK-55: Add MLX env vars to .env.example
             - TASK-56: Add KNOWLEDGE_BASE_DIR, ALLOW_LEGACY_PICKLE_EMBEDDINGS to .env.example
Evidence:     PORTAL_AUDIT_REPORT.md run 10
```

---

## 4. Planned — Core (Production Path)

### [ROAD-P01] LLM-Based Intelligent Routing

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       DONE
Description:  Full LLM-based routing implemented in both routing paths:
              - Proxy Router (:8000): LLMClassifier primary, regex fallback
              - IntelligentRouter (:8081): dual LLMClassifier + TaskClassifier
              ROUTING_LLM_MODEL env var now respected via create_classifier().
Evidence:     PR #96, PR #97
```

### [ROAD-P02] MLX Backend for Apple Silicon

```
Status:       COMPLETE
Priority:     P3-MEDIUM
Effort:       DONE
Description:  Full MLX backend implementation:
             - MLXServerBackend targeting mlx_lm.server on :8800
             - Same HTTP adapter pattern as OllamaBackend
             - Three MLX models (3B, 7B, 14B Qwen2.5)
             - Settings in BackendsConfig
Evidence:     PR #99
```

### [ROAD-P03] mypy Error Reduction to Zero

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  mypy 170 → 0 across all audit cycles
```

---

## 5. Planned — Future Evolution

### [ROAD-F01] Per-Workspace ACLs

```
Status:       DISCUSSED
Priority:     P3-MEDIUM
Description:  Extend WorkspaceRegistry with ACL rules
```

### [ROAD-F02] Streaming Memory Context

```
Status:       DISCUSSED
Priority:     P3-MEDIUM
Description:  Pass memory as dedicated system message segment
```

### [ROAD-F03] MCP Tool Permission Scoping

```
Status:       DISCUSSED
Priority:     P3-MEDIUM
Description:  Different workspaces have different MCP tool access
```

### [ROAD-F04] WebSocket Token Auth Improvement

```
Status:       DISCUSSED
Priority:     P3-MEDIUM
Description:  Consider WS query param or subprotocol auth
```

### [ROAD-F05] Structured Config Hot-Reload

```
Status:       DISCUSSED
Priority:     P4-LOW
Description:  ConfigWatcher propagates changes without restart
```

### [ROAD-F06] HITL Non-Redis Fallback

```
Status:       DISCUSSED
Priority:     P4-LOW
Description:  In-memory fallback for single-instance deployments
```

### [ROAD-F07] Portal Documentation Reference

```
Status:       COMPLETE
Priority:     P3-MEDIUM
Effort:       L
Dependencies: ROAD-P04 (in progress)
Description:  PORTAL_DOCUMENTATION_AGENT.md executed (run 9).
             PORTAL_HOW_IT_WORKS.md produced — comprehensive documentation.
Evidence:     PORTAL_HOW_IT_WORKS.md committed on claude/execute-portal-docs-agent-lP5Vb
```

---

## 6. Explicitly Deferred / Out of Scope

### [ROAD-D01] LMStudio Backend

```
Status:       DEFERRED
Description:  Removed in v1.3.5; not in current hardware target
```

### [ROAD-D02] Cloud Inference

```
Status:       DEFERRED
Description:  Portal is explicitly local-first
```

### [ROAD-D03] External Agent Frameworks

```
Status:       DEFERRED
Description:  Portal is intentionally lightweight and framework-free
```

### [ROAD-D04] Multi-User / Multi-Tenant

```
Status:       DEFERRED
Description:  Out of scope for single-owner local model
```

### [ROAD-D05] Web Admin UI

```
Status:       DEFERRED
Description:  Existing CLI + third-party UIs cover the use case
```

---

### [ROAD-F01] Per-Workspace ACLs

```
Status:       DISCUSSED
Priority:     P3-MEDIUM
Description:  Extend WorkspaceRegistry with ACL rules
```

### [ROAD-F02] Streaming Memory Context

```
Status:       DISCUSSED
Priority:     P3-MEDIUM
Description:  Pass memory as dedicated system message segment
```

### [ROAD-F03] MCP Tool Permission Scoping

```
Status:       DISCUSSED
Priority:     P3-MEDIUM
Description:  Different workspaces have different MCP tool access
```

### [ROAD-F04] WebSocket Token Auth Improvement

```
Status:       DISCUSSED
Priority:     P3-MEDIUM
Description:  Consider WS query param or subprotocol auth
```

### [ROAD-F05] Structured Config Hot-Reload

```
Status:       DISCUSSED
Priority:     P4-LOW
Description:  ConfigWatcher propagates changes without restart
```

### [ROAD-F06] HITL Non-Redis Fallback

```
Status:       DISCUSSED
Priority:     P4-LOW
Description:  In-memory fallback for single-instance deployments
```

### [ROAD-F07] Portal Documentation Reference

```
Status:       COMPLETE
Priority:     P3-MEDIUM
Effort:       L
Dependencies: ROAD-P04 (in progress)
Description:  PORTAL_DOCUMENTATION_AGENT.md executed (run 9).
             PORTAL_HOW_IT_WORKS.md produced — comprehensive documentation.
Evidence:     PORTAL_HOW_IT_WORKS.md committed on claude/execute-portal-docs-agent-lP5Vb
```

---

*Last updated: 2026-03-02 (run 10) — MLX backend COMPLETE. ROAD-P04 IN-PROGRESS (TASK-53: wire K8s probes, TASK-54: metrics port, TASK-55: MLX env vars, TASK-56: knowledge env vars). Health: 9.4/10. Version 1.4.5.*
