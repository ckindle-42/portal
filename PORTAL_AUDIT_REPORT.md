# Portal — Full Codebase Audit Report

**Date:** 2026-03-02 (delta run — run 7)
**Version audited:** 1.4.5
**Auditor:** Claude Code (claude-sonnet-4-6)
**Repository:** https://github.com/ckindle-42/portal

---

## 1. Executive Summary

**Health Score: 9.3/10 — PRODUCTION-READY (TASK-41 + 3 minor cleanup items remain)**

Portal 1.4.5 represents a significant step forward from run 6. Commit `f6ed8dd` completed
7 of the 8 ROAD-P01 tasks: lint and type errors resolved, 16 unit tests added, proxy router
(`router.py`) wired with LLMClassifier, `router_rules.json` configured, `.env.example`
updated, and version bumped. TASK-41 (IntelligentRouter wiring) was not implemented.
Three new findings were discovered: dead `stream_classify()` method, `ROUTING_LLM_MODEL`
env var documented but inoperative, and version drift in `pyproject.toml` and
`docs/ARCHITECTURE.md`.

| # | Area | Prior | Current | Status |
|---|------|-------|---------|--------|
| 1 | **Health score** | 9.0/10 | 9.3/10 | IMPROVED |
| 2 | **Tests** | 874 pass / 1 skip | 890 pass / 1 skip | IMPROVED (+16) |
| 3 | **Lint violations** | 2 | 0 | FIXED |
| 4 | **mypy errors** | 2 | 0 | FIXED |
| 5 | **ROAD-P01 (proxy router)** | NOT integrated | COMPLETE (TASK-40) | FIXED |
| 6 | **ROAD-P01 (IntelligentRouter)** | NOT integrated | NOT integrated | STILL OPEN |
| 7 | **Version (pyproject.toml)** | 1.4.4 | 1.4.4 (stale) | REGRESSION |
| 8 | **stream_classify() dead code** | — | Exists | NEW FINDING |
| 9 | **ROUTING_LLM_MODEL env var** | — | Documented but inoperative | NEW FINDING |

---

## 2. Delta Summary

### Changes Since Prior Audit (2026-03-02, v1.4.4, run 6)

| Metric | Prior | Current | Delta |
|--------|-------|---------|-------|
| Health Score | 9.0/10 | 9.3/10 | +0.3 |
| mypy errors | 2 | 0 | −2 (fixed) |
| Lint violations | 2 | 0 | −2 (fixed) |
| Test count | 874 pass / 1 skip | 890 pass / 1 skip | +16 tests |
| Source files | 97 | 97 | — |
| Version (`__init__.py`) | 1.4.4 | 1.4.5 | bumped |
| Version (`pyproject.toml`) | 1.4.4 | 1.4.4 | NOT bumped (drift) |
| Version (`ARCHITECTURE.md`) | 1.4.4 | 1.4.4 | NOT bumped (drift) |

### Completed Since Prior Audit

| Task | Description | Commit |
|------|-------------|--------|
| TASK-36 | Lint fixed (UP035, W292) in llm_classifier.py | f6ed8dd |
| TASK-37 | mypy arg-type errors fixed in create_classifier() | f6ed8dd |
| TASK-38 | 16 unit tests added (tests/unit/test_llm_classifier.py) | f6ed8dd |
| TASK-39 | ROUTING_LLM_MODEL documented in .env.example | f6ed8dd |
| TASK-40 | router.py::resolve_model() made async, LLMClassifier integrated | f6ed8dd |
| TASK-42 | "classifier" config block added to router_rules.json | f6ed8dd |
| TASK-43 | Version bumped to 1.4.5 in __init__.py, CHANGELOG updated | f6ed8dd |

### Still Open from Prior Audit

| Task | Description | Status |
|------|-------------|--------|
| TASK-41 | intelligent_router.py::IntelligentRouter.route() not wired to LLMClassifier | STILL OPEN |

### New Findings (this run)

1. **DEAD-01** `llm_classifier.py:166–172` — `stream_classify()` is speculative dead code; no production caller, no test
2. **CONFIG-01** `router.py:63` — `LLMClassifier(ollama_host=OLLAMA_HOST)` bypasses `create_classifier()`; `ROUTING_LLM_MODEL` env var documented in `.env.example` has no effect
3. **DOC-01** `pyproject.toml:7` — version `1.4.4` stale; `__init__.py` says `1.4.5`
4. **DOC-02** `docs/ARCHITECTURE.md:3,443` — version `1.4.4` stale; should be `1.4.5`

---

## 3. Git History Summary

