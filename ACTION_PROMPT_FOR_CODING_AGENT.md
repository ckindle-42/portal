# Portal Coding Agent — Action Prompt

**Project:** Portal v1.3.8 — Local-first AI Platform
**Repository:** https://github.com/ckindle-42/portal
**Source:** `PORTAL_AUDIT_REPORT.md` (generated 2026-03-01)
**Branch:** `ai-modularize-YYYY-MM-DD` (create fresh from main)

---

## Project Context

Portal is a **local-first AI platform** (Python 3.11 / FastAPI / async). It exposes an
OpenAI-compatible `/v1/chat/completions` endpoint. Architecture:

```
[Telegram/Slack/Web] → CentralDispatcher → SecurityMiddleware → AgentCore
  → IntelligentRouter → ExecutionEngine → OllamaBackend → LLM
  → MCPRegistry → Tool calls (max 3 rounds)
  → ContextManager + MemoryManager → EventBus → back to interface
```

**Non-negotiable constraints — do NOT violate:**

1. **API contract locked** — `/v1/chat/completions`, `/v1/models`, `/health`, `/ws`,
   `/v1/audio/transcriptions` must return identical response schemas. No behavior changes.
2. **No new features** — remediate defects only (Tier 1, 2). Tier 3 tasks add structure,
   not functionality.
3. **No cloud dependencies** — no external AI APIs, no cloud inference. Local only.
4. **No external frameworks** — no LangChain, LlamaIndex, Celery (without explicit ask).
5. **Preserve all behavior** — zero externally observable behavior changes unless
   correcting a verified defect.
6. **Tests must stay green** — `ruff check src/ tests/ && pytest tests/ -v` must pass
   after every commit.

---

## Execution Rules

1. **Branch:** Create `ai-modularize-YYYY-MM-DD` from main before starting.
2. **Commits:** One commit per logical change. Conventional prefix: `fix:`, `refactor:`,
   `test:`, `docs:`, `chore:`.
3. **Order:** Complete ALL Tier 1 tasks before any Tier 2. Complete ALL Tier 2 before Tier 3.
4. **CI gate after each task:**
   ```bash
   ruff check src/ tests/
   ruff format --check src/ tests/
   pytest tests/ -v --tb=short
   ```
5. **HIGH-risk tasks:** Checkpoint commit before starting; revert on first test failure.
6. **Parity check:** After any change to `interfaces/web/server.py`, manually verify
   `/health`, `/v1/models`, and `/v1/chat/completions` contract shapes are unchanged.

---

## TIER 1 — Remediation Tasks

*Complete Tier 1 entirely before starting Tier 2.*
*All items marked ✅ are already applied on `claude/audit-ci-hardening-6qD0L`.*

---

```
TASK-1 (✅ Applied)
Tier:        1
File(s):     tests/unit/test_router.py
Symbol(s):   TestCentralDispatcher.test_registered_interfaces_accessible
Category:    BUG
Finding:     pytest.importorskip("telegram") does not catch pyo3_runtime.PanicException
             from broken cryptography native module in CI.
Action:      Replace importorskip with try/except BaseException → pytest.skip().
Risk:        LOW
Blast Radius: Test only.
Parity:      Test behavior unchanged — skip instead of FAIL.
Acceptance:  pytest tests/unit/test_router.py -v shows PASS or SKIP, not FAIL.
```

---

```
TASK-2 (✅ Applied)
Tier:        1
File(s):     tests/unit/tools/test_document_tools.py
Symbol(s):   TestDocumentMetadataExtractorTool.test_extract_metadata
Category:    BUG
Finding:     `import pypdf` at module level raises pyo3_runtime.PanicException in
             environments with broken cryptography native module, blocking collection.
Action:      Wrap module-level pypdf import in `try/except BaseException` → `_has_pypdf`
             flag; add @pytest.mark.skipif guard on the test.
Risk:        LOW
Blast Radius: Test only.
Parity:      Test skips cleanly instead of crashing collection.
Acceptance:  pytest tests/unit/tools/test_document_tools.py -v shows PASS or SKIP.
```

