# Portal — Action Prompt for Coding Agent

**Generated:** 2026-03-03 (run 27)
**Source audit:** PORTAL_DOCUMENTATION_AGENT_v4.md (same date)
**Current version:** 3.0.2

---

## Project Context

Portal is a local-first AI platform (Python 3.11+ / FastAPI / async).
Source: `src/portal/` (100+ Python modules).
Tests: `tests/` (999 tests collected, 27 deselected for e2e).

**Non-negotiable constraints:**
- API contract locked: no behavior changes to existing endpoints
- No new features unless explicitly requested
- No cloud dependencies, no external AI frameworks

---

## Prior Work Summary

All 6 phases of feature-complete implementation are now complete:

- **Phase 0**: Tool pipeline connected (tool schemas → Ollama, all MCPs registered)
- **Phase 1**: Wan2.2 video + SDXL images implemented
- **Phase 2**: Fish Speech TTS MCP server created
- **Phase 3**: Telegram/Slack workspace selection and file delivery
- **Phase 4**: Orchestrator detection fixed (conservative regex)
- **Phase 5**: Documentation updated
- **Phase 6**: Deployment alignment (launch.sh health checks, docker-compose)

**Current state:** 1001 tests collected, 0 mypy errors, 0 lint violations. All CI gates green.

---

## Open Tasks

**RESOLVED TASK-01 (Version Bump)**
- File: `pyproject.toml`, `CLAUDE.md`, `PORTAL_ROADMAP.md`
- Category: VERSION_BUMP
- Status: RESOLVED - Version is 3.0.2 in all files

**TASK-02 (Branch Cleanup)**
- File: git remote branches
- Category: MAINTENANCE
- Finding: Stale branch `remotes/origin/claude/execute-portal-finish-line-YGiaE` remains
- Action: Note for manual cleanup (cannot delete remote branches)
- Risk: LOW

---

## Session Bootstrap

```bash
# Verify environment
cd /Users/chris/portal
source .venv/bin/activate 2>/dev/null || python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev,test]" -q

# Verify CI gates (all should pass)
python3 -m ruff check src/ tests/           # expect 0 violations
python3 -m ruff format --check src/ tests/  # expect no changes needed
python3 -m mypy src/portal                  # expect 0 errors
python3 -m pytest tests/ -v --tb=short      # expect 999 collected, 27 deselected
```

---

## Notes

- Portal 3.0.2 is fully production-ready
- All Code Findings Register items resolved
- No known issues
- Health score: 10/10 — FULLY PRODUCTION-READY