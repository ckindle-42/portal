# Known Issues

This file tracks intentional known-failure states, deferred work, and structural
debt. It is referenced by `tests/conftest.py` to explain why certain tests are
marked `xfail`.

---

## Section 1 — Resolved

### Section 3 — Doubled-Directory Package Layout (RESOLVED)

All seven tool sub-packages (`automation_tools`, `data_tools`,
`document_processing`, `system_tools`, `media_tools`, `web_tools`, `knowledge`)
that had an extra inner directory of the same name have been flattened.  Each
inner directory's contents were moved up to the outer directory (which now holds
the `__init__.py` and modules directly), and the empty inner directory was
removed.

**Result:** The 5 pytest collection errors in `tests/tests/unit/tools/` are
resolved.  Those files now collect successfully (56 tests collected, 0 errors)
and the `xfail` markers from `LEGACY_API_TESTS` apply as intended.

---

## Section 2 — Resolved: Legacy API Mismatches (2026-02-26)

The following 18 tests were removed from the `LEGACY_API_TESTS` xfail set in
`tests/conftest.py` after being fixed:

- `test_base_tool.py::test_tool_execution` — fixed by updating
  `BaseTool._success_response()` and `_error_response()` to accept `**kwargs`
- `test_data_integrity.py` atomic write tests (×4) — already passing once
  LocalKnowledgeTool._save_db atomic pattern was confirmed correct
- `test_job_queue.py::test_event_bus_integration` — fixed by replacing
  `sys.path` hack in `job_worker.py` with absolute imports (resolves
  EventType module-identity mismatch between `core.event_bus` and
  `portal.core.event_bus`)
- `test_router.py` classifier/router tests (×4) — fixed by updating assertions
  to use `result.complexity.value` (TaskClassification dataclass)
- `test_security.py::test_rate_limit_allows_initial_requests` — fixed by
  making the test async and adding `await`
- `test_security.py::test_path_traversal_detected` — was already passing
- `test_automation_tools.py::test_list_jobs` — fixed parameter `operation`→`action`
- `test_mcp_protocol.py::test_protocol_directory_structure` — updated path
  from `pocketportal/protocols` to `src/portal/protocols`
- `test_observability.py::test_observability_module_structure` — updated path
  from `pocketportal/observability` to `src/portal/observability`; added
  `watchdog.py` and `log_rotation.py` to file list

Remaining xfail entries (33) are tests requiring optional dependencies not
installed in the base dev environment: pandas, Docker SDK, openpyxl,
python-docx, python-pptx, pytesseract, aiohttp session mocking, faster-whisper.

**Open: CSP trade-off** — The default Content-Security-Policy in
`src/portal/interfaces/web/server.py` includes `'unsafe-inline' 'unsafe-eval'`
for compatibility with Open WebUI's JavaScript. This should be tightened in
production deployments that do not use a web UI frontend.