---

```
TASK-3 (✅ Applied)
Tier:        1
File(s):     tests/integration/test_websocket.py
Symbol(s):   test_websocket_oversized_message_blocked
Category:    BUG
Finding:     Test asserts exact string "Message exceeds maximum length" but source
             at interfaces/web/server.py:549 now returns
             "Message exceeds maximum length of {max_len} characters".
Action:      Change assertion to: assert data.get("error", "").startswith("Message exceeds maximum length")
Risk:        LOW
Blast Radius: Test only.
Parity:      Validates same error category, tolerates message evolution.
Acceptance:  pytest tests/integration/test_websocket.py::test_websocket_oversized_message_blocked -v → PASS
```

---

```
TASK-4 (✅ Applied)
Tier:        1
File(s):     src/portal/tools/knowledge/local_knowledge.py
Symbol(s):   LocalKnowledgeTool._get_embedding, _load_db, _save_db
Category:    OBSERVABILITY
Finding:     8 print() statements in production I/O paths bypass structured logging
             and lose trace IDs.
Action:      Add `import logging` + `logger = logging.getLogger(__name__)` (after portal imports).
             Replace each print() with equivalent logger call:
               print("Warning: ...") → logger.warning(...)
               print("Error: ...")   → logger.error(...)
               print("Successfully") → logger.info(...)
             Use %-style formatting (not f-strings) to defer interpolation.
Risk:        LOW
Blast Radius: Local to module. Log output changes channel (stdout→log file), not content.
Parity:      Tool behavior identical; error messages now appear in structured logs.
Acceptance:  ruff check src/ → 0 errors; pytest tests/ → all pass.
```

---

```
TASK-5 (✅ Applied)
Tier:        1
File(s):     CLAUDE.md, docs/ARCHITECTURE.md, CONTRIBUTING.md
Category:    DOCS
Finding:     3 documentation drift items:
             - CLAUDE.md:33 says Python "<3.13" upper bound (wrong)
             - docs/ARCHITECTURE.md:443 shows version "1.3.4" (stale)
             - CONTRIBUTING.md:11 uses ".[all,dev]" (extra redundant)
             - CONTRIBUTING.md:37 uses --ignore-missing-imports flag (deprecated)
Action:
  CLAUDE.md:33 → change "<3.13" → remove upper bound: "3.11+ required"
  docs/ARCHITECTURE.md:443 → change "1.3.4" → "1.3.8"
  CONTRIBUTING.md:11 → change "pip install -e '.[all,dev]'" → "pip install -e '.[dev]'"
  CONTRIBUTING.md:37 → change "mypy src/portal --ignore-missing-imports" → "mypy src/portal"
Risk:        LOW
Blast Radius: Docs only.
Parity:      No behavior change.
Acceptance:  grep "3.13" CLAUDE.md → no results; grep "1.3.4" docs/ARCHITECTURE.md → no results.
```

---

```
TASK-6
Tier:        1
File(s):     src/portal/interfaces/web/server.py
Symbol(s):   _warmup() inner function
Category:    BUG
Finding:     `except Exception: pass` at line 211 silently suppresses agent warmup
             errors. A failing warmup is diagnosable only by health endpoint
             returning "warming_up" with no explanation.
Action:      Replace `pass` with:
               logger.warning("Agent warmup health check failed", exc_info=True)
             Keep the `finally: _agent_ready.set()` unchanged — warmup must
             complete even on error.
Risk:        LOW
Blast Radius: Adds a log line on startup error; no behavior change.
Parity:      Server behavior identical. Warmup still sets _agent_ready event.
Acceptance:  pytest tests/ -v → all pass; ruff check → 0 errors.
```

---

