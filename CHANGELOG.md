# Changelog

All notable changes to Portal will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

`pyproject.toml` is the Single Source of Truth for the version number. All other
version references (`__init__.py`) must stay in sync with it.

---

## [1.0.2] - 2026-02-25

### Fixed — Phase 1 quality review resolutions

All critical runtime breaks, architectural seams, and quality gaps identified in
the 1.0.1 quality review have been addressed in this patch.

#### Critical fixes

- **CRIT-1** `factories.py:DependencyContainer.create_agent_core()` — replaced the
  broken hand-rolled `AgentCore(context_manager=..., event_broker=None, ...)` call
  (wrong kwargs, five missing args) with `AgentCore(**self.get_all())`.
- **CRIT-2** `agent_core.py` — added `stream_response(incoming: IncomingMessage)`
  async generator; wraps `process_message()` and yields the response as a single
  token until true per-token streaming is wired to the Ollama backend (Phase 2).
- **CRIT-3** `core/types.py` — consolidated the two incompatible `ProcessingResult`
  classes into one canonical dataclass.  The local definition in `agent_core.py`
  is removed; all modules now import from `portal.core.types`.  Unified fields:
  `response`, `success`, `model_used`, `execution_time`, `tools_used`, `warnings`,
  `metadata`, `trace_id`, `prompt_tokens`, `completion_tokens`, `error`,
  `tool_results`.
- **CRIT-4** `config/settings.py` — dual config schema resolved:
  - `env_prefix` changed from `POCKETPORTAL_` → `PORTAL_` (ARCH-4).
  - `SlackConfig` added (was missing entirely).
  - `TelegramConfig.allowed_user_ids` renamed to `authorized_users` to match
    `TelegramInterface`'s access pattern.
  - `SecurityConfig.rate_limit_requests` added (used by `TelegramInterface`).
  - `Settings.to_agent_config()` added — converts a `Settings` object into the
    plain dict that `DependencyContainer` and `create_agent_core()` consume;
    fixes the `lifecycle.py` path where `create_agent_core(settings)` was called
    with a Pydantic object instead of a dict.
  - `validate_required_config()` updated to use the renamed field.
  - `LoggingConfig.verbose` field added (used by `TelegramInterface`).
- **CRIT-5** `slack/interface.py` — `hmac.new(key, msg, hashlib.sha256)` confirmed
  valid for Python 3.11; `hashlib.sha256` (constructor, not instance) is the
  correct digestmod argument.  Comprehensive unit tests added in
  `tests/unit/test_slack_hmac.py`.

#### Architectural fixes

- **ARCH-1** `interfaces/base.py` — confirmed already a clean re-export of
  `core/interfaces/agent_interface.BaseInterface`; no second contract exists.
- **ARCH-2** `interfaces/web/server.py` — fixed non-streaming path from
  `await agent_core.process_message(incoming)` (passing an `IncomingMessage`
  dataclass) to the correct kwargs call
  `process_message(chat_id=..., message=..., interface=InterfaceType.WEB)`.
  `_format_completion()` fixed: `result.text` → `result.response`.
- **ARCH-3** `agent_core.py` — MCP dispatch wired: `mcp_registry` is now an
  optional parameter to `AgentCore.__init__()`, stored as `self.mcp_registry`,
  and a `_dispatch_mcp_tools()` method is ready to be called once
  `ExecutionEngine` surfaces tool-call entries from LLM responses (Phase 2).
- **ARCH-4** — resolved under CRIT-4 above.

Also in `agent_core.py`:
  - `process_message()` now coerces plain string `interface` arguments to
    `InterfaceType` so that callers like `TelegramInterface` that pass
    `interface="telegram"` (string) don't trigger `AttributeError` on `.value`.

#### Quality fixes

- **QUAL-1** `docs/ARCHITECTURE.md` — replaced five-line placeholder with full
  architecture document covering component roles, data flow, startup sequence,
  directory structure, and known Phase 2 limitations.
- **QUAL-2** `web/server.py:/health` — endpoint now calls
  `agent_core.health_check()` and reflects the real state (`"ok"` /
  `"degraded"` / `"error"`) instead of hard-coding `"ok"`. `AgentCore.health_check()`
  added.
- **QUAL-3** `mcp_registry.py:call_tool()` — mcpo endpoint format documented
  in-code; integration test against a live mcpo instance deferred to Phase 2.
- **QUAL-4** `settings.py:validate_required_config()` — updated to use
  `telegram.authorized_users` (renamed field) and extended to cover the Slack
  `require_approval_for_high_risk` check.
