# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-02 (delta run v6 — ROAD-P01 integration)
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.4.5

---

## Project Context

Portal is a local-first AI platform (Python 3.11+ / FastAPI / async).
Source: `src/portal/` (97 Python files, ~16,067 LOC).
Tests: `tests/` (68 Python files, ~13,533 LOC, 874 currently passing).

**Non-negotiable constraints:**
- API contract locked: no behavior changes to existing endpoints
- No new features unless explicitly requested
- No cloud dependencies, no external AI frameworks
- Regex fallback must always be preserved (LLM classifier unavailability is expected)

---

## Session Bootstrap — Run Before Any Task

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
   python3 -m ruff check src/ tests/       # expect 2 violations in llm_classifier.py
   python3 -m pytest tests/ -v --tb=short  # expect 874 PASS
   python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -3  # expect 2 errors
   ```

---

## Prior Work Summary

All tasks through TASK-35 are COMPLETE. TASK-36 through TASK-43 are the open ROAD-P01 integration tasks.

- TASK-32 (version 1.4.3): COMPLETE
- TASK-33 (mypy 17→0): COMPLETE
- TASK-34 (version 1.4.4 + CHANGELOG): COMPLETE
- TASK-35 (ARCHITECTURE.md version): COMPLETE

**Current state:** 874 tests passing, 2 mypy errors, 2 lint violations (all in new `llm_classifier.py`).
`llm_classifier.py` exists but is not integrated into `router.py` or `intelligent_router.py`.

---

## Open Tasks — ROAD-P01: LLM-Based Intelligent Routing

### Session Bootstrap — Run Before Any Task

Do not read or modify any source file until this bootstrap completes successfully.

```bash
if [ -d .venv ]; then source .venv/bin/activate; else python3 -m venv .venv && source .venv/bin/activate && pip install --upgrade pip setuptools wheel; fi
pip install -e ".[all,dev]" 2>&1 | tail -5
python3 -c "import portal; print('portal: OK')"
python3 -m ruff --version && python3 -m pytest --version
```

---

### TASK-36
```
Tier:        1
File(s):     src/portal/routing/llm_classifier.py
Symbol(s):   module-level imports, EOF
Category:    LINT
Finding:     2 auto-fixable ruff violations: UP035 (typing.AsyncIterator) and W292 (no trailing newline)
Action:      Run: python3 -m ruff check src/portal/routing/llm_classifier.py --fix
             Then verify: python3 -m ruff check src/ tests/ → 0 violations
Risk:        LOW
Blast Radius: llm_classifier.py only
Parity:      No behavior change — import alias only
Acceptance:  python3 -m ruff check src/ tests/ → 0 errors
```

---

### TASK-37
```
Tier:        1
File(s):     src/portal/routing/llm_classifier.py
Symbol(s):   create_classifier() → lines 175-185
Category:    TYPE_SAFETY
Finding:     create_classifier() passes str|None to LLMClassifier where str is expected
             (mypy error [arg-type] for both ollama_host and model arguments)
Action:      Use explicit type-narrowing variables with str annotations:

             def create_classifier(
                 ollama_host: str | None = None,
                 model: str | None = None,
             ) -> LLMClassifier:
                 import os
                 host: str = ollama_host or os.getenv("OLLAMA_HOST", "http://localhost:11434")
                 classifier_model: str = model or os.getenv("ROUTING_LLM_MODEL", "qwen2.5:0.5b")
                 return LLMClassifier(ollama_host=host, model=classifier_model)

             Note: os.getenv(key, default: str) → str (typeshed stubs confirm str return with default).
             Explicit str annotation on host and classifier_model resolves the arg-type errors.
Risk:        LOW
Blast Radius: create_classifier() only
Parity:      Runtime behavior unchanged
Acceptance:  python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2 → "Found 0 errors"
```

---

### TASK-38
```
Tier:        1
File(s):     tests/unit/routing/test_llm_classifier.py (NEW)
Symbol(s):   LLMClassifier, LLMCategory, LLMClassification, create_classifier
Category:    TEST
Finding:     No unit tests for llm_classifier.py (new module, 185 LOC, zero coverage)
Action:      Create tests/unit/routing/test_llm_classifier.py covering:

             1. classify() — mocked Ollama available, returns valid category → LLMClassification
             2. classify() — mocked Ollama unavailable (ConnectError) → fallback to regex
             3. classify() — mocked Ollama returns invalid category string → defaults to GENERAL
             4. _fallback_to_regex() — all TaskCategory values map to expected LLMCategory
             5. create_classifier() — returns LLMClassifier with correct defaults

             Use pytest-asyncio for async tests. Mock httpx.AsyncClient with pytest-mock or
             unittest.mock. Do not spin up real Ollama.

             Pattern: look at existing tests/unit/routing/test_task_classifier.py for style.
Risk:        LOW (test-only file)
Blast Radius: None (test addition only)
Parity:      N/A
Acceptance:  python3 -m pytest tests/unit/routing/test_llm_classifier.py -v → all PASS
             python3 -m pytest tests/ --tb=short → 879+ PASS (874 + 5 new), 0 FAIL