```
TASK-7
Tier:        1
File(s):     src/portal/routing/model_backends.py
Symbol(s):   OllamaBackend._generate_stream
Category:    BUG
Finding:     `except Exception:` at line 244 swallows aiohttp parse errors and
             JSON decode failures indistinguishably.
Action:      Replace with:
               except (aiohttp.ClientError, json.JSONDecodeError, asyncio.TimeoutError) as e:
                   logger.error("Stream error from Ollama: %s", e, exc_info=True)
                   raise
             (Any exception not in that tuple will naturally propagate.)
Risk:        MEDIUM — changes exception propagation. Verify ExecutionEngine handles it.
Blast Radius: execution_engine.py catches errors from backend; circuit breaker still fires.
Parity:      Non-parseable responses now surface as errors rather than silent truncation.
Acceptance:  pytest tests/unit/test_execution_engine_comprehensive.py -v → all pass.
```

---

```
TASK-8
Tier:        1
File(s):     src/portal/tools/document_processing/pandoc_converter.py
Symbol(s):   Module level pandoc version check
Category:    BUG
Finding:     `except Exception:` at line 31 catches all errors on pandoc version check.
             Should only catch FileNotFoundError and subprocess errors.
Action:      Replace `except Exception:` with:
               except (FileNotFoundError, subprocess.SubprocessError, OSError):
Risk:        LOW
Blast Radius: Tool only. If pandoc binary exists but errors in unexpected way, will now
              propagate instead of silently marking pandoc unavailable.
Parity:      For normal case (pandoc present or absent), behavior identical.
Acceptance:  pytest tests/ -v → all pass; ruff check → 0 errors.
```

---

```
TASK-9
Tier:        1
File(s):     tests/integration/test_web_interface.py
Symbol(s):   New test: test_models_fallback_when_ollama_unreachable
Category:    TEST (ADD_MISSING)
Finding:     GET /v1/models has no test for Ollama-unreachable scenario.
             Code falls back to ["auto"] model; this contract is untested.
Action:      Add test that patches the Ollama HTTP call to raise httpx.ConnectError,
             then asserts GET /v1/models returns 200 with a non-empty "data" list
             (the fallback auto model).
Risk:        LOW
Blast Radius: Test only.
Parity:      Documents existing fallback behavior.
Acceptance:  New test passes; pytest tests/integration/test_web_interface.py -v → all pass.
```

---

```
TASK-10
Tier:        1
File(s):     tests/integration/test_web_interface.py
Symbol(s):   New test: test_chat_completions_non_streaming_usage_field
Category:    TEST (ADD_MISSING)
Finding:     POST /v1/chat/completions non-streaming response does not have a test
             verifying the `usage` field (prompt_tokens, completion_tokens, total_tokens).
             OpenAI spec requires this field.
Action:      Add test that posts a non-streaming request, asserts response contains
             `usage` key with sub-keys `prompt_tokens`, `completion_tokens`, `total_tokens`
             all as integers ≥ 0.
Risk:        LOW
Blast Radius: Test only. Protects OpenAI API contract.
Parity:      Documents existing behavior.
Acceptance:  New test passes; pytest tests/integration/test_web_interface.py -v → all pass.
```

---

```
TASK-11
Tier:        1
File(s):     README.md
Symbol(s):   Public surface section
Category:    DOCS
Finding:     /ws (WebSocket) and /v1/audio/transcriptions endpoints are not documented
             in README. Users cannot discover them without reading source code.
Action:      Add a "API Endpoints" section to README.md (or extend existing table)
             listing:
               GET  /health                — system health
               GET  /v1/models             — OpenAI-compatible model list
               POST /v1/chat/completions   — chat (streaming + non-streaming)
               POST /v1/audio/transcriptions — audio transcription (Whisper)
               WS   /ws                    — WebSocket streaming chat
             Keep description brief (1 line each). Do not duplicate ARCHITECTURE.md.
Risk:        LOW
Blast Radius: Docs only.
Parity:      No behavior change.
Acceptance:  README.md contains entries for /ws and /v1/audio/transcriptions.
```

---

## TIER 2 — Structural Refactors

*Start only after ALL Tier 1 tasks are complete and `pytest tests/ -v` is green.*

---