| Commit | Theme | Status | Debt/TODOs Left |
|--------|-------|--------|-----------------|
| `f6ed8dd` | feat(routing): ROAD-P01 LLM-based intelligent routing integration | PARTIAL | TASK-41 skipped; 3 new minor findings |
| `2f8428c` | fix(mcp): fix scrapling launch and mcpo server configuration | COMPLETE | None |
| `b077b14` | docs(audit): delta run 6 — ROAD-P01 IN-PROGRESS, TASK-36–43 action plan | COMPLETE | None |
| `0a7f28f` | feat(routing): add LLM-based task classifier | COMPLETE | All issues fixed in f6ed8dd |

**Unfinished Work Register:**

| Source | Description | Evidence | Priority |
|--------|------------|----------|----------|
| `f6ed8dd` | IntelligentRouter.route() still uses TaskClassifier, not wired to LLMClassifier | intelligent_router.py:80 | MEDIUM |
| `f6ed8dd` | agent_core.py:322 still calls self.router.route(query) without await | agent_core.py:322 | MEDIUM |
| `f6ed8dd` | stream_classify() method is dead code | grep callsites: 0 | LOW |
| `f6ed8dd` | router.py instantiates LLMClassifier directly; ROUTING_LLM_MODEL env var unused | router.py:63 | LOW |
| Various | pyproject.toml version 1.4.4 stale (init says 1.4.5) | file diff | LOW |
| Various | docs/ARCHITECTURE.md version 1.4.4 stale | file diff | LOW |

---

## 4. Baseline Status

