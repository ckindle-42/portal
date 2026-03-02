# Portal Documentation Sync Plan

**Generated:** 2026-03-02
**Focus:** Fixes and documentation syncing

---

## Issues Identified

### Issue 1: Duplicate Roadmap Files (Priority: HIGH)
- `ROADMAP.md` — standalone, shows LLM routing as "in progress" (Status: Complete)
- `PORTAL_ROADMAP.md` — comprehensive, all tasks complete
- **Action:** Deprecate `ROADMAP.md` in favor of `PORTAL_ROADMAP.md`

### Issue 2: Stale Action Prompt Artifact (Priority: MEDIUM)
- `ACTION_PROMPT_FOR_CODING_AGENT.md` — exists but all tasks are complete
- The PORTAL_AUDIT_REPORT.md already shows 10/10 health with no open tasks
- **Action:** Update to reflect "all tasks complete" state or remove if redundant

### Issue 3: Redundant Agent Prompts in Root (Priority: LOW)
- `PORTAL_CODEBASE_REVIEW_AGENT_v5.md`
- `PORTAL_DOCUMENTATION_AGENT.md`
- Both are operational prompts, not user documentation
- **Action:** Move to `docs/agents/` directory for better organization

### Issue 4: ROADMAP.md Status Outdated (Priority: HIGH)
- Section 1 ("LLM-Based Intelligent Routing") shows "Status: In Progress"
- Should show "Status: Complete (both proxy router and IntelligentRouter — as of 2026-03-02)"
- **Action:** Update status in `ROADMAP.md`

---

## Tasks

### TASK-1: Update ROADMAP.md LLM Routing Status
**File:** `ROADMAP.md`
**Change:** Update line 10 from "Status: In Progress" to "Status: Complete (both proxy router and IntelligentRouter — as of 2026-03-02)"
**Risk:** LOW — text-only change

### TASK-2: Consolidate or Deprecate ROADMAP.md
**Files:** `ROADMAP.md`, `PORTAL_ROADMAP.md`
**Change:** Either (A) add deprecation notice to ROADMAP.md pointing to PORTAL_ROADMAP.md, or (B) delete ROADMAP.md entirely
**Risk:** LOW — documentation cleanup

### TASK-3: Update ACTION_PROMPT_FOR_CODING_AGENT.md
**File:** `ACTION_PROMPT_FOR_CODING_AGENT.md`
**Change:** Update to reflect all tasks complete; add "NO ACTION REQUIRED — Portal is production-ready" section
**Risk:** LOW — documentation update

### TASK-4: Move Agent Prompts to docs/agents/
**Files:** `PORTAL_CODEBASE_REVIEW_AGENT_v5.md`, `PORTAL_DOCUMENTATION_AGENT.md`
**Change:** Create `docs/agents/` directory and move files there; update any references
**Risk:** LOW — file reorganization

### TASK-5: Verify Documentation Consistency
**Files:** `docs/ARCHITECTURE.md`, `PORTAL_HOW_IT_WORKS.md`, `PORTAL_ROADMAP.md`
**Change:** Cross-check key claims (version numbers, port numbers, feature status)
**Risk:** LOW — verification task

---

## Execution Order

1. Run `make lint` and `make test-unit` to establish baseline
2. Execute TASK-1 (quick fix)
3. Execute TASK-2 (deprecate or remove duplicate)
4. Execute TASK-3 (update action prompt)
5. Execute TASK-4 (move agent prompts)
6. Execute TASK-5 (verify consistency)
7. Run `make lint` and `make test-unit` to confirm no regressions
8. Commit all changes

---

## Notes

- All code is production-ready (10/10 health score)
- No code changes required — this is purely documentation sync
- The focus is on eliminating confusion from duplicate/outdated docs