```
TASK-12
Tier:        2
File(s):     src/portal/config/settings.py
             src/portal/interfaces/web/server.py
             src/portal/routing/router.py
Symbol(s):   SecurityConfig, WebConfig, RoutingConfig, os.getenv() calls
Category:    CONFIG_HARDENING
Finding:     11× os.getenv() in server.py and 3× in router.py bypass Settings/Pydantic
             validation. WEB_API_KEY, WEB_PORT, PORTAL_MAX_AUDIO_MB, WHISPER_URL,
             REQUIRE_API_KEY, ALLOWED_ORIGINS, etc. are read ad-hoc rather than
             through the centralized Settings model.
Action:
  1. In settings.py SecurityConfig, add:
       web_api_key: str = Field("", description="Bearer token for web API access")
       require_api_key: bool = Field(False, description="Require API key for all requests")
  2. In settings.py WebConfig, add:
       max_audio_mb: int = Field(25, ge=1, le=500)
       whisper_url: str = Field("http://localhost:10300/inference")
       cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:8080"])
  3. In server.py, replace os.getenv() calls with settings.security.web_api_key,
       settings.interfaces.web.max_audio_mb, etc. Inject settings via constructor.
  4. In router.py, move ROUTER_TOKEN and ROUTER_BIND_IP to RoutingConfig in settings.py.
Risk:        MEDIUM — touches server startup and auth flow.
Blast Radius: All WebInterface tests that set env vars may need monkeypatch → settings.
Parity:      All env vars still respected; defaults identical. Auth behavior unchanged.
Acceptance:  grep "os.getenv" src/portal/interfaces/web/server.py → 0 results
             pytest tests/ -v → all pass.
```

---

```
TASK-13
Tier:        2
File(s):     src/portal/routing/model_backends.py
             src/portal/tools/web_tools/http_client.py
             pyproject.toml
Symbol(s):   OllamaBackend, HTTPClientTool
Category:    LEGACY_ARTIFACT
Finding:     aiohttp is used in model_backends.py (OllamaBackend) and
             tools/web_tools/http_client.py while httpx is already a core dependency
             and used everywhere else. Dual HTTP clients add ~3MB to deps and split
             maintenance surface. TODO(Track B) comment already documents intent.
Action:
  1. Rewrite OllamaBackend to use httpx.AsyncClient:
       - Replace aiohttp.ClientSession with httpx.AsyncClient(timeout=httpx.Timeout(120))
       - Replace aiohttp streaming with httpx streaming (iter_lines / iter_raw)
       - Match identical retry/timeout behavior
  2. Rewrite http_client.py tool to use httpx (already optional-import pattern is there)
  3. Remove aiohttp from core dependencies in pyproject.toml (verify nothing else imports it)
  4. Run full test suite; update any mocked aiohttp sessions in tests to httpx mocks.
Risk:        MEDIUM — core inference path changes. Run streaming end-to-end test.
Blast Radius: ExecutionEngine, tests that mock aiohttp (check tests/conftest.py).
Parity:      Streaming behavior must be identical: same token chunks, same [DONE] terminator.
Acceptance:  grep "import aiohttp" src/ → 0 results; pytest tests/ -v → all pass;
             streaming SSE test passes.
```

---

```
TASK-14
Tier:        2
File(s):     src/portal/interfaces/web/server.py
Symbol(s):   _build_cors_origins()
Category:    SECURITY
Finding:     CORS origins are parsed by splitting on comma with no URL format validation.
             A misconfigured ALLOWED_ORIGINS env var could inject a malformed origin.
Action:      In _build_cors_origins(), validate each origin after splitting:
               from urllib.parse import urlparse
               def _is_valid_origin(o: str) -> bool:
                   try:
                       p = urlparse(o)
                       return p.scheme in ("http", "https") and bool(p.netloc)
                   except ValueError:
                       return False
               origins = [o for o in raw_origins if _is_valid_origin(o)]
               if not origins:
                   logger.warning("No valid CORS origins parsed; defaulting to localhost:8080")
                   return ["http://localhost:8080"]
Risk:        LOW
Blast Radius: Server startup only; normal valid origins pass unchanged.
Parity:      Valid origins work identically. Malformed ones are dropped with a warning.
Acceptance:  Unit test with valid and malformed origins. pytest → all pass.
```