```

---

### TASK-39
```
Tier:        1
File(s):     .env.example
Symbol(s):   ROUTING_LLM_MODEL
Category:    CONFIG_HARDENING / DOCS
Finding:     ROUTING_LLM_MODEL env var used in create_classifier() but absent from .env.example
Action:      Add the following line to .env.example in the routing/Ollama section
             (near OLLAMA_HOST):

             ROUTING_LLM_MODEL=qwen2.5:0.5b

             Also verify OLLAMA_HOST is already documented (it is — line 15).
Risk:        LOW (docs only)
Blast Radius: .env.example only
Parity:      No code change
Acceptance:  grep "ROUTING_LLM_MODEL" .env.example → present
```

---

### TASK-40
```
Tier:        2
File(s):     src/portal/routing/router.py
Symbol(s):   resolve_model(), proxy()
Category:    ROAD-P01 integration (proxy router)
Finding:     resolve_model() step 3 uses compiled regex rules; LLMClassifier not wired in.
             Per ROADMAP design: replace regex step with LLM classifier call.
Action:      1. Make resolve_model() async:
                async def resolve_model(requested_model: str, messages: list[dict]) -> tuple[str, str]:

             2. Instantiate LLMClassifier at module level (after RULES is loaded):
                from portal.routing.llm_classifier import LLMClassifier
                _llm_classifier = LLMClassifier(ollama_host=OLLAMA_HOST)

             3. Replace regex step 3 with LLM classifier call:
                # 3. LLM classifier (replaces regex_rules; falls back to regex internally)
                classification = await _llm_classifier.classify(user_text)
                category_model_map = RULES.get("classifier", {}).get("categories", {})
                llm_model = category_model_map.get(classification.category.value)
                if llm_model:
                    return llm_model, f"llm_classifier: {classification.category.value}"
                # 3b. Legacy regex fallback (if no classifier config in router_rules.json)
                for priority, name, patterns, model in _compiled_rules:
                    for pattern in patterns:
                        if pattern.search(user_text):
                            return model, f"rule: {name}"

             4. Update proxy() call: resolved_model, reason = await resolve_model(requested, messages)
             5. Update dry_run() call: resolved, reason = await resolve_model(requested, messages)

             Keep _compiled_rules as secondary fallback so existing router_rules.json behavior
             is preserved until classifier config is added (TASK-42).
Risk:        MEDIUM — changes request routing in proxy router (:8000)
Blast Radius: All requests through proxy router. Fallback chain preserved.
Parity:      @model: override and workspace routing (steps 1 and 2) unchanged.
             Regex rules still fire if LLM classifier returns no match in category_model_map.
             Default (step 4) unchanged.
Acceptance:  python3 -m pytest tests/ -v --tb=short → same pass count (or more), 0 FAIL
             python3 -m ruff check src/ tests/ → 0
             python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2 → 0 errors
```

---

### TASK-41
```
Tier:        2
File(s):     src/portal/routing/intelligent_router.py
             src/portal/core/agent_core.py
Symbol(s):   IntelligentRouter.route(), AgentCore._execute_with_routing()
Category:    ROAD-P01 integration (AgentCore router)
Finding:     IntelligentRouter.route() still uses TaskClassifier directly.
             Per ROADMAP design: replace with shared LLMClassifier.
             Caller _execute_with_routing() is already async def — safe to await.
Action:      1. In intelligent_router.py __init__, add LLMClassifier alongside TaskClassifier:
                from .llm_classifier import LLMClassifier
                self.llm_classifier = LLMClassifier()
                self.classifier = TaskClassifier()  # keep as fallback for sync path

             2. Make route() async:
                async def route(self, query: str, max_cost: float = 1.0,
                                workspace_id: str | None = None) -> RoutingDecision:

             3. In the workspace routing branch (if ws_model found), keep TaskClassifier for
                classification metadata (sync fallback is fine — metadata only, no model selection):
                classification = self.classifier.classify(query)

             4. In the main classification path, replace TaskClassifier with LLMClassifier:
                llm_class = await self.llm_classifier.classify(query)
                # Map LLMCategory back to TaskClassification for downstream strategy methods
                # Simplest: call self.classifier.classify() for TaskClassification metadata
                # then override category via LLM result for model selection

             5. Update agent_core.py line 322:
                decision = await self.router.route(query)

             Note on async strategy methods: _route_auto, _route_speed, etc. are all sync.
             They take a TaskClassification object. The approach is to use LLMClassifier for
             the primary category decision, then pass TaskClassifier output to strategy methods
             for complexity/metadata. This avoids rewriting all strategy methods.

             Recommended implementation for step 4:
                task_class = self.classifier.classify(query)    # sync, for metadata
                llm_class = await self.llm_classifier.classify(query)  # async, for category
                # Override category using LLM result
                category_override = {
                    LLMCategory.CODE: TaskCategory.CODE,
                    LLMCategory.REASONING: TaskCategory.ANALYSIS,
                    LLMCategory.CREATIVE: TaskCategory.CREATIVE,
                    LLMCategory.TOOL_USE: TaskCategory.TOOL_USE,
                    LLMCategory.GENERAL: TaskCategory.GENERAL,
                }
                from .llm_classifier import LLMCategory
                overridden_category = category_override.get(llm_class.category, task_class.category)
                classification = TaskClassification(
                    category=overridden_category,
                    complexity=task_class.complexity,
                    confidence=llm_class.confidence,
                    requires_code=task_class.requires_code,
                    requires_math=task_class.requires_math,
                )

