# ACTION_PROMPT_FOR_CODING_AGENT.md

> **Superseded** — This document described the 2026-02-27 shrink session task
> list. All tasks in that session have been completed and committed. See
> `CHANGELOG.md` for the recorded outcomes.

## Project Context

Portal is a local-first AI platform (Python 3.11+, FastAPI, Pydantic v2) with
multi-interface support (Web, Telegram, Slack). Source in `src/portal/`, tools in
`src/portal/tools/`, MCP servers in `mcp/`, tests in `tests/`.

## Completed Tasks (v1.3.0 → v1.3.3)

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

### v1.3.3
- [x] Remove dead example code from 4 document tools (~250 lines)
- [x] Fix legacy "PocketPortal" references (2 docstrings)
- [x] Fix stale version string in exceptions.py
- [x] Extract constants (DEFAULT_MCP_TOOL_MAX_ROUNDS, HIGH_RISK_TOOLS)
- [x] Replace f-string logging in agent_core tool confirmation path
- [x] Add 51 new tests (MemoryManager, ContextManager, PromptManager, constants, registry)
- [x] Sync version strings to 1.3.3
- [x] Update CHANGELOG.md, CODE_REVIEW_SUMMARY.md, ACTION_PROMPT

## Remaining Prioritized Task List

### Batch A — Testing (Priority: High)

1. Add integration tests for full MCP tool loop with retries.
2. Target >=95% test coverage (currently ~75% estimated).

### Batch B — Performance (Priority: Medium)

3. Replace O(n) vector search in `knowledge_base_sqlite.py` with sqlite-vec.
4. Add performance regression benchmarks for model backends.

### Batch C — Observability (Priority: Low)

5. Wire OpenTelemetry tracing when OTLP endpoint is configured.
6. Add model discovery auto-refresh timer in model_registry.

### Batch D — Code Quality (Priority: Low)

7. Convert remaining f-string logging in routing/*.py to %-formatting.

## Testing & Verification

- Run `python -m pytest tests/ -v` after every batch
- Run `python -m ruff check src/ tests/` — must be 0 errors
- All new tests must pass; no regressions

## Success Criteria

- [x] 372+ tests passing
- [x] 0 lint errors
- [x] CHANGELOG.md updated
- [x] Health score at 9.6/10
- [ ] All batches A–D completed → 10/10
