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

## Section 2 — Open: Legacy API Mismatches (`xfail` tests)

~51 tests in `tests/tests/unit/` and `tests/tests/e2e/` use old API signatures
that no longer match the current source. They are marked `xfail` in
`tests/conftest.py` via the `LEGACY_API_TESTS` set. They are preserved as a
modernisation backlog and should be updated once the corresponding source APIs
are stabilised.

Categories:
- `BaseTool._success_response` signature changed
- `TestTaskClassifier` / `TestIntelligentRouter` expect a different router API
- Docker / git / document tool responses have a different shape
- E2E tests check directory paths that no longer exist

**Action required:** update each test to match the current API (or update the
source and test together) and remove the corresponding entry from
`LEGACY_API_TESTS`.
