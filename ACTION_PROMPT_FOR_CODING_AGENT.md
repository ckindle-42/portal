# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-02 (delta run v14)
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.4.5 (all CI gates green)

---

## Project Context

Portal is a local-first AI platform (Python 3.11+ / FastAPI / async).
Source: `src/portal/` (100 Python files).
Tests: `tests/` (915 tests currently selected; 1 failing, 913 passing, 1 skipped).

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
   pip install -e ".[all,dev,test]" 2>&1 | tail -20
   ```

3. Verify core imports and tooling:
   ```bash
   python3 -c "import portal; print('portal:', portal.__version__)"
   python3 -m ruff --version
   python3 -m pytest --version
   ```

4. Verify tests can be collected:
   ```bash
   python3 -m pytest tests/ --collect-only 2>&1 | tail -5
   ```

5. Run baseline verification (expect: 0 lint, 1 test failure, 1 mypy error):
   ```bash
   python3 -m ruff check src/ tests/        # expect 0 violations
   python3 -m mypy src/portal               # expect 1 error (server.py:784)
   python3 -m pytest tests/ -v --tb=short   # expect 1 FAILED, 913 PASSED, 1 SKIPPED
   ```

---

## Prior Work Summary

All previously audited tasks (TASK-53 through TASK-56, ROAD-F05, ROAD-F06, Docker updates) are complete.

**Current state:** 913 tests passing, 1 mypy error, 0 lint violations.

**Two regressions were introduced by commit `6d4c0a1` (auto-pull models) and not caught in run 13 due to incomplete test verification. Both are shallow fixes.**

---

## Open Tasks

### TASK-57: Fix test_all_models_available_by_default for HuggingFace backend

**Priority:** HIGH — blocks full CI green
**File:** `tests/unit/test_data_driven_registry.py`, lines 45-55
**Root cause:** Commit `6d4c0a1` added `hf_llama32_3b` to `default_models.json` with `"available": false` (correct — HuggingFace models require manual GGUF conversion and import). The test `test_all_models_available_by_default` was not updated and asserts all non-`mlx` models must be available.

**Current failing code (lines 48-55):**
```python
def test_all_models_available_by_default(self):
    """All default Ollama models should be marked available. MLX models are unavailable by default."""
    registry = ModelRegistry()
    for model in registry.get_all_models():
        if model.backend == "mlx":
            # MLX models require mlx_lm.server to be running
            assert not model.available, (
                f"{model.model_id} should be unavailable by default (requires MLX server)"
            )
        else:
            assert model.available, f"{model.model_id} should be available"
```

**Required fix:**
```python
def test_all_models_available_by_default(self):
    """Ollama models available by default. MLX and HuggingFace models are not (require external setup)."""
    registry = ModelRegistry()
    for model in registry.get_all_models():
        if model.backend in ("mlx", "huggingface"):
            # MLX models require mlx_lm.server; HuggingFace models require manual GGUF import
            assert not model.available, (
                f"{model.model_id} should be unavailable by default "
                f"(backend '{model.backend}' requires external setup)"
            )
        else:
            assert model.available, f"{model.model_id} should be available"
```

**Verification:** `python3 -m pytest tests/unit/test_data_driven_registry.py -v --tb=short` should show all 19 tests passing.

---

### TASK-58: Fix mypy type error in server.py:784

**Priority:** HIGH — breaks mypy clean state (was 0 errors; now 1)
**File:** `src/portal/interfaces/web/server.py`, line 784
**Error:** `Incompatible types in assignment (expression has type "Settings", variable has type "dict[Any, Any] | None") [assignment]`

**Context:** The `create_app()` function has a `config: dict[Any, Any] | None = None` parameter. Commit `0713218` added `config = settings` at line 784 to pass the `Settings` object to `WebInterface`. This is a duck-typing approach that works at runtime but violates the declared type.

**Current code (lines 779-784):**
```python
settings = Settings()
cfg = config or settings.to_agent_config()
agent_core = _create(cfg)
# Pass Settings object to WebInterface so it reads backends.ollama_url correctly
config = settings
```

**Recommended fix (suppress with specific noqa code, minimal-impact approach):**
```python
settings = Settings()
cfg = config or settings.to_agent_config()
agent_core = _create(cfg)
# Pass Settings object to WebInterface so it reads backends.ollama_url correctly
config = settings  # type: ignore[assignment]
```

**Verification:** `python3 -m mypy src/portal` should report 0 errors.

---

## CI Gate (run after all tasks)

```bash
source .venv/bin/activate 2>/dev/null || true
python3 -m ruff check src/ tests/           # expect 0 violations
python3 -m ruff format --check src/ tests/  # expect no changes needed
python3 -m mypy src/portal                  # expect 0 errors
python3 -m pytest tests/ -v --tb=short      # expect 0 FAILED, 913+ PASSED
```

---

## Execution Order

1. Fix TASK-57 (test fix — 5 lines changed)
2. Verify: `python3 -m pytest tests/unit/test_data_driven_registry.py -v`
3. Fix TASK-58 (type annotation — 1 line changed)
4. Verify: `python3 -m mypy src/portal`
5. Run full CI gate: `python3 -m ruff check src/ tests/ && python3 -m mypy src/portal && python3 -m pytest tests/ -v --tb=short`
6. Commit with: `fix(tests): fix test_all_models_available_by_default for huggingface backend + mypy fix`

---

## Notes for Agent

- Both fixes are in different files; they can be done in any order
- TASK-57 is a test fix only — no production code changes needed
- TASK-58 is a single-line suppression — `# type: ignore[assignment]` is the correct ruff/mypy directive; do NOT use bare `# type: ignore`
- After both fixes, all CI gates should return to green (0 violations, 0 mypy errors, 0 test failures)
- The `test_pdf_ocr` skip (`tests/unit/tools/test_document_tools.py`) is expected — requires optional PDF OCR deps not installed in test environment
