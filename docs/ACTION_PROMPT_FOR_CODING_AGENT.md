# ACTION_PROMPT_FOR_CODING_AGENT.md

## Project Context

Portal is a local-first AI platform (Python 3.11+, FastAPI, Pydantic v2) with
multi-interface support (Web, Telegram, Slack). Source in `src/portal/`, tools in
`src/portal/tools/`, MCP servers in `mcp/`, tests in `tests/`.

## Completed Tasks (v1.3.0 → v1.3.2)

### v1.3.0
- [x] Fix MCP tool loop context loss (`messages=None` → `messages=current_messages`)
- [x] Fix `execute_parallel()` cancellation (`return_exceptions=True`)
- [x] Replace O(n) `list.pop(0)` with `deque(maxlen=N)` in EventBus
- [x] Deduplicate tool registration logic (`_register_tool_instance()`)
- [x] Fix ruff I001 import sorting in `tools/__init__.py`
- [x] Remove unnecessary Path alias in `lifecycle.py`
- [x] Version bump to 1.3.0 (pyproject.toml, __init__.py, ARCHITECTURE.md)
- [x] CHANGELOG.md updated with v1.3.0 entry

### v1.3.1
- [x] Extract `BaseHTTPBackend._build_chat_messages()` (DRY, ~40 lines saved)
- [x] Fix N+1 query in `_sync_list_conversations()` with single LEFT JOIN
- [x] Implement `ROUTER_TOKEN` auth on proxy, `/api/dry-run`, `/api/tags`
- [x] Replace all 34 `datetime.now()` with `datetime.now(tz=UTC)` across 11 files
- [x] Fix version string mismatches (WebInterface + ARCHITECTURE.md: 1.2.0 → 1.3.0)
- [x] Data-driven model registry (175 → 65 lines)
- [x] Add 36 new tests (CircuitBreaker, secret redaction, router auth, message builder, model registry)
- [x] Update CHANGELOG.md, CODE_REVIEW_SUMMARY.md

### v1.3.2
- [x] Remove dead EventBroker abstraction (238 lines of dead code)
- [x] Flatten lifecycle.py shutdown() — extract 5 helper methods (nesting 5→2)
- [x] Replace f-string interpolation in logger calls with %-formatting
- [x] Sync version strings to 1.3.2 across all files
- [x] Add 47 new tests (lifecycle, event bus subscribers, security edge cases)
- [x] Update CHANGELOG.md, CODE_REVIEW_SUMMARY.md, ACTION_PROMPT

## Remaining Prioritized Task List

### Batch A — Testing (Priority: High)

1. Add MemoryManager edge-case tests (empty retrieval, concurrent access).
2. Add integration tests for full MCP tool loop with retries.
3. Target >=95% test coverage (currently ~70% measured).

### Batch B — Performance (Priority: Medium)

4. Replace O(n) vector search in `knowledge_base_sqlite.py` with sqlite-vec.
5. Add performance regression benchmarks for model backends.

### Batch C — Observability (Priority: Low)

6. Wire OpenTelemetry tracing when OTLP endpoint is configured.
7. Add model discovery auto-refresh timer in model_registry.

## Testing & Verification

- Run `python -m pytest tests/ -v` after every batch
- Run `python -m ruff check src/ tests/` — must be 0 errors
- All new tests must pass; no regressions

## Success Criteria

- [x] 321+ tests passing
- [x] 0 lint errors
- [x] CHANGELOG.md updated
- [x] Health score at 9.4/10
- [ ] All batches A–C completed → 10/10
