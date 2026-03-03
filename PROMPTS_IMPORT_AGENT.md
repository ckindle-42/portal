# PROMPTS_IMPORT_AGENT.md
## Portal Persona Library — prompts.chat Import & Hardening Agent

---

### Role

You are a Python developer and prompt engineer working on the Portal project.
Your job is to fetch the prompts.chat community prompt library, filter it for
high-value personas relevant to Portal's use cases, harden each raw prompt into
a Portal-compatible persona YAML, and wire them into Portal's PromptManager and
workspace routing system.

You operate in **execution mode**. You write files, not plans.

**Target Repository:** https://github.com/ckindle-42/portal (already cloned locally)

---

### What You Are Building

Portal's `PromptManager` builds system prompts from config. Portal's
`router_rules.json` maps virtual workspace names (e.g. `red-team`, `splunk-analyst`)
to real Ollama models. Currently:

- `config/personas/` does not exist — you are creating it
- `router_rules.json` has a `workspaces` block — you are extending it
- `PromptManager` loads from config — you are giving it persona content to load

The end state is:

```
portal/
├── config/
│   └── personas/                       ← NEW directory
│       ├── cybersecurity-analyst.yaml
│       ├── penetration-tester.yaml
│       ├── linux-terminal.yaml
│       ├── splunk-analyst.yaml
│       ├── network-engineer.yaml
│       ├── code-reviewer.yaml
│       ├── python-developer.yaml
│       ├── sql-expert.yaml
│       ├── soc-analyst.yaml
│       ├── it-architect.yaml
│       ├── machine-learning-engineer.yaml
│       ├── data-scientist.yaml
│       ├── devops-engineer.yaml
│       ├── technical-writer.yaml
│       └── ... (all filtered personas)
├── src/portal/
│   ├── core/
│   │   └── prompt_manager.py           ← EXTEND to load personas/
│   └── routing/
│       └── router_rules.json           ← EXTEND workspaces block
└── tests/
    └── unit/
        └── test_persona_library.py     ← NEW test file
```

---

### Ground Rules

- **Source:** `https://raw.githubusercontent.com/f/prompts.chat/main/prompts.csv`
  as primary. Fall back to `PROMPTS.md` if CSV fetch fails.
- **License:** CC0 1.0 Universal — no attribution required, unrestricted use.
- **Filter ruthlessly.** Only prompts that serve a technical, analytical,
  security, or professional workflow go in. Entertainment, roleplay, and
  novelty prompts are excluded.
- **Harden every prompt.** Raw prompts.chat prompts are ChatGPT-era and generic.
  Each one gets hardened for Portal before writing to disk (see Phase 2).
- **Do not break existing Portal behavior.** Existing `router_rules.json` workspace
  entries and `PromptManager` behavior are preserved.
- **One file per persona.** No monolithic YAML dumps.
- **Tests must pass.** Run the full test suite before declaring done.

---

## Phase-by-Phase Process

---

### Phase 0: Confirm Repository State

Before fetching anything:

1. Confirm `src/portal/core/prompt_manager.py` exists and read it fully — understand
   how system prompts are currently built and what config keys it reads.
2. Confirm `src/portal/routing/router_rules.json` exists and read the full
   `workspaces` block — understand the current schema.
3. Confirm `config/` directory exists at repo root. If not, create it.
4. Confirm `config/personas/` does not yet exist (expected). Create it.
5. Read `src/portal/config/settings.py` — confirm whether a `personas_dir` or
   equivalent config key exists. If not, note that you will add one.

Output a brief orientation summary before proceeding to Phase 1.

---

### Phase 2: Fetch and Filter the Prompt Library

**Step 1 — Fetch**

Download the prompt library:

```python
import httpx

# Primary: structured CSV
url_csv = "https://raw.githubusercontent.com/f/prompts.chat/main/prompts.csv"

# Fallback: Markdown
url_md = "https://raw.githubusercontent.com/f/prompts.chat/main/PROMPTS.md"
```

Parse the CSV. Expected columns: `act` (persona name), `prompt` (system prompt text).
If CSV is malformed or unavailable, parse the Markdown — each `## Heading` is the
persona name and the fenced code block beneath it is the prompt.

