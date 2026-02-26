# CLAUDE.md – Guidelines for Claude Code in the Portal Project

**Project**: Portal — Local-First AI Platform  
**Repository**: https://github.com/ckindle-42/portal  
**Last Updated**: February 26, 2026  

### Core Directives (All Equally Important – Follow Every Session)
As a **high-priority directive**, **aggressively identify and safely remove technical debt** throughout every review and change. Technical debt includes:
- Dead/unused code (imports, functions, files, routes, configs)
- Duplicated logic or unnecessary abstractions
- Overly nested or complex structures
- Stale/outdated documentation or comments
- Performance anti-patterns affecting local AI workloads
- Tight coupling between modules

All other directives are equally non-negotiable:
- Perform an **exhaustive top-to-bottom review** of every single file and every line of code.
- Flatten structures, reduce nesting/complexity, and consolidate modules wherever it improves readability and maintainability.
- Keep **all documentation 100 % synchronized** with the code at all times.
- Validate **every existing feature** and proactively plan/implement realistic enhancements that align with local-first, privacy-first, and hardware-efficient goals.
- **Explicit goal on every run**: Drive overall code health score to **10/10** (see definition below).
- Never break existing functionality or hardware-specific paths (M4 Pro primary, CUDA support).

When in doubt, ask: “Does this change reduce technical debt while preserving functionality and advancing local-first goals?”

### 10/10 Code Health Definition for Portal
A file/repo reaches 10/10 when it has:
- **Zero technical debt** (no dead code, duplication, over-nesting, or stale docs)
- ≥95 % test coverage with full edge-case and hardware-specific tests
- Flattened, readable architecture (nesting ≤3, functions ≤40 lines where possible)
- All features fully validated + meaningful new high-impact enhancements added
- Performance & security optimized for local M4 Pro / CUDA workloads
- New interfaces still addable in ≤50 lines of Python
- Perfect documentation sync + clean conventional git history

### Project Overview & Non-Negotiable Values
Portal is a **local-first AI platform** that runs entirely on user hardware (M4 Pro primary, full CUDA support).  
- Unified **AgentCore** is shared across all interfaces (Open WebUI/LibreChat are primary).  
- New interfaces must remain addable in ≤50 lines of Python.  
- Tech stack: Python 3.11+, Poetry, MCP tools in `/mcp/`, hardware-specific code in `/hardware/`, main source in `src/portal/`.  
- Always prefer flat/simple structures.  
- Privacy-first, hardware-efficient, and fully local execution are immutable.

### Mandatory Workflow for Every Session
1. Load and explicitly reference this CLAUDE.md at the start of every session.
2. Full file inventory + technical debt scan (high-priority directive).
3. Exhaustive top-to-bottom code & documentation review.
4. Identify dead code, flattening opportunities, bugs, and enhancement ideas.
5. Execute changes in safe batches:  
   **debt removal → flattening → fixes → doc sync → enhancements**.
6. Run full test suite after each batch.
7. Update CHANGELOG.md and all documentation.
8. Commit with conventional messages highlighting debt removal where applicable.
9. Create PR with debt-reduction metrics alongside other improvements.

### Code Quality Standards
- Full type hints, `pathlib`, Pydantic v2, async where beneficial.
- Ruff + Black formatting enforced.
- Function length <50 lines, nesting depth <4 (target ≤3) wherever possible.
- Evidence-based debt removal only (full dependency tracing required).
- Prefer flat structures over deep abstractions.

### Testing & Git/PR Rules
- Run `poetry run pytest` (or equivalent) after every batch; target >80 % coverage initially, drive to ≥95 %.
- Branch name format: `ai-full-modernization-YYYY-MM-DD`
- Commit prefixes: `chore(debt):`, `refactor:`, `feat:`, `docs:`, `fix:`
- Every PR **must** include:
  - Technical debt reduction summary (files removed, complexity delta, lines saved, etc.)
  - Overall health improvement metrics
  - Updated 10/10 checklist status

### Review Checklist (Apply Every Time)
- [ ] Full file inventory completed
- [ ] Technical debt identified and safely removed (high-priority)
- [ ] Structures flattened and complexity reduced (nesting ≤3 target)
- [ ] All documentation 100 % synchronized
- [ ] Every feature validated + realistic enhancements planned/implemented
- [ ] Tests passing + coverage maintained or improved (≥95 % target)
- [ ] CHANGELOG.md updated
- [ ] Code health moved measurably closer to 10/10

**Claude Code Instructions**  
Read this file first in every session. Follow the full 9-step workflow + 10/10 checklist on every run. Treat technical debt removal as a high-priority directive to be pursued alongside all other objectives.  

*This file is authoritative for all Claude Code sessions on the Portal repository.*
