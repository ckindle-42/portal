# CLAUDE.md – Guidelines for Claude Code in the Portal Project

**Project**: Portal — Local-First AI Platform  
**Repository**: https://github.com/ckindle-42/portal  
**Last Updated**: February 26, 2026  

## Core Directives (All Equally Important – Follow Every Session)
As a high-priority directive, **aggressively identify and safely remove technical debt** throughout every review and change. Technical debt includes:
- Dead/unused code (imports, functions, files, routes, configs)
- Duplicated logic or unnecessary abstractions
- Overly nested or complex structures
- Stale/outdated documentation or comments
- Performance anti-patterns affecting local AI workloads
- Tight coupling between modules

Other equally important directives:
- Perform exhaustive top-to-bottom review of every file and line of code
- Flatten structures and reduce complexity wherever it improves readability/maintainability
- Keep all documentation perfectly synchronized with code
- Validate existing features and proactively plan realistic enhancements aligned with local-first, privacy-first, hardware-efficient goals
- Never break existing functionality or hardware-specific paths

## Project Overview & Non-Negotiable Values
- Local-first AI platform running entirely on user hardware (M4 Pro primary, CUDA support).
- Unified AgentCore shared across interfaces (Open WebUI/LibreChat primary).
- New interfaces must still be addable in ≤50 lines of Python.
- Tech stack: Python 3.11+, Poetry, MCP tools in `/mcp/`, hardware-specific in `/hardware/`.

## Mandatory Workflow for Every Session
1. Load and explicitly reference this CLAUDE.md.
2. Full file inventory + technical debt scan (as high-priority directive).
3. Exhaustive code & documentation review.
4. Identify dead code, flattening opportunities, bugs, and enhancement ideas.
5. Execute changes in safe batches: debt removal → flattening → fixes → doc sync → enhancements.
6. Run full test suite after each batch.
7. Update CHANGELOG.md and all documentation.
8. Commit with conventional messages highlighting debt removal where applicable.
9. Create PR with debt-reduction metrics alongside other improvements.

## Code Quality Standards
- Full type hints, pathlib, Pydantic v2, async where beneficial.
- Ruff + Black formatting.
- Function length <50 lines, nesting depth <4 where possible.
- Evidence-based debt removal only (full dependency tracing required).

## Testing & Git/PR Rules
- `poetry run pytest` (or equivalent) after every batch; target >80% coverage.
- Branch: `ai-full-modernization-YYYY-MM-DD`
- Commit prefixes: `chore(debt):`, `refactor:`, `feat:`, `docs:`, `fix:`
- PR must include technical debt reduction summary (files removed, complexity delta, etc.) plus overall health improvement.

## Review Checklist (Apply Every Time)
- [ ] Full file inventory completed
- [ ] Technical debt identified and removed (high-priority directive)
- [ ] Structures flattened and complexity reduced
- [ ] All documentation synchronized
- [ ] Features validated + enhancements planned/implemented
- [ ] Tests passing + coverage maintained or improved
- [ ] CHANGELOG.md updated

**Claude Code Instructions**:
- Read this file at the start of every session.
- Treat technical debt removal as a high-priority directive to follow alongside all other objectives.
- When in doubt, ask: “Does this change reduce technical debt while preserving functionality and supporting local-first goals?”

---
*This file is authoritative for all Claude Code sessions on the Portal repository.*
