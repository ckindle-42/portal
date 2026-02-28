# CLAUDE.md — Claude Code Guidelines for Portal

**Project**: Portal — Local-First AI Platform
**Repository**: https://github.com/ckindle-42/portal
**Version**: 1.3.6
**Last Updated**: February 28, 2026

---

## What Portal Is

Portal is a **local-first AI platform** that runs entirely on user hardware. It exposes an OpenAI-compatible `/v1/chat/completions` endpoint that web UIs (Open WebUI, LibreChat) connect to, with optional Telegram and Slack interfaces sharing the same AgentCore, routing, tools, and conversation context.

**Hardware targets**: Apple M4 (primary), NVIDIA CUDA (Linux), WSL2.
**Architecture**: Modular monolith under `src/portal/`. Interface → SecurityMiddleware → AgentCore → Router → ExecutionEngine → LLM Backend (Ollama/LMStudio/MLX).
**Core values**: Privacy-first, hardware-efficient, fully local execution. New interfaces must remain addable in ≤50 lines of Python.

---

## Tech Stack & Tooling

| Tool | Command | Notes |
|------|---------|-------|
| **Package manager** | `uv` | NOT Poetry. Lock file is `uv.lock`. |
| **Install** | `pip install -e ".[dev]"` or `make install` | Installs all extras + dev tools |
| **Linter** | `ruff check src/ tests/` or `make lint` | Ruff handles both linting and formatting |
| **Formatter** | `ruff format src/ tests/` | NOT Black — Ruff does both |
| **Type check** | `mypy src/portal` or `make typecheck` | `strict = false` currently |
| **Tests (unit)** | `pytest tests/unit/ -v --tb=short` or `make test-unit` | Default: excludes e2e and integration |
| **Tests (all)** | `pytest tests/ -v --tb=short` or `make test` | Includes integration (not e2e) |
| **Tests (coverage)** | `make test-cov` | With `--cov=src/portal` |
| **Full CI** | `make ci` | install → lint → typecheck → test-cov |
| **Python** | 3.11+ required, <3.13 | Per `pyproject.toml` |
| **Framework** | FastAPI + Pydantic v2 | Async throughout |

---

## Project Layout

```
src/portal/
├── agent/            # CentralDispatcher (interface registry)
├── config/           # Pydantic v2 settings (Settings, load_settings)
├── core/             # AgentCore, EventBus, ContextManager, types, factories
├── interfaces/       # Web (FastAPI :8081), Telegram, Slack — all active
├── memory/           # MemoryManager (Mem0 or SQLite)
├── middleware/       # HITL approval, tool confirmation
├── observability/    # Health checks, Prometheus metrics, watchdog, log rotation
├── protocols/mcp/    # MCPRegistry for MCP server connections
├── routing/          # IntelligentRouter, ExecutionEngine, ModelRegistry, proxy router
├── security/         # Auth, rate limiting, input sanitization, Docker sandbox
└── tools/            # Auto-discovered MCP-compatible tools

tests/                # Unit + integration + e2e tests
hardware/             # Platform-specific launch scripts (used by cli.py)
deploy/web-ui/        # LibreChat and OpenWebUI deployment configs
mcp/                  # MCP server configs and helper scripts
scripts/              # Utility scripts (release, bootstrap, MCP servers)
```

---

## Architectural Knowledge (Read Before Making Changes)

These facts prevent wasted effort and accidental breakage:

**Removed in the 2026-02-27 shrink (do not re-add):**
- `src/portal/persistence/` — entire module was dead (never imported). App uses `ContextManager` + `MemoryManager`.
- `src/portal/observability/tracer.py` — was never imported by production code.
- `ContextNotFoundError`, `ModelQuotaExceededError` — were never raised anywhere.
- `set_trace_id()`, `get_trace_id()` — were never called.
- `run_with_lifecycle()` — was never called.
- `execute_parallel()` — had no production callers.
- `JobQueueHealthCheck`, `WorkerPoolHealthCheck` — were speculative (no job queue exists).

**Actively used (do NOT delete or "consolidate"):**
- `hardware/` — platform-specific launchers referenced by `cli.py` and `launch.sh`.
- `deploy/web-ui/` — distinct configs for LibreChat and OpenWebUI variants.
- `interfaces/telegram/` and `interfaces/slack/` — optional but actively maintained interfaces.
- `conftest.py` (root) — shared pytest fixtures, not a duplicate of `tests/conftest.py`.
- `mcp/` — MCP server configurations used by the platform.
- This file (`CLAUDE.md`) — authoritative config for Claude Code sessions.

---

## How to Work in This Codebase

### Task-Focused Sessions (Default)

For normal tasks (bug fixes, feature work, refactoring):

1. Understand the task. Read relevant source files.
2. Make changes in focused batches.
3. Run `make lint` and `make test-unit` after each batch.
4. Update any documentation affected by your changes.
5. Commit with conventional messages: `fix:`, `feat:`, `refactor:`, `docs:`, `chore:`, `test:`

### Audit / Shrink Sessions (When Explicitly Requested)

Only when the user asks for a full audit or debt removal session:

1. Full file inventory + dependency tracing.
2. Identify dead code with **evidence** (grep, import analysis — never assume).
3. Execute removals in safe batches: dead code → consolidation → optimization → doc sync.
4. Run full test suite after each batch.
5. Update CHANGELOG.md with metrics (LOC removed, tests removed, etc.).
6. Branch: `ai-shrink-YYYY-MM-DD`. Conventional commits with scope.

### What NOT to Do

- **Do not proactively add features or enhancements** unless explicitly asked. Speculative code becomes dead code.
- **Do not delete files without import tracing.** Previous AI sessions incorrectly flagged active modules as dead.
- **Do not chase coverage numbers.** Tests that verify internal constants or module exports are worse than no tests. Every test must protect a critical behavioral path.
- **Do not do a full codebase audit** on routine tasks. It wastes context window and produces noise.

---

## Code Quality Standards

- Full type hints, `pathlib`, Pydantic v2, async where beneficial.
- Ruff for linting and formatting (line-length 100, target Python 3.11).
- Functions ≤40 lines, nesting ≤3 levels where practical.
- Evidence-based debt removal only (full dependency tracing required before deletion).
- Prefer flat structures over deep abstractions.
- No `# noqa` without a specific code (e.g., `# noqa: F401`, not bare `# noqa`).

## Testing Standards

- Run `make test-unit` (fast) or `make test` (full) after changes.
- Target ≥85% **high-value** coverage on critical paths. Quality over quantity.
- Every test must earn its place by testing observable behavior, not implementation wiring.
- Delete tests that: have more mock setup than assertions, test dead code, verify constants/exports, or duplicate another test's coverage.
- Use `@pytest.mark.parametrize` to consolidate repetitive test cases.

## Git Standards

- Branch names: `ai-<purpose>-YYYY-MM-DD` (e.g., `ai-shrink-2026-02-27`)
- Commit prefixes: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `test:`, `perf:`
- Include scope when useful: `fix(router): source health version from __version__`

---

## Planned Features (Do Not Implement Without Explicit Request)

See [ROADMAP.md](ROADMAP.md) for scoped designs of planned features:
- **LLM-Based Intelligent Routing** — replace regex routing with small-model classifier
- **MLX Backend** — Apple Silicon native inference via mlx_lm.server

These are designed but not yet implemented. Do not start either project during routine
task sessions — they require dedicated feature branches.

---

*This file is authoritative for all Claude Code sessions on the Portal repository.*
