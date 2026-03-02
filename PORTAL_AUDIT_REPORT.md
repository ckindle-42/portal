# Portal — Full Codebase Audit Report

**Date:** 2026-03-02 (delta run — run 6)
**Version audited:** 1.4.4 + unreleased ROAD-P01 partial
**Auditor:** Claude Code (claude-sonnet-4-6)
**Repository:** https://github.com/ckindle-42/portal

---

## 1. Executive Summary

**Health Score: 9.0/10 — PRODUCTION-READY (with open ROAD-P01 integration work)**

Portal 1.4.4 remains production-ready on existing paths. A new commit (`0a7f28f`) added `llm_classifier.py` (185 LOC) for ROAD-P01, introducing 2 lint violations and 2 mypy errors in that file. The module is not yet integrated into the routing layer and has no tests.

| # | Area | Prior | Current | Status |
|---|------|-------|---------|--------|
| 1 | **Health score** | 10/10 | 9.0/10 | REGRESSED (new code, open findings) |
| 2 | **Tests** | 874 pass / 1 skip | 874 pass / 1 skip | PASS (no new tests) |
| 3 | **Lint violations** | 0 | 2 (llm_classifier.py) | REGRESSED |
| 4 | **mypy errors** | 0 | 2 (llm_classifier.py) | REGRESSED |
| 5 | **ROAD-P01 integration** | PLANNED | IN-PROGRESS (module only) | PARTIAL |
| 6 | **Version** | 1.4.4 | 1.4.4 | UNCHANGED |

---

## 2. Delta Summary

### Changes Since Prior Audit (2026-03-02, v1.4.4, run 5)

| Metric | Prior | Current | Delta |
|--------|-------|---------|-------|
| Health Score | 10/10 | 9.0/10 | -1.0 |
| mypy errors | 0 | 2 | +2 (llm_classifier.py) |
| Test count | 874 pass / 1 skip | 874 pass / 1 skip | — (no new tests) |
| Source files | 96 | 97 | +1 (llm_classifier.py) |
| Lint violations | 0 | 2 | +2 (llm_classifier.py) |
| Version | 1.4.4 | 1.4.4 | — |

### New Commits Since Prior Audit

| Commit | Description | Status |
|--------|-------------|--------|
| `0a7f28f` | `feat(routing): add LLM-based task classifier` | PARTIAL — module added, not integrated |

### Findings from New Commit

1. **LINT-01** `src/portal/routing/llm_classifier.py:12` — UP035: `from typing import AsyncIterator` should be `from collections.abc import AsyncIterator` (auto-fixable)
2. **LINT-02** `src/portal/routing/llm_classifier.py:185` — W292: no newline at end of file (auto-fixable)
3. **TYPE-01** `src/portal/routing/llm_classifier.py:185` — `create_classifier()` passes `str | None` where `str` expected for `ollama_host` argument
4. **TYPE-02** `src/portal/routing/llm_classifier.py:185` — `create_classifier()` passes `str | None` where `str` expected for `model` argument
5. **MISSING-01** `LLMClassifier` — no unit tests
6. **MISSING-02** `router.py::resolve_model()` — still uses `regex_rules` (step 3), LLM classifier not wired in
7. **MISSING-03** `intelligent_router.py::IntelligentRouter` — still uses `TaskClassifier` directly, not `LLMClassifier`
8. **MISSING-04** `router_rules.json` — no `classifier` config block; `regex_rules` still the only classification mechanism
9. **MISSING-05** `.env.example` — `ROUTING_LLM_MODEL` env var not documented
10. **MISSING-06** Version not bumped for the new feature commit

---

## 3. Git History Summary

| Commit | Theme | Status | Debt/TODOs Left |
|--------|-------|--------|-----------------|
| `0a7f28f` | feat(routing): add LLM-based task classifier | PARTIAL | 10 open findings (see above) |
| `51ecf1b` | docs(audit): delta run 5 artifacts | COMPLETE | None |
| `257103e` | docs(arch): update version string to 1.4.4 | COMPLETE | None |
| `1337031` | bump: version to 1.4.4 | COMPLETE | None |

**Unfinished Work Register:**

| Source | Description | Evidence | Priority |
|--------|------------|----------|----------|
| `0a7f28f` | LLMClassifier module added but not integrated into router.py or intelligent_router.py | grep of callsites | HIGH |
| `0a7f28f` | No tests for llm_classifier.py | test directory scan | HIGH |
| `0a7f28f` | 2 lint + 2 mypy violations introduced | ruff + mypy output | HIGH |
| ROADMAP | router_rules.json not updated with classifier schema | file content | MEDIUM |
| ROADMAP | .env.example missing ROUTING_LLM_MODEL | file content | LOW |

---

## 4. Baseline Status