- **QUAL-5** `tests/unit/test_bootstrap.py` — bootstrap smoke tests added:
  `DependencyContainer` initialisation, `get_all()` completeness, `create_agent_core()`
  return type, async method signatures, Settings-object acceptance, and
  `ProcessingResult` field coverage.
- **QUAL-6** `telegram/interface.py` — `ToolConfirmationMiddleware` import from
  `portal.middleware` confirmed working; `portal.middleware.__init__` correctly
  exports the class.  Additionally, `TelegramInterface` updated to import and
  pass `InterfaceType.TELEGRAM` (enum) instead of the plain string `"telegram"`.
- **QUAL-7** `factories.py:get_all()` — `mcp_registry` added to the returned
  dict so it reaches `AgentCore` on every `create_agent_core()` call.

#### Tests added

| File | Covers |
|------|--------|
| `tests/unit/test_bootstrap.py` | QUAL-5: DI wiring, ProcessingResult fields, factory function |
| `tests/unit/test_slack_hmac.py` | CRIT-5: hmac.new() correctness, Slack signature verify/reject |

---

## [1.0.1] - 2026-02-25

### Changed — Quality Review & Issue Register

Full codebase review completed across all layers (`src/`, `tests/`, `docs/`).
No runtime changes in this patch; this entry catalogues every known defect
discovered during the port from PocketPortal so that Phase 1 fixes are tracked
against a clear baseline.

#### Critical issues identified (will break at runtime)

- **CRIT-1** `factories.py:create_agent_core()` passes wrong kwargs to `AgentCore`;
  `event_broker=None` is not an accepted parameter and five required dependencies
  (`model_registry`, `execution_engine`, `event_bus`, `prompt_manager`, `config`)
  are omitted entirely. Every instantiation raises `TypeError`.
- **CRIT-2** `WebInterface` and `SlackInterface` call
  `agent_core.stream_response(incoming)` — method does not exist on `AgentCore`.
  Every web/Slack request raises `AttributeError`.
- **CRIT-3** Two incompatible `ProcessingResult` classes coexist:
  `agent_core.py` uses field `response`; `core/types.py` uses field `text`.
  `WebInterface` imports from `types.py` but receives the `agent_core.py` object,
  causing `AttributeError` on every response format step.
- **CRIT-4** Dual config schemas (`settings.py` flat structure vs.
  `settings_schema.py` nested structure) are incompatible. `lifecycle.py` loads
  the flat schema while all three interfaces expect nested objects
  (`config.interfaces.telegram.authorized_users`, etc.), causing `AttributeError`
  on every interface startup. `env_prefix='POCKETPORTAL_'` in `settings.py` also
  prevents any Portal env var from being picked up.
- **CRIT-5** `SlackInterface._verify_slack_signature()` uses `hmac.new()` with
  `hashlib.sha256` as digestmod — behaviour needs an explicit unit test to confirm
  it is correct under Python 3.11 given the security-critical nature of signature
  verification.

#### Architectural seams identified

- **ARCH-1** Two separate `BaseInterface` contracts exist:
  `core/interfaces/agent_interface.py` and `interfaces/base.py`. The three
  concrete interfaces each inherit from a different one (or neither). No single
  enforced contract.
- **ARCH-2** `AgentCore.process_message()` expects five positional arguments;
  `WebInterface` passes a single `IncomingMessage` dataclass. Signatures are
  incompatible.
- **ARCH-3** `MCPRegistry` is assembled by `DependencyContainer` but never
  referenced inside `AgentCore.process_message()`. MCP tool dispatch is wired
  in the container but completely absent from the processing pipeline.
- **ARCH-4** `env_prefix='POCKETPORTAL_'` in `settings.py` causes all Portal
  environment variables to be silently ignored (covered under CRIT-4).

#### Quality gaps identified

- **QUAL-1** `docs/ARCHITECTURE.md` is a five-line placeholder.
- **QUAL-2** `/health` endpoint in `WebInterface` always returns `"agent_core": "ok"`
  regardless of actual agent state.
- **QUAL-3** `MCPRegistry.call_tool()` endpoint path format (`/{tool_name}`) has
  not been verified against a live mcpo instance.
- **QUAL-4** `settings.py:validate_required_config()` checks `interfaces.telegram`
  as a bool flag — will need updating once the config schema is consolidated.
- **QUAL-5** No test covers the startup path end-to-end (`Runtime.bootstrap()`,
  `DependencyContainer.create_agent_core()`).
- **QUAL-6** `TelegramInterface` imports `ToolConfirmationMiddleware` from
  `portal.middleware` — that symbol does not exist in the module, causing
  `ImportError` at Telegram startup.
