# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-02 (delta run v7 — ROAD-P01 completion + cleanup)
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.4.5 (version sync only; no new features)

---

## Project Context

Portal is a local-first AI platform (Python 3.11+ / FastAPI / async).
Source: `src/portal/` (97 Python files, ~16,095 LOC).
Tests: `tests/` (69 Python files, ~13,724 LOC, 890 currently passing).

**Non-negotiable constraints:**
- API contract locked: no behavior changes to existing endpoints
- No new features unless explicitly requested
- No cloud dependencies, no external AI frameworks
- Regex fallback must always be preserved (LLM classifier unavailability is expected)

---

## Session Bootstrap — Run Before Any Task

Do not read or modify any source file until this bootstrap completes successfully.

1. Activate or create the virtual environment:
   ```bash
   if [ -d .venv ]; then
     source .venv/bin/activate
   else
     python3 -m venv .venv && source .venv/bin/activate
     pip install --upgrade pip setuptools wheel
   fi
   ```

2. Install project and all dependency groups:
   ```bash
   pip install -e ".[all,dev]" 2>&1 | tail -10
   ```

3. Verify core imports and tooling:
   ```bash
   python3 -c "import portal; print('portal:', portal.__version__)"
   python3 -m ruff --version
   python3 -m pytest --version
   python3 -m mypy --version
   ```

4. Verify tests can be collected:
   ```bash
   python3 -m pytest tests/ --collect-only 2>&1 | tail -5
   ```

5. Run baseline verification:
   ```bash
   python3 -m ruff check src/ tests/        # expect 0 violations
   python3 -m pytest tests/ -v --tb=short   # expect 890 PASS
   python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2  # expect 0 errors
   ```

---

## Prior Work Summary

All tasks through TASK-40 and TASK-42–43 are COMPLETE. TASK-41 is the only
remaining prior task.

- TASK-36 (lint fix): COMPLETE
- TASK-37 (mypy fix): COMPLETE
- TASK-38 (llm_classifier tests): COMPLETE
- TASK-39 (.env.example): COMPLETE
- TASK-40 (router.py async + LLM): COMPLETE
- TASK-41 (intelligent_router.py LLM integration): **STILL OPEN**
- TASK-42 (router_rules.json): COMPLETE
- TASK-43 (version 1.4.5 + CHANGELOG): COMPLETE

**Current state:** 890 tests passing, 0 mypy errors, 0 lint violations.
`intelligent_router.py::route()` still synchronous and still uses TaskClassifier.
`agent_core.py:322` still calls `self.router.route(query)` without await.

---

## Open Tasks

### TASK-41 (from prior run — partially abandoned)
```
Tier:        2
File(s):     src/portal/routing/intelligent_router.py
             src/portal/core/agent_core.py
Symbol(s):   IntelligentRouter.route(), AgentCore._execute_with_routing()
Category:    ROAD-P01 integration (AgentCore router)
Finding:     IntelligentRouter.route() is still synchronous and still uses TaskClassifier.
             Commit f6ed8dd only added a comment to intelligent_router.py; no functional
             change was made. agent_core.py:322 still calls self.router.route(query) without await.

Action:      1. In intelligent_router.py __init__, import and add LLMClassifier alongside TaskClassifier:
                from .llm_classifier import LLMClassifier
                self.llm_classifier = LLMClassifier()
                self.classifier = TaskClassifier()  # keep for metadata

             2. Make route() async:
                async def route(
                    self, query: str, max_cost: float = 1.0,
                    workspace_id: str | None = None
                ) -> RoutingDecision:

             3. In the workspace routing branch (lines 58–77), keep TaskClassifier for
                classification metadata (sync is fine — no model selection involved):
                classification = self.classifier.classify(query)

             4. In the main classification path (line 80), use dual classification:
                task_class = self.classifier.classify(query)    # sync, for metadata
                llm_class = await self.llm_classifier.classify(query)  # async, for category
                from .llm_classifier import LLMCategory
                category_override = {
                    LLMCategory.CODE: TaskCategory.CODE,
                    LLMCategory.REASONING: TaskCategory.ANALYSIS,
                    LLMCategory.CREATIVE: TaskCategory.CREATIVE,
                    LLMCategory.TOOL_USE: TaskCategory.TOOL_USE,
                    LLMCategory.GENERAL: TaskCategory.GENERAL,
                }
                overridden_category = category_override.get(llm_class.category, task_class.category)
                classification = TaskClassification(
                    category=overridden_category,
                    complexity=task_class.complexity,
                    confidence=llm_class.confidence,
                    requires_code=task_class.requires_code,
                    requires_math=task_class.requires_math,
                )

             5. Update agent_core.py line 322:
                decision = await self.router.route(query)

             Note: strategy methods (_route_auto, _route_speed, etc.) are all sync
             and take TaskClassification — they continue to work unchanged.

Risk:        MEDIUM — changes model selection in AgentCore (/:8081 chat path)
Blast Radius: All chat requests via Portal API (:8081). Fallback via TaskClassifier preserved.
Parity:      Workspace routing unchanged. Strategy selection logic unchanged.
             TaskClassifier provides complexity/metadata; LLMClassifier provides category.
Acceptance:  python3 -m pytest tests/ -v --tb=short → 890+ PASS, 0 FAIL
             python3 -m ruff check src/ tests/ → 0
             python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2 → 0 errors
```