---

```
TASK-15
Tier:        2
File(s):     src/portal/interfaces/web/server.py (lines 420, 469, 476, 567)
             src/portal/observability/metrics.py (line 47)
             src/portal/observability/watchdog.py (line 293)
             src/portal/security/sandbox/docker_sandbox.py (line 244)
             src/portal/tools/git_tools/git_tool.py (line 114)
             src/portal/tools/data_tools/text_transformer.py (lines 69, 90)
Symbol(s):   Various bare except Exception: handlers
Category:    BUG
Finding:     10 remaining bare `except Exception:` handlers after Tier 1. Each
             masks the specific error type and prevents precise error handling.
Action:      For each location, replace with specific exception types:
               server.py:420  → except (httpx.ConnectError, httpx.TimeoutException, json.JSONDecodeError)
               server.py:469  → except (httpx.RequestError, asyncio.TimeoutError)
               server.py:476  → except (httpx.RequestError, asyncio.TimeoutError)
               server.py:567  → except (RuntimeError, WebSocketDisconnect)
               metrics.py:47  → except ValueError  (duplicate prometheus registration)
               watchdog.py:293 → except asyncio.CancelledError: raise
                                 except Exception as e: logger.error("Watchdog error", exc_info=True)
               docker_sandbox.py:244 → except (docker.errors.APIError, docker.errors.DockerException)
               git_tool.py:114 → except (subprocess.SubprocessError, FileNotFoundError, OSError)
               text_transformer.py:69,90 → except (ValueError, UnicodeDecodeError)
Risk:        LOW (each change is local to one function)
Blast Radius: Each is isolated; errors that were swallowed before will now propagate.
              Verify tests still pass after each narrowing.
Parity:      For normal paths, behavior identical. Error paths now produce typed exceptions.
Acceptance:  grep "except Exception:" src/ → 0 results; pytest tests/ -v → all pass.
```

---

```
TASK-16
Tier:        2
File(s):     src/portal/tools/knowledge/knowledge_base_sqlite.py
Symbol(s):   Module level, KnowledgeBaseSQLite class methods
Category:    OBSERVABILITY
Finding:     knowledge_base_sqlite.py (502 LOC) has no logger; uses no structured
             logging. Errors disappear silently.
Action:      Add `import logging` and `logger = logging.getLogger(__name__)` after
             portal imports. Replace any raw exception handling with logger.error() calls.
Risk:        LOW
Blast Radius: Module-local. No behavior change.
Parity:      Tool behavior identical; errors now visible in structured logs.
Acceptance:  ruff check src/ → 0 errors; pytest tests/ -v → all pass.
```

---

## TIER 3 — Evolution Tasks

*Start only after ALL Tier 2 tasks are complete and CI is green.*

---

```
TASK-17
Tier:        3
File(s):     src/portal/routing/backend_registry.py (NEW)
             src/portal/routing/execution_engine.py
             src/portal/core/factories.py
Symbol(s):   BackendRegistry, ExecutionEngine.__init__, create_execution_engine
Category:    ARCHITECTURE
Finding:     `OllamaBackend` is hardcoded in ExecutionEngine.__init__() line 45.
             Adding a second backend (MLX, LMStudio) requires source edits, not config.
             The ModelBackend ABC and GenerationResult already provide a clean interface.
Action:
  1. Create routing/backend_registry.py:
       class BackendRegistry:
           def __init__(self) -> None:
               self._backends: dict[str, ModelBackend] = {}
           def register(self, name: str, backend: ModelBackend) -> None:
               self._backends[name] = backend
           def get(self, name: str) -> ModelBackend:
               if name not in self._backends:
                   raise KeyError(f"Backend '{name}' not registered")
               return self._backends[name]
           def available(self) -> list[str]:
               return list(self._backends.keys())
  2. Update ExecutionEngine.__init__ to accept pre-built backends dict:
       def __init__(self, ..., backends: dict[str, ModelBackend] | None = None):
           self.backends = backends or {}
  3. Update factories.create_execution_engine() to instantiate OllamaBackend
     and pass it in via the new parameter.
  4. No behavior change — same Ollama backend, same logic. Registry is new wiring only.
Risk:        MEDIUM — changes ExecutionEngine constructor signature.
Blast Radius: factories.py, any test that instantiates ExecutionEngine directly.
Parity:      Identical runtime behavior. Registry adds no new paths.
Acceptance:  Unit test for BackendRegistry (register, get, KeyError on unknown).
             pytest tests/ -v → all pass.
```

