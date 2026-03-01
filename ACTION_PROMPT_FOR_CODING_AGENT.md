# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-01
**Source audit:** PORTAL_AUDIT_REPORT.md (same date)
**Target version after completion:** 1.3.9

---

## Project Context

Portal is a local-first AI platform (Python 3.11 / FastAPI / async).
Source: `src/portal/` (98 Python files, ~15,800 LOC).
Tests: `tests/` (67 Python files, ~13,300 LOC, 862 currently passing).

**Non-negotiable constraints:**
- API contract locked: `/v1/chat/completions`, `/v1/models`, `/health`, `/ws`, `/v1/audio/transcriptions` — no behavior changes
- No new features unless explicitly a task below
- No cloud dependencies, no external AI frameworks (LangChain, etc.)
- All behavior must remain identical to pre-task state
- Every task must leave lint and tests green

**CI gate (run before marking any tier complete):**
```bash
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
```

**Branch:** `ai-type-safety-YYYY-MM-DD`
**Commits:** conventional (`fix:`, `refactor:`, `docs:`, `chore:`, `test:`), one per logical change.

---

## Tier 1 — Remediation (Bug Fixes, Docs, Dead Code)

Run CI gate after completing all Tier 1 tasks before starting Tier 2.

---

### TASK-01

```
TASK-01
Tier:        1
File(s):     src/portal/tools/data_tools/text_transformer.py
Symbol(s):   TextTransformerTool._serialize
Category:    BUG
Finding:     _serialize() returns None when format is unrecognized or serialization
             fails, but its return type is annotated as str. Callers receive None
             and pass it to the response without crashing only because the outer
             execute() wraps it in a dict.
Action:      Change lines 103-106 — where the function falls through without
             returning — to return "" instead of None. Keep the
             _error_response() for unknown format; remove the implicit None
             returns from the two bare `return None` / `return None` paths.
Risk:        LOW
Blast Radius: TextTransformerTool.execute() output only.
Parity:      _error_response() path behavior unchanged. Success paths unchanged.
Acceptance:  pytest tests/unit/tools/test_data_tools.py::TestTextTransformerTool -v
             — all tests pass. mypy src/portal/tools/data_tools/text_transformer.py
             — no return-value errors.
```

---

### TASK-02

```
TASK-02
Tier:        1
File(s):     src/portal/core/structured_logger.py
Symbol(s):   TraceContext.token, TraceContext.__enter__, TraceContext.__exit__
Category:    TYPE_SAFETY
Finding:     self.token is declared as None but _trace_id_var.set() returns a
             Token[str | None] object. _trace_id_var.reset(self.token) is
             therefore called with the wrong type (None instead of Token).
             mypy errors at lines 137 and 142.
Action:      Change the class body so self.token is typed as
             Token[str | None] | None = None and __exit__ guards the reset
             call: if self.token is not None: _trace_id_var.reset(self.token)
Risk:        LOW
Blast Radius: TraceContext context manager only. Behavior is identical —
             the token variable was already being set correctly at runtime;
             this fixes the type annotation and the guard.
Parity:      Trace ID context var behavior unchanged.
Acceptance:  mypy src/portal/core/structured_logger.py — 0 errors on this file.
             pytest tests/ -v --tb=short -- all pass.
```

---

### TASK-03

```
TASK-03
Tier:        1
File(s):     src/portal/core/interfaces/agent_interface.py
Symbol(s):   BaseInterface.__init__
Category:    TYPE_SAFETY
Finding:     self.config = None and self.metadata = None override dict[str, Any]
             type annotations. mypy errors at lines 29 and 48.
Action:      Change defaults to self.config: dict[str, Any] = {}
             and self.metadata: dict[str, Any] = {}
Risk:        LOW
Blast Radius: BaseInterface subclasses. No behavior change — None was never
             a valid value at runtime; {} is equivalent.
Parity:      All subclass behaviors unchanged.
Acceptance:  mypy src/portal/core/interfaces/agent_interface.py — 0 errors.
             pytest tests/ -- all pass.
```

---

### TASK-04

