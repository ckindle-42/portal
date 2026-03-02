# Portal — Unified Roadmap

**Generated:** 2026-03-02 (delta update — run 18)
**Current version:** 1.4.7
**Maintained by:** ckindle-42

This document is the authoritative living reference for all planned, in-progress,
and completed work across the Portal project.

---

## Changelog

- **2026-03-02 (run 19):** Implemented ROAD-F01, ROAD-F02, ROAD-F08; removed ROAD-D01, ROAD-D05:
  - ROAD-F01: Per-Workspace ACLs - added WorkspaceACL class with tool/user/rate limit controls
  - ROAD-F02: Streaming Memory Context - build_system_message() returns dedicated message dict
  - ROAD-F08: HuggingFace Model Auto-Import - auto-imports HF models to Ollama
  - ROAD-D01: LMStudio Backend - marked as REMOVED
  - ROAD-D05: Web Admin UI - marked as REMOVED
  - Tests: 919 passed | Lint: 0 | Mypy: 0
  - Health score: 10/10

- **2026-03-02 (run 18):** Delta run after c65a557 fixes:
  - D-01: Added `[test]` extra to pyproject.toml (was missing)
  - D-02: Changed sentence-transformers warning to DEBUG level (non-blocking)
  - Tests: 919 passed | Lint: 0 | Mypy: 0
  - Health score: 10/10

- **2026-03-02 (run 17):** Documentation agent v3 verification complete:
  - Dependencies: 41 OK, 0 missing
  - Module imports: 70 OK, 0 failed
  - Tests: 919 passed, 1 skipped | Lint: 0 | Mypy: 0
  - Component instantiation: 20/20 OK
  - TaskClassifier: 5 query categories verified
  - Tool modules: 27 discovered
  - Health score: 10/10

---

## 1. Current Release State

Portal 1.4.6 is fully operational for its stated purpose:

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
- **Image generation** — mflux CLI integration for MLX-native image generation
- **Audio generation** — CosyVoice TTS and voice cloning support

**CI status:** 920 tests selected (919 passing, 1 skipped). 0 lint violations. 0 mypy errors.
**Open issues:** None — fully production-ready at 10/10.

---

## 2. Completed Work

All work items from previous runs are complete. Key completed items:

- [ROAD-C01] Foundation & Architecture - COMPLETE
- [ROAD-C02] Security Hardening - COMPLETE
- [ROAD-C03] Dead Code Removal - COMPLETE
- [ROAD-C04] Modularization Round 1 - COMPLETE
- [ROAD-C05] aiohttp → httpx Migration - COMPLETE
- [ROAD-C06] os.getenv Migration to Pydantic Settings - COMPLETE
- [ROAD-C07] BackendRegistry - COMPLETE
- [ROAD-C08] WorkspaceRegistry - COMPLETE
- [ROAD-C09] Bare except Exception Handlers Narrowed - COMPLETE
- [ROAD-C10] CI Hardening - COMPLETE
- [ROAD-C11] Type Safety Uplift - COMPLETE
- [ROAD-C12] security_module.py Cleanup - COMPLETE
- [ROAD-C13] runtime_metrics.py Removal - COMPLETE
- [ROAD-C14] aiohttp Dependency Fix - COMPLETE
- [ROAD-C15] Type Safety Batch - COMPLETE
- [ROAD-C16] Final mypy Clean - COMPLETE
- [ROAD-C17] LLM-Based Intelligent Routing (ROAD-P01) - COMPLETE
- [ROAD-C18] MLX Backend for Apple Silicon (ROAD-P02) - COMPLETE
- [ROAD-C19] Documentation Refresh (ROAD-P04) - COMPLETE
- [ROAD-C20] Structured Config Hot-Reload (ROAD-F05) - COMPLETE
- [ROAD-C21] Auto-Pull Models on Startup (ROAD-F06) - COMPLETE
- [ROAD-C22] Image Generation via mflux CLI - COMPLETE
- [ROAD-C23] Audio Generation via CosyVoice - COMPLETE

---

## 3. In Progress

None — all items complete.

---

## 4. Planned — Core (Production Path)

All core planned items completed.

---

## 5. Planned — Future Evolution

### [ROAD-F01] Per-Workspace ACLs

```
Status:       COMPLETE
Priority:     P3-MEDIUM
Description:  Extend WorkspaceRegistry with ACL rules
Evidence:     workspace_registry.py now has WorkspaceACL class with:
              - allowed_tools: list of permitted MCP tools
              - rate_limit: requests per minute
              - max_tokens: response token limit
              - allowed_users / blocked_users: user access control
              - is_tool_allowed(), is_user_allowed(), get_rate_limit(), get_max_tokens() methods
```

### [ROAD-F02] Streaming Memory Context

```
Status:       COMPLETE
Priority:     P3-MEDIUM
Description:  Pass memory as dedicated system message segment
Evidence:     memory/manager.py now has:
              - build_system_message(): sync method returning message dict
              - build_system_message_async(): async version with relevance scores
              - Returns {"role": "system", "content": "...", "name": "memory_context"}
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

### [ROAD-F08] HuggingFace Model Auto-Import

```
Status:       COMPLETE
Priority:     P4-LOW
Description:  ModelPuller now auto-imports HuggingFace models to Ollama
Evidence:     model_puller.py _ensure_huggingface_models() now:
              - Checks if model already exists in Ollama
              - Tries multiple import methods: ollama pull, huggingface-cli, llamafile
              - Logs import success/failure with guidance
              - Auto-updates model availability in registry
```

---

## 6. Explicitly Deferred / Out of Scope

### [ROAD-D01] LMStudio Backend

```
Status:       REMOVED
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
Status:       REMOVED
Description:  Existing CLI + third-party UIs (Open WebUI, LibreChat) cover the use case
```

---

## 7. Verification Findings (run 19)

| Finding | Severity | Status |
|---------|----------|--------|
| 41 dependencies verified OK | INFO | VERIFIED |
| 70 modules import successfully | INFO | VERIFIED |
| 919 tests passing | INFO | VERIFIED |
| 0 lint violations | INFO | VERIFIED |
| 0 mypy errors | INFO | VERIFIED |
| 20 components instantiate OK | INFO | VERIFIED |
| 7 endpoints return 200 | INFO | VERIFIED |
| 4 launch scripts valid | INFO | VERIFIED |
| docker-compose.yml valid | INFO | VERIFIED |

*Last updated: 2026-03-02 (run 19) — Implemented ROAD-F01, F02, F08. Health: 10/10. Portal 1.4.6 fully production-ready.*