- **QUAL-7** `DependencyContainer.get_all()` omits `mcp_registry` from its
  returned dict, so even after CRIT-1 is fixed the MCP registry will not reach
  `AgentCore` via `get_all()`.

#### Improvement roadmap recorded

Three-phase plan documented in the quality review:

| Phase | Goal | Gate |
|-------|------|------|
| Phase 1 (1–2 days) | Make it boot — fix CRIT-1 through CRIT-5, ARCH-1/2, QUAL-5/6/7 | `pytest tests/unit/test_bootstrap.py` passes without Docker or Ollama |
| Phase 2 (3–5 days) | Make it reliable — true token streaming, MCP dispatch, real health check | Web UI sends a message, gets a streamed response, MCP tool call resolves |
| Phase 3 (1 week) | Make it production-ready — Slack E2E, ComfyUI/Whisper MCP, watchdog, `portal doctor` | Full multi-interface smoke test |

Recommended fix order for Phase 1: CRIT-4 → CRIT-3 → CRIT-2 + CRIT-1 →
ARCH-1 → ARCH-2 → QUAL-6 → QUAL-5 (bootstrap smoke test).

---

## [1.0.0] - 2026-02-10

### Added — Initial Portal release (ported from PocketPortal 4.7.4)

Portal is a complete redesign of PocketPortal as a **web-primary, multi-interface,
hardware-agnostic** local AI platform. This release establishes the full directory
skeleton, package layout, and component structure.

#### Core

- `AgentCore` — central AI processing engine with `process_message()` and
  `health_check()` methods, routing, context management, tool dispatch
- `DependencyContainer` — factory and dependency-injection container for all
  AgentCore dependencies (`ModelRegistry`, `IntelligentRouter`, `ExecutionEngine`,
  `ContextManager`, `EventBus`, `PromptManager`, `ToolRegistry`)
- `IntelligentRouter` — hardware-aware model routing with AUTO, QUALITY, SPEED,
  and BALANCED strategies; supports Ollama, LMStudio, and MLX backends
- `ExecutionEngine` — async LLM invocation with circuit-breaker pattern and
  per-backend failure tracking
- `Runtime` / `lifecycle.py` — bootstrap, OS signal handling, graceful shutdown
  with priority-ordered callbacks and task draining

#### Interfaces

- `WebInterface` — FastAPI + WebSocket server; OpenAI-compatible `/v1/chat/completions`
  endpoint; static file serving; session management; SSE streaming scaffold
- `TelegramInterface` — python-telegram-bot v20 integration with per-user
  authorisation and `ToolConfirmationMiddleware` support
- `SlackInterface` — Slack Events API handler with HMAC signature verification,
  slash command routing, and block-kit message formatting

#### MCP layer

- `MCPRegistry` — discovers, registers, and health-checks MCP servers defined
  in config; supports `stdio` and `openapi` transports
- MCP server definitions for Filesystem, Time, ComfyUI image generation, and
  Whisper transcription (`mcp/` directory)
- `mcpo` proxy integration for exposing MCP servers over HTTP

#### Config & settings

- `settings_schema.py` — Pydantic v2 nested config schema with
  `WebInterfaceConfig`, `TelegramInterfaceConfig`, `SlackInterfaceConfig`,
  `LLMConfig`, `ObservabilityConfig`, and hardware-profile support
- Hardware-specific env files for M4 Mac (`hardware/m4-mac/`) and
  RTX 5090 Linux (`hardware/linux-rtx5090/`)
- `.env.example` with full variable documentation

#### Observability & security

- `WatchdogMonitor` — component health monitoring with auto-restart and
  exponential backoff
- `CostTracker` middleware — per-user, per-model token cost estimation
- `SecurityModule` — rate limiting, prompt injection detection, PII scrubbing,
  output sanitisation
- Structured JSON logging via `observability/logger.py`

#### CLI & deployment

- `portal` CLI (`cli.py`) with `up`, `down`, `doctor`, `status`, `config` commands
- `Dockerfile` — multi-stage build targeting Python 3.11-slim
- `deploy/` — docker-compose stacks for M4 Mac and RTX 5090 configurations

#### Tests

- `tests/unit/` — routing logic, security module
- `tests/integration/` — WebInterface routes, MCP health endpoint

---

## Version Numbering

- **Major** — breaking API or config changes
- **Minor** — new features, backward-compatible
- **Patch** — bug fixes, documentation, backward-compatible

## Links

- [Repository](https://github.com/ckindle-42/portal)
- [Issues](https://github.com/ckindle-42/portal/issues)
