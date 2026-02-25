# Changelog

All notable changes to Portal will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Release model

Changes are accumulated on the development branch and published together as a
named release.  Each section below represents one **tagged release** (e.g.
`v1.0.2`), not an individual commit or pull request.  The authoritative version
number lives in `pyproject.toml`; `src/portal/__init__.py` must stay in sync.

To cut a release:

1. Update `version` in `pyproject.toml` and `__version__` in
   `src/portal/__init__.py`.
2. Add a new `## [x.y.z] - YYYY-MM-DD` section here summarising what the
   release delivers.
3. Commit, tag (`git tag vx.y.z`), and push both the commit and the tag
   (`git push origin vx.y.z`).  The GitHub Actions release workflow picks up the
   tag and creates the GitHub Release automatically.

---

## [1.0.2] - 2026-02-25

### Phase 1 — Boot-path quality pass

All critical runtime breaks, architectural seams, and quality gaps identified
during the initial post-port review have been resolved.  The application now
boots, passes its unit-test smoke suite, and is ready for Phase 2 work.

#### Runtime fixes

- **`factories.py`** — `DependencyContainer.create_agent_core()` now calls
  `AgentCore(**self.get_all())` instead of a hand-rolled kwarg set that was
  missing five required dependencies and included one invalid one.
- **`agent_core.py`** — added `stream_response(incoming)` async generator so
  that `WebInterface` and `SlackInterface` calls no longer raise
  `AttributeError`; wraps `process_message()` and yields a single token until
  true per-token streaming is wired in Phase 2.  `process_message()` now
  coerces plain string `interface` arguments to `InterfaceType` so callers
  passing `interface="telegram"` don't trigger `AttributeError` on `.value`.
  `AgentCore.health_check()` added; `mcp_registry` stored as an instance
  attribute with a `_dispatch_mcp_tools()` stub ready for Phase 2.
- **`core/types.py`** — unified the two incompatible `ProcessingResult`
  definitions into one canonical dataclass; all modules import from
  `portal.core.types`.
- **`config/settings.py`** — resolved dual-schema conflict: `env_prefix`
  corrected to `PORTAL_`, `SlackConfig` added, `TelegramConfig.allowed_user_ids`
  renamed to `authorized_users`, `SecurityConfig.rate_limit_requests` added,
  `Settings.to_agent_config()` added, `LoggingConfig.verbose` added,
  `validate_required_config()` updated for renamed fields and Slack coverage.
- **`slack/interface.py`** — `hmac.new(key, msg, hashlib.sha256)` confirmed
  correct for Python 3.11; unit tests added.
- **`web/server.py`** — non-streaming path fixed to pass correct kwargs to
  `process_message()`; `_format_completion()` corrected from `result.text` to
  `result.response`; `/health` endpoint now calls `agent_core.health_check()`
  and reflects real state instead of hard-coding `"ok"`.
- **`factories.py`** — `get_all()` now includes `mcp_registry` so it reaches
  `AgentCore` on every call.
- **`telegram/interface.py`** — imports and passes `InterfaceType.TELEGRAM`
  (enum) instead of the plain string `"telegram"`.

#### Tests added

| File | Covers |
|------|--------|
| `tests/unit/test_bootstrap.py` | DI wiring, `ProcessingResult` fields, factory function |
| `tests/unit/test_slack_hmac.py` | `hmac.new()` correctness, Slack signature verify/reject |

#### Docs

- `docs/ARCHITECTURE.md` — replaced five-line placeholder with a full
  architecture document covering component roles, data flow, startup sequence,
  directory structure, and Phase 2 limitations.

---

## [1.0.0] - 2026-02-10

### Initial release — ported from PocketPortal 4.7.4

Portal is a complete redesign of PocketPortal as a **web-primary,
multi-interface, hardware-agnostic** local AI platform.

#### Core

- `AgentCore` — central processing engine with `process_message()` and
  `health_check()`, routing, context management, and tool dispatch
- `DependencyContainer` — factory and DI container for `ModelRegistry`,
  `IntelligentRouter`, `ExecutionEngine`, `ContextManager`, `EventBus`,
  `PromptManager`, and `ToolRegistry`
- `IntelligentRouter` — hardware-aware model routing (AUTO / QUALITY / SPEED /
  BALANCED) across Ollama, LMStudio, and MLX backends
- `ExecutionEngine` — async LLM invocation with circuit-breaker pattern
- `Runtime` / `lifecycle.py` — bootstrap, OS signal handling, graceful shutdown

#### Interfaces

- `WebInterface` — FastAPI + WebSocket server; OpenAI-compatible
  `/v1/chat/completions`; static file serving; session management; SSE scaffold
- `TelegramInterface` — python-telegram-bot v20 with per-user authorisation and
  `ToolConfirmationMiddleware`
- `SlackInterface` — Slack Events API with HMAC verification, slash commands,
  and Block Kit formatting

#### MCP

- `MCPRegistry` — discovers, registers, and health-checks MCP servers over
  `stdio` and `openapi` transports; `mcpo` proxy integration
- Bundled server definitions: Filesystem, Time, ComfyUI, Whisper

#### Config & observability

- Pydantic v2 nested config schema with hardware-profile support
- Hardware env files for M4 Mac and RTX 5090 Linux
- `WatchdogMonitor`, `CostTracker`, `SecurityModule`, structured JSON logging

#### CLI & deployment

- `portal` CLI: `up`, `down`, `doctor`, `status`, `config`
- Multi-stage `Dockerfile`; docker-compose stacks for M4 and RTX 5090

---

## Version numbering

| Segment | When to bump |
|---------|-------------|
| **Major** | Breaking API or config changes |
| **Minor** | New features, backward-compatible |
| **Patch** | Bug fixes, documentation, backward-compatible |

## Links

- [Repository](https://github.com/ckindle-42/portal)
- [Releases](https://github.com/ckindle-42/portal/releases)
- [Issues](https://github.com/ckindle-42/portal/issues)
