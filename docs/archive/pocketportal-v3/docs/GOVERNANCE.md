# PocketPortal Governance Rules

**Last Updated:** 2025-12-18
**Status:** Enforced

---

## Purpose

This document defines **binary governance rules** for PocketPortal development. These rules prevent documentation drift, version inconsistency, and architectural degradation.

All rules are **binary** (no exceptions) and must be enforced in code review.

---

## Rule 1: Single Source of Truth (SSOT)

### Version Numbers

**Rule:** Version numbers physically exist in **only one place**: `pyproject.toml`

**Enforcement:**
- ✅ **Allowed:** `pyproject.toml` contains `version = "4.7.3"`
- ✅ **Allowed:** Runtime code uses `importlib.metadata.version("pocketportal")`
- ❌ **Forbidden:** Hardcoded version strings in `__init__.py`, `cli.py`, `README.md`, or anywhere else
- ❌ **Forbidden:** Fallback version strings like `__version__ = "4.7.3"`

**Verification:**
```bash
# Only one hardcoded version should exist
grep -r "version.*=.*\"[0-9]" pyproject.toml | wc -l  # Should be 1
grep -r "__version__.*=.*\"[0-9]" src/ | wc -l  # Should be 0
```

**Rationale:** Prevents version drift across files. Single source guarantees consistency.

---

### Release History

**Rule:** Root `CHANGELOG.md` is the **only authoritative release history**

**Enforcement:**
- ✅ **Allowed:** `/CHANGELOG.md` (root level)
- ❌ **Forbidden:** `/docs/CHANGELOG.md` or any other changelog copies
- ❌ **Forbidden:** Version-specific changes documented in `README.md`

**Verification:**
```bash
# Only one CHANGELOG.md should exist
find . -name "CHANGELOG.md" -type f | grep -v node_modules | wc -l  # Should be 1
```

**Rationale:** Prevents conflicting release notes. README describes current capabilities, CHANGELOG describes historical changes.

---

## Rule 2: Living Roadmap

**Rule:** `ROADMAP.md` is the **primary source for future planning** and must be updated as features are completed or reprioritized

**Enforcement:**
- ✅ **Required:** Update `ROADMAP.md` when features move from planned → completed
- ✅ **Required:** Move completed items from ROADMAP to CHANGELOG upon release
- ❌ **Forbidden:** Leaving completed features in ROADMAP as "done"
- ❌ **Forbidden:** Documenting future plans in CHANGELOG or commit messages only

**Verification:**
```bash
# ROADMAP.md must exist and contain only forward-looking items
test -f ROADMAP.md && echo "✅ ROADMAP exists" || echo "❌ Missing ROADMAP"
```

**Rationale:** Prevents planning documents from becoming stale retrospectives. ROADMAP is forward-looking, CHANGELOG is historical.

---

## Rule 3: Docs = Code

**Rule:** Any PR changing **behavior or structure** must update `README.md` and/or `docs/architecture.md` **in the same PR**

**Enforcement:**
- ✅ **Required:** PRs adding new modules → update `docs/architecture.md` project structure
- ✅ **Required:** PRs changing CLI commands → update `README.md` quick start
- ✅ **Required:** PRs moving files → update architecture diagrams
- ❌ **Forbidden:** Merging code changes without updating affected documentation
- ❌ **Forbidden:** Documentation-only PRs that don't match current code state

**Examples:**
- Adding new tool → Update tool list in `docs/architecture.md`
- Moving `tools/` to `protocols/` → Update file tree in both README and architecture
- Adding new CLI command → Update quick start in `README.md`

**Verification:** Code reviewers must verify documentation changes in every non-trivial PR.

**Rationale:** Prevents documentation lag. Users should trust docs to reflect reality.

---

## Rule 4: Generic Install Documentation

**Rule:** Installation documentation must **not reference specific patch versions**

**Enforcement:**
- ✅ **Allowed:** `tar -xzf pocketportal-<version>.tar.gz`
- ✅ **Allowed:** `docker build -t pocketportal:latest .`
- ✅ **Allowed:** `# INFO - Starting PocketPortal <version>`
- ❌ **Forbidden:** `tar -xzf pocketportal-4.7.0.tar.gz`
- ❌ **Forbidden:** `docker build -t pocketportal:4.7.0 .`
- ❌ **Forbidden:** `# PocketPortal Configuration v4.7.0`

