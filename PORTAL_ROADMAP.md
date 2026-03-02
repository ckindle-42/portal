# Portal — Unified Roadmap

**Generated:** 2026-03-02 (delta update — run 8)
**Current version:** 1.4.5
**Maintained by:** ckindle-42

This document is the authoritative living reference for all planned, in-progress,
and completed work across the Portal project.

---

## Changelog

- **2026-03-02 (run 8):** ROAD-P01 FULLY COMPLETE — IntelligentRouter.route() now async with dual LLMClassifier + TaskClassifier (TASK-41). TASK-44–47 complete (version sync, dead code removal, create_classifier fix). All prior open tasks resolved. New findings: ARCHITECTURE.md routing description stale, CHANGELOG 1.4.5 entry incomplete, ROADMAP.md status stale, 12 undocumented env vars, stale `master` branch. Health score 9.3 → 9.5/10. New tasks: TASK-48–52 (documentation only). PORTAL_DOCUMENTATION_AGENT.md added to repo (documentation agent prompt).
- **2026-03-02 (run 7):** ROAD-P01 proxy router integration COMPLETE (TASK-40). IntelligentRouter still pending (TASK-41 — open). 3 new findings: dead stream_classify() method, ROUTING_LLM_MODEL env var inoperative, pyproject.toml + ARCHITECTURE.md version drift. Health score 9.0 → 9.3/10. Version 1.4.5 shipped. New tasks: TASK-44–47.
- **2026-03-02 (run 6):** ROAD-P01 status changed PLANNED → IN-PROGRESS. Commit `0a7f28f` added `llm_classifier.py` (185 LOC) — the LLMClassifier module. Integration into `router.py` and `intelligent_router.py` not yet complete. 10 open findings (TASK-36 through TASK-43). Health score 10/10 → 9.0/10 (new code, open issues). Version target 1.4.5 on completion.
- **2026-03-02 (run 5):** TASK-34 and TASK-35 confirmed complete (PR #90). Version bumped to 1.4.4. ARCHITECTURE.md version updated. CHANGELOG 1.4.4 entry added. Health score 9.5 → 10/10. **FULLY PRODUCTION-READY.**
- **2026-03-02 (run 4):** TASK-32 and TASK-33 confirmed complete (PR #88). mypy errors reduced 17 → 0 — first fully mypy-clean state. ROAD-P03 COMPLETE. New TASK-34 and TASK-35 added. Health score 9.0 → 9.5/10.

---

## 1. Current Release State

Portal 1.4.5 is fully operational for its stated purpose:

- **OpenAI-compatible REST API** at `:8081/v1/*` — works with Open WebUI and LibreChat
- **Ollama proxy router** at `:8000` — workspace routing, LLM classifier (TASK-40), regex fallback
- **IntelligentRouter** at `:8081` — dual LLM + regex routing (TASK-41 complete)
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
- **LLMClassifier** — async Ollama-based query classification with regex fallback (BOTH routers)
- **Fully mypy-clean** — 0 type errors across 97 source files

**CI status:** 890 tests passing, 0 lint violations, 0 mypy errors.
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

---

## 3. In Progress

None. All active work is complete. Open items are documentation-only cleanup (see Section 4).

---

## 4. Planned — Core (Production Path)

### [ROAD-P01] LLM-Based Intelligent Routing

```
Status:       COMPLETE
Priority:     P2-HIGH
Effort:       DONE
Description:  Full LLM-based routing implemented in both routing paths:
              - Proxy Router (:8000): LLMClassifier primary, regex fallback (TASK-40)
              - IntelligentRouter (:8081): dual LLMClassifier + TaskClassifier (TASK-41)
              ROUTING_LLM_MODEL env var now respected via create_classifier().
Evidence:     Commits f6ed8dd, 71ce797 (PR #96)
```

### [ROAD-P02] MLX Backend for Apple Silicon

```
Status:       PLANNED
Priority:     P3-MEDIUM
Effort:       M
Dependencies: ROAD-P01 complete (now done). BackendRegistry in place.
Description:  Add MLXServerBackend targeting mlx_lm.server on :8800.
              Same HTTP adapter pattern as OllamaBackend.
              Only active when COMPUTE_BACKEND=mps.
Evidence:     ROADMAP.md §2, BackendRegistry (ROAD-C07)
```

### [ROAD-P03] mypy Error Reduction to Zero

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  mypy 170 → 0 across all audit cycles
```

### [ROAD-P04] Documentation Refresh (TASK-48–52)

```
Status:       PLANNED
Priority:     P3-MEDIUM
Effort:       S
Dependencies: None
Description:  Documentation cleanup following ROAD-P01 completion:
              - TASK-48: ARCHITECTURE.md routing descriptions updated
              - TASK-49: CHANGELOG.md 1.4.5 entry completed with PR #96 entries
              - TASK-50: ROADMAP.md LLM routing status marked Complete
              - TASK-51: .env.example extended with 12 undocumented env vars
              - TASK-52: Stale `master` local branch deleted
Evidence:     PORTAL_AUDIT_REPORT.md run 8 (DOC-03 through DOC-06, ENV-01, BRANCH-01)
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
Status:       DISCUSSED
Priority:     P3-MEDIUM
Effort:       L
Dependencies: ROAD-P04 complete (docs current)
Description:  Execute PORTAL_DOCUMENTATION_AGENT.md to produce PORTAL_HOW_IT_WORKS.md —
              a comprehensive, verified technical reference for new developers.
              Deferred until documentation cleanup (ROAD-P04) is complete so the
              resulting doc reflects the current state accurately.
Evidence:     PORTAL_DOCUMENTATION_AGENT.md added 2026-03-02 (commit 214b16c)
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

*Last updated: 2026-03-02 (run 8) — ROAD-P01 FULLY COMPLETE (both routing paths). Open: ROAD-P04 (documentation cleanup TASK-48–52). Health: 9.5/10. Version 1.4.5.*
