# Portal — Full Codebase Audit Report

**Date:** 2026-03-02 (delta run — run 14)
**Version audited:** 1.4.5
**Auditor:** Claude Code (claude-sonnet-4-6)
**Repository:** https://github.com/ckindle-42/portal
**Branch:** claude/execute-codebase-review-R6rif

---

## 1. Executive Summary

**Health Score: 9.0/10 — PRODUCTION-READY WITH 2 OPEN ISSUES**

Portal 1.4.5 remains functionally sound and production-ready. However, two regressions introduced by the `feat: add auto-pull models on startup` commit (`6d4c0a1`) were not caught in run 13 because run 13 claimed tests "pass (sample verified)" rather than running the full suite. A full run now shows:

- **1 test failing**: `test_all_models_available_by_default` — test does not account for the `huggingface` backend (which legitimately has `available: false` by default).
- **1 mypy error**: `server.py:784` — `Settings` object assigned to variable typed `dict[Any, Any] | None`.

Both issues are shallow fixes (< 10 lines each). All other CI gates are clean.

| # | Area | Prior | Current | Status |
|---|------|-------|---------|--------|
| 1 | **Health score** | 10/10 | 9.0/10 | REGRESSION |
| 2 | **Tests** | "sample verified" | 913 passed, 1 failed, 1 skipped | REGRESSION |
| 3 | **Lint violations** | 0 | 0 | CLEAN |
| 4 | **mypy errors** | 0 | 1 | REGRESSION |
| 5 | **Source files** | 98 | 100 | +2 (model_puller.py, new __init__) |

---

## 2. Delta Summary

### Changes Since Prior Audit (2026-03-02, v1.4.5, run 13)

| Metric | Prior | Current | Delta |
|--------|-------|---------|-------|
| Health Score | 10/10 | 9.0/10 | -1.0 (2 regressions) |
| mypy errors | "0" | 1 | +1 |
| Lint violations | 0 | 0 | 0 |
| Test count (collected) | 915 | 915 | 0 |
| Tests passing | "all" (sample) | 913 | -1 net |
| Tests failing | 0 (claimed) | 1 | +1 |
| Source files | 98 | 100 | +2 |
| Version (`__init__.py`) | 1.4.5 | 1.4.5 | 0 |

### Completed Since Prior Audit

All commits in run 13 were already present (run 13 audited commits `6d4c0a1` and `d3910f3`). No new feature commits since run 13.

### Regressions Introduced (Now Detected)

| ID | Source | Commit | Description |
|----|--------|--------|-------------|
| BUG-01 | `tests/unit/test_data_driven_registry.py:45-55` | `6d4c0a1` | `test_all_models_available_by_default` fails because HuggingFace model `hf_llama32_3b` has `available: false` in `default_models.json` but test only exempts `mlx` backend. Test needs to also exempt `huggingface` backend (or any non-ollama, non-mlx backends). |
| BUG-02 | `src/portal/interfaces/web/server.py:784` | `0713218` | mypy error: `config = settings` assigns `Settings` to variable typed `dict[Any, Any] \| None`. The variable `config` is a function parameter of that type; the assignment should be `config = settings  # type: ignore[assignment]` or the function signature should accept `Settings`. |

### Still Open from Prior Audit

All prior tasks were stated as complete. The two items above are new regressions.

---

## 3. Git History Summary

| Commit | Theme | Status |
|--------|-------|--------|
| `7a40712` | docs: remove working plan file after completion | COMPLETE |
| `8635a60` | docs: sync documentation and move agent prompts to docs/agents/ | COMPLETE |
| `3d7343b` | docs: update version in CLAUDE.md to 1.4.5 | COMPLETE |
| `eb53e3d` | docs(audit): delta run 13 — auto-pull models, docker updates | COMPLETE |
| `d3910f3` | chore: update docker images to latest versions | COMPLETE |
| `6d4c0a1` | feat: add auto-pull models on startup | COMPLETE (but introduced BUG-01 + BUG-02) |
| `0713218` | fix: load Ollama URL from Settings properly | COMPLETE (introduced BUG-02) |
| `b77d527` | docs(audit): delta run 12 | COMPLETE |