**Verification:**
```bash
# Installation docs should not contain patch versions
grep -E "4\.[0-9]+\.[0-9]+" docs/setup.md && echo "❌ Found hardcoded version" || echo "✅ Clean"
```

**Rationale:** Prevents documentation maintenance debt. Installation instructions should remain valid across releases.

---

## Rule 5: Name-Match

**Rule:** Primary files must match the name of their **primary exported class**

**Enforcement:**
- ✅ **Correct:** Class `AgentCore` → file `agent_core.py`
- ✅ **Correct:** Class `ContextManager` → file `context_manager.py`
- ✅ **Correct:** Class `TelegramInterface` → file `telegram_interface.py` or `interface.py` (within `telegram/` package)
- ❌ **Forbidden:** Class `AgentCore` → file `engine.py`
- ❌ **Forbidden:** Class `BaseTool` → file `base_tool.py` (should be `tool.py` if it's the primary export)

**Exceptions:**
- Files exporting multiple unrelated classes (e.g., `exceptions.py`)
- Package `__init__.py` files
- Utility modules without primary classes

**Rationale:** Improves discoverability. Developers can guess file names from class names without searching.

---

## Enforcement in Code Review

### Checklist for Reviewers

Before approving any PR, verify:

- [ ] **SSOT:** No new hardcoded versions introduced
- [ ] **SSOT:** If version changed, only in `pyproject.toml`
- [ ] **Living Roadmap:** Completed features removed from `ROADMAP.md`, added to `CHANGELOG.md`
- [ ] **Docs = Code:** All affected documentation updated in same PR
- [ ] **Generic Install:** No new patch version references in setup docs
- [ ] **Name-Match:** New classes follow file naming convention

### Automated Checks (Future)

Consider adding pre-commit hooks for:
- Detect multiple `CHANGELOG.md` files
- Detect hardcoded versions outside `pyproject.toml`
- Detect version references in `docs/setup.md`

---

## Repository State Compliance

### Current Status (2025-12-18)

- ✅ **SSOT Rule:** Compliant (only `pyproject.toml` has version)
- ✅ **SSOT Rule:** Compliant (only root `CHANGELOG.md` exists)
- ✅ **Living Roadmap Rule:** Compliant (`ROADMAP.md` created, forward-looking only)
- ✅ **Docs = Code Rule:** Compliant (architecture.md matches current structure)
- ✅ **Generic Install Rule:** Compliant (all `<version>` placeholders used)
- ✅ **Name-Match Rule:** Compliant (`AgentCore` in `agent_core.py`)

---

## Violations and Remediation

### If Rules Are Violated

1. **Detect:** Code review or automated check identifies violation
2. **Reject:** PR is marked as "changes requested"
3. **Fix:** Author updates PR to comply with rules
4. **Verify:** Reviewer confirms compliance
5. **Merge:** Only after all rules satisfied

### Emergency Exceptions

**None.** These rules are binary and have no exceptions. If a rule cannot be followed, the rule itself must be amended through team discussion first.

---

## Rule Amendments

### Process for Changing Rules

1. **Propose:** Open GitHub issue with rule change proposal
2. **Discuss:** Team reviews and debates necessity
3. **Vote:** Maintainers approve/reject
4. **Document:** Update this file with new/modified rule
5. **Announce:** Notify all contributors of change

### Amendment History

- **2025-12-18:** Initial governance rules established

---

## References

- **Related Documents:**
  - [Architecture Documentation](architecture.md)
  - [CHANGELOG](../CHANGELOG.md)
  - [ROADMAP](../ROADMAP.md)
  - [README](../README.md)

- **Inspiration:**
  - Python Packaging Authority (SSOT for versions)
  - Conventional Commits (structured history)
  - Carmack's .plan files (living documentation)

---

**Governance Maintained By:** PocketPortal Core Team
**Questions/Concerns:** Open GitHub issue with `governance` label
