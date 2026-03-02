# Portal — Unified Roadmap

**Generated:** 2026-03-02 (delta update — run 6)
**Current version:** 1.4.4 (targeting 1.4.5 on ROAD-P01 completion)
**Maintained by:** ckindle-42

This document is the authoritative living reference for all planned, in-progress,
and completed work across the Portal project.

---

## Changelog

- **2026-03-02 (run 6):** ROAD-P01 status changed PLANNED → IN-PROGRESS. Commit `0a7f28f` added `llm_classifier.py` (185 LOC) — the LLMClassifier module. Integration into `router.py` and `intelligent_router.py` not yet complete. 10 open findings (TASK-36 through TASK-43). Health score 10/10 → 9.0/10 (new code, open issues). Version target 1.4.5 on completion.
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
- **Fully mypy-clean** — 0 type errors across 96 source files (2 new errors in llm_classifier.py pending fix)

**CI status:** 874 tests passing, 2 lint violations (llm_classifier.py), 2 mypy errors (llm_classifier.py).
**Type safety:** 2 mypy errors (new file; down from 170 at project start — 98.8% reduction).

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

### [ROAD-P01] LLM-Based Intelligent Routing

```
Status:       IN-PROGRESS
Priority:     P2-HIGH
Effort:       M
Started:      2026-03-02 (commit 0a7f28f)
Description:  Replace regex-based task classification with LLM classifier.
              Uses qwen2.5:0.5b via Ollama for semantic query classification.
              Falls back to TaskClassifier when Ollama unavailable.
```

**What's done:**
- `src/portal/routing/llm_classifier.py` — `LLMClassifier`, `LLMClassification`, `LLMCategory`, `create_classifier()` (185 LOC)
- Fallback to `TaskClassifier` when Ollama unavailable
- LRU cache for identical prompts

**What remains (TASK-36 through TASK-43):**
- Fix 2 lint violations in `llm_classifier.py` (TASK-36)
- Fix 2 mypy errors in `create_classifier()` (TASK-37)
- Add unit tests for `LLMClassifier` (TASK-38)
- Document `ROUTING_LLM_MODEL` in `.env.example` (TASK-39)
- Integrate into `router.py::resolve_model()` — async, replace regex step (TASK-40)
- Integrate into `intelligent_router.py::route()` — async, update agent_core.py caller (TASK-41)
- Add `classifier` config block to `router_rules.json` (TASK-42)
- Bump version to 1.4.5, update CHANGELOG (TASK-43)

**Blocking issues:** None. Implementation path is clear.

---

## 4. Planned — Core (Production Path)

### [ROAD-P02] MLX Backend for Apple Silicon

```
Status:       PLANNED
Priority:     P3-MEDIUM
Effort:       M
Dependencies: ROAD-P01 complete (BackendRegistry already in place)
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

*Last updated: 2026-03-02 (run 6) — ROAD-P01 IN-PROGRESS. llm_classifier.py added. Integration pending (TASK-36 through TASK-43). Version target 1.4.5.*