---

```
TASK-18
Tier:        3
File(s):     src/portal/routing/workspace_registry.py (NEW)
             src/portal/routing/router.py
             src/portal/routing/intelligent_router.py
Symbol(s):   resolve_model (router.py), IntelligentRouter.route
Category:    ARCHITECTURE
Finding:     Workspace routing exists only in the Ollama proxy (router.py:8000).
             AgentCore's IntelligentRouter has no workspace concept. Telegram/Slack/
             WebSocket callers cannot use workspace (persona) routing.
Action:
  1. Create routing/workspace_registry.py:
       class WorkspaceRegistry:
           def __init__(self, workspaces: dict[str, Any]) -> None:
               self._workspaces = workspaces
           def get_model(self, workspace_id: str) -> str | None:
               ws = self._workspaces.get(workspace_id)
               return ws.get("model") if ws else None
           def list_workspaces(self) -> list[str]:
               return list(self._workspaces.keys())
  2. Load from settings (workspaces config) in factories.py.
  3. In router.py, replace inline workspace dict lookup with WorkspaceRegistry.get_model().
  4. In intelligent_router.py, accept optional WorkspaceRegistry; if workspace_id
     is present on IncomingMessage, consult registry before task classification.
  5. Pass WorkspaceRegistry through DependencyContainer.
Risk:        HIGH — touches core routing logic. Use checkpoint commit; revert on failure.
Blast Radius: router.py, intelligent_router.py, factories.py, IncomingMessage type.
Parity:      Proxy router behavior must be identical (same workspace→model mapping).
             New IntelligentRouter workspace lookup is additive.
Acceptance:  Existing workspace routing tests in tests/unit/test_intelligent_router.py pass.
             New test: IntelligentRouter.route() with workspace_id → returns workspace model.
             pytest tests/ -v → all pass.
```

---

## Final Checklist (Before Closing Branch)

```bash
# Lint
ruff check src/ tests/
ruff format --check src/ tests/

# Type check
mypy src/portal --ignore-missing-imports

# Tests
pytest tests/ -v --tb=short

# Coverage
pytest --cov=src/portal --cov-report=term-missing tests/
# Target: ≥85% on src/portal/core/, src/portal/routing/, src/portal/interfaces/web/

# Dead code check
grep -rn "import aiohttp" src/portal/  # should be 0 after TASK-13
grep -rn "except Exception:" src/portal/  # should be 0 after TASK-15
grep -rn "os.getenv" src/portal/interfaces/web/server.py  # should be 0 after TASK-12

# Behavior parity verification
# Start server in test mode, verify these return correct schemas:
# GET  /health              → {"status": "ok"|"warming_up", "version": "1.3.8", ...}
# GET  /v1/models           → {"object": "list", "data": [...]}
# POST /v1/chat/completions → {"object": "chat.completion", "choices": [...], "usage": {...}}
# POST /v1/chat/completions (stream=true) → SSE with data: lines + data: [DONE]

# Verify no new features added
git diff main --stat  # only files listed in task descriptions should appear

# Update CHANGELOG.md with:
# - LOC before/after
# - List of tasks completed
# - Production readiness re-score (target: 4.5/5 after all tiers)
```

---

*Generated from PORTAL_AUDIT_REPORT.md on 2026-03-01.*
*All ✅ tasks are pre-applied on branch `claude/audit-ci-hardening-6qD0L`.*
