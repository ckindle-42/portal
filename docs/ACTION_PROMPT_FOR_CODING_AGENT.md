# ACTION_PROMPT_FOR_CODING_AGENT.md

## Project Context

Portal is a local-first AI platform (Python 3.11+, FastAPI, Pydantic v2) with
multi-interface support (Web, Telegram, Slack). Source in `src/portal/`, tools in
`src/portal/tools/`, MCP servers in `mcp/`, tests in `tests/`.

## Completed Tasks (v1.3.0 → v1.3.1)

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

## Remaining Prioritized Task List

### Batch A — Performance (Priority: Medium)

1. Replace O(n) vector search in `knowledge_base_sqlite.py` with sqlite-vec.
2. Add performance regression benchmarks.

### Batch B — Structural (Priority: Low)

3. Split `AgentCore` (792 lines) into `MessageProcessor`, `ExecutionOrchestrator`, `ResponseBuilder`.
4. Split `lifecycle.bootstrap()` (117 lines) and `shutdown()` (147 lines) into sub-functions.
5. Add return type hints to remaining ~50% of functions.

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
