# CLAUDE.md – Guidelines for Claude Code in the Portal Project

**Project**: Portal — Local-First AI Platform  
**Repository**: https://github.com/ckindle-42/portal  
**Last Updated**: February 26, 2026  

### Core Directives (All Equally Important)
- Aggressively identify and safely remove technical debt (high-priority).  
- Perform exhaustive top-to-bottom review of every file and line.  
- Flatten structures, reduce nesting/complexity.  
- Keep **all documentation 100 % synchronized**.  
- Validate features and add **realistic, high-impact enhancements** only.  
- Drive to **10/10 code health** (see definition below).  

### Updated 10/10 Code Health Definition (Feb 26, 2026)
- Zero technical debt  
- **≥85 % high-value test coverage** focused on critical paths, hardware paths, edge cases, and concurrency (lean test suite preferred; avoid bloat)  
- Flattened architecture (nesting ≤3, functions ≤40 lines)  
- All features validated + meaningful enhancements  
- Performance & security optimized for local hardware  
- New interfaces still ≤50 lines of Python  
- Perfect documentation sync + clean git history  

*(Note: Coverage is important but no longer the dominant metric. Quality and maintainability take precedence over line coverage.)*

### Mandatory Workflow, Code Quality Standards, Testing & Git Rules, Review Checklist
*(unchanged from previous version — only the 10/10 definition and testing language updated above)*

**Claude Code Instructions**  
Read this file first. Follow the 9-step workflow with the new balanced 10/10 definition.