**Unfinished Work Register:**

| Source | Description | Priority |
|--------|-------------|----------|
| BUG-01 | Fix `test_all_models_available_by_default` to exempt `huggingface` backend | HIGH |
| BUG-02 | Fix mypy error in `server.py:784` — `config = settings` type mismatch | HIGH |

---

## 4. Baseline Status

```
BASELINE STATUS
---------------
Environment:  Python 3.11.14 | .venv active | portal 1.4.5 importable
              fastapi 0.135.1 | pydantic 2.12.5
Dev tools:    ruff (all checks passed)  pytest 9.0.2  mypy (1 error)
Tests:        FAIL=1  SKIP=1  PASS=913  (915 selected from 942 collected)
Lint:         VIOLATIONS=0
Mypy:         ERRORS=1 (server.py:784 — type mismatch on config assignment)
Branches:     LOCAL=2 (master, claude/execute-codebase-review-R6rif)
              REMOTE=2 (origin/claude/execute-codebase-review-R6rif, origin/main)
CLAUDE.md:    git policy PRESENT
API routes:   confirmed (see Section 5)
Proceed:      YES — production-ready, 2 minor regressions require fixes
```

---

## 5. Public Surface Inventory — UNCHANGED

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/chat/completions` | Bearer | OpenAI-compatible chat, streaming SSE |
| GET | `/v1/models` | Bearer | Virtual model list from Ollama router |
| POST | `/v1/audio/transcriptions` | Bearer | Whisper audio transcription proxy |
| WS | `/ws` | Bearer | WebSocket streaming chat |
| GET | `/health` | None | System health |
| GET | `/health/live` | None | K8s liveness probe |
| GET | `/health/ready` | None | K8s readiness probe |
| GET | `/metrics` | None | Prometheus metrics |
| GET/POST | `/:8000/*` | ROUTER_TOKEN | Proxy router: Ollama API with model rewriting |
| GET | `/:8000/health` | None | Proxy router health |
| POST | `/:8000/api/dry-run` | ROUTER_TOKEN | Routing decision preview |

---

## 6. File Inventory

Total: **100 Python source files** (up from 98 — added `model_puller.py` and `__init__.py` changes).

### New Files Since Run 13

| File | LOC | Purpose |
|------|-----|---------|
| `src/portal/routing/model_puller.py` | 156 | ModelPuller class — auto-pull Ollama + HuggingFace models |

### Key Files by Module

| Module | Files | Notes |
|--------|-------|-------|
| `src/portal/agent/` | 2 | CentralDispatcher, __init__ |
| `src/portal/config/` | 2 | Settings (Pydantic v2 BaseSettings), __init__ |
| `src/portal/core/` | 9 | AgentCore, EventBus, ContextManager, factories, db, structured_logger, types, exceptions, interfaces |
| `src/portal/interfaces/` | 5 | Web (FastAPI :8081), Telegram, Slack |
| `src/portal/memory/` | 2 | MemoryManager (Mem0 or SQLite) |
| `src/portal/middleware/` | 3 | HITL approval, tool confirmation, __init__ |
| `src/portal/observability/` | 5 | Health, metrics, config_watcher, watchdog, log_rotation |
| `src/portal/protocols/mcp/` | 2 | MCPRegistry |
| `src/portal/routing/` | 11 | IntelligentRouter, ExecutionEngine, ModelRegistry, model_puller, BackendRegistry, WorkspaceRegistry, LLMClassifier, TaskClassifier, circuit_breaker, router, model_backends |
| `src/portal/security/` | 5 | Auth, rate_limiter, input_sanitizer, middleware, sandbox |
| `src/portal/tools/` | 34 | Auto-discovered MCP-compatible tools (media, data, git, web, automation, document, system, knowledge) |
| Root | 3 | `__init__.py`, `cli.py`, `lifecycle.py` |

---

## 7. Documentation Drift Report

| File | Issue | Current Text | Required Correction | Impact |
|------|-------|-------------|---------------------|--------|
| Run-13 PORTAL_AUDIT_REPORT.md | Claimed 0 test failures without running full suite | "Tests: PASS (sample verified) FAIL=0" | Full suite shows 1 failure | Audit artifact inaccuracy |
| Run-13 PORTAL_AUDIT_REPORT.md | Claimed 0 mypy errors | "Mypy: ERRORS=0" | Full mypy run shows 1 error | Audit artifact inaccuracy |

No production documentation drift found. README, ARCHITECTURE.md, CHANGELOG.md, and .env.example remain accurate for v1.4.5.

---

## 8. Dependency Heatmap

No structural changes. Module coupling unchanged from run 13. Key coupling paths:

```
lifecycle.py → config/settings.py → (all configs)
lifecycle.py → core/agent_core.py → routing/execution_engine.py
                                  → routing/model_registry.py
                                  → routing/intelligent_router.py
interfaces/web/server.py → security/middleware.py → core/agent_core.py
routing/model_puller.py → routing/model_registry.py (new dependency)
lifecycle.py → routing/model_puller.py (new — lazy import)
```

---

## 9. Code Findings Register

| # | File | Lines | Category | Finding | Action | Risk |
|---|------|-------|----------|---------|--------|------|
| 1 | `tests/unit/test_data_driven_registry.py` | 45-55 | BUG | `test_all_models_available_by_default` does not account for `huggingface` backend — `hf_llama32_3b` has `available: false` by design but test asserts all non-`mlx` models must be available. Root cause: commit `6d4c0a1` added HuggingFace model entry but did not update the test. Fix: add `or model.backend == "huggingface"` to the MLX exclusion condition. | TASK-57: Fix test to exclude `huggingface` backend from availability assertion | HIGH |
| 2 | `src/portal/interfaces/web/server.py` | 784 | BUG/TYPE | mypy error `[assignment]`: `config = settings` assigns `Settings` to `dict[Any, Any] \| None` parameter. The intent (commit `0713218`) was to pass `Settings` to `WebInterface` for proper backend URL resolution. Fix: add `# type: ignore[assignment]` to line 784, or change function signature to accept `Settings \| dict[Any, Any] \| None`. | TASK-58: Fix mypy type error in `server.py:784` | MEDIUM |
| 3 | `src/portal/tools/media_tools/image_generator.py` | 30 | TODO | `# TODO: Implement actual mflux invocation` — placeholder stub. Known, deferred. | Deferred — external dependency (mflux) | LOW |
| 4 | `src/portal/tools/media_tools/audio_generator.py` | 22 | TODO | `# TODO: Implement actual CosyVoice/MOSS-TTS invocation` — placeholder stub. Known, deferred. | Deferred — external dependency (CosyVoice) | LOW |
| 5 | `src/portal/protocols/mcp/mcp_registry.py` | 29 | INFO | mypy note (not error): untyped function body not checked. Not a blocker. | No action required | NONE |
| 6 | `src/portal/interfaces/web/server.py` | 528 | INFO | mypy note (not error): untyped function body not checked. Not a blocker. | No action required | NONE |

**Active issues: 2 (BUG-01 test failure, BUG-02 mypy error). Deferred: 2 TODOs.**

---

## 10. Test Suite Rationalization

| Action | Target | Reason |
|--------|--------|--------|
| FIX | `tests/unit/test_data_driven_registry.py:45-55` | Add `huggingface` to backend exclusion list alongside `mlx` in `test_all_models_available_by_default` |
| KEEP | All other 914 tests | Unchanged and passing |

**Current state**: 913 passed, 1 failed (`test_all_models_available_by_default`), 1 skipped (`test_extract_text_from_pdf` — requires optional PDF OCR deps), 27 deselected (e2e + integration).

**Root cause of failure**: The `feat: add auto-pull models on startup` commit (`6d4c0a1`) added a HuggingFace example model entry to `default_models.json` with `"available": false` (correct — HF models require manual GGUF conversion). The test `test_all_models_available_by_default` was not updated to exempt the `huggingface` backend, which it should treat the same as `mlx` (requires external infra, starts unavailable).

**Fix**:
```python
# Line 48-55 in tests/unit/test_data_driven_registry.py
for model in registry.get_all_models():
    if model.backend in ("mlx", "huggingface"):
        # MLX models require mlx_lm.server; HuggingFace models require manual import
        assert not model.available, (
            f"{model.model_id} should be unavailable by default "
            f"(backend '{model.backend}' requires external setup)"
        )
    else:
        assert model.available, f"{model.model_id} should be available"
```

---

## 11. Architecture Assessment

### Module Blueprint — UNCHANGED

All features confirmed complete and operational:
- **LLM Routing (ROAD-P01):** COMPLETE — dual LLMClassifier + TaskClassifier in IntelligentRouter; LLMClassifier + regex fallback in proxy router (:8000)
- **MLX Backend (ROAD-P02):** COMPLETE — MLXServerBackend targeting mlx_lm.server on :8800
- **K8s Health Probes:** COMPLETE — `/health/live` and `/health/ready` wired
- **Config Hot-Reload (ROAD-F05):** COMPLETE — ConfigWatcher propagates rate limit changes at runtime
- **Auto-Pull Models (ROAD-F06):** COMPLETE — ModelPuller class (but introduced regression)
- **WorkspaceRegistry:** COMPLETE — virtual model names mapped to concrete Ollama models
- **BackendRegistry:** COMPLETE — named backend instances (Ollama, MLX)
- **Documentation:** COMPLETE

### New Regression Assessment

The two regressions (BUG-01, BUG-02) are shallow. They do not affect runtime behavior — the test failure is a test-expectation mismatch (not a production bug), and the mypy error is a type annotation issue that does not affect runtime behavior (Python is duck-typed, and `Settings` does duck-type as a config-like object for `WebInterface`). However, both should be fixed to restore CI green state.

---

## 12. Evolution Gap Register

| ID | Area | Current State | Target State | Priority |
|----|------|--------------|--------------|----------|
| BUG-01 | Test suite | 1 failing test | All tests passing | HIGH — blocks CI |
| BUG-02 | Type safety | 1 mypy error | 0 mypy errors | HIGH — breaks mypy clean |

---

## 13. Production Readiness Score

| Dimension | Score | Narrative |
|-----------|-------|-----------|
| Env config separation | 5/5 | All env vars documented in .env.example; Pydantic Settings v2 |
| Error handling / observability | 5/5 | Structured logging, trace IDs, circuit breaker, Prometheus at :8081/metrics |
| Security posture | 5/5 | HMAC auth, rate limiting, CORS, input sanitization, Docker sandbox option |
| Dependency hygiene | 5/5 | All extras correct; 0 vulnerable pins; httpx replaces aiohttp in core path |
| Documentation completeness | 4/5 | All docs accurate; run-13 audit artifacts contained inaccurate test/mypy claims |
| Build / deploy hygiene | 5/5 | Multi-platform launchers; systemd + Docker Compose; K8s health probes |
| Module boundary clarity | 5/5 | Clean DI; well-scoped modules; model_puller correctly isolated in routing/ |
| Test coverage quality | 4/5 | 913/915 tests passing; 1 failure is test-expectation mismatch, not production bug |
| Evolution readiness | 5/5 | MLX backend complete; routing fully functional; auto-pull implemented |
| Type safety | 4/5 | 1 mypy error in server.py:784; trivial fix |

**Composite: 4.7/5 — 9.0/10 — PRODUCTION-READY WITH 2 MINOR REGRESSIONS**

Two shallow regressions from the `feat: add auto-pull models on startup` commit were not caught in run 13 (because run 13 used "sample verified" instead of full suite). Fix both to restore 10/10.