```
BASELINE STATUS
---------------
Environment:  Python 3.11.14 | .venv active | portal 1.4.5 importable
Dev tools:    ruff=0.15.4  pytest=9.0.2  mypy=1.19.1
Tests:        PASS=890  FAIL=0  SKIP=1  ERROR=0
Lint:         VIOLATIONS=0
Mypy:         ERRORS=0 (97 source files; standard strict=false mode)
Branches:     LOCAL=2 (claude/execute-codebase-review-mrIAM + stale master)
              REMOTE=2 (origin/claude/... + origin/main)
              master: stale local-only; all commits present in origin/main
CLAUDE.md:    git policy PRESENT (Environment Setup section absent but non-critical)
API routes:   confirmed (/v1/chat/completions, /v1/models, /health, /metrics)
Proceed:      YES
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
| GET | `/metrics` | None | Prometheus metrics |
| GET/POST | `/:8000/*` | ROUTER_TOKEN | Proxy router: Ollama API with model rewriting |
| GET | `/:8000/health` | None | Proxy router health |
| POST | `/:8000/api/dry-run` | ROUTER_TOKEN | Routing decision preview |

---

## 6. File Inventory — DELTA

All 97 source files from run 6 are unchanged except:

| File Path | LOC | Status |
|-----------|-----|--------|
| `src/portal/routing/llm_classifier.py` | 197 | UPDATED (lint+type fixed; stream_classify added — dead) |
| `src/portal/routing/router.py` | 304 | UPDATED (resolve_model async, LLMClassifier wired) |
| `src/portal/routing/intelligent_router.py` | 220 | COMMENT ONLY (comment added, no functional change) |
| `src/portal/routing/router_rules.json` | 56 | UPDATED (classifier block added) |
| `src/portal/__init__.py` | 12 | UPDATED (version 1.4.5) |
| `tests/unit/test_llm_classifier.py` | 191 | NEW (16 tests) |
| `tests/unit/test_router_auth.py` | 95 | UPDATED (async test adaptations) |
| `.env.example` | 35 | UPDATED (ROUTING_LLM_MODEL added) |
| `CHANGELOG.md` | ~350 | UPDATED (1.4.5 entry added) |

---

## 7. Documentation Drift Report

| File | Issue | Current Text | Required Correction | Impact |
|------|-------|-------------|---------------------|--------|
| `pyproject.toml:7` | Version stale | `version = "1.4.4"` | `version = "1.4.5"` | MED — packaging tools read this |
| `docs/ARCHITECTURE.md:3` | Version stale | `**Version:** 1.4.4` | `**Version:** 1.4.5` | LOW |
| `docs/ARCHITECTURE.md:443` | Version stale | `version = "1.4.4"` | `version = "1.4.5"` | LOW |
| `docs/ARCHITECTURE.md:146` | LLM routing described as future | "Future unification...LLM-based" | Note partial implementation in proxy router | LOW |
| `CHANGELOG.md` | TASK-41 pending not noted | 1.4.5 entry says "integrated" | Add note that IntelligentRouter still uses TaskClassifier | LOW |

---

## 8. Dependency Heatmap — UNCHANGED

No structural changes to module coupling since run 5.

---

## 9. Code Findings Register

| # | File | Lines | Category | Finding | Action | Risk |
|---|------|-------|----------|---------|--------|------|
| 1 | intelligent_router.py | 49–80 | MISSING | route() still sync, still uses TaskClassifier; TASK-41 not implemented | Wire LLMClassifier per TASK-41 spec | MEDIUM |
| 2 | agent_core.py | 322 | MISSING | self.router.route(query) not awaited (companion to finding 1) | Change to await when route() goes async | MEDIUM |
| 3 | llm_classifier.py | 166–172 | DEAD_CODE | stream_classify() — speculative async generator, no callers, no tests | Remove the method | LOW |
| 4 | router.py | 63 | CONFIG_HARDENING | LLMClassifier instantiated without model arg; ROUTING_LLM_MODEL env var unused | Use create_classifier(ollama_host=OLLAMA_HOST) instead | LOW |
| 5 | pyproject.toml | 7 | DOCS | version 1.4.4 stale; __init__.py says 1.4.5 | Bump to 1.4.5 | LOW |
| 6 | docs/ARCHITECTURE.md | 3,443 | DOCS | version 1.4.4 stale; should be 1.4.5 | Update both references | LOW |

---

## 10. Test Suite Rationalization

| Action | Target | Reason |
|--------|--------|--------|
| KEEP | tests/unit/test_llm_classifier.py (16 tests) | All 16 pass; cover all critical paths |
| ADD_MISSING | stream_classify() — None (method should be removed) | N/A after TASK-46 |
| KEEP | tests/unit/test_router_auth.py (7 tests) | Updated for async resolve_model; all pass |
| KEEP | All 874 existing tests | Unchanged; all pass |

**Test counts (collected/passing):**
- Collected: 891 (27 deselected as e2e/integration needing Ollama)
- Passing: 890 | Skip: 1 | Fail: 0

---

## 11. Architecture Assessment

### ROAD-P01 Integration Gap — Current State

**Proxy Router (`:8000` — router.py):** FULLY INTEGRATED (TASK-40 complete)
- `resolve_model()` is now `async def`
- Step 3: `_llm_classifier.classify(user_text)` called when `requested_model == "auto"`
- Fallback chain: LLM classifier → regex rules → explicit model → default
- Category-model map read from `router_rules.json["classifier"]["categories"]`

**AgentCore Router (`:8081` — intelligent_router.py):** NOT INTEGRATED (TASK-41 still open)
- `route()` is still `def` (synchronous)
- Still uses `TaskClassifier` exclusively
- `agent_core.py:322` still calls `self.router.route(query)` (no await)
- This means all `/v1/chat/completions` requests routed through AgentCore still use regex heuristics

### ENV VAR Gap

`ROUTING_LLM_MODEL` is documented in `.env.example` and used in `create_classifier()`, but
`router.py:63` instantiates `LLMClassifier(ollama_host=OLLAMA_HOST)` directly — bypassing
`create_classifier()`. The env var has no effect on the model actually used.

**Fix:** `_llm_classifier = create_classifier(ollama_host=OLLAMA_HOST)` in router.py.

---

## 12. Evolution Gap Register

| ID | Area | Current State | Target State | Priority |
|----|------|--------------|--------------|----------|
| EG-01 | LLM Routing (IntelligentRouter) | TaskClassifier only | LLMClassifier wired | P2-HIGH |
| EG-02 | ENV var wiring for LLM model | ROUTING_LLM_MODEL inoperative | create_classifier() used | P3-MEDIUM |
| EG-03 | Dead code removal | stream_classify() exists | Removed | P4-LOW |
| EG-04 | Version sync | pyproject.toml / ARCHITECTURE.md stale | 1.4.5 everywhere | P3-MEDIUM |
| EG-05 | MLX Backend | Ollama only | MLX server | P3-MEDIUM |

---

## 13. Production Readiness Score

| Dimension | Score | Narrative |
|-----------|-------|-----------|
| Env config separation | 4/5 | ROUTING_LLM_MODEL documented but inoperative |
| Error handling / observability | 5/5 | Structured logging, trace IDs, circuit breaker |
| Security posture | 5/5 | HMAC auth, rate limiting, CORS |
| Dependency hygiene | 5/5 | All extras correct; 0 vulnerable pins |
| Documentation completeness | 4/5 | pyproject.toml + ARCHITECTURE.md version stale |
| Build / deploy hygiene | 5/5 | Multi-platform launchers; systemd + Docker |
| Module boundary clarity | 5/5 | Clean DI; llm_classifier.py well-scoped |
| Test coverage quality | 5/5 | 890 tests, all critical paths covered |
| Evolution readiness | 4/5 | Proxy router LLM-ready; AgentCore still regex |
| Type safety | 5/5 | 0 mypy errors (97 files, standard mode) |

**Composite: 4.7/5 — PRODUCTION-READY**

Existing Portal 1.4.5 production paths are clean. The remaining open work (TASK-41 +
minor fixes) does not affect system stability or security — it completes ROAD-P01.
