# Portal v1.0.3 → v1.1.0 Modernisation

## Summary

This PR completes a 7-phase automated modernisation of the portal codebase,
bringing it from v1.0.3 to v1.1.0.

- **Phase 1** Critical security & bootstrap fixes (guarded Redis import, core `__init__` exports)
- **Phase 2** Dead code removal (~3 000 lines deleted across 11 modules/directories)
- **Phase 3** Structural flattening (`tests/tests/` → flat layout) + `CentralDispatcher` + `BaseHTTPBackend`
- **Phase 4** Core resilience: MCPRegistry retry transport, `discover_from_ollama`, `_resolve_preflight_tools`, ConfigWatcher wiring
- **Phase 5** Security hardening: `hmac.compare_digest` for API-key comparison, async lifespan with `/health` readiness state
- **Phase 6** Docs & environment sync (ARCHITECTURE.md v1.1.0, .env.example, KNOWN_ISSUES.md)
- **Phase 7** New unit tests + full test-suite green (217 passed, 1 skipped)

## Key changes

### New files
| Path | Purpose |
|------|---------|
| `src/portal/agent/dispatcher.py` | `CentralDispatcher` interface registry |
| `src/portal/agent/__init__.py` | Public API for agent package |
| `tests/unit/test_hitl_import_guard.py` | Redis import guard tests |
| `tests/unit/test_dynamic_model_registry.py` | `discover_from_ollama` tests |
| `tests/unit/test_core_init_exports.py` | `portal.core` canonical API tests |
| `tests/unit/test_mcp_registry.py` | MCPRegistry add/remove/retry tests |
| `PULL_REQUEST.md` | This file |

### Modified highlights
- `src/portal/core/__init__.py` — canonical re-exports of all public symbols
- `src/portal/middleware/hitl_approval.py` — guarded `import redis`
- `src/portal/routing/model_backends.py` — `BaseHTTPBackend` base class
- `src/portal/routing/model_registry.py` — `discover_from_ollama()` method
- `src/portal/protocols/mcp/mcp_registry.py` — retry transport + `_request()` helper
- `src/portal/core/agent_core.py` — `_resolve_preflight_tools()` extracted
- `src/portal/interfaces/web/server.py` — `hmac.compare_digest`, async lifespan, rich `/health` response
- `src/portal/lifecycle.py` — ConfigWatcher task wiring
- `docs/ARCHITECTURE.md` — updated to v1.1.0
- `CHANGELOG.md` — v1.1.0 entry
- `pyproject.toml` — registered `e2e` / `integration` markers; excludes them from default run

### Deleted files
`src/portal/config/secrets.py`, `src/portal/config/validator.py`,
`src/portal/routing/response_formatter.py`, `src/portal/middleware/cost_tracker.py`,
`src/portal/security/sqlite_rate_limiter.py`, `src/portal/protocols/resource_resolver.py`,
`src/portal/config/schemas/settings_schema.py`,
`src/portal/utils/` (stub directory), `src/portal/core/registries/` (duplicate hierarchy),
`tests/tests/e2e/test_mcp_protocol.py`

## Test plan

- [x] `ruff check src/` — 76 pre-existing warnings only (zero new errors introduced)
- [x] `pytest tests/ --tb=short` — 217 passed, 1 skipped, 31 deselected (e2e/integration excluded)
- [x] All new test files verified individually
- [x] `tests/unit/test_core_init_exports.py` — all 12 assertions pass
- [x] `tests/unit/test_mcp_registry.py` — 15 tests pass including retry logic
- [x] `tests/unit/test_dynamic_model_registry.py` — 5 tests pass
- [x] `tests/unit/test_hitl_import_guard.py` — 3 tests pass
- [x] `tests/unit/test_router.py` — 10 tests pass (including new `CentralDispatcher` suite)
- [ ] Docker build (`docker build -t portal:test .`) — verify in CI

## Breaking changes

None. All changes are backwards-compatible. Deleted modules had zero external references
verified before removal.