```
TASK-04
Tier:        1
File(s):     src/portal/cli.py
Symbol(s):   up (command)
Category:    BUG
Finding:     portal up checks ports 6379 (redis) and 6333 (qdrant) unless
             --minimal is set, even though redis and qdrant are optional
             services not started by the default portal up flow. This causes
             spurious "port in use" errors on machines where Redis is running
             for unrelated purposes.
Action:      Remove the redis and qdrant entries from the required_ports list
             in the `up` command. They are optional sidecar services and should
             not be in the startup gate. Leave the portal-api (8081),
             web-ui (8080), and ollama (11434) checks.
Risk:        LOW
Blast Radius: portal up startup gate only.
Parity:      Core startup behavior unchanged. Optional service checks removed.
Acceptance:  portal up --skip-port-check equivalent check: manually verify the
             required_ports list no longer includes 6379 and 6333.
             pytest tests/ -- all pass (no CLI unit tests for this check).
```

---

### TASK-05

```
TASK-05
Tier:        1
File(s):     src/portal/security/input_sanitizer.py
Symbol(s):   InputSanitizer.sanitize_command (DANGEROUS_PATTERNS list)
Category:    OBSERVABILITY
Finding:     Warning strings in DANGEROUS_PATTERNS contain raw emoji bytes that
             render as mojibake (âš ï¸ instead of ⚠️) in many terminals and log
             aggregators. This is because the source bytes were pasted as
             raw UTF-8 in an ASCII-expecting context.
Action:      Replace the emoji warning prefix strings in the DANGEROUS_PATTERNS
             tuples with ASCII [WARNING] prefix, e.g.:
             ("[WARNING] Recursive delete from root", ...) — or use proper
             Unicode escape sequences like "\u26a0\ufe0f Recursive delete...".
             Either approach is acceptable; ASCII is more portable.
Risk:        LOW
Blast Radius: Warning message text in logs only. No behavioral change.
Parity:      sanitize_command() logic unchanged; only the warning strings change.
Acceptance:  grep "âš " src/portal/security/input_sanitizer.py — 0 matches.
             pytest tests/unit/test_security_middleware.py -- all pass.
```

---

### TASK-06

```
TASK-06
Tier:        1
File(s):     docs/ARCHITECTURE.md
Symbol(s):   BaseHTTPBackend description, ExecutionEngine table
Category:    DOCUMENTATION
Finding:     ARCHITECTURE.md describes BaseHTTPBackend as using "aiohttp session
             management" even though aiohttp was replaced by httpx in TASK-13
             (PR #82). The ExecutionEngine table also says "(lmstudio and mlx
             planned)" which is stale — LMStudio was removed in 1.3.5;
             MLX is a ROADMAP item.
Action:      1. In the BaseHTTPBackend description, change "aiohttp" to "httpx".
             2. In the ExecutionEngine/backends table, change "(lmstudio and mlx
                planned)" to "(mlx: planned — see ROADMAP.md)".
Risk:        NONE
Blast Radius: Documentation only.
Parity:      N/A — documentation correction.
Acceptance:  grep "aiohttp" docs/ARCHITECTURE.md — 0 matches.
```

---

### TASK-07

```
TASK-07
Tier:        1
File(s):     .env.example
Symbol(s):   RATE_LIMIT_PER_MINUTE
Category:    DOCUMENTATION
Finding:     .env.example sets RATE_LIMIT_PER_MINUTE=60 but the Settings class
             (SecurityConfig) defaults max_requests_per_minute=20. This means
             operators who copy .env.example get a 3x higher limit than the
             code default, creating confusion about which value is canonical.
Action:      Change RATE_LIMIT_PER_MINUTE=60 to RATE_LIMIT_PER_MINUTE=20
             in .env.example to match the Settings default.
Risk:        LOW
Blast Radius: .env.example documentation only. Existing deployments unaffected.
Parity:      No behavior change — .env.example is a template, not loaded
             by the application directly.
Acceptance:  grep "RATE_LIMIT_PER_MINUTE" .env.example | grep "=20" — match found.
```

---

### TASK-08

```
TASK-08
Tier:        1
File(s):     CONTRIBUTING.md
Symbol(s):   Running Tests section
Category:    DOCUMENTATION
Finding:     pytest --cov=portal is incorrect; the package is installed under
             src/portal. The correct path is --cov=src/portal.
Action:      Change "pytest --cov=portal" to
             "pytest --cov=src/portal --cov-report=term-missing"
             in CONTRIBUTING.md.
Risk:        NONE
Blast Radius: Documentation only.
Acceptance:  grep "cov=portal" CONTRIBUTING.md — 0 matches.
```

