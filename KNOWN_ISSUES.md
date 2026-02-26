# Known Issues

This file tracks intentional known-failure states, deferred work, and structural
debt. It is referenced by `tests/conftest.py` to explain why certain tests are
marked `xfail`.

---

## Section 1 — Resolved

No resolved items to document yet.

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

---

## Section 3 — Open: 5 Collection Errors from Doubled-Directory Package Layout

### Summary

Five test files in `tests/tests/unit/tools/` cannot be *collected* by pytest at
all because they import from `portal.tools.<package>.<module>` while the actual
source files are one directory level deeper at
`portal.tools.<package>.<package>.<module>`.  This is a structural packaging
bug introduced when several tool sub-packages were copied into `src/portal/tools/`
retaining their own inner package directory rather than being flattened.

Because the import fails at collection time (before pytest can apply the `xfail`
markers from Section 2), these 5 files produce hard `ERROR` lines during
`pytest --collect-only`.

### Root Cause: Doubled Directories

`pyproject.toml` uses:

```toml
[tool.setuptools.packages.find]
where = ["src"]
```

This means `src/portal/tools/automation_tools/` is the Python package
`portal.tools.automation_tools`.  Four tool groups (`dev_tools`, `docker_tools`,
`git_tools`, `document_tools`) were correctly added as flat packages with their
modules directly inside the outer directory and an `__init__.py` at that level.

Seven other tool groups were added with an extra inner directory of the same
name — a leftover from being developed as standalone packages where the inner
directory was the actual Python package root:

```
src/portal/tools/
├── dev_tools/          ← correct: __init__.py here, modules here
│   ├── __init__.py
│   └── python_env_manager.py
│
├── automation_tools/   ← broken: no __init__.py at this level
│   └── automation_tools/   ← inner duplicate directory
│       ├── __init__.py
│       ├── scheduler.py
│       └── shell_safety.py
│
├── data_tools/         ← broken: same doubled pattern
│   └── data_tools/
│       ├── __init__.py
│       ├── csv_analyzer.py
│       ├── file_compressor.py
│       ├── math_visualizer.py
│       ├── qr_generator.py
│       └── text_transformer.py
│
├── document_processing/  ← broken
│   └── document_processing/
│       ├── __init__.py
│       ├── document_metadata_extractor.py
│       ├── excel_processor.py
│       ├── pandoc_converter.py
│       ├── powerpoint_processor.py
│       └── word_processor.py
│
├── knowledge/          ← broken (not directly tested, but same issue)
│   └── knowledge/
│       ├── __init__.py
│       ├── knowledge_base_sqlite.py
│       └── local_knowledge.py
│
├── media_tools/        ← broken
│   └── media_tools/
│       ├── __init__.py
│       └── audio/
│           ├── __init__.py
│           └── audio_transcriber.py
│
├── system_tools/       ← broken
│   └── system_tools/
│       ├── __init__.py
│       ├── clipboard_manager.py
│       ├── process_monitor.py
│       └── system_stats.py
│
└── web_tools/          ← broken
    └── web_tools/
        ├── __init__.py
        └── http_client.py
```