Risk:        MEDIUM — changes model selection in AgentCore
Blast Radius: All chat requests via Portal API (:8081). Fallback via TaskClassifier preserved.
Parity:      Workspace routing unchanged. Strategy selection logic unchanged (same methods).
             TaskClassifier provides complexity/metadata; LLMClassifier provides category override.
Acceptance:  python3 -m pytest tests/ -v --tb=short → same pass count, 0 FAIL
             python3 -m ruff check src/ tests/ → 0
             python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2 → 0 errors
```

---

### TASK-42
```
Tier:        2
File(s):     src/portal/routing/router_rules.json
Symbol(s):   top-level "classifier" key
Category:    CONFIG_HARDENING
Finding:     router_rules.json has no "classifier" config block per ROADMAP design.
             resolve_model() in TASK-40 will fall back to regex_rules if no classifier config.
Action:      Add "classifier" block to router_rules.json following the ROADMAP schema:

             {
               "classifier": {
                 "model": "qwen2.5:0.5b",
                 "categories": {
                   "general": "qwen2.5:7b",
                   "code": "qwen2.5-coder:32b",
                   "reasoning": "deepseek-r1:32b",
                   "tool_use": "qwen2.5:7b",
                   "creative": "qwen2.5:14b"
                 }
               }
             }

             Keep existing "regex_rules" as secondary fallback — do not remove them.
Risk:        LOW — JSON config only
Blast Radius: router.py resolve_model() step 3 behavior
Parity:      regex_rules still present as fallback
Acceptance:  python3 -m pytest tests/ -v --tb=short → 0 FAIL
             Verify router.py dry-run returns llm_classifier reason for matching categories
```

---

### TASK-43
```
Tier:        1
File(s):     src/portal/__init__.py, CHANGELOG.md
Symbol(s):   __version__, [Unreleased]
Category:    DOCS / VERSION
Finding:     feat(routing) commit 0a7f28f not reflected in version or CHANGELOG.
             TASK-36 through TASK-42 complete ROAD-P01, warranting version bump.
Action:      1. Bump __version__ from "1.4.4" to "1.4.5" in src/portal/__init__.py
             2. Add [1.4.5] entry to CHANGELOG.md:

             ## [1.4.5] - 2026-03-02 — ROAD-P01 LLM-Based Intelligent Routing

             ### Added
             - LLMClassifier (src/portal/routing/llm_classifier.py): async Ollama-based query
               classification replacing regex heuristics. Falls back to TaskClassifier when
               Ollama unavailable. LRU cache avoids reclassifying identical prompts.
             - LLM classifier integrated into proxy router (router.py::resolve_model())
             - LLM classifier integrated into IntelligentRouter (intelligent_router.py::route())
             - "classifier" config block added to router_rules.json
             - ROUTING_LLM_MODEL env var documented in .env.example

             ### Fixed
             - llm_classifier.py: UP035 (AsyncIterator import), W292 (trailing newline)
             - llm_classifier.py: mypy arg-type errors in create_classifier()

             ### Tests
             - Added tests/unit/routing/test_llm_classifier.py (5 test cases)
Risk:        LOW
Blast Radius: Version string and docs only
Parity:      No behavior change
Acceptance:  python3 -c "import portal; print(portal.__version__)" → "1.4.5"
             grep "1.4.5" CHANGELOG.md → present
```

---

## CI Gate (run after every task, before starting the next)

```bash
source .venv/bin/activate 2>/dev/null || true
python3 -m ruff check src/ tests/                                       # 0 violations
python3 -m ruff format --check src/ tests/                              # 0 violations
python3 -m pytest tests/ -v --tb=short                                  # 874+ PASS, 0 FAIL
python3 -m mypy src/portal --ignore-missing-imports 2>&1 | tail -2     # 0 errors
test "$(git branch | grep -v 'main\|claude/' | wc -l)" -eq 0 || echo "WARNING: stale branches"
```

## Execution Order

```
TASK-36 → TASK-37  (lint + type fixes — CI must be 0 violations, 0 errors before continuing)
TASK-38            (tests — all new tests must pass)
TASK-39            (.env.example doc — trivial)
TASK-40            (router.py integration — CI gate after)
TASK-41            (intelligent_router.py integration — CI gate after)
TASK-42            (router_rules.json config — CI gate after)
TASK-43            (version bump + CHANGELOG — final)
```

Commit after each task. Conventional commits: `fix:`, `feat:`, `test:`, `docs:`, `chore:`.
All commits to current branch (`claude/codebase-review-road-p01-PUdeG`).