---

## Tier 2 — Structural (Type Safety, Behavioral Gaps)

Run CI gate after completing all Tier 2 tasks before starting Tier 3.

---

### TASK-09

```
TASK-09
Tier:        2
File(s):     src/portal/interfaces/telegram/interface.py
Symbol(s):   _handle_callback_query, _handle_message, _handle_start,
             _handle_help, _handle_status, _handle_health, _handle_tools,
             _handle_approve, _handle_deny (and all handlers that
             access update.callback_query or update.message)
Category:    TYPE_SAFETY / BUG
Finding:     mypy reports 29 union-attr errors because update.callback_query
             and update.message can be None per python-telegram-bot's type
             stubs. Each handler accesses these without a None check,
             creating real NoneType dereference risks if Telegram sends
             unexpected update types.
Action:      Add early-return None guards at the top of each handler:
               if update.callback_query is None: return   (for callback handlers)
               if update.message is None: return          (for message handlers)
             Add: if update.message.from_user is None: return
             where from_user is accessed.
             Do NOT change any handler logic — only add the None guards.
Risk:        MEDIUM
Blast Radius: Telegram interface handlers only. Behavior identical for
             well-formed Telegram updates; returns silently for malformed ones.
Parity:      All existing Telegram bot behaviors preserved.
Acceptance:  mypy src/portal/interfaces/telegram/interface.py 2>&1 |
             grep "union-attr" — 0 matches.
             pytest tests/ -- all pass (including any Telegram unit tests).
```

---

### TASK-10

```
TASK-10
Tier:        2
File(s):     src/portal/interfaces/telegram/interface.py
Symbol(s):   import at top of file (from portal.security.security_module import RateLimiter)
Category:    DEAD_CODE / MODULARIZE
Finding:     telegram/interface.py imports RateLimiter from
             portal.security.security_module (the backward-compat shim),
             not from portal.security.rate_limiter (the actual module).
             The shim exists solely to support this stale import.
Action:      Change the import to:
               from portal.security.rate_limiter import RateLimiter
             This is a pure import path change — no logic changes.
             After this change, security_module.py becomes unused externally.
Risk:        LOW
Blast Radius: Import path only. No behavior change.
Parity:      RateLimiter behavior identical.
Acceptance:  grep "security_module" src/portal/interfaces/telegram/interface.py
             — 0 matches.
             pytest tests/ -- all pass.
```

---

### TASK-11

```
TASK-11
Tier:        2
File(s):     src/portal/security/sandbox/docker_sandbox.py
Symbol(s):   DockerPythonSandbox._client, setup_image, run, cleanup
Category:    TYPE_SAFETY
Finding:     self._client is typed as Any | None and initialized to None.
             Multiple methods (setup_image, run, cleanup) access self._client
             without None checks, generating 6 mypy union-attr errors.
             If _client is None and a method is called, AttributeError is raised.
Action:      Add a helper _require_client() that raises RuntimeError with
             a descriptive message if self._client is None, then call it
             at the start of setup_image(), run(), and cleanup().
             Example:
               def _require_client(self):
                   if self._client is None:
                       raise RuntimeError(
                           "Docker client not initialized. "
                           "Call setup() before using the sandbox."
                       )
Risk:        LOW
Blast Radius: DockerPythonSandbox methods only. Behavior equivalent — error
             is raised either way; now it is a descriptive RuntimeError
             instead of AttributeError.
Parity:      Sandbox behavior when Docker is available unchanged.
Acceptance:  mypy src/portal/security/sandbox/docker_sandbox.py |
             grep "union-attr\|has no attribute" — 0 matches.
             pytest tests/unit/test_docker_sandbox.py -- all pass.
```

---

### TASK-12

```
TASK-12
Tier:        2
File(s):     src/portal/tools/__init__.py
Symbol(s):   ToolRegistry._discover_entry_point_tools
Category:    TYPE_SAFETY
Finding:     importlib.metadata.get() is called with a list argument on a
             Deprecated object — mypy error at line 140. This is the old
             importlib.metadata.entry_points() API.
Action:      Replace the deprecated call with the current API:
               importlib.metadata.entry_points(group="portal.tools")
             (or whatever group string is used). Verify the existing behavior
             is preserved by reading the current implementation first.
Risk:        LOW
Blast Radius: Plugin entry-point discovery only. No built-in tools affected.
Parity:      Entry-point discovery behavior identical on Python 3.11+.
Acceptance:  mypy src/portal/tools/__init__.py | grep "Deprecated\|list\[Never\]"
             — 0 matches.
             pytest tests/ -- all pass.
```