Because the outer `automation_tools/`, `data_tools/`, etc. directories have no
`__init__.py`, Python treats them as namespace packages.  A namespace package
cannot expose sub-modules from a child directory that happens to share its name;
`portal.tools.automation_tools.scheduler` resolves to
`src/portal/tools/automation_tools/scheduler.py` (which doesn't exist), not to
`src/portal/tools/automation_tools/automation_tools/scheduler.py` (which does).

No existing code in `src/` uses the doubled import path
(`portal.tools.automation_tools.automation_tools.scheduler`), so there are no
callers that would break during the flatten.

---

### Fix: Flatten Each Doubled Package

For each affected package, the remedy is identical:

1. Move every file from the inner directory up to the outer directory.
2. Delete the now-empty inner directory.
3. The outer directory already serves as the package root via the `src/` layout —
   no further `pyproject.toml` changes are needed.

#### 3a — `automation_tools`

**Files to move:**
```
src/portal/tools/automation_tools/automation_tools/__init__.py
src/portal/tools/automation_tools/automation_tools/scheduler.py
src/portal/tools/automation_tools/automation_tools/shell_safety.py
```
**Move to:**
```
src/portal/tools/automation_tools/__init__.py
src/portal/tools/automation_tools/scheduler.py
src/portal/tools/automation_tools/shell_safety.py
```
**Directory to remove:** `src/portal/tools/automation_tools/automation_tools/`

After this, `from portal.tools.automation_tools.scheduler import JobSchedulerTool`
resolves correctly.

---

#### 3b — `data_tools`

**Files to move:**
```
src/portal/tools/data_tools/data_tools/__init__.py
src/portal/tools/data_tools/data_tools/csv_analyzer.py
src/portal/tools/data_tools/data_tools/file_compressor.py
src/portal/tools/data_tools/data_tools/math_visualizer.py
src/portal/tools/data_tools/data_tools/qr_generator.py
src/portal/tools/data_tools/data_tools/text_transformer.py
```
**Move to:**
```
src/portal/tools/data_tools/__init__.py
src/portal/tools/data_tools/csv_analyzer.py
src/portal/tools/data_tools/file_compressor.py
src/portal/tools/data_tools/math_visualizer.py
src/portal/tools/data_tools/qr_generator.py
src/portal/tools/data_tools/text_transformer.py
```
**Directory to remove:** `src/portal/tools/data_tools/data_tools/`

---

#### 3c — `document_processing`

**Files to move:**
```
src/portal/tools/document_processing/document_processing/__init__.py
src/portal/tools/document_processing/document_processing/document_metadata_extractor.py
src/portal/tools/document_processing/document_processing/excel_processor.py
src/portal/tools/document_processing/document_processing/pandoc_converter.py
src/portal/tools/document_processing/document_processing/powerpoint_processor.py
src/portal/tools/document_processing/document_processing/word_processor.py
```
**Move to:**
```
src/portal/tools/document_processing/__init__.py
src/portal/tools/document_processing/document_metadata_extractor.py
src/portal/tools/document_processing/excel_processor.py
src/portal/tools/document_processing/pandoc_converter.py
src/portal/tools/document_processing/powerpoint_processor.py
src/portal/tools/document_processing/word_processor.py
```
**Directory to remove:** `src/portal/tools/document_processing/document_processing/`

---

#### 3d — `system_tools`

**Files to move:**
```
src/portal/tools/system_tools/system_tools/__init__.py
src/portal/tools/system_tools/system_tools/clipboard_manager.py
src/portal/tools/system_tools/system_tools/process_monitor.py
src/portal/tools/system_tools/system_tools/system_stats.py
```
**Move to:**
```
src/portal/tools/system_tools/__init__.py
src/portal/tools/system_tools/clipboard_manager.py
src/portal/tools/system_tools/process_monitor.py
src/portal/tools/system_tools/system_stats.py
```
**Directory to remove:** `src/portal/tools/system_tools/system_tools/`

---

#### 3e — `media_tools`

This package has a nested `audio/` subdirectory that must be preserved.

**Files/directories to move:**
```
src/portal/tools/media_tools/media_tools/__init__.py
src/portal/tools/media_tools/media_tools/audio/          (entire subdirectory)
```
**Move to:**
```
src/portal/tools/media_tools/__init__.py
src/portal/tools/media_tools/audio/                      (entire subdirectory)
```
**Directory to remove:** `src/portal/tools/media_tools/media_tools/`

After this, `from portal.tools.media_tools.audio.audio_transcriber import AudioTranscribeTool`
resolves correctly.

---

#### 3f — `web_tools`

**Files to move:**
```
src/portal/tools/web_tools/web_tools/__init__.py
src/portal/tools/web_tools/web_tools/http_client.py
```
**Move to:**
```
src/portal/tools/web_tools/__init__.py
src/portal/tools/web_tools/http_client.py
```
**Directory to remove:** `src/portal/tools/web_tools/web_tools/`

---

#### 3g — `knowledge` (not directly causing a test collection error today, but has the same structural defect)

**Files to move:**
```
src/portal/tools/knowledge/knowledge/__init__.py
src/portal/tools/knowledge/knowledge/knowledge_base_sqlite.py
src/portal/tools/knowledge/knowledge/local_knowledge.py
```
**Move to:**
```
src/portal/tools/knowledge/__init__.py
src/portal/tools/knowledge/knowledge_base_sqlite.py
src/portal/tools/knowledge/local_knowledge.py
```
**Directory to remove:** `src/portal/tools/knowledge/knowledge/`

---

### No `pyproject.toml` changes required

`setuptools.packages.find` with `where = ["src"]` already discovers any package
that has an `__init__.py` anywhere under `src/`.  After flattening, the outer
directories gain their `__init__.py` and are discovered automatically.  No
entries need to be added to or removed from `pyproject.toml`.

### No test file changes required

The 5 failing test files already import from the correct (post-flatten) paths.
Once the source tree is flattened, all 5 collection errors resolve and the
tests inside become collectable — at which point the `xfail` markers in
`tests/conftest.py` (`LEGACY_API_TESTS`) kick in as intended for those tests that
still have API mismatches.

### Verification after flattening

```bash
# Should show 0 collection errors and ~190+ collected tests
pytest tests/ --co -q 2>&1 | tail -5

# The 5 previously-erroring files should now show xfail, not ERROR
pytest tests/tests/unit/tools/ -v 2>&1 | grep -E "PASSED|FAILED|xfail|ERROR"
```
