# ACTION_PROMPT_FOR_CODING_AGENT.md

## Project Context

Portal is a local-first AI platform (Python 3.11+, FastAPI, Pydantic v2) with
multi-interface support (Web, Telegram, Slack). Source in `src/portal/`, tools in
`src/portal/tools/`, MCP servers in `mcp/`, tests in `tests/`.

## Completed Tasks (v1.3.0)

- [x] Fix MCP tool loop context loss (`messages=None` → `messages=current_messages`)
- [x] Fix `execute_parallel()` cancellation (`return_exceptions=True`)
- [x] Replace O(n) `list.pop(0)` with `deque(maxlen=N)` in EventBus
- [x] Deduplicate tool registration logic (`_register_tool_instance()`)
- [x] Fix ruff I001 import sorting in `tools/__init__.py`
- [x] Remove unnecessary Path alias in `lifecycle.py`
- [x] Version bump to 1.3.0 (pyproject.toml, __init__.py, ARCHITECTURE.md)
- [x] CHANGELOG.md updated with v1.3.0 entry

## Remaining Prioritized Task List

### Batch A — DRY / Complexity (Priority: High)

1. **`src/portal/routing/model_backends.py`** — Extract shared message-building
   logic from `OllamaBackend.generate()`, `OllamaBackend.generate_stream()`,
   `LMStudioBackend.generate()`, `LMStudioBackend.generate_stream()` into a
   `BaseHTTPBackend._build_chat_messages(prompt, system_prompt, messages)` method.

2. **`src/portal/persistence/sqlite_impl.py`** — Fix N+1 query in
   `_sync_list_conversations()`: use a single JOIN query.

### Batch B — Security (Priority: Medium)

3. **`src/portal/routing/router.py`** — Implement `ROUTER_TOKEN` auth:
   if env var is set, require `Authorization: Bearer <token>` on proxy endpoints.

4. **`src/portal/middleware/tool_confirmation_middleware.py`** — Replace
   `datetime.now()` with `datetime.now(timezone.utc)`.

### Batch C — New Tests (Priority: Medium)

5. Add `tests/unit/test_circuit_breaker.py` — CLOSED → OPEN → HALF_OPEN → CLOSED.
6. Add `tests/unit/test_structured_logger.py` — Secret redaction patterns.
7. Expand `tests/unit/test_memory_manager.py` — Empty retrieval, concurrent access.
8. Add `tests/unit/test_model_backends.py` — Expand from 2 to 10+ tests.

### Batch D — Performance

9. Replace O(n) vector search in `knowledge_base_sqlite.py` with sqlite-vec.
10. Add performance regression benchmarks.

## Testing & Verification

- Run `python -m pytest tests/ -v` after every batch
- Run `python -m ruff check src/ tests/` — must be 0 errors
- All new tests must pass; no regressions

## Success Criteria

- [ ] All batches A–D completed
- [ ] 250+ tests passing
- [ ] 0 lint errors
- [ ] CHANGELOG.md updated
- [ ] Health score at 9.5+/10
