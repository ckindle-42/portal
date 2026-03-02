# Portal — Unified Roadmap

**Generated:** 2026-03-02 (delta update — run 5)
**Current version:** 1.4.4
**Maintained by:** ckindle-42

This document is the authoritative living reference for all planned, in-progress,
and completed work across the Portal project.

---

## Changelog

- **2026-03-02 (run 5):** TASK-34 and TASK-35 confirmed complete (PR #90). Version bumped to 1.4.4. ARCHITECTURE.md version updated. CHANGELOG 1.4.4 entry added. Health score 9.5 → 10/10. **FULLY PRODUCTION-READY.**
- **2026-03-02 (run 4):** TASK-32 and TASK-33 confirmed complete (PR #88). mypy errors reduced 17 → 0 — first fully mypy-clean state. ROAD-P03 COMPLETE. New TASK-34 and TASK-35 added. Health score 9.0 → 9.5/10.

---

## 1. Current Release State

Portal 1.4.4 is fully operational for its stated purpose:

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
- **BackendRegistry** — named backend instances
- **Structured logging** — JSON with trace IDs, secret redaction
- **No backward-compat shims** — all legacy code removed
- **Fully mypy-clean** — 0 type errors across 96 source files

**CI status:** 874 tests passing, 0 lint errors, 0 mypy errors.
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
Description:  11x os.getenv() moved to Pydantic Settings
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

---

## 3. In Progress

No tasks currently in progress. All prior open tasks were completed in PR #90.

---

## 4. Planned — Core (Production Path)

### [ROAD-P01] LLM-Based Intelligent Routing

```
Status:       PLANNED
Priority:     P2-HIGH
Effort:       M
Description:  Replace regex-based task classification with LLM classifier
```

### [ROAD-P02] MLX Backend for Apple Silicon

```
Status:       PLANNED
Priority:     P3-MEDIUM
Effort:       M
Description:  Add MLXServerBackend targeting mlx_lm.server
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

*Last updated: 2026-03-02 (run 5) — TASK-34 and TASK-35 complete. Health score 10/10.
Portal is fully production-ready. All ROAD-Cxx items COMPLETE. mypy: 170 → 0.*
