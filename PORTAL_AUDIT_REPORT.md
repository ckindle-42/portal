# Portal — Full Codebase Audit Report

**Date:** 2026-03-02 (delta run — run 8)
**Version audited:** 1.4.5
**Auditor:** Claude Code (claude-sonnet-4-6)
**Repository:** https://github.com/ckindle-42/portal

---

## 1. Executive Summary

**Health Score: 9.5/10 — PRODUCTION-READY (documentation updates remain)**

Portal 1.4.5 has reached full ROAD-P01 completion. PR #96 (branch
`claude/execute-coding-agent-prompt-FRItj`, commit `71ce797`) implemented all
remaining TASK-41 through TASK-47: IntelligentRouter.route() is now async with
dual LLMClassifier + TaskClassifier, stream_classify() dead code removed,
router.py uses create_classifier() (ROUTING_LLM_MODEL now respected), and
version strings synced. Zero lint violations, zero mypy errors, 890 tests
passing. Remaining open work is entirely documentation: ARCHITECTURE.md stale
routing descriptions, incomplete CHANGELOG 1.4.5 entry, stale ROADMAP.md
status fields, and undocumented env vars.

| # | Area | Prior | Current | Status |
|---|------|-------|---------|--------|
| 1 | **Health score** | 9.3/10 | 9.5/10 | IMPROVED |
| 2 | **Tests** | 890 pass / 1 skip | 890 pass / 1 skip | UNCHANGED |
| 3 | **Lint violations** | 0 | 0 | CLEAN |
| 4 | **mypy errors** | 0 | 0 | CLEAN |
| 5 | **TASK-41 (IntelligentRouter LLM)** | NOT implemented | COMPLETE | FIXED |
| 6 | **TASK-44 (pyproject.toml version)** | 1.4.4 stale | 1.4.5 | FIXED |
| 7 | **TASK-45 (ARCHITECTURE.md version)** | 1.4.4 stale | 1.4.5 | FIXED |
| 8 | **TASK-46 (stream_classify dead code)** | Present | Removed | FIXED |
| 9 | **TASK-47 (create_classifier wiring)** | Bypassed | Fixed | FIXED |
| 10 | **ARCHITECTURE.md routing desc** | — | Stale (TaskClassifier-only) | NEW FINDING |
| 11 | **CHANGELOG 1.4.5 entry** | — | Incomplete (pre-PR #96) | NEW FINDING |
| 12 | **ROADMAP.md status** | — | Shows "Planned" for completed work | NEW FINDING |
| 13 | **Undocumented env vars** | — | 12 vars used but absent from .env.example | NEW FINDING |
| 14 | **Stale `master` branch** | — | Local-only, 0 unique commits | NEW FINDING |

---

## 2. Delta Summary

### Changes Since Prior Audit (2026-03-02, v1.4.5, run 7)

| Metric | Prior | Current | Delta |
|--------|-------|---------|-------|
| Health Score | 9.3/10 | 9.5/10 | +0.2 |
| mypy errors | 0 | 0 | — |
| Lint violations | 0 | 0 | — |
| Test count | 890 pass / 1 skip | 890 pass / 1 skip | — |
| Source files | 97 | 97 | — |
| Version (`__init__.py`) | 1.4.5 | 1.4.5 | — |
| Evolution readiness | 4/5 | 5/5 | IMPROVED |
| Documentation completeness | 4/5 | 3.5/5 | REGRESSED (new drift found) |

### Completed Since Prior Audit

| Task | Description | Commit |
|------|-------------|--------|
| TASK-41 | IntelligentRouter.route() made async; dual LLMClassifier + TaskClassifier | 620d0a4 |
| TASK-44 | pyproject.toml version synced to 1.4.5 | b6f0671 |
| TASK-45 | docs/ARCHITECTURE.md version synced to 1.4.5 | b6f0671 |
| TASK-46 | stream_classify() and AsyncIterator import removed from llm_classifier.py | fa8e5ae |
| TASK-47 | router.py changed to use create_classifier(); ROUTING_LLM_MODEL now works | 4ac58c8 |
| chore | ruff formatting: trailing blank line in llm_classifier.py | 0038dc5 |
| upload | PORTAL_DOCUMENTATION_AGENT.md added to repo root | 214b16c |

### Still Open from Prior Audit

None — all prior open tasks are now complete.

### New Findings (this run)

1. **DOC-03** `docs/ARCHITECTURE.md:142` — Proxy Router described as "regex-based model selection"; LLMClassifier now primary since TASK-40
2. **DOC-04** `docs/ARCHITECTURE.md:144,149` — IntelligentRouter described as `TaskClassifier (100+ regex patterns)` only; TASK-41 now adds dual classification. Also "Future unification is a Track B opportunity" is stale
3. **DOC-05** `CHANGELOG.md` — [1.4.5] entry reflects only commit `f6ed8dd`; TASK-41 through TASK-47 (PR #96) not mentioned
4. **DOC-06** `ROADMAP.md` — Item 1 "LLM-Based Intelligent Routing" shows `Status: Planned`; it is now fully COMPLETE
5. **ENV-01** 12 env vars read in code absent from `.env.example`: REDIS_URL, MEM0_API_KEY, PORTAL_AUTH_DB, PORTAL_BOOTSTRAP_USER_ID, PORTAL_BOOTSTRAP_USER_ROLE, RATE_LIMIT_DATA_DIR, PORTAL_VRAM_USAGE_MB, PORTAL_UNIFIED_MEMORY_USAGE_MB, PORTAL_ENV, TELEGRAM_USER_ID (legacy singular), PORTAL_MEMORY_DB, PORTAL_MEMORY_PROVIDER
6. **BRANCH-01** `master` — stale local-only branch with 0 unique commits vs origin/main

---

## 3. Git History Summary

| Commit | Theme | Status | Debt/TODOs Left |
|--------|-------|--------|-----------------|
| `71ce797` | Merge PR #96: IntelligentRouter async + LLMClassifier full integration | COMPLETE | DOC-03/04/05/06 found |
| `214b16c` | Add files via upload: PORTAL_DOCUMENTATION_AGENT.md | COMPLETE | None (doc artifact) |
| `22f27c2` | Merge PR #95: delta run 7 audit artifacts | COMPLETE | None |
| `f6ed8dd` | feat(routing): ROAD-P01 LLM-based intelligent routing integration | COMPLETE | All follow-ups done in PR #96 |

**Unfinished Work Register:**

| Source | Description | Evidence | Priority |
|--------|------------|----------|----------|
| PR #96 merged | ARCHITECTURE.md routing descriptions stale post-TASK-40/41 | docs/ARCHITECTURE.md:142,144,149 | MEDIUM |
| PR #96 merged | CHANGELOG 1.4.5 entry missing TASK-41 through TASK-47 | CHANGELOG.md — no PR #96 entries | LOW |
| ROADMAP.md | LLM routing status shows "Planned" — now Complete | ROADMAP.md:10 | LOW |
| Code audit | 12 env vars used in code, absent from .env.example | grep os.getenv | LOW |
| Branch inventory | `master` local branch has 0 unique commits vs main | git branch | LOW |

---

## 4. Baseline Status

```
BASELINE STATUS
---------------
Environment:  Python 3.11.14 | .venv active | portal 1.4.5 importable
Dev tools:    ruff=0.15.4  pytest=9.0.2  mypy=1.19.1
Tests:        PASS=890  FAIL=0  SKIP=1  ERROR=0
Lint:         VIOLATIONS=0
Mypy:         ERRORS=0 (97 source files; strict=false mode)
Branches:     LOCAL=2 (claude/execute-codebase-review-Jdhwo + stale master)
              REMOTE=2 (origin/claude/execute-codebase-review-Jdhwo + origin/main)
              master: stale local-only; 0 unique commits vs origin/main
CLAUDE.md:    git policy PRESENT
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

Files changed since run 7:

| File Path | LOC | Status |
|-----------|-----|--------|
| `src/portal/routing/intelligent_router.py` | 241 | UPDATED (route() async, LLMClassifier dual classification) |
| `src/portal/routing/llm_classifier.py` | 187 | UPDATED (stream_classify removed, AsyncIterator import removed) |
| `src/portal/routing/router.py` | 303 | UPDATED (create_classifier() call, unchanged LOC) |
| `PORTAL_DOCUMENTATION_AGENT.md` | ~370 | NEW (documentation agent prompt — project artifact) |
| `docs/ARCHITECTURE.md` | same | version only updated; routing description stale |
| `pyproject.toml` | same | version synced to 1.4.5 |

All other 91 source files unchanged from run 6. Total: 97 Python source files.

---

## 7. Documentation Drift Report

| File | Issue | Current Text | Required Correction | Impact |
|------|-------|-------------|---------------------|--------|
| `docs/ARCHITECTURE.md:142` | Proxy Router desc stale | "regex-based model selection" | "LLM classifier (qwen2.5:0.5b) with regex fallback" | MED |
| `docs/ARCHITECTURE.md:144` | IntelligentRouter desc stale | "uses TaskClassifier (100+ regex patterns)" | "uses LLMClassifier (async) + TaskClassifier (metadata)" | MED |
| `docs/ARCHITECTURE.md:149` | Future work claim stale | "Future unification is a Track B opportunity" | Remove — ROAD-P01 is complete | LOW |
| `CHANGELOG.md:[1.4.5]` | Incomplete — TASK-41–47 absent | Only covers f6ed8dd | Add entries for PR #96 commits (b6f0671, fa8e5ae, 4ac58c8, 620d0a4, 0038dc5) | LOW |
| `ROADMAP.md:10` | Status stale | `Status: Planned` (Item 1) | `Status: Complete` | LOW |
| `.env.example` | 12 env vars absent | (missing entries) | Add REDIS_URL, MEM0_API_KEY, PORTAL_AUTH_DB, PORTAL_BOOTSTRAP_USER_ID/ROLE, RATE_LIMIT_DATA_DIR, PORTAL_VRAM_USAGE_MB, PORTAL_UNIFIED_MEMORY_USAGE_MB, PORTAL_ENV, PORTAL_MEMORY_DB, PORTAL_MEMORY_PROVIDER, TELEGRAM_USER_ID | LOW |

---

## 8. Dependency Heatmap — UNCHANGED

No structural changes to module coupling since run 5. The routing layer gained
one new dependency direction: `intelligent_router.py` → `llm_classifier.py`
(already present in proxy router since run 6). No circular dependencies.

---

## 9. Code Findings Register

| # | File | Lines | Category | Finding | Action | Risk |
|---|------|-------|----------|---------|--------|------|
| 1 | docs/ARCHITECTURE.md | 142 | DOCS | Proxy Router desc says "regex-based" — LLMClassifier is now primary | Update desc | LOW |
| 2 | docs/ARCHITECTURE.md | 144,149 | DOCS | IntelligentRouter desc says TaskClassifier only; future unification claim stale | Update desc | LOW |
| 3 | CHANGELOG.md | [1.4.5] | DOCS | Entry missing TASK-41–47 (PR #96 commits b6f0671, fa8e5ae, 4ac58c8, 620d0a4, 0038dc5) | Add missing changelog entries | LOW |
| 4 | ROADMAP.md | 10 | DOCS | LLM routing status "Planned" — now Complete | Mark Complete | LOW |
| 5 | .env.example | — | CONFIG_HARDENING | 12 env vars read via os.getenv absent from .env.example | Add with comments | LOW |
| 6 | master (local branch) | — | BRANCH | Stale local-only branch with 0 unique commits vs origin/main | Delete: `git branch -d master` | NONE |

---

## 10. Test Suite Rationalization

| Action | Target | Reason |
|--------|--------|--------|
| KEEP | tests/unit/test_intelligent_router.py (42 tests) | All pass; cover async route(), dual classification, all strategies |
| KEEP | tests/unit/test_llm_classifier.py (16 tests) | All pass; cover LLMClassifier, create_classifier |
| KEEP | All 832 other tests | Unchanged; all pass |

**Test counts (collected/passing):**
- Collected: 891 (27 deselected as e2e/integration needing Ollama)
- Passing: 890 | Skip: 1 | Fail: 0

**Coverage of new TASK-41 path:**
- `test_intelligent_router.py` uses `AsyncMock` for `router.llm_classifier.classify`
- All strategy paths tested with both TaskClassifier + LLMClassifier mocked
- Workspace routing tested (still uses TaskClassifier only — correct by design)

---

## 11. Architecture Assessment

### ROAD-P01 Integration — FULLY COMPLETE

**Proxy Router (`:8000` — router.py):** COMPLETE (since TASK-40, run 6)
- `resolve_model()` async; LLMClassifier fires for `requested_model == "auto"`
- Uses `create_classifier(ollama_host=OLLAMA_HOST)` — ROUTING_LLM_MODEL now respected

**AgentCore Router (`:8081` — intelligent_router.py):** COMPLETE (TASK-41, PR #96)
- `route()` is now `async def`
- Dual classification: `task_class = self.classifier.classify(query)` (sync, metadata)
  + `llm_class = await self.llm_classifier.classify(query)` (async, category override)
- Category override map: LLMCategory.CODE→CODE, REASONING→ANALYSIS, CREATIVE→CREATIVE, etc.
- `agent_core.py:322`: `decision = await self.router.route(query)` — awaited correctly
- Workspace routing branch: still uses TaskClassifier only (correct — workspace = explicit selection)

**Routing Architecture:**
```
Request → AgentCore → IntelligentRouter.route()
                           │
          ┌────────────────┴──────────────────┐
          │ Workspace?                          │ No
          │ → TaskClassifier (metadata only)    │
          │ → Workspace model                   │ → TaskClassifier (complexity, metadata)
          └─────────────────────────────────────┤ + LLMClassifier (category override)
                                                │ → Strategy → Model selection
                                                └───────────────
```

---

## 12. Evolution Gap Register

| ID | Area | Current State | Target State | Priority |
|----|------|--------------|--------------|----------|
| EG-01 | LLM Routing | COMPLETE (both routers) | N/A | DONE |
| EG-02 | ENV var wiring | COMPLETE (create_classifier used) | N/A | DONE |
| EG-03 | Dead code (stream_classify) | COMPLETE (removed) | N/A | DONE |
| EG-04 | Version sync | COMPLETE (pyproject.toml + ARCHITECTURE.md) | N/A | DONE |
| EG-05 | ARCHITECTURE.md routing desc | Stale (TaskClassifier-only) | Updated desc | P3-MEDIUM |
| EG-06 | CHANGELOG completeness | [1.4.5] entry incomplete | All PR #96 changes listed | P3-MEDIUM |
| EG-07 | ROADMAP.md status | Shows "Planned" | Shows "Complete" | P4-LOW |
| EG-08 | .env.example completeness | 12 undocumented vars | All vars documented | P4-LOW |
| EG-09 | MLX Backend | Ollama only | MLX server | P3-MEDIUM |

---

## 13. Production Readiness Score

| Dimension | Score | Narrative |
|-----------|-------|-----------|
| Env config separation | 4.2/5 | ROUTING_LLM_MODEL now respected; 12 vars undocumented |
| Error handling / observability | 5/5 | Structured logging, trace IDs, circuit breaker, Prometheus |
| Security posture | 5/5 | HMAC auth, rate limiting, CORS, input sanitization |
| Dependency hygiene | 5/5 | All extras correct; 0 vulnerable pins |
| Documentation completeness | 3.5/5 | ARCHITECTURE.md routing stale, CHANGELOG incomplete, ROADMAP.md stale |
| Build / deploy hygiene | 5/5 | Multi-platform launchers; systemd + Docker Compose |
| Module boundary clarity | 5/5 | Clean DI; llm_classifier.py well-scoped; no circular deps |
| Test coverage quality | 5/5 | 890 tests; all critical paths covered including async routing |
| Evolution readiness | 5/5 | Both routing paths now use LLMClassifier — ROAD-P01 COMPLETE |
| Type safety | 5/5 | 0 mypy errors (97 files, standard mode) |

**Composite: 4.77/5 — 9.5/10 — PRODUCTION-READY**

All production paths are clean. Open work is documentation cleanup only —
no functional defects, no security issues, no API contract changes.