**Step 2 — Filter**

Apply the inclusion filter. A prompt passes if it belongs to one or more of these
functional categories:

| Category | Keep | Notes |
|---|---|---|
| Security & OT | YES | Cybersecurity specialist, pen tester, SOC analyst, network engineer, IDS/IPS expert |
| Linux / Systems | YES | Linux terminal, sysadmin, shell expert |
| Development | YES | Python, SQL, JavaScript, code reviewer, git expert, DevOps, Docker |
| Data & Analytics | YES | Data scientist, ML engineer, statistician, Excel/data analyst |
| IT Architecture | YES | IT architect, cloud architect, solution architect |
| Compliance / Audit | YES | IT auditor, compliance officer, risk analyst |
| Technical Writing | YES | Technical writer, documentation specialist |
| General professional | MAYBE | Recruiter, career counselor, logistician — include only if broadly useful |
| Creative / Entertainment | NO | Storyteller, rapper, comedian, poet, novelist |
| Medical / Health | NO | Doctor, dentist, mental health adviser — not Portal's domain |
| Novelty / Simulation | NO | Magic 8-ball, text adventure, terminal simulator for novelty |
| Relationship / Social | NO | Relationship coach, travel guide |

Produce a **Filter Log** table before proceeding:

| Persona Name | Category | Decision | Reason |
|---|---|---|---|

Minimum expected pass count: 25–40 prompts. If you pass fewer than 25, your
filter is too aggressive — re-examine.

---

### Phase 3: Harden Each Prompt into a Portal Persona YAML

For every prompt that passed the filter, produce a YAML file at
`config/personas/{slug}.yaml`.

**Slug generation rules:**
- Lowercase the persona name
- Replace spaces and slashes with hyphens
- Remove special characters
- Examples: "Cyber Security Specialist" → `cybersecurity-specialist.yaml`,
  "Linux Terminal" → `linux-terminal.yaml`

**YAML schema (required fields):**

```yaml
# config/personas/cybersecurity-specialist.yaml
name: Cyber Security Specialist
slug: cybersecurity-specialist
category: security                  # security | development | data | systems | architecture | compliance | writing | general
source: prompts.chat                # attribution (even though CC0 — good practice)
workspace_model: null               # null = use portal default; set to model name to override

# The hardened system prompt — Portal-native version
system_prompt: |
  You are a senior cybersecurity specialist with expertise in threat analysis,
  security architecture, and incident response. When analyzing security problems,
  you structure your responses around: threat actor, attack vector, blast radius,
  and recommended controls. You apply defense-in-depth principles and cite relevant
  frameworks (NIST CSF, MITRE ATT&CK, CIS Controls) when appropriate. You ask
  clarifying questions when scope or environment details are ambiguous before
  recommending solutions. You do not speculate beyond available evidence.

# Original prompt preserved for reference and diff tracking
original_prompt: |
  I want you to act as a cyber security specialist. I will provide some specific
  information about how data is stored and shared, and it will be your job to
  come up with strategies for protecting this data from malicious actors...

# Workspace routing (populates router_rules.json workspaces block)
workspace:
  enabled: true
  description: "Cybersecurity analysis, threat modeling, and security strategy"
  suggested_model: null             # null defers to portal default; set e.g. "deepseek-r1:32b"

# Tags for future knowledge base search
tags:
  - cybersecurity
  - threat-analysis
  - security-architecture
  - incident-response
```

**Hardening rules — apply to every prompt:**

1. **Strip the opener.** Remove all "I want you to act as a..." preamble. Portal
   personas speak in first person about what they do, not second-person instructions
   about what to pretend to be.

2. **Add domain grounding.** Inject one sentence establishing concrete domain
   expertise and the frameworks or methodologies the persona applies.

3. **Add structured response guidance.** Add one sentence describing *how* the
   persona structures its answers (e.g., bullet list of frameworks, step-by-step
   breakdown, structured extraction format).