```
BASELINE STATUS
---------------
Environment:  Python 3.11.14 | .venv active | portal 1.4.4 importable
Dev tools:    ruff=0.15.4  pytest=9.0.2  mypy=1.19.1
Tests:        PASS=874  FAIL=0  SKIP=1  ERROR=0
Lint:         VIOLATIONS=2 (llm_classifier.py — UP035, W292)
Mypy:         ERRORS=2 (llm_classifier.py — arg-type in create_classifier())
Branches:     LOCAL=1 (current)  REMOTE=1
CLAUDE.md:    git policy PRESENT
API routes:   confirmed
Proceed:      YES (existing behavior unaffected; new file not integrated)
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

---

## 6. File Inventory — DELTA

| File Path | LOC | Status |
|-----------|-----|--------|
| `src/portal/routing/llm_classifier.py` | 185 | NEW — has 2 lint + 2 mypy violations, not integrated |
| All other 96 files | — | UNCHANGED |

---

## 7. Documentation Drift Report

| File | Issue | Impact |
|------|-------|--------|
| `.env.example` | `ROUTING_LLM_MODEL` not documented | LOW |
| `CHANGELOG.md` | No entry for `0a7f28f` LLM classifier commit | LOW |

---

## 8. Dependency Heatmap — UNCHANGED

No structural changes to module coupling.

---

## 9. Code Findings Register

| # | File | Lines | Category | Finding | Action | Risk |
|---|------|-------|----------|---------|--------|------|
| 1 | llm_classifier.py | 12 | LINT | UP035: typing.AsyncIterator → collections.abc.AsyncIterator | `ruff --fix` | LOW |
| 2 | llm_classifier.py | 185 | LINT | W292: no newline at end of file | `ruff --fix` | LOW |
| 3 | llm_classifier.py | 185 | TYPE_SAFETY | create_classifier() arg "ollama_host" str\|None → str | Add type narrowing | LOW |
| 4 | llm_classifier.py | 185 | TYPE_SAFETY | create_classifier() arg "model" str\|None → str | Add type narrowing | LOW |
| 5 | llm_classifier.py | — | TEST | No unit tests for LLMClassifier | Add tests/unit/routing/test_llm_classifier.py | MEDIUM |
| 6 | router.py | 125-129 | MISSING | regex_rules step not replaced by LLM classifier | Wire LLMClassifier into resolve_model() | MEDIUM |
| 7 | intelligent_router.py | 44,61,79 | MISSING | TaskClassifier not replaced by LLMClassifier | Make route() async, wire LLMClassifier | MEDIUM |
| 8 | router_rules.json | — | CONFIG | No "classifier" config block | Add classifier schema per ROADMAP design | LOW |
| 9 | .env.example | — | DOCS | ROUTING_LLM_MODEL not present | Add with default value | LOW |
| 10 | __init__.py, CHANGELOG | — | DOCS | New feature not versioned or documented | Bump to 1.4.5, add CHANGELOG entry | LOW |

---

## 10. Test Suite Rationalization

| Action | Target | Reason |
|--------|--------|--------|
| ADD_MISSING | tests/unit/routing/test_llm_classifier.py | No coverage of new module |

**Required test contracts for `LLMClassifier`:**
- `classify()` with mocked Ollama returning valid category → returns `LLMClassification`
- `classify()` with mocked Ollama unavailable → falls back to regex classifier
- `classify()` with mocked Ollama returning invalid category → defaults to `GENERAL`
- `_fallback_to_regex()` maps all `TaskCategory` values correctly
- `create_classifier()` returns `LLMClassifier` instance with correct defaults

---

## 11. Architecture Assessment

### ROAD-P01 Integration Gap

`llm_classifier.py` introduces an async classifier but has not been wired in:

**router.py** (`resolve_model()` is synchronous, called from async proxy handler):
- Step 3 still uses precompiled regex from `_compiled_rules`
- Needs: `resolve_model()` → `async def resolve_model()`, step 3 replaced by `LLMClassifier.classify()` call
- Caller `proxy()` is already `async def` — safe to await

**intelligent_router.py** (`route()` is synchronous, called from `async def _execute_with_routing()` in agent_core.py):
- `self.classifier = TaskClassifier()` at line 44
- `self.classifier.classify(query)` at lines 61 and 79
- Needs: `route()` → `async def route()`, TaskClassifier replaced by LLMClassifier
- `agent_core.py:322` `self.router.route(query)` → `await self.router.route(query)`

Both changes require the LLMClassifier to also expose a synchronous path for use in the workspace routing branch (which still calls `self.classifier.classify(query)` even in the workspace-routing fast path for `classification` metadata).

---

## 12. Evolution Gap Register

| ID | Area | Current State | Target State | Priority |
|----|------|--------------|--------------|----------|
| EG-01 | LLM Routing | Module created, not integrated | Fully integrated in both routers | P2-HIGH |
| EG-02 | MLX Backend | Ollama only | MLX server | P3-MEDIUM |

---

## 13. Production Readiness Score

| Dimension | Score | Narrative |
|-----------|-------|-----------|
| Env config separation | 5/5 | Pydantic Settings fully wired |
| Error handling / observability | 5/5 | Structured logging, trace IDs |
| Security posture | 5/5 | HMAC auth, rate limiting, CORS |
| Dependency hygiene | 5/5 | All extras correct |
| Documentation completeness | 4/5 | .env.example and CHANGELOG gap |
| Build / deploy hygiene | 5/5 | Multi-platform launchers |
| Module boundary clarity | 5/5 | Clean DI |
| Test coverage quality | 4/5 | LLMClassifier uncovered |
| Evolution readiness | 4/5 | ROAD-P01 module exists but not integrated |
| Type safety | 4/5 | 2 mypy errors in new file |

**Composite: 4.6/5 — PRODUCTION-READY (existing paths clean; ROAD-P01 integration pending)**

Existing Portal 1.4.4 functionality is unaffected. The new `llm_classifier.py` module needs lint/type fixes, tests, and integration to complete ROAD-P01.