---

### TASK-13

```
TASK-13
Tier:        2
File(s):     src/portal/tools/document_processing/word_processor.py
Symbol(s):   Multiple Document.save() and Document() calls
Category:    TYPE_SAFETY
Finding:     python-docx expects str | IO[bytes] but Path objects are passed
             to Document.save() and Document() in ~10 locations.
             mypy reports arg-type errors.
Action:      Wrap Path arguments with str() in all Document.save(path) and
             Document(path) calls throughout word_processor.py.
             Example: Document.save(str(output_path))
             Do not change any logic; only add str() wrappers around Path objects.
Risk:        LOW
Blast Radius: WordProcessor tool only.
Parity:      File I/O behavior identical (python-docx accepts str paths).
Acceptance:  mypy src/portal/tools/document_processing/word_processor.py |
             grep "arg-type" — 0 matches.
             pytest tests/unit/test_word_processor.py -- all pass.
```

---

### TASK-14

```
TASK-14
Tier:        2
File(s):     src/portal/core/context_manager.py
Symbol(s):   ContextManager._MAX_AGE_DAYS (class attribute)
Category:    CONFIG_HARDENING
Finding:     _MAX_AGE_DAYS = int(os.getenv("PORTAL_CONTEXT_RETENTION_DAYS", "30"))
             is evaluated at class definition time (module import), not at
             construction time. This means the env var cannot be overridden
             after module load and makes test isolation harder.
Action:      Move the env read into __init__:
               self._max_age_days = int(
                   os.getenv("PORTAL_CONTEXT_RETENTION_DAYS", "30")
               )
             Update all internal references from _MAX_AGE_DAYS to
             self._max_age_days. No behavior change.
Risk:        LOW
Blast Radius: ContextManager._prune_old_messages only.
Parity:      Pruning behavior identical.
Acceptance:  grep "_MAX_AGE_DAYS" src/portal/core/context_manager.py — 0 matches.
             pytest tests/unit/test_context_manager.py -- all pass.
```

---

### TASK-15

```
TASK-15
Tier:        2
File(s):     src/portal/memory/manager.py
Symbol(s):   MemoryManager._MAX_AGE_DAYS (class attribute)
Category:    CONFIG_HARDENING
Finding:     Same pattern as TASK-14. _MAX_AGE_DAYS and PORTAL_MEMORY_DB are
             read at class scope.
Action:      Move os.getenv("PORTAL_MEMORY_RETENTION_DAYS") to __init__
             as self._max_age_days. The PORTAL_MEMORY_DB read in __init__
             is acceptable as-is (constructor scope).
Risk:        LOW
Blast Radius: MemoryManager._prune_old_messages only.
Parity:      Pruning behavior identical.
Acceptance:  grep "_MAX_AGE_DAYS" src/portal/memory/manager.py — 0 matches.
             pytest tests/unit/test_memory_manager_comprehensive.py -- all pass.
```

---

## Tier 3 — Hardening (New Tests, MCP Verification, Shim Cleanup)

Run CI gate after completing all Tier 3 tasks.

---

### TASK-16

```
TASK-16
Tier:        3
File(s):     tests/unit/tools/test_data_tools.py
Symbol(s):   TestTextTransformerTool
Category:    TEST (ADD_MISSING)
Finding:     No test verifies that TextTransformer returns an empty string
             (not None) when serialization fails or format is unknown.
             This is the acceptance criterion for TASK-01.
Action:      Add two parametrized test cases to TestTextTransformerTool:
             1. Unsupported output format → execute returns error response
                (not null/None)
             2. Malformed input for json→yaml conversion → execute returns
                error response with non-None content field
Risk:        LOW
Blast Radius: Test suite only.
Parity:      N/A — new tests.
Acceptance:  pytest tests/unit/tools/test_data_tools.py::TestTextTransformerTool
             — all pass including new cases.
```

---

### TASK-17

