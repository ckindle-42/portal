# Portal — Unified Roadmap

**Generated:** 2026-03-02 (delta update — run 14)
**Current version:** 1.4.5
**Maintained by:** ckindle-42

This document is the authoritative living reference for all planned, in-progress,
and completed work across the Portal project.

---

## Changelog

- **2026-03-02 (run 14):** Two regressions detected from run 13. BUG-01: `test_all_models_available_by_default` fails due to HuggingFace model with `available: false` not being excluded like MLX models (introduced by commit `6d4c0a1`). BUG-02: mypy error in `server.py:784` — `Settings` assigned to `dict[Any, Any] | None` parameter (introduced by commit `0713218`). Health score reduced to 9.0/10. Both are shallow fixes. Run 13 incorrectly claimed 0 test failures and 0 mypy errors due to using "sample verified" rather than running full suite.
- **2026-03-02 (run 13):** Auto-pull models (ROAD-F06) added — ModelPuller class automatically downloads missing Ollama models on startup. Docker image updates — OpenWebUI/LibreChat now use latest with pull_policy:always. Portal claimed fully production-ready at 10/10 (NOTE: run 14 found this was inaccurate due to incomplete verification).
- **2026-03-02 (run 12):** Config hot-reload (ROAD-F05) completed — ConfigWatcher now propagates rate limit changes at runtime. Fixed mypy type error in lifecycle.py. Branch hygiene performed — cleaned 10 stale remote branches.
- **2026-03-02 (run 11 - documentation review):** PORTAL_DOCUMENTATION_AGENT.md executed. Verified all prior discrepancies resolved: D-02 (K8s health probes wired), D-03 (metrics port corrected), D-04 (env vars documented), D-05 (warmup state handled). Updated PORTAL_HOW_IT_WORKS.md discrepancy log to show all issues resolved.
- **2026-03-02 (run 11):** ALL TASKS COMPLETE — TASK-53 through TASK-56 all resolved. Health score maintained at 10/10.
- **2026-03-02 (run 10):** MLX backend COMPLETE (PR #99 merged). TASK-48 through TASK-52 complete. TASK-53 (K8s probes), TASK-54 (metrics port), TASK-55 (MLX env vars), TASK-56 (knowledge env vars) added.
- **2026-03-02 (run 9):** ROAD-F07 COMPLETE — PORTAL_HOW_IT_WORKS.md produced.

---

## 1. Current Release State

Portal 1.4.5 is fully operational for its stated purpose:

- **OpenAI-compatible REST API** at `:8081/v1/*` — works with Open WebUI and LibreChat
- **Ollama proxy router** at `:8000` — workspace routing, LLM classifier, regex fallback
- **IntelligentRouter** at `:8081` — dual LLM + regex routing
- **MLX Backend** at `:8800` — Apple Silicon Neural Engine acceleration
- **Telegram interface** — polling mode, per-user auth, HITL confirmation, rate limiting
- **Slack interface** — webhook events, channel whitelist, streaming replies
- **MCP tool dispatch** — via mcpo proxy (openapi transport) and streamable-http
- **Circuit breaker** — per-backend failure isolation and automatic recovery
- **Prometheus metrics** — at `:8081/metrics`, all key request/token counters
- **K8s-style health probes** — `/health`, `/health/live`, `/health/ready` all wired
- **Watchdog** — optional component auto-restart
- **Log rotation** — optional log file management
- **Config hot-reload** — rate limits can be updated without restart
- **Auto-pull models** — ModelPuller automatically downloads missing Ollama models
- **WorkspaceRegistry** — virtual model names mapped to concrete Ollama models
- **BackendRegistry** — named backend instances (Ollama, MLX)
- **Structured logging** — JSON with trace IDs, secret redaction
- **LLMClassifier** — async Ollama-based query classification with regex fallback
- **Structured config** — Pydantic v2 BaseSettings with full validation

**CI status:** 915 tests selected (913 passing, 1 failing, 1 skipped). 0 lint violations.
**Type safety:** 1 mypy error (server.py:784 — regression from run 13).
**Open issues:** BUG-01 (test failure), BUG-02 (mypy error). Both shallow.

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

### [ROAD-C15] Type Safety Batch

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  mypy 103 → 17
```

### [ROAD-C16] Final mypy Clean

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  mypy 17 → 0 (FULLY CLEAN — NOTE: regression introduced in run 13, see open items)
```

### [ROAD-C17] LLM-Based Intelligent Routing (ROAD-P01)

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  Full LLM-based routing in both routing paths:
             - Proxy Router (:8000): LLMClassifier primary, regex fallback
             - IntelligentRouter (:8081): dual LLMClassifier + TaskClassifier
Evidence:     PR #96, PR #97
```

### [ROAD-C18] MLX Backend for Apple Silicon (ROAD-P02)

```
Status:       COMPLETE
Priority:     P3-MEDIUM
Description:  Full MLX backend implementation:
             - MLXServerBackend targeting mlx_lm.server on :8800
             - Same HTTP adapter pattern as OllamaBackend
             - Three MLX models (3B, 7B, 14B Qwen2.5)
             - Settings in BackendsConfig
Evidence:     PR #99
```

### [ROAD-C19] Documentation Refresh (ROAD-P04)

```
Status:       COMPLETE
Priority:     P3-MEDIUM
Description:  All documentation tasks complete:
             - ARCHITECTURE.md routing descriptions updated
             - CHANGELOG.md 1.4.5 entry completed
             - ROADMAP.md status fields correct
             - .env.example with all env vars (MLX, knowledge base)
             - K8s health probes wired (/health/live, /health/ready)
             - Metrics port corrected to :8081
Evidence:     Commit 94ae694
```

### [ROAD-C20] Structured Config Hot-Reload (ROAD-F05)

```
Status:       COMPLETE
Priority:     P4-LOW
Description:  ConfigWatcher now propagates rate limit config changes at runtime:
             - update_limits() method added to RateLimiter
             - ConfigWatcher registered in RuntimeContext
             - Callback propagates config changes to rate limiter
Evidence:     Commit 31d1e61
```

### [ROAD-C21] Auto-Pull Models on Startup (ROAD-F06)

```
Status:       COMPLETE (with minor regression — see open items)
Priority:     P4-LOW
Description:  ModelPuller class auto-downloads missing Ollama models on startup:
             - Checks defined models in default_models.json
             - Queries Ollama /api/tags for installed models
             - Pulls missing models via /api/pull endpoint
             - Config option auto_pull_models (default: true)
             - Also added HuggingFace example model (hf_llama32_3b) to default_models.json
Note:        Test not updated for HuggingFace backend (BUG-01); mypy type
             regression in server.py:784 (BUG-02). Both require shallow fixes.
Evidence:     Commit 6d4c0a1
```

---

## 3. In Progress

### [ROAD-O01] Regression Fixes from Run 13

```
Status:       OPEN — requires 2 shallow fixes
Priority:     P1-CRITICAL (blocks CI green)
Description:  Two regressions introduced by commit 6d4c0a1 and 0713218:
             BUG-01: test_all_models_available_by_default fails for hf_llama32_3b
                     Fix: add "huggingface" to backend exclusion in test (5 lines)
             BUG-02: mypy error in server.py:784 — Settings assigned to dict|None
                     Fix: add # type: ignore[assignment] to line 784 (1 line)
Tasks:        TASK-57, TASK-58
```

---

## 4. Planned — Core (Production Path)

### [ROAD-P01] LLM-Based Intelligent Routing

```
Status:       COMPLETE
Priority:     P2-HIGH
Description:  Full LLM-based routing implemented in both routing paths
Evidence:     PR #96, PR #97
```

### [ROAD-P02] MLX Backend for Apple Silicon

```
Status:       COMPLETE
Priority:     P3-MEDIUM
Description:  Full MLX backend implementation complete
Evidence:     PR #99
```

### [ROAD-P03] mypy Error Reduction to Zero

```
Status:       COMPLETE (regression in run 13 — fix via TASK-58)
Priority:     P2-HIGH
Description:  mypy 170 → 0 across all audit cycles; 1 regression from run 13
```

### [ROAD-P04] Documentation Refresh

```
Status:       COMPLETE
Priority:     P3-MEDIUM
Description:  All documentation complete and accurate
Evidence:     Commit 94ae694
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
Status:       COMPLETE
Priority:     P4-LOW
Description:  ConfigWatcher propagates changes without restart
Evidence:     Commit 31d1e61
```

### [ROAD-F06] Auto-Pull Models on Startup

```
Status:       COMPLETE (regression fix pending)
Priority:     P4-LOW
Description:  ModelPuller class auto-downloads missing Ollama models
Evidence:     Commit 6d4c0a1
```

### [ROAD-F07] How-It-Works Documentation

```
Status:       COMPLETE
Priority:     P4-LOW
Description:  PORTAL_HOW_IT_WORKS.md produced
Evidence:     Commit eeead80
```

### [ROAD-F08] HuggingFace Model Auto-Import

```
Status:       DISCUSSED
Priority:     P4-LOW
Description:  ModelPuller currently logs a message for HuggingFace models requiring
             manual GGUF conversion. A future enhancement could automate the
             huggingface-cli → ollama import pipeline.
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

*Last updated: 2026-03-02 (run 14) — 2 open regressions (BUG-01, BUG-02). Health: 9.0/10. Fix TASK-57 and TASK-58 to restore 10/10.*