4. **Add an ambiguity clause.** Every persona ends with: "You ask clarifying
   questions when the request is ambiguous or lacks critical context before
   proceeding." This reduces hallucination on underspecified queries.

5. **Remove example requests.** Strip "My first request is..." sentences — Portal
   personas are used as standing system prompts, not one-shot examples.

6. **Preserve domain specificity.** Do not genericize a narrow persona. A
   "Penetration Tester" should remain specifically about offensive security
   methodology, not become a generic "security expert."

**Security-domain personas get additional hardening:**

For any persona in the `security` or `compliance` category, add:

```yaml
safety_note: |
  This persona discusses security concepts, attack methodologies, and
  defensive controls for educational and professional purposes. It does not
  provide working exploit code, active malware, or step-by-step attack
  instructions targeting specific live systems.
```

---

### Phase 4: Extend PromptManager to Load Personas

Read `src/portal/core/prompt_manager.py` fully before making any changes.

**Goal:** `PromptManager` should be able to return a system prompt for a named
persona. When a request arrives with a workspace model like `cybersecurity-specialist`,
the system prompt comes from the corresponding persona YAML.

**Implementation approach:**

Add a `PersonaLibrary` class (or integrate into existing `PromptManager`) that:

1. Scans `config/personas/` at startup for all `*.yaml` files
2. Loads and validates each one against the schema (required fields: `name`,
   `slug`, `system_prompt`)
3. Exposes `get_persona(slug: str) -> dict | None`
4. Exposes `list_personas() -> list[dict]` (returns name, slug, category, description)
5. Integrates with `PromptManager.build_system_prompt()` — if a persona slug is
   provided in `user_context`, the persona's `system_prompt` is used as the base
   instead of the default

**Config key to add in `settings.py`:**

```python
personas_dir: Path = Field(
    default=Path("config/personas"),
    description="Directory containing persona YAML files"
)
```

**Do not rewrite PromptManager.** Extend it minimally. The existing system prompt
construction logic for non-persona requests must be unchanged.

---

### Phase 5: Extend router_rules.json Workspace Block

For every persona where `workspace.enabled: true`, add an entry to the
`workspaces` block in `src/portal/routing/router_rules.json`.

**Schema (matches existing workspace format):**

```json
"cybersecurity-specialist": {
  "model": "deepseek-r1:32b",
  "description": "Cybersecurity analysis, threat modeling, and security strategy",
  "persona": "cybersecurity-specialist"
}
```

**Model assignment rules:**

| Category | Default Model Assignment |
|---|---|
| security, compliance | `deepseek-r1:32b` |
| development, systems | `qwen2.5-coder:32b` |
| data, architecture | `deepseek-r1:32b` |
| writing, general | portal default (no override) |

Use the `default_model` from the existing `router_rules.json` as the fallback
for any category not listed above.

Add a comment block above the new entries in the JSON:

```json
"_comment_personas": "Auto-generated workspace entries from prompts.chat import. Edit persona YAMLs to change behavior.",
```

---

### Phase 6: Add a /v1/personas Endpoint (Optional but Recommended)

If `PromptManager` or `PersonaLibrary` exposes `list_personas()`, add a read-only
endpoint to `WebInterface`:

```
GET /v1/personas
```

Response:
```json
{
  "object": "list",
  "data": [
    {
      "slug": "cybersecurity-specialist",
      "name": "Cyber Security Specialist",
      "category": "security",
      "description": "Cybersecurity analysis, threat modeling...",
      "workspace_model": "deepseek-r1:32b"
    }
  ]
}
```

This endpoint:
- Requires auth (same `_auth_context` dependency as `/v1/models`)
- Returns only `slug`, `name`, `category`, `description`, `workspace_model` — not the full system prompt
- Is used by Open WebUI / LibreChat model pickers to discover available personas

---

### Phase 7: Write Tests

Create `tests/unit/test_persona_library.py`.

Required tests:

```python
class TestPersonaLibrary:

    def test_all_persona_yamls_are_valid(self):
        """Every YAML in config/personas/ loads without error and has required fields."""

    def test_slugs_are_unique(self):
        """No two persona files have the same slug."""

    def test_hardened_prompts_strip_preamble(self):
        """No system_prompt starts with 'I want you to act as'."""

    def test_security_personas_have_safety_note(self):
        """All category=security or category=compliance personas have safety_note field."""

    def test_persona_library_loads_at_startup(self, tmp_path):
        """PersonaLibrary initializes correctly with a temp personas dir."""

    def test_get_persona_returns_correct_slug(self, persona_library):
        """get_persona('cybersecurity-specialist') returns the correct persona dict."""

    def test_get_persona_returns_none_for_unknown(self, persona_library):
        """get_persona('does-not-exist') returns None without raising."""

    def test_list_personas_returns_all_loaded(self, persona_library):
        """list_personas() count matches number of YAML files in dir."""

    def test_workspace_entries_match_personas(self):
        """Every enabled persona slug appears in router_rules.json workspaces."""

    def test_router_rules_json_is_valid_after_extension(self):
        """router_rules.json parses as valid JSON after workspace entries added."""
```

---

### Phase 8: Run and Verify

```bash
# Lint — must be clean
python -m ruff check src/

# Full test suite — must pass
python -m pytest tests/ -q

# Persona-specific tests
python -m pytest tests/unit/test_persona_library.py -v

# Smoke check — list loaded personas
python -c "
from portal.core.prompt_manager import PersonaLibrary
lib = PersonaLibrary()
for p in lib.list_personas():
    print(f\"{p['slug']:40} {p['category']:15} {p['name']}\")
print(f'Total: {len(lib.list_personas())} personas loaded')
"
```

Expected output: 25–50 personas listed, zero test failures, zero lint errors.

---

## Output: Three Deliverables

### Deliverable 1: Filter Log
A table showing every prompt from prompts.chat and the keep/exclude decision with reason.

### Deliverable 2: File manifest
List of every file created or modified, with one-line description of what changed.

### Deliverable 3: Smoke test output
The output of the smoke check command showing all loaded personas.

---

## Commit Convention

```
feat(personas): import prompts.chat library as hardened Portal personas

- Add config/personas/ with N persona YAML files (CC0)
- Extend PromptManager with PersonaLibrary loader
- Add workspace routing entries for all enabled personas
- Add /v1/personas discovery endpoint
- Add test_persona_library.py with 10 tests

Source: https://github.com/f/prompts.chat (CC0 1.0 Universal)
```

---

## Priority Persona Reference

The following are the highest-priority personas for Portal's use cases. If the
automated filter misses any of these, add them manually:

| Persona Name (from prompts.chat) | Portal Slug | Category | Priority |
|---|---|---|---|
| Cyber Security Specialist | `cybersecurity-specialist` | security | P1 |
| Linux Terminal | `linux-terminal` | systems | P1 |
| Python Interpreter | `python-interpreter` | development | P1 |
| SQL Terminal | `sql-terminal` | development | P1 |
| Network Engineer (Nmap) | `network-engineer` | security | P1 |
| IT Expert | `it-expert` | systems | P1 |
| DevOps Engineer | `devops-engineer` | development | P1 |
| Code Reviewer | `code-reviewer` | development | P1 |
| Machine Learning Engineer | `ml-engineer` | data | P2 |
| Data Analyst (CSV) | `data-analyst` | data | P2 |
| IT Architect | `it-architect` | architecture | P2 |
| Statistician | `statistician` | data | P2 |
| Cyber Security Analyst | `soc-analyst` | security | P2 |
| Penetration Tester | `penetration-tester` | security | P1 |
| Technical Writer | `technical-writer` | writing | P2 |
| Software Quality Assurance | `qa-engineer` | development | P2 |
| Fullstack Developer | `fullstack-developer` | development | P2 |
| Senior Frontend Developer | `frontend-developer` | development | P3 |
| Git Expert | `git-expert` | development | P2 |
| Docker Expert | `docker-expert` | systems | P2 |

---

### Begin

Start with **Phase 0 — Confirm Repository State**.

Read `prompt_manager.py` and `router_rules.json` in full before writing a single file.
Produce the Filter Log in Phase 2 before writing any YAML.
Do not skip phases.
