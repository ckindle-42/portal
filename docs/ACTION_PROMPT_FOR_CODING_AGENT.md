# ACTION_PROMPT_FOR_CODING_AGENT.md

## Project Context

Portal is a local-first AI platform (Python 3.11+, FastAPI, Pydantic v2) with
multi-interface support (Web, Telegram, Slack). Source in `src/portal/`, tools in
`src/portal/tools/`, MCP servers in `mcp/`, tests in `tests/`.

## Prioritized Task List

Execute in order. After each batch: run `python -m pytest tests/`, fix failures,
commit with conventional message.

### Batch A — Remaining Bug Fixes (Priority: High)

1. **`tests/integration/test_web_interface.py`** — Add `@pytest.mark.integration`
   decorator to the test class so it's excluded from default `pytest tests/` runs
   (currently runs by default because it lacks the marker despite being in
   `tests/integration/`).

2. **`tests/integration/test_web_interface.py::test_create_app_returns_fastapi_instance`**
   — Fix: the test patches `create_app` then calls the mock. Replace with a direct
   call to `create_app(mock_agent_core)` and assert `isinstance(app, FastAPI)`.

3. **`src/portal/routing/execution_engine.py:414`** — Add `return_exceptions=True`
   to `asyncio.gather(*tasks)` in `execute_parallel()` so one failure doesn't
   cancel the others.

4. **`src/portal/middleware/tool_confirmation_middleware.py`** — Replace
   `datetime.now()` with `datetime.now(timezone.utc)` (import `timezone` from
   `datetime`).

5. **`src/portal/persistence/repositories.py`** — Convert `JobStatus` and
   `JobPriority` from plain classes with class attributes to proper `Enum` classes
   for consistency.

### Batch B — DRY / Complexity Reduction (Priority: Medium)

6. **`src/portal/routing/model_backends.py`** — Extract shared message-building
   logic from `OllamaBackend.generate()`, `OllamaBackend.generate_stream()`,
   `LMStudioBackend.generate()`, `LMStudioBackend.generate_stream()` into a
   `BaseHTTPBackend._build_chat_messages(prompt, system_prompt, messages)` method.

7. **`src/portal/persistence/sqlite_impl.py`** — Fix N+1 query in
   `_sync_list_conversations()`: use a single JOIN query to fetch conversations
   with their messages instead of calling `_sync_get_messages()` per conversation.

8. **`src/portal/persistence/sqlite_impl.py`** — Implement `filters` parameter
   in `search()`, `count_documents()`, `list_documents()`, `search_by_embedding()`
   (currently silently ignored — at minimum raise `NotImplementedError` if filters
   are passed).

### Batch C — Security Hardening (Priority: Medium)

9. **`src/portal/routing/router.py`** — Implement `ROUTER_TOKEN` auth:
   if `ROUTER_TOKEN` env var is set, require `Authorization: Bearer <token>` on
   all proxy endpoints. Use `hmac.compare_digest` for timing-safe comparison.

10. **`mcp/core/librechat_mcp_fragment.yaml`** — Change filesystem MCP server
    allowed directory from `/tmp` to `${HOME}/.portal/data/`.

### Batch D — New Tests (Priority: Medium)

11. Add `tests/unit/test_circuit_breaker.py` — Test `CircuitBreaker` CLOSED →
    OPEN → HALF_OPEN → CLOSED transitions, failure threshold, recovery timeout.

12. Add `tests/unit/test_structured_logger.py` — Test `_redact_secrets()` masks
    Slack tokens, OpenAI keys, Telegram tokens, GitHub PATs, Bearer tokens.

13. Add `tests/unit/test_config_watcher.py` — Test `ConfigWatcher` detects file
    changes and triggers callbacks; test validation rejection with rollback.

### Batch E — Documentation Sync

14. Update `docs/ARCHITECTURE.md` header version to match `pyproject.toml`.
15. Update `CHANGELOG.md` with all changes from this session.
16. Verify `.env.example` documents all active env vars and no dead ones.

## Testing & Verification

- Run `python -m pytest tests/ -v` after every batch
- Maintain 235+ passing tests
- All new tests must pass
- No regressions allowed

## Success Criteria

- [ ] All batches A–E completed
- [ ] 245+ tests passing (235 existing + 10 new minimum)
- [ ] CHANGELOG.md updated with version bump
- [ ] git commit with conventional messages per batch
- [ ] PR created with full change summary
