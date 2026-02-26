# CLAUDE.md – Guidelines for Claude Code in the Portal Project

**Project**: Portal — Local-First AI Platform  
**Repository**: https://github.com/ckindle-42/portal  
**Last Updated**: February 2026  
**Purpose**: Claude Code (web or CLI) must follow these rules on every interaction to ensure consistent, high-quality, production-grade modernization of the codebase.

## 1. Project Overview & Core Values
- **Local-first AI platform** that runs **entirely on the user’s hardware**.
- Zero cloud dependencies, zero subscriptions, full data sovereignty.
- Unified backend (`AgentCore`) shared across multiple interfaces: Open WebUI / LibreChat (primary), Telegram, Slack, and future interfaces.
- Hardware-optimized: Apple M4 Pro (primary), NVIDIA CUDA (Linux/WSL2), with hardware-specific launch scripts.
- Tech stack: **Python 3.11+**, Poetry (`pyproject.toml`), Docker, FastAPI-style routing, MCP (Model-Controller-Provider) tools in `/mcp/`, source in `src/portal/`.
- Key directories to always respect:
  - `src/portal/` → core application
  - `docs/` → especially `ARCHITECTURE.md`
  - `mcp/` → interface-agnostic tools
  - `hardware/` → platform-specific configs
  - `tests/` → full test coverage required
  - `deploy/web-ui/` → deployment artifacts

**Non-negotiable mindset for every change**:
- Privacy-first, hardware-efficient, minimal dependencies.
- New interfaces must be added with ~50 lines of Python (keep this bar).
- All changes must improve or preserve **local performance** and **zero-cloud** guarantees.

## 2. Code Quality & Modernization Principles
- **Aggressive Dead-Code Elimination**: After full dependency tracing (grep, IDE search, static analysis), remove unused imports, functions, classes, files, routes, configs. Justify every removal with evidence.
- **Flatten & Simplify**: Reduce nesting depth, collapse small modules, eliminate unnecessary abstraction layers. Prefer flat structures in `src/portal/` unless complexity is truly warranted.
- **Complexity Reduction**: Target cyclomatic complexity < 10 per function, function length < 50 lines where possible. Consolidate repeated logic.
- **Modern Python Standards**:
  - Strict PEP 8 + ruff / black formatting
  - Full type hints (Python 3.11+ syntax)
  - Pydantic v2 for all models
  - Async where performance-critical (local AI inference)
  - Use `pathlib` exclusively (no `os.path`)
- **Security & Reliability**:
  - Never introduce external network calls unless explicitly for optional features.
  - All file I/O must be sandboxed to user-configured directories.
  - Proper error handling with structured logging.

## 3. Documentation Synchronization (Mandatory)
- Every code change **must** update:
  - `docs/ARCHITECTURE.md`
  - `README.md`
  - `CHANGELOG.md` (use conventional commits + date-stamped entry)
  - All relevant inline comments and docstrings
  - `.env.example`
- Keep documentation perfectly in sync — never let drift occur.

## 4. Testing Requirements
- Run full test suite (`poetry run pytest` or equivalent) after every batch of changes.
- Maintain or increase coverage (>80% target).
- Add tests for any new feature, bug fix, or refactored path.
- Test hardware-specific paths where possible (mock when needed).

## 5. Git & PR Workflow
- Always work on a branch named `ai-full-modernization-YYYY-MM-DD`
- Use conventional commit messages:
  - `refactor:` / `chore:` / `feat:` / `docs:` / `fix:`
- After every major phase: commit, push, then create PR with full summary from the review.
- PR title format: `AI Modernization & Refactor Pass [YYYY-MM-DD]`
- Include change table, before/after complexity metrics, and health score improvement.

## 6. Review & Modernization Checklist (Apply to Every Session)
- [ ] Full directory tree reviewed
- [ ] Every file in `src/portal/`, `mcp/`, `hardware/`, `docs/`, `tests/` examined line-by-line
- [ ] Dead/unused code removal plan created and executed
- [ ] Structural flattening proposals implemented
- [ ] All documentation updated and cross-checked
- [ ] Feature enhancements validated against local-first goals
- [ ] Tests passing + new tests added
- [ ] CHANGELOG.md updated
- [ ] Overall health score improved

## 7. Edge Cases & Special Instructions
- Hardware-specific code (`hardware/m4-mac/`, CUDA paths) must remain functional or be generalized without breaking existing setups.
- MCP tools are sacred — do not refactor their public interface without updating all callers.
- Adding a new interface must still require ≤50 lines of Python.
- Performance-critical paths (inference routing, context management) must never regress in speed or memory usage.
- If removing a file, ensure `git rm` is used and `pyproject.toml` / imports are cleaned.

**Claude Code Instructions**:
- Read this file at the start of every session.
- Reference it explicitly in your reasoning.
- When in doubt, default to: **simpler, flatter, fewer files, better documented, more local-efficient**.

You are now operating under these permanent project rules.  
Begin every modernization task by confirming you have loaded CLAUDE.md.

---
*This file is authoritative. Any conflict with README or ARCHITECTURE.md is resolved in favor of this CLAUDE.md until updated.*