---

### TASK-44
```
Tier:        1
File(s):     pyproject.toml
Symbol(s):   version field (line 7)
Category:    DOCS / VERSION
Finding:     pyproject.toml still says version = "1.4.4" while __init__.py says "1.4.5".
             This causes `pip show portal` and build tools to report the wrong version.
Action:      Change line 7: version = "1.4.4" → version = "1.4.5"
Risk:        LOW
Blast Radius: Package metadata only; no behavior change
Parity:      N/A
Acceptance:  grep "version" pyproject.toml | head -1 → version = "1.4.5"
```

---

### TASK-45
```
Tier:        1
File(s):     docs/ARCHITECTURE.md
Symbol(s):   Version header (line 3), file tree comment (line 443)
Category:    DOCS
Finding:     ARCHITECTURE.md still references version "1.4.4" in two places.
Action:      1. Line 3: **Version:** 1.4.4 → **Version:** 1.4.5
             2. Line 443: version = "1.4.4" → version = "1.4.5"
Risk:        LOW (docs only)
Blast Radius: docs/ARCHITECTURE.md only
Parity:      No code change
Acceptance:  grep "1.4.4" docs/ARCHITECTURE.md → no output
```

---

### TASK-46
```
Tier:        1
File(s):     src/portal/routing/llm_classifier.py
Symbol(s):   stream_classify() (lines 166–172)
Category:    DEAD_CODE
Finding:     stream_classify() is an async generator method with no production callers
             and no tests. The test file docstring mentions it but no test exercises it.
             It is speculative future code that adds confusion and maintenance burden.
Action:      Delete lines 166–172 (the stream_classify method) entirely.
             Also remove AsyncIterator from the import on line 9 (from collections.abc
             import AsyncIterator) since it will no longer be used.
             Verify: grep -n "stream_classify\|AsyncIterator" src/portal/routing/llm_classifier.py
             → no output after removal.
Risk:        LOW — no callers in production or tests
Blast Radius: llm_classifier.py only
Parity:      No behavior change (dead code removal)
Acceptance:  python3 -m ruff check src/ tests/ → 0
             python3 -m pytest tests/ --tb=short → 890 PASS
             grep "stream_classify" src/ -r --include="*.py" → no output (or only comments)
```

---

### TASK-47
```
Tier:        1
File(s):     src/portal/routing/router.py
Symbol(s):   _llm_classifier (line 63)
Category:    CONFIG_HARDENING
Finding:     router.py instantiates LLMClassifier directly:
               _llm_classifier = LLMClassifier(ollama_host=OLLAMA_HOST)
             This bypasses create_classifier() and means ROUTING_LLM_MODEL env var
             (documented in .env.example) has no effect. The classifier always uses
             the hardcoded default model "qwen2.5:0.5b".
Action:      Change line 63 to use create_classifier():
               from portal.routing.llm_classifier import LLMClassifier, create_classifier
               _llm_classifier = create_classifier(ollama_host=OLLAMA_HOST)
             Update the import line 16 to also import create_classifier:
               from portal.routing.llm_classifier import LLMClassifier, create_classifier
             Remove the standalone LLMClassifier import if it's no longer needed directly
             (create_classifier returns LLMClassifier, so the type is still correct).
             Verify: ROUTING_LLM_MODEL=test_model python3 -c "
               import os; os.environ['ROUTING_LLM_MODEL']='test_model'
               from portal.routing.llm_classifier import create_classifier
               c = create_classifier(ollama_host='http://localhost:11434')
               print(c.model)  # should print test_model
             "
Risk:        LOW — behavior change only if ROUTING_LLM_MODEL is set (env var now respected)
Blast Radius: router.py proxy routing model selection only
Parity:      If ROUTING_LLM_MODEL is not set, defaults to qwen2.5:0.5b (unchanged behavior)
Acceptance:  python3 -m ruff check src/ tests/ → 0
             python3 -m pytest tests/ --tb=short → 890 PASS, 0 FAIL
             python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2 → 0 errors
```

---

## CI Gate (run after every task, before starting the next)

```bash
source .venv/bin/activate 2>/dev/null || true
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2
```

## Execution Order

```
TASK-44 → TASK-45   (version sync — trivial, commit together)
TASK-46             (dead code removal — CI gate after)
TASK-47             (env var fix — CI gate after)
TASK-41             (intelligent_router.py integration — CI gate after; highest complexity)
```

Commit after each task. Conventional commits: `fix:`, `feat:`, `test:`, `docs:`, `chore:`.
All commits to current branch or main per CLAUDE.md git policy.