```
TASK-17
Tier:        3
File(s):     tests/unit/test_telegram_interface.py (new file or existing)
Symbol(s):   TelegramInterface handlers
Category:    TEST (ADD_MISSING)
Finding:     No unit tests verify that Telegram handlers return silently
             (do not raise) when update.message is None or
             update.callback_query is None. These are the acceptance
             criteria for TASK-09.
Action:      Add unit tests for at least two handlers:
             1. _handle_message with update.message = None — assert no exception
             2. _handle_callback_query with update.callback_query = None —
                assert no exception
             Use pytest-asyncio and mock the Update object.
Risk:        LOW
Blast Radius: Test suite only.
Parity:      N/A — new tests.
Acceptance:  pytest tests/unit/test_telegram_interface.py -- all pass.
             The tests should fail if the None guards from TASK-09 are removed.
```

---

### TASK-18

```
TASK-18
Tier:        3
File(s):     src/portal/protocols/mcp/mcp_registry.py
Symbol(s):   MCPRegistry.call_tool
Category:    BUG (verification + documentation)
Finding:     The call_tool() method has a code comment:
             "NOTE — mcpo endpoint format (needs live verification):
              For openapi transport the URL is constructed as:
              POST {server_url}/{tool_name}"
             This means the MCP tool dispatch path has not been verified
             against a live mcpo instance and may silently fail in production.
Action:      1. Verify the mcpo endpoint format by reading mcpo documentation
                or running a local test. The expected format is:
                POST http://localhost:9000/{tool_name}
             2. If correct, remove the NOTE comment block (lines 163-173).
             3. If incorrect, fix the URL construction and remove the comment.
             4. Add a unit test in tests/unit/test_mcp_registry.py that
                mocks httpx and asserts the correct URL is called for
                openapi transport.
Risk:        MEDIUM
Blast Radius: MCP tool dispatch path. If URL format is wrong, all MCP
             tool calls fail silently in production.
Parity:      MCPRegistry external API unchanged.
Acceptance:  NOTE comment removed from mcp_registry.py.
             pytest tests/unit/test_mcp_registry.py -- all pass including
             new URL-format test.
```

---

### TASK-19

```
TASK-19
Tier:        3
File(s):     CHANGELOG.md
Symbol(s):   [Unreleased] section
Category:    DOCUMENTATION
Finding:     The top of CHANGELOG.md has an [Unreleased] section containing
             the TASK-6 through TASK-18 work. This work is complete and
             merged but not yet given a version number.
Action:      Change "## [Unreleased] - 2026-03-01" to
             "## [1.3.9] - 2026-03-01" and update pyproject.toml version
             from "1.3.8" to "1.3.9" and src/portal/__init__.py __version__
             accordingly.
             Also merge or relabel the second "[Unreleased]" block
             (2026-02-28 modularization work) — that work was already
             included in 1.3.8, so relabel it to match.
Risk:        LOW
Blast Radius: CHANGELOG.md, pyproject.toml, __init__.py version strings only.
Parity:      N/A — documentation and version bump.
Acceptance:  grep "\[Unreleased\]" CHANGELOG.md — 0 matches.
             python3 -c "import portal; print(portal.__version__)" — "1.3.9".
```

---

## Execution Rules

1. Work on branch `ai-type-safety-YYYY-MM-DD` (substitute today's date).
2. One commit per task: `fix(telegram): add None guards for union-attr errors (TASK-09)`.
3. Run the CI gate after each tier completes before starting the next.
4. Do not modify any of the following without explicit instruction:
   - `/v1/chat/completions` request/response schema
   - `/v1/models` response schema
   - `/health` response schema
   - Any Prometheus metric names
   - The `WEB_API_KEY` / `ROUTER_TOKEN` auth flows
5. Tasks may be done in any order within a tier. Complete all tasks in a tier before starting the next.
6. HIGH-risk tasks (TASK-18) get a checkpoint commit immediately before the change.

---

## CI Gate (required between tiers)

```bash
python3 -m ruff check src/ tests/
python3 -m ruff format --check src/ tests/
python3 -m pytest tests/ -v --tb=short
```

Expected output after all tasks complete:
- ruff check: 0 violations
- pytest: 862+ PASS, 0 FAIL, 0 ERROR
- mypy: errors reduced from 170 to <30 (tools layer has external lib issues that are acceptable)
