# Portal — Open WebUI Configuration, Import & Clean Environment Agent

**Version:** 2.0 (unified)
**Date:** March 3, 2026
**Scope:** Two combined problem sets resolved in a single agent run:
1. **Import completeness** — every MCP tool, workspace, and function has a ready-to-import JSON file so users never manually type a URL or system prompt into the GUI.
2. **Clean environment on every up** — `docker compose up` seeds a fresh Open WebUI automatically, `down` leaves no stale state, and testing gets a true clean slate without nuking Ollama model downloads.

---

## Background — What Is Currently Broken

### Problem A: Incomplete Import Files

`imports/openwebui/` has 4 tool JSON files covering music, documents, code, and TTS. Six MCP servers have **no import file**: ComfyUI (8910), Video (8911), Whisper (8915), Shell (8091), Web (8092), plus `mcp-filesystem` (stdio). There are **no workspace preset files** and **no function import files** anywhere in the repo.

`setup_openwebui.py` exists but has a **silent critical bug**: it registers MCP servers by calling `POST /api/v1/settings` with a `mcp_servers` key. This endpoint does not register Tool Servers in Open WebUI. It returns HTTP 200 and does nothing. Every user who has run this script has gotten zero MCP servers registered.

### Problem B: State Persists Across Restarts

`docker compose down` stops containers but **does not remove named volumes**. The `open-webui-data` volume holds Open WebUI's entire SQLite database — all users, tool registrations, workspace configs, model settings, chat history. This means:

- **First run:** Open WebUI is completely unconfigured. User must manually register 9 tool servers, create 9 workspaces, install functions. No automation exists in the startup flow.
- **Subsequent runs:** Whatever was in the database from last session is still there — including any broken or partial configurations from previous testing.
- **Testing:** You are never testing against a clean known state unless you manually run `docker compose down -v` every time, which most users don't know to do.

`setup_openwebui.py` is **never called** from `launch.sh` or any Docker Compose hook. It exists as a standalone script with no integration into the startup flow.

**Personas** load correctly into Portal's own routing engine via `PersonaLibrary` (reads `config/personas/*.yaml` at runtime) — that part works. But personas do **not** automatically appear as configured workspaces in Open WebUI's GUI. Open WebUI only knows about them if the setup script runs against its API after it starts.

---

## Volume Persistence Map (What Survives `down`)

| Storage | Type | Survives `down` | Survives `down -v` | Contains |
|---|---|---|---|---|
| `open-webui-data` | Named volume | ✅ YES | ❌ no | Users, tool servers, workspaces, models, chat history |
| `ollama_data` | Named volume | ✅ YES | ❌ no | Ollama model weights (keep — 4GB+ downloads) |
| `qdrant_data` | Named volume | ✅ YES | ❌ no | Vector embeddings / RAG |
| `comfyui_models` | Named volume | ✅ YES | ❌ no | ComfyUI model weights (keep — huge files) |
| `./data` | Bind mount | ✅ YES | ✅ YES | Portal memory.db, auth.db, rate limit state |
| `~/.portal` | Bind mount | ✅ YES | ✅ YES | Portal config |

**The fix:** `open-webui-data` must be wiped on clean resets, but `ollama_data` and `comfyui_models` must be preserved. These need to be decoupled — a targeted `down -v open-webui-data` rather than a full `down -v`.

---

## Phase 0 — Environment Bootstrap

```bash
cd /path/to/portal
source .venv/bin/activate || (uv venv && source .venv/bin/activate && uv pip install -e ".[dev]")
python --version   # must be 3.11+
uv run ruff check src/ tests/ || true   # lint baseline, non-blocking
pytest tests/unit/ -q --tb=no 2>/dev/null | tail -3   # unit test baseline
```

**Do NOT proceed if venv is not active. Do NOT install packages globally.**

---

## Phase 1 — Audit Current State Before Touching Anything

### 1.1 — Map All MCP Services vs. Import Files

```bash
python3 -c "
import yaml, json
from pathlib import Path

# Services from compose
with open('docker-compose.yml') as f:
    dc = yaml.safe_load(f)
services = dc.get('services', {})
mcp_services = {}
for name, svc in services.items():
    if 'mcp' in name.lower():
        ports = [str(p).split(':')[0] for p in svc.get('ports', [])]
        mcp_services[name] = ports

# Existing import files
existing = list(Path('imports/openwebui/tools').glob('*.json'))
existing_names = [f.stem for f in existing]

print('=== MCP Services in docker-compose ===')
for name, ports in mcp_services.items():
    status = '✅ has import' if any(name.replace('mcp-','portal_') in e for e in existing_names) else '❌ MISSING'
    print(f'  {name}: ports={ports}  {status}')

print()
print(f'=== Existing tool import files ({len(existing)}) ===')
for f in sorted(existing):
    print(f'  {f.name}')
"
```

### 1.2 — Verify the Broken API Call in setup_openwebui.py

```bash
grep -n "api/v1/settings\|api/v1/tools\|mcp_servers\|tool_servers" scripts/setup_openwebui.py
```

**Expected finding:** Line calling `POST /api/v1/settings` with `mcp_servers` payload. This is DEFECT-1. The correct endpoint is `POST /api/v1/tools/server/`.

### 1.3 — Confirm setup_openwebui.py Is Never Called From launch.sh

```bash
grep -n "setup_openwebui" launch.sh
# Expected: no output — it is never called
```

### 1.4 — Confirm open-webui-data Survives down

```bash
grep -n "down -v\|down.*volume\|open-webui-data" launch.sh
# Expected: 'down -v' only appears in 'reset --full' and 'switch-ui'
# The normal 'down' subcommand calls 'docker compose down' without -v
```

### 1.5 — Confirm No Auto-Seed Hook Exists

```bash
grep -n "openwebui-init\|post.*up\|setup_openwebui\|seed" deploy/web-ui/openwebui/docker-compose.yml
# Expected: no output
```

### 1.6 — Baseline Status Block

Document before proceeding:

```
MCP tool import files:     ____ / 9
Workspace import files:    ____ / 9
Function import files:     ____ / 1
setup_openwebui.py bug:    CONFIRMED / NOT CONFIRMED
Auto-seed hook:            EXISTS / MISSING
launch.sh clean-ui-data:   EXISTS / MISSING
```

---

## Phase 2 — Import File Tasks

---

### TASK-IMP-01: Complete the MCP Tool Server Import Files

**Directory:** `imports/openwebui/tools/`
**Priority:** CRITICAL
**Effort:** 30 min

Create the 5 missing HTTP-accessible MCP tool server JSON files. Follow the exact format of the existing 4 files:

```json
{
  "id": "portal_<n>",
  "name": "Portal <Display Name>",
  "type": "mcp",
  "meta": {
    "description": "<what it does>",
    "manifest": {
      "type": "mcp",
      "url": "http://host.docker.internal:<port>/mcp"
    }
  },
  "settings": {
    "api_key": ""
  }
}
```

Files to create:

| Filename | id | name | port | description |
|---|---|---|---|---|
| `portal_comfyui.json` | `portal_comfyui` | Portal ComfyUI | 8910 | Generate images and videos via ComfyUI workflows |
| `portal_video.json` | `portal_video` | Portal Video | 8911 | Generate video clips using Wan2.2 |
| `portal_whisper.json` | `portal_whisper` | Portal Whisper | 8915 | Transcribe audio and video files to text |
| `portal_shell.json` | `portal_shell` | Portal Shell | 8091 | Execute shell commands in a sandboxed environment |
| `portal_web.json` | `portal_web` | Portal Web | 8092 | Scrape and search the web for current information |

Note: `mcp-filesystem` uses stdio transport (no HTTP port). Do not create a tool server file for it — add a comment in the README explaining this.

**Verify:**
```bash
ls imports/openwebui/tools/*.json | wc -l   # must be 9
python3 -c "
import json, glob
files = glob.glob('imports/openwebui/tools/*.json')
for f in files:
    data = json.load(open(f))
    assert 'id' in data and 'meta' in data, f'{f} missing fields'
    url = data['meta']['manifest']['url']
    port = int(url.split(':')[-1].split('/')[0])
    assert 1024 < port < 65536, f'{f} has invalid port {port}'
print(f'All {len(files)} tool files valid')
"
```

---

### TASK-IMP-02: Update mcp-servers.json to All 9 Services

**File:** `imports/openwebui/mcp-servers.json`
**Priority:** CRITICAL
**Effort:** 15 min

Replace current 4-entry file with all 9 HTTP-accessible MCP servers:

```json
{
  "version": "1.1",
  "description": "Portal MCP Tool Server configurations for Open WebUI. Used by: python scripts/setup_openwebui.py",
  "tool_servers": [
    { "name": "Portal ComfyUI",   "url": "http://host.docker.internal:8910/mcp", "api_key": "" },
    { "name": "Portal Video",     "url": "http://host.docker.internal:8911/mcp", "api_key": "" },
    { "name": "Portal Music",     "url": "http://host.docker.internal:8912/mcp", "api_key": "" },
    { "name": "Portal Documents", "url": "http://host.docker.internal:8913/mcp", "api_key": "" },
    { "name": "Portal Code",      "url": "http://host.docker.internal:8914/mcp", "api_key": "" },
    { "name": "Portal Whisper",   "url": "http://host.docker.internal:8915/mcp", "api_key": "" },
    { "name": "Portal TTS",       "url": "http://host.docker.internal:8916/mcp", "api_key": "" },
    { "name": "Portal Shell",     "url": "http://host.docker.internal:8091/mcp", "api_key": "" },
    { "name": "Portal Web",       "url": "http://host.docker.internal:8092/mcp", "api_key": "" }
  ],
  "notes": {
    "macos":           "Use host.docker.internal — Docker Desktop resolves this automatically",
    "linux":           "Replace host.docker.internal with your host IP: $(ip route | awk '/default/{print $3}')",
    "filesystem_mcp":  "mcp-filesystem uses stdio transport — not registered here, not accessible via HTTP"
  }
}
```

**Verify:** `python3 -c "import json; d=json.load(open('imports/openwebui/mcp-servers.json')); assert len(d['tool_servers'])==9; print('OK — 9 servers')"`

---

### TASK-IMP-03: Create Workspace Import Files

**Directory:** `imports/openwebui/workspaces/` (create new)
**Priority:** HIGH
**Effort:** 45 min

Create one JSON file per Portal workspace. Pull system prompt strings from `scripts/setup_openwebui.py`'s `WORKSPACES` dict — do not duplicate by hand, use this script:

```bash
python3 - <<'EOF'
import json
from pathlib import Path
import sys
sys.path.insert(0, 'scripts')

# Inline the WORKSPACES dict rather than importing (avoids httpx dependency at this stage)
WORKSPACES = {
    "auto": {
        "name": "Portal Auto Router",
        "description": "Automatically selects the best model for your task",
        "system_prompt": "You are Portal, an AI assistant that intelligently routes requests to specialized models.",
    },
    "auto-coding": {
        "name": "Code Expert",
        "description": "Specialized in code generation and debugging",
        "system_prompt": "You are an expert programmer. Generate clean, well-documented code. Always prefer idiomatic solutions.",
    },
    "auto-security": {
        "name": "Security Analyst",
        "description": "Security analysis and defensive coding",
        "system_prompt": "You are a security expert. Focus on secure coding practices, vulnerability analysis, and defensive measures.",
    },
    "auto-creative": {
        "name": "Creative Writer",
        "description": "Creative content generation",
        "system_prompt": "You are a creative writer. Generate engaging, imaginative content with vivid descriptions.",
    },
    "auto-reasoning": {
        "name": "Deep Reasoner",
        "description": "Complex reasoning and analysis",
        "system_prompt": "You are a deep reasoning AI. Break down complex problems step-by-step and provide thorough analysis.",
    },
    "auto-documents": {
        "name": "Document Builder",
        "description": "Create documents, spreadsheets, presentations",
        "system_prompt": "You help create professional documents. Use available tools to generate Word, Excel, and PowerPoint files.",
    },
    "auto-video": {
        "name": "Video Creator",
        "description": "Generate videos with Wan2.2",
        "system_prompt": "You create videos. Use ComfyUI to generate videos from text prompts.",
    },
    "auto-music": {
        "name": "Music Producer",
        "description": "Generate music with AudioCraft",
        "system_prompt": "You create music. Use the music generation tool to produce audio clips.",
    },
    "auto-research": {
        "name": "Research Assistant",
        "description": "Web research and information synthesis",
        "system_prompt": "You are a research assistant. Search the web and synthesize information from multiple sources.",
    },
}

out_dir = Path("imports/openwebui/workspaces")
out_dir.mkdir(exist_ok=True)

all_workspaces = []
for ws_id, cfg in WORKSPACES.items():
    payload = {
        "id": ws_id,
        "name": cfg["name"],
        "meta": {
            "description": cfg["description"],
            "profile_image_url": ""
        },
        "params": {
            "system": cfg["system_prompt"],
            "model": ws_id
        }
    }
    filename = f"workspace_{ws_id.replace('-', '_')}.json"
    (out_dir / filename).write_text(json.dumps(payload, indent=2))
    all_workspaces.append(payload)
    print(f"Created: {filename}")

# Also write the bulk import file
(out_dir / "workspaces_all.json").write_text(json.dumps(all_workspaces, indent=2))
print(f"Created: workspaces_all.json ({len(all_workspaces)} workspaces)")
EOF
```

**Verify:**
```bash
ls imports/openwebui/workspaces/
python3 -c "
import json
from pathlib import Path
files = list(Path('imports/openwebui/workspaces').glob('workspace_*.json'))
assert len(files) == 9, f'Expected 9, got {len(files)}'
for f in files:
    d = json.loads(f.read_text())
    assert all(k in d for k in ['id','name','params']), f'{f.name} missing keys'
    assert d['params'].get('system'), f'{f.name} has empty system prompt'
print(f'All {len(files)} workspace files valid')
"
```

---

### TASK-IMP-04: Create Open WebUI Functions Import File

**Directory:** `imports/openwebui/functions/` (create new)
**Priority:** MEDIUM
**Effort:** 1 hour

Open WebUI Functions are Python snippets that run inside Open WebUI's pipeline. They differ from Tool Servers (which are external HTTP MCP servers). Portal needs one `pipe` function that exposes Portal's workspaces as selectable models in the Open WebUI model dropdown — useful when Open WebUI's connection to Portal doesn't surface workspace models automatically.

Create `imports/openwebui/functions/portal_router_pipe.json`.

The `content` field must be a JSON string containing valid Python. Write and test the Python independently first:

```python
# Test this Python independently before embedding in JSON:
# Save as /tmp/test_portal_pipe.py and verify it compiles

PIPE_CODE = '''
"""Portal Workspace Router — Open WebUI Pipe Function
Routes requests to Portal workspace endpoints (auto-coding, auto-security, etc.)
Install via: Open WebUI > Workspace > Functions > Import
"""
from pydantic import BaseModel
from typing import Optional


class Pipe:
    class Valves(BaseModel):
        portal_base_url: str = "http://host.docker.internal:8081/v1"
        portal_api_key: str = "portal"
        timeout_seconds: int = 120

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self) -> list[dict]:
        """Return the list of workspace models exposed in Open WebUI model dropdown."""
        return [
            {"id": "auto",           "name": "🤖 Portal Auto Router"},
            {"id": "auto-coding",    "name": "💻 Portal Code Expert"},
            {"id": "auto-security",  "name": "🔐 Portal Security Analyst"},
            {"id": "auto-creative",  "name": "✍️ Portal Creative Writer"},
            {"id": "auto-reasoning", "name": "🧠 Portal Deep Reasoner"},
            {"id": "auto-documents", "name": "📄 Portal Document Builder"},
            {"id": "auto-video",     "name": "🎬 Portal Video Creator"},
            {"id": "auto-music",     "name": "🎵 Portal Music Producer"},
            {"id": "auto-research",  "name": "🔍 Portal Research Assistant"},
        ]

    async def pipe(self, body: dict, __user: Optional[dict] = None) -> str | dict:
        """Forward request to Portal with the selected workspace model."""
        import httpx

        # Strip the pipe prefix Open WebUI prepends (e.g. "portal_router_pipe.auto" -> "auto")
        model_id = body.get("model", "auto")
        if "." in model_id:
            model_id = model_id.split(".", 1)[1]
        body = {**body, "model": model_id}

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.valves.portal_base_url}/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {self.valves.portal_api_key}"},
                    timeout=self.valves.timeout_seconds,
                )
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            return {"error": f"Portal returned HTTP {e.response.status_code}: {e.response.text[:200]}"}
        except Exception as e:
            return {"error": f"Portal connection failed: {e}"}
'''

# Verify it compiles
compile(PIPE_CODE, '<portal_router_pipe>', 'exec')
print("Python is valid — safe to embed in JSON")
```

Run the compile check. If it passes, create the JSON:

```bash
python3 - <<'EOF'
import json
from pathlib import Path

PIPE_CODE = open('/tmp/test_portal_pipe.py').read() if False else """
\"\"\"Portal Workspace Router — Open WebUI Pipe Function
Routes requests to Portal workspace endpoints (auto-coding, auto-security, etc.)
Install via: Open WebUI > Workspace > Functions > Import
\"\"\"
from pydantic import BaseModel
from typing import Optional


class Pipe:
    class Valves(BaseModel):
        portal_base_url: str = "http://host.docker.internal:8081/v1"
        portal_api_key: str = "portal"
        timeout_seconds: int = 120

    def __init__(self):
        self.valves = self.Valves()

    def pipes(self) -> list[dict]:
        return [
            {"id": "auto",           "name": "Portal Auto Router"},
            {"id": "auto-coding",    "name": "Portal Code Expert"},
            {"id": "auto-security",  "name": "Portal Security Analyst"},
            {"id": "auto-creative",  "name": "Portal Creative Writer"},
            {"id": "auto-reasoning", "name": "Portal Deep Reasoner"},
            {"id": "auto-documents", "name": "Portal Document Builder"},
            {"id": "auto-video",     "name": "Portal Video Creator"},
            {"id": "auto-music",     "name": "Portal Music Producer"},
            {"id": "auto-research",  "name": "Portal Research Assistant"},
        ]

    async def pipe(self, body: dict, __user=None):
        import httpx
        model_id = body.get("model", "auto")
        if "." in model_id:
            model_id = model_id.split(".", 1)[1]
        body = {**body, "model": model_id}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.valves.portal_base_url}/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {self.valves.portal_api_key}"},
                    timeout=self.valves.timeout_seconds,
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            return {"error": str(e)}
"""

# Verify compiles
compile(PIPE_CODE, '<pipe>', 'exec')

out_dir = Path("imports/openwebui/functions")
out_dir.mkdir(exist_ok=True)

payload = {
    "id": "portal_router_pipe",
    "name": "Portal Workspace Router",
    "type": "pipe",
    "meta": {
        "description": "Routes requests to Portal workspace endpoints. Exposes auto, auto-coding, auto-security, etc. as selectable models in the chat header."
    },
    "content": PIPE_CODE
}

(out_dir / "portal_router_pipe.json").write_text(json.dumps(payload, indent=2))
print("Created: imports/openwebui/functions/portal_router_pipe.json")
EOF
```

**Verify:**
```bash
python3 -c "
import json
from pathlib import Path
d = json.loads(Path('imports/openwebui/functions/portal_router_pipe.json').read_text())
assert d['type'] == 'pipe'
compile(d['content'], '<pipe>', 'exec')
print('Function file valid and Python compiles cleanly')
"
```

---

### TASK-IMP-05: Fix setup_openwebui.py — Correct the Tool Server API Call

**File:** `scripts/setup_openwebui.py`
**Priority:** CRITICAL (silent bug — runs without error but does nothing)
**Effort:** 1 hour

**DEFECT-1:** `configure_mcp_servers()` calls `GET /api/v1/settings` then `POST /api/v1/settings` with a `mcp_servers` key. Open WebUI does not register Tool Servers via this endpoint. The function returns `True` on HTTP 200 but zero servers are registered.

**The correct Open WebUI Tool Server registration endpoint** (v0.4+):
```
POST /api/v1/tools/server/
{
  "url": "http://host.docker.internal:8912/mcp",
  "config": { "name": "Portal Music", "auth_type": "none", "key": "" }
}
```

**Replace the entire `configure_mcp_servers()` function** with:

```python
def register_tool_servers(
    client: httpx.Client, url: str, api_key: str, mcp_file_path: str
) -> bool:
    """Register Portal MCP servers as Tool Servers in Open WebUI.

    Uses POST /api/v1/tools/server/ — the correct endpoint for Tool Server registration.
    The old configure_mcp_servers() used /api/v1/settings which silently did nothing.
    """
    mcp_file = Path(mcp_file_path)
    if not mcp_file.exists():
        print(f"  MCP config file not found: {mcp_file_path}")
        return False

    if not api_key:
        print("  Skipping Tool Server registration: no API key provided (use --api-key)")
        return False

    try:
        with open(mcp_file) as f:
            mcp_data = json.load(f)
    except Exception as e:
        print(f"  Failed to read {mcp_file_path}: {e}")
        return False

    servers = mcp_data.get("tool_servers", [])
    if not servers:
        print("  No tool_servers entries found in MCP config")
        return False

    # Fetch existing registrations to avoid duplicates
    existing_urls: set[str] = set()
    try:
        resp = client.get(
            f"{url}/api/v1/tools/server/",
            headers=get_auth_headers(api_key),
        )
        if resp.status_code == 200:
            data = resp.json()
            server_list = data if isinstance(data, list) else data.get("data", [])
            for s in server_list:
                existing_urls.add(s.get("url", ""))
    except Exception as e:
        print(f"  Warning: could not fetch existing tool servers: {e}")

    registered = skipped = failed = 0

    for server in servers:
        server_url = server["url"]
        server_name = server["name"]
        server_key = server.get("api_key", "")

        if server_url in existing_urls:
            print(f"  Skip (exists): {server_name}")
            skipped += 1
            continue

        payload = {
            "url": server_url,
            "config": {
                "name": server_name,
                "auth_type": "none" if not server_key else "bearer",
                "key": server_key,
            },
        }

        try:
            resp = client.post(
                f"{url}/api/v1/tools/server/",
                json=payload,
                headers=get_auth_headers(api_key),
                timeout=10.0,
            )
            if resp.status_code in (200, 201):
                print(f"  Registered: {server_name} ({server_url})")
                registered += 1
            else:
                print(
                    f"  Failed {server_name}: HTTP {resp.status_code}"
                    f" — {resp.text[:120]}"
                )
                failed += 1
        except Exception as e:
            print(f"  Error registering {server_name}: {e}")
            failed += 1

    print(
        f"  Tool Servers: {registered} registered, "
        f"{skipped} skipped (existing), {failed} failed"
    )
    return failed == 0
```

**Also add CLI flags** to `main()`:

```python
parser.add_argument(
    "--skip-tools",
    action="store_true",
    help="Skip MCP tool server registration (useful if MCP containers aren't running yet)",
)
parser.add_argument(
    "--skip-workspaces",
    action="store_true",
    help="Skip workspace creation",
)
```

**Update `main()`** to call `register_tool_servers()` instead of `configure_mcp_servers()`, and respect the new flags:

```python
# Replace the existing MCP config block at the end of main() with:
if not args.skip_tools:
    script_dir = Path(__file__).parent
    mcp_file = script_dir.parent / "imports" / "openwebui" / "mcp-servers.json"
    if mcp_file.exists():
        print("\nRegistering MCP Tool Servers...")
        register_tool_servers(client, args.url, args.api_key or "", str(mcp_file))
    else:
        print(f"\nSkipping tool servers: {mcp_file} not found")
else:
    print("\nSkipping tool server registration (--skip-tools)")
```

**Verify:**
```bash
python scripts/setup_openwebui.py --help
# Must show: --skip-tools, --skip-workspaces, --dry-run

python3 -c "
import ast, pathlib
src = pathlib.Path('scripts/setup_openwebui.py').read_text()
assert 'configure_mcp_servers' not in src, 'Old broken function still present'
assert 'register_tool_servers' in src, 'New function missing'
assert '/api/v1/tools/server/' in src, 'Wrong API endpoint'
assert '/api/v1/settings' not in src or 'mcp_servers' not in src, 'Old broken call still present'
print('API endpoint fix verified')
"
```

---

### TASK-IMP-06: Load Workspaces from Import Files (Remove Hardcoded Dict)

**File:** `scripts/setup_openwebui.py`
**Priority:** MEDIUM
**Effort:** 30 min

The `WORKSPACES` dict is hardcoded in the script. Now that `imports/openwebui/workspaces/` is the canonical source, load from there and use the hardcoded dict only as fallback:

```python
def load_workspaces_from_imports(imports_dir: Path) -> dict[str, dict]:
    """Load workspace definitions from imports/openwebui/workspaces/*.json.

    Returns empty dict if directory doesn't exist, allowing the hardcoded
    WORKSPACES fallback to take over.
    """
    ws_dir = imports_dir / "workspaces"
    if not ws_dir.exists():
        return {}

    workspaces: dict[str, dict] = {}
    for ws_file in sorted(ws_dir.glob("workspace_*.json")):
        try:
            ws = json.loads(ws_file.read_text())
            ws_id = ws.get("id", ws_file.stem)
            workspaces[ws_id] = {
                "name": ws.get("name", ws_id),
                "description": ws.get("meta", {}).get("description", ""),
                "system_prompt": ws.get("params", {}).get("system", ""),
            }
        except Exception as e:
            print(f"  Warning: could not load {ws_file.name}: {e}")
    return workspaces
```

In `main()`, use this loader:

```python
# Load workspaces: prefer import files, fall back to hardcoded dict
imports_dir = Path(__file__).parent.parent / "imports" / "openwebui"
workspaces_to_use = load_workspaces_from_imports(imports_dir) or WORKSPACES
if workspaces_to_use is WORKSPACES:
    print("Note: Using hardcoded workspace definitions (imports/openwebui/workspaces/ not found)")
```

**Verify:**
```bash
python3 -c "
import sys; sys.path.insert(0, 'scripts')
from pathlib import Path

# Simulate the function inline
import json
ws_dir = Path('imports/openwebui/workspaces')
workspaces = {}
for f in sorted(ws_dir.glob('workspace_*.json')):
    ws = json.loads(f.read_text())
    workspaces[ws['id']] = ws
print(f'Loaded {len(workspaces)} workspaces from import files: {sorted(workspaces.keys())}')
assert len(workspaces) == 9
"
```

---

### TASK-IMP-07: Add generate_import_bundle.py Script

**File:** `scripts/generate_import_bundle.py` (new)
**Priority:** MEDIUM
**Effort:** 30 min

Generates a single `portal_import_bundle.json` from all individual import files — useful as a reference and for tooling that supports bulk imports:

```python
#!/usr/bin/env python3
"""Generate a combined Portal import bundle from all individual import files.

Usage:
    python scripts/generate_import_bundle.py
    python scripts/generate_import_bundle.py --output /tmp/portal_bundle.json
"""

import argparse
import json
from pathlib import Path


def build_bundle(imports_dir: Path) -> dict:
    bundle: dict = {
        "version": "1.0",
        "generator": "scripts/generate_import_bundle.py",
        "tool_servers": [],
        "tools": [],
        "workspaces": [],
        "functions": [],
    }

    mcp_file = imports_dir / "mcp-servers.json"
    if mcp_file.exists():
        bundle["tool_servers"] = json.loads(mcp_file.read_text()).get("tool_servers", [])

    for f in sorted((imports_dir / "tools").glob("*.json")):
        bundle["tools"].append(json.loads(f.read_text()))

    ws_dir = imports_dir / "workspaces"
    if ws_dir.exists():
        for f in sorted(ws_dir.glob("workspace_*.json")):
            bundle["workspaces"].append(json.loads(f.read_text()))

    fn_dir = imports_dir / "functions"
    if fn_dir.exists():
        for f in sorted(fn_dir.glob("*.json")):
            bundle["functions"].append(json.loads(f.read_text()))

    return bundle


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Portal Open WebUI import bundle")
    parser.add_argument(
        "--output",
        default="imports/openwebui/portal_import_bundle.json",
    )
    args = parser.parse_args()

    imports_dir = Path(__file__).parent.parent / "imports" / "openwebui"
    bundle = build_bundle(imports_dir)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(bundle, indent=2))

    print(f"Generated: {output}")
    print(f"  Tool servers : {len(bundle['tool_servers'])}")
    print(f"  Tool imports : {len(bundle['tools'])}")
    print(f"  Workspaces   : {len(bundle['workspaces'])}")
    print(f"  Functions    : {len(bundle['functions'])}")
    print()
    print("Automated setup:  python scripts/setup_openwebui.py --api-key YOUR_KEY")
    print("GUI import path:  Open WebUI > Admin > Tools > Import (individual JSON files)")


if __name__ == "__main__":
    main()
```

**Verify:**
```bash
python scripts/generate_import_bundle.py
python3 -c "
import json
d = json.load(open('imports/openwebui/portal_import_bundle.json'))
assert len(d['tool_servers']) == 9
assert len(d['tools']) == 9
assert len(d['workspaces']) == 9
assert len(d['functions']) >= 1
print('Bundle valid')
"
```

---

## Phase 3 — Clean Environment Tasks

---

### TASK-ENV-01: Add openwebui-init One-Shot Container to docker-compose

**File:** `deploy/web-ui/openwebui/docker-compose.yml`
**Priority:** CRITICAL
**Effort:** 1 hour

Add a one-shot init container that runs `setup_openwebui.py` automatically after Open WebUI is healthy. This is the central fix for the "never seeded on first run" problem.

The init container must:
- Only run after `open-webui` passes its healthcheck
- Wait for the API to actually respond (not just be healthy)
- Run `setup_openwebui.py` with admin credentials
- Exit 0 on success so Docker doesn't restart it
- Use `restart: "no"` so it never reruns on subsequent ups after the volume is already seeded

Open WebUI requires an admin account to exist before API calls can work. The init flow:
1. Create admin account via the signup endpoint (first user = admin, only works on fresh volume)
2. Get the API key from the login response
3. Run `setup_openwebui.py` with that key

Add this service to `deploy/web-ui/openwebui/docker-compose.yml`:

```yaml
  # -----------------------------------------------------------------------
  # Open WebUI Init — seeds workspaces and tool servers on first run
  # Runs once after open-webui is healthy, then exits.
  # On subsequent ups with an existing volume, the signup call will fail
  # (user already exists) and the script handles this gracefully.
  # -----------------------------------------------------------------------
  openwebui-init:
    image: python:3.11-slim
    container_name: portal-openwebui-init
    restart: "no"
    depends_on:
      open-webui:
        condition: service_healthy
    environment:
      - OPENWEBUI_URL=http://open-webui:8080
      - OPENWEBUI_ADMIN_EMAIL=${OPENWEBUI_ADMIN_EMAIL:-admin@portal.local}
      - OPENWEBUI_ADMIN_PASSWORD=${OPENWEBUI_ADMIN_PASSWORD:-portal-admin-change-me}
      - OPENWEBUI_ADMIN_NAME=${OPENWEBUI_ADMIN_NAME:-Portal Admin}
    volumes:
      - ../../../scripts:/scripts:ro
      - ../../../imports:/imports:ro
    command: >
      sh -c "
        pip install httpx --quiet &&
        python /scripts/openwebui_init.py
      "
```

Also add to `deploy/web-ui/openwebui/docker-compose.yml`'s `depends_on` block for Caddy if Caddy exists.

The init container calls a new dedicated init script (see TASK-ENV-02).

**Add these env vars to `.env.example`:**

```bash
# --- Open WebUI Init (auto-seeding) ---
# Admin credentials created on first fresh volume start
# Change these before first launch — admin@portal.local is the default
OPENWEBUI_ADMIN_EMAIL=admin@portal.local
OPENWEBUI_ADMIN_PASSWORD=portal-admin-change-me
OPENWEBUI_ADMIN_NAME=Portal Admin
```

**Verify (structural check — can't run without Docker):**
```bash
python3 -c "
import yaml
with open('deploy/web-ui/openwebui/docker-compose.yml') as f:
    dc = yaml.safe_load(f)
assert 'openwebui-init' in dc['services'], 'Init container not found'
init = dc['services']['openwebui-init']
assert init.get('restart') == 'no', 'restart must be no'
deps = init.get('depends_on', {})
assert 'open-webui' in deps, 'Must depend on open-webui'
assert deps['open-webui'].get('condition') == 'service_healthy'
print('openwebui-init service definition valid')
"
```

---

### TASK-ENV-02: Create scripts/openwebui_init.py

**File:** `scripts/openwebui_init.py` (new)
**Priority:** CRITICAL
**Effort:** 1.5 hours

This is the script the init container runs. It handles first-run account creation and configuration seeding, and is idempotent — safe to run against an already-configured instance.

```python
#!/usr/bin/env python3
"""
Open WebUI First-Run Initialization Script

Runs inside the openwebui-init Docker container after Open WebUI is healthy.
Handles:
  1. Admin account creation (first run only — idempotent)
  2. API key acquisition
  3. MCP Tool Server registration (via correct /api/v1/tools/server/ endpoint)
  4. Workspace creation

Environment variables (all have defaults for local dev):
  OPENWEBUI_URL              — default: http://open-webui:8080
  OPENWEBUI_ADMIN_EMAIL      — default: admin@portal.local
  OPENWEBUI_ADMIN_PASSWORD   — default: portal-admin-change-me
  OPENWEBUI_ADMIN_NAME       — default: Portal Admin
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx

OPENWEBUI_URL = os.environ.get("OPENWEBUI_URL", "http://open-webui:8080").rstrip("/")
ADMIN_EMAIL = os.environ.get("OPENWEBUI_ADMIN_EMAIL", "admin@portal.local")
ADMIN_PASSWORD = os.environ.get("OPENWEBUI_ADMIN_PASSWORD", "portal-admin-change-me")
ADMIN_NAME = os.environ.get("OPENWEBUI_ADMIN_NAME", "Portal Admin")

IMPORTS_DIR = Path("/imports/openwebui")
MCP_FILE = IMPORTS_DIR / "mcp-servers.json"
WORKSPACES_DIR = IMPORTS_DIR / "workspaces"

MAX_WAIT_SECONDS = 120
POLL_INTERVAL = 5


# ─── Utilities ────────────────────────────────────────────────────────────────

def wait_for_openwebui(client: httpx.Client) -> bool:
    """Poll until Open WebUI health endpoint responds."""
    print(f"Waiting for Open WebUI at {OPENWEBUI_URL}...")
    deadline = time.time() + MAX_WAIT_SECONDS
    while time.time() < deadline:
        try:
            resp = client.get(f"{OPENWEBUI_URL}/health", timeout=5.0)
            if resp.status_code == 200:
                print("  Open WebUI is healthy")
                return True
        except Exception:
            pass
        print(f"  Not ready yet — retrying in {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)
    print("ERROR: Open WebUI did not become ready in time")
    return False


def create_admin_account(client: httpx.Client) -> str | None:
    """Create the admin account. Returns API token or None if already exists."""
    print(f"Creating admin account: {ADMIN_EMAIL}")
    try:
        resp = client.post(
            f"{OPENWEBUI_URL}/api/v1/auths/signup",
            json={
                "name": ADMIN_NAME,
                "email": ADMIN_EMAIL,
                "password": ADMIN_PASSWORD,
            },
            timeout=15.0,
        )
        if resp.status_code in (200, 201):
            token = resp.json().get("token")
            print("  Admin account created")
            return token
        elif resp.status_code == 400:
            # User already exists — this is expected on non-first runs
            detail = resp.json().get("detail", "")
            if "already" in detail.lower() or "exist" in detail.lower():
                print("  Admin account already exists (not first run)")
                return None
            print(f"  Signup failed: {detail}")
            return None
        else:
            print(f"  Signup failed: HTTP {resp.status_code} — {resp.text[:150]}")
            return None
    except Exception as e:
        print(f"  Signup error: {e}")
        return None


def login(client: httpx.Client) -> str | None:
    """Login and return API token."""
    print(f"Logging in as: {ADMIN_EMAIL}")
    try:
        resp = client.post(
            f"{OPENWEBUI_URL}/api/v1/auths/signin",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15.0,
        )
        if resp.status_code == 200:
            token = resp.json().get("token")
            print("  Login successful")
            return token
        else:
            print(f"  Login failed: HTTP {resp.status_code} — {resp.text[:150]}")
            return None
    except Exception as e:
        print(f"  Login error: {e}")
        return None


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ─── Tool Server Registration ─────────────────────────────────────────────────

def register_tool_servers(client: httpx.Client, token: str) -> None:
    """Register all Portal MCP servers as Tool Servers in Open WebUI."""
    print("\nRegistering MCP Tool Servers...")

    if not MCP_FILE.exists():
        print(f"  Skipping — {MCP_FILE} not found")
        return

    servers = json.loads(MCP_FILE.read_text()).get("tool_servers", [])
    if not servers:
        print("  Skipping — no tool_servers in mcp-servers.json")
        return

    # Get existing registrations
    existing_urls: set[str] = set()
    try:
        resp = client.get(
            f"{OPENWEBUI_URL}/api/v1/tools/server/",
            headers=auth_headers(token),
        )
        if resp.status_code == 200:
            data = resp.json()
            for s in (data if isinstance(data, list) else data.get("data", [])):
                existing_urls.add(s.get("url", ""))
    except Exception as e:
        print(f"  Warning: could not check existing tool servers: {e}")

    registered = skipped = failed = 0
    for server in servers:
        url = server["url"]
        name = server["name"]
        key = server.get("api_key", "")

        if url in existing_urls:
            print(f"  Skip (exists): {name}")
            skipped += 1
            continue

        try:
            resp = client.post(
                f"{OPENWEBUI_URL}/api/v1/tools/server/",
                json={
                    "url": url,
                    "config": {
                        "name": name,
                        "auth_type": "none" if not key else "bearer",
                        "key": key,
                    },
                },
                headers=auth_headers(token),
                timeout=10.0,
            )
            if resp.status_code in (200, 201):
                print(f"  Registered: {name}")
                registered += 1
            else:
                print(f"  Failed {name}: HTTP {resp.status_code} — {resp.text[:100]}")
                failed += 1
        except Exception as e:
            print(f"  Error {name}: {e}")
            failed += 1

    print(f"  Done: {registered} registered, {skipped} skipped, {failed} failed")


# ─── Workspace Creation ───────────────────────────────────────────────────────

def create_workspaces(client: httpx.Client, token: str) -> None:
    """Create Portal workspace presets in Open WebUI."""
    print("\nCreating Workspaces...")

    if not WORKSPACES_DIR.exists():
        print(f"  Skipping — {WORKSPACES_DIR} not found")
        return

    ws_files = sorted(WORKSPACES_DIR.glob("workspace_*.json"))
    if not ws_files:
        print("  Skipping — no workspace files found")
        return

    # Get existing workspaces
    existing_names: set[str] = set()
    try:
        resp = client.get(
            f"{OPENWEBUI_URL}/api/v1/models/",
            headers=auth_headers(token),
        )
        if resp.status_code == 200:
            data = resp.json()
            models = data if isinstance(data, list) else data.get("data", [])
            for m in models:
                existing_names.add(m.get("id", ""))
    except Exception as e:
        print(f"  Warning: could not check existing models: {e}")

    created = skipped = failed = 0
    for ws_file in ws_files:
        ws = json.loads(ws_file.read_text())
        ws_id = ws.get("id", "")

        if ws_id in existing_names:
            print(f"  Skip (exists): {ws['name']}")
            skipped += 1
            continue

        payload = {
            "id": ws_id,
            "name": ws["name"],
            "meta": ws.get("meta", {}),
            "params": ws.get("params", {}),
        }

        try:
            resp = client.post(
                f"{OPENWEBUI_URL}/api/v1/models/",
                json=payload,
                headers=auth_headers(token),
                timeout=10.0,
            )
            if resp.status_code in (200, 201):
                print(f"  Created: {ws['name']}")
                created += 1
            else:
                print(f"  Failed {ws['name']}: HTTP {resp.status_code} — {resp.text[:100]}")
                failed += 1
        except Exception as e:
            print(f"  Error {ws['name']}: {e}")
            failed += 1

    print(f"  Done: {created} created, {skipped} skipped, {failed} failed")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    client = httpx.Client(timeout=30.0)

    # Wait for Open WebUI to be ready
    if not wait_for_openwebui(client):
        return 1

    # Create admin account (first run) or skip if exists
    token = create_admin_account(client)

    # If signup failed (account exists), login instead
    if token is None:
        token = login(client)

    if not token:
        print("ERROR: Could not obtain API token — check admin credentials in .env")
        print(f"  OPENWEBUI_ADMIN_EMAIL: {ADMIN_EMAIL}")
        print("  Set OPENWEBUI_ADMIN_EMAIL and OPENWEBUI_ADMIN_PASSWORD in .env")
        return 1

    # Seed the instance
    register_tool_servers(client, token)
    create_workspaces(client, token)

    print("\n✅ Portal Open WebUI initialization complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Verify (syntax and import check — no running Open WebUI needed):**
```bash
python3 -c "
import ast, pathlib
src = pathlib.Path('scripts/openwebui_init.py').read_text()
ast.parse(src)
print('openwebui_init.py syntax valid')
"
python3 -m py_compile scripts/openwebui_init.py && echo "Compiles cleanly"
```

---

### TASK-ENV-03: Add Targeted clean-ui Command to launch.sh

**File:** `launch.sh`
**Priority:** HIGH
**Effort:** 45 min

The current `reset --full` nukes everything including Ollama models (4GB+ downloads) and the `.env` file. Testing needs a command that wipes only Open WebUI state so the init container re-seeds on next `up` — without touching Ollama, Qdrant, or ComfyUI volumes.

Add a new `clean-ui` subcommand to `launch.sh`. Place it in the subcommand dispatch block alongside `reset`, `down`, `doctor`:

```bash
clean_ui() {
    local DEPLOY_DIR="$PORTAL_ROOT/deploy/web-ui/${WEB_UI:-openwebui}"

    echo "=== Portal UI Clean ==="
    echo ""
    echo "This removes the Open WebUI database volume (users, tool servers,"
    echo "workspaces, chat history) so the init container re-seeds on next up."
    echo ""
    echo "Ollama models, Qdrant, and ComfyUI model files are NOT affected."
    echo ""

    if [ -d "$DEPLOY_DIR" ] && docker info &>/dev/null; then
        echo -n "Confirm: wipe open-webui-data volume? [y/N] "
        read -r confirm
        if [ "${confirm:-N}" != "y" ] && [ "${confirm:-N}" != "Y" ]; then
            echo "Cancelled."
            return 0
        fi

        echo "[docker] stopping ${WEB_UI:-openwebui} stack..."
        (cd "$DEPLOY_DIR" && docker compose down) 2>/dev/null || true

        echo "[docker] removing open-webui-data volume..."
        docker volume rm "$(basename "$DEPLOY_DIR")_open-webui-data" 2>/dev/null \
            || docker volume rm "open-webui-data" 2>/dev/null \
            || (cd "$DEPLOY_DIR" && docker compose down -v) 2>/dev/null \
            || echo "  Warning: could not remove volume directly — used compose down -v"

        echo ""
        echo "Done. Run 'bash launch.sh up' to start fresh with auto-seeding."
        echo ""
        echo "Default admin credentials after clean:"
        echo "  Email:    ${OPENWEBUI_ADMIN_EMAIL:-admin@portal.local}"
        echo "  Password: ${OPENWEBUI_ADMIN_PASSWORD:-(set in .env)}"
    else
        echo "Docker not running or deploy directory not found: $DEPLOY_DIR"
        return 1
    fi
}
```

Add to the subcommand dispatch block:

```bash
    clean-ui)
        if [ -f "$PORTAL_ROOT/.env" ]; then
            set -a; source "$PORTAL_ROOT/.env"; set +a
        fi
        clean_ui
        ;;
```

Add to the help text:

```bash
        echo "  clean-ui                       Wipe Open WebUI database (preserves Ollama models)"
```

**Also update `stop_all()`** — the normal `down` subcommand — to document that it does NOT wipe volumes:

Find the `stop_all()` function and add a comment at the end:
```bash
    echo "Portal stopped. (Volumes preserved — run 'bash launch.sh clean-ui' to wipe Open WebUI state)"
```

**Verify:**
```bash
bash launch.sh help 2>&1 | grep "clean-ui"
# Must show the clean-ui entry

grep -n "clean_ui\|clean-ui" launch.sh
# Must show: function definition + dispatch case + help text
```

---

### TASK-ENV-04: Add seed Subcommand to launch.sh

**File:** `launch.sh`
**Priority:** HIGH
**Effort:** 30 min

Add a `seed` subcommand that runs `openwebui_init.py` against a running stack. This is the manual re-seed path — useful after a `clean-ui` + `up` when you don't want to wait for Docker health checks, or when you need to re-register tools after updating `mcp-servers.json`.

```bash
seed_openwebui() {
    local python_bin="python3"
    if [ -f "$PORTAL_ROOT/.venv/bin/python" ]; then
        python_bin="$PORTAL_ROOT/.venv/bin/python"
    fi

    local init_script="$PORTAL_ROOT/scripts/openwebui_init.py"
    if [ ! -f "$init_script" ]; then
        echo "ERROR: $init_script not found"
        exit 1
    fi

    # Use localhost URL for host-side execution (not the Docker internal URL)
    export OPENWEBUI_URL="${OPENWEBUI_URL:-http://localhost:8080}"

    echo "=== Seeding Open WebUI ==="
    echo "  URL:   $OPENWEBUI_URL"
    echo "  Email: ${OPENWEBUI_ADMIN_EMAIL:-admin@portal.local}"
    echo ""

    "$python_bin" "$init_script"
}
```

Add to subcommand dispatch:

```bash
    seed)
        if [ -f "$PORTAL_ROOT/.env" ]; then
            set -a; source "$PORTAL_ROOT/.env"; set +a
        fi
        seed_openwebui
        ;;
```

Add to help text:

```bash
        echo "  seed                           Re-seed Open WebUI (workspaces + tool servers)"
```

**Verify:**
```bash
bash launch.sh help 2>&1 | grep "seed"
grep -n "seed_openwebui\|\"seed\"" launch.sh
```

---

### TASK-ENV-05: Add Unit Tests for Import Files and Init Script

**File:** `tests/unit/test_openwebui_config.py` (new)
**Priority:** MEDIUM
**Effort:** 45 min

```python
"""
Validates that all Open WebUI import files are structurally correct
and consistent with docker-compose service definitions.
Runs without a live Open WebUI instance.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent.parent
IMPORTS_DIR = REPO_ROOT / "imports" / "openwebui"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"


def _compose_mcp_ports() -> set[int]:
    """Extract all port numbers from MCP services in docker-compose.yml."""
    with open(COMPOSE_FILE) as f:
        dc = yaml.safe_load(f)
    ports: set[int] = set()
    for name, svc in dc.get("services", {}).items():
        if "mcp" in name.lower():
            for mapping in svc.get("ports", []):
                host_port = int(str(mapping).split(":")[0])
                ports.add(host_port)
    return ports


# ─── Tool Import Files ────────────────────────────────────────────────────────

class TestToolImportFiles:
    def test_nine_tool_files_exist(self):
        files = list((IMPORTS_DIR / "tools").glob("*.json"))
        assert len(files) == 9, (
            f"Expected 9 tool JSON files, found {len(files)}. "
            f"Missing files for: comfyui, video, music, documents, code, whisper, tts, shell, web"
        )

    def test_all_tool_files_valid_json(self):
        for f in (IMPORTS_DIR / "tools").glob("*.json"):
            try:
                json.loads(f.read_text())
            except json.JSONDecodeError as e:
                pytest.fail(f"{f.name} is not valid JSON: {e}")

    def test_all_tool_files_have_required_fields(self):
        for f in (IMPORTS_DIR / "tools").glob("*.json"):
            d = json.loads(f.read_text())
            for field in ["id", "name", "type", "meta"]:
                assert field in d, f"{f.name} missing required field: '{field}'"
            assert "manifest" in d["meta"], f"{f.name} missing meta.manifest"
            assert "url" in d["meta"]["manifest"], f"{f.name} missing meta.manifest.url"

    def test_tool_ports_match_docker_compose(self):
        compose_ports = _compose_mcp_ports()
        for f in (IMPORTS_DIR / "tools").glob("*.json"):
            d = json.loads(f.read_text())
            url = d["meta"]["manifest"]["url"]
            port = int(url.split(":")[-1].split("/")[0])
            assert port in compose_ports, (
                f"{f.name}: port {port} not found in docker-compose MCP services. "
                f"Available ports: {sorted(compose_ports)}"
            )

    def test_urls_use_host_docker_internal(self):
        for f in (IMPORTS_DIR / "tools").glob("*.json"):
            d = json.loads(f.read_text())
            url = d["meta"]["manifest"]["url"]
            assert "host.docker.internal" in url, (
                f"{f.name}: URL should use host.docker.internal, got: {url}"
            )


# ─── MCP Servers JSON ─────────────────────────────────────────────────────────

class TestMcpServersJson:
    def test_file_exists(self):
        assert (IMPORTS_DIR / "mcp-servers.json").exists()

    def test_has_nine_servers(self):
        d = json.loads((IMPORTS_DIR / "mcp-servers.json").read_text())
        count = len(d.get("tool_servers", []))
        assert count == 9, f"Expected 9 tool servers, found {count}"

    def test_all_servers_have_required_fields(self):
        d = json.loads((IMPORTS_DIR / "mcp-servers.json").read_text())
        for server in d["tool_servers"]:
            assert "name" in server, f"Server missing 'name': {server}"
            assert "url" in server, f"Server missing 'url': {server}"
            assert ":" in server["url"], f"Server URL missing port: {server['url']}"


# ─── Workspace Files ──────────────────────────────────────────────────────────

class TestWorkspaceFiles:
    EXPECTED_IDS = {
        "auto", "auto-coding", "auto-security", "auto-creative",
        "auto-reasoning", "auto-documents", "auto-video",
        "auto-music", "auto-research",
    }

    def test_nine_workspace_files_exist(self):
        files = list((IMPORTS_DIR / "workspaces").glob("workspace_*.json"))
        assert len(files) == 9, f"Expected 9 workspace files, found {len(files)}"

    def test_workspace_ids_match_expected(self):
        actual_ids = set()
        for f in (IMPORTS_DIR / "workspaces").glob("workspace_*.json"):
            d = json.loads(f.read_text())
            actual_ids.add(d["id"])
        assert actual_ids == self.EXPECTED_IDS, (
            f"Workspace ID mismatch.\n"
            f"Missing: {self.EXPECTED_IDS - actual_ids}\n"
            f"Extra:   {actual_ids - self.EXPECTED_IDS}"
        )

    def test_all_workspaces_have_system_prompts(self):
        for f in (IMPORTS_DIR / "workspaces").glob("workspace_*.json"):
            d = json.loads(f.read_text())
            system = d.get("params", {}).get("system", "")
            assert system.strip(), f"{f.name} has empty system prompt"

    def test_bulk_file_exists(self):
        assert (IMPORTS_DIR / "workspaces" / "workspaces_all.json").exists()

    def test_bulk_file_contains_all_workspaces(self):
        bulk = json.loads((IMPORTS_DIR / "workspaces" / "workspaces_all.json").read_text())
        assert isinstance(bulk, list)
        assert len(bulk) == 9


# ─── Function Files ───────────────────────────────────────────────────────────

class TestFunctionFiles:
    def test_router_pipe_exists(self):
        assert (IMPORTS_DIR / "functions" / "portal_router_pipe.json").exists()

    def test_router_pipe_content_is_valid_python(self):
        d = json.loads((IMPORTS_DIR / "functions" / "portal_router_pipe.json").read_text())
        content = d.get("content", "")
        assert content, "portal_router_pipe.json has empty content"
        try:
            ast.parse(content)
        except SyntaxError as e:
            pytest.fail(f"portal_router_pipe content has Python syntax error: {e}")

    def test_router_pipe_has_pipes_method(self):
        d = json.loads((IMPORTS_DIR / "functions" / "portal_router_pipe.json").read_text())
        assert "def pipes(" in d["content"], "Pipe function missing pipes() method"
        assert "def pipe(" in d["content"], "Pipe function missing pipe() method"


# ─── Init Script ──────────────────────────────────────────────────────────────

class TestOpenWebuiInitScript:
    INIT_SCRIPT = REPO_ROOT / "scripts" / "openwebui_init.py"

    def test_script_exists(self):
        assert self.INIT_SCRIPT.exists()

    def test_script_compiles(self):
        src = self.INIT_SCRIPT.read_text()
        try:
            ast.parse(src)
        except SyntaxError as e:
            pytest.fail(f"openwebui_init.py syntax error: {e}")

    def test_script_uses_correct_api_endpoint(self):
        src = self.INIT_SCRIPT.read_text()
        assert "/api/v1/tools/server/" in src, (
            "Init script must use /api/v1/tools/server/ for tool registration"
        )
        assert "/api/v1/settings" not in src, (
            "Init script must not use the broken /api/v1/settings endpoint"
        )

    def test_setup_script_uses_correct_api_endpoint(self):
        setup = (REPO_ROOT / "scripts" / "setup_openwebui.py").read_text()
        assert "/api/v1/tools/server/" in setup, (
            "setup_openwebui.py must use /api/v1/tools/server/ for tool registration (DEFECT-1 fix)"
        )
        assert "configure_mcp_servers" not in setup, (
            "Old broken configure_mcp_servers() function must be removed"
        )
```

**Verify:**
```bash
pytest tests/unit/test_openwebui_config.py -v
# All tests must pass before proceeding to commit
```

---

### TASK-ENV-06: Update imports/openwebui/README.md

**File:** `imports/openwebui/README.md` (full rewrite)
**Priority:** HIGH
**Effort:** 30 min

The current README only documents 4 tools and has no mention of workspaces, functions, the init container, or the clean-ui command. Replace entirely.

The new README must contain these sections in this order:

**1. One-liner summary** — "This directory contains all importable configurations for Open WebUI. Two setup paths exist: fully automated (happens on first `docker compose up`) and manual GUI fallback."

**2. Automated Setup (happens automatically)** — explain the `openwebui-init` container. State that on first launch with a fresh volume, it creates the admin account, registers all 9 MCP tool servers, and creates all 9 workspace presets. State the default admin credentials and where to change them (`.env`). State the `bash launch.sh seed` command for re-running manually.

**3. Clean Restart for Testing** — explain the `bash launch.sh clean-ui` command. Explain what it wipes (Open WebUI database) and what it preserves (Ollama models, Qdrant, ComfyUI models). State the full sequence: `bash launch.sh clean-ui && bash launch.sh up`.

**4. GUI Fallback (if automation fails)** — three numbered sections:
- Tool Servers: Admin > Settings > Tools > Add Tool Server, then import individual `tools/*.json` files one at a time
- Workspaces: Workspace > Models > Import, select individual `workspaces/workspace_*.json` or the bulk `workspaces_all.json`
- Functions: Workspace > Functions > Import, select `functions/portal_router_pipe.json`

**5. Complete File Index Table:**

| File | Type | Import Location | Count |
|---|---|---|---|
| `tools/portal_comfyui.json` | MCP Tool Server | Admin > Settings > Tools | 1 of 9 |
| `tools/portal_video.json` | MCP Tool Server | Admin > Settings > Tools | 2 of 9 |
| `tools/portal_music.json` | MCP Tool Server | Admin > Settings > Tools | 3 of 9 |
| `tools/portal_documents.json` | MCP Tool Server | Admin > Settings > Tools | 4 of 9 |
| `tools/portal_code.json` | MCP Tool Server | Admin > Settings > Tools | 5 of 9 |
| `tools/portal_whisper.json` | MCP Tool Server | Admin > Settings > Tools | 6 of 9 |
| `tools/portal_tts.json` | MCP Tool Server | Admin > Settings > Tools | 7 of 9 |
| `tools/portal_shell.json` | MCP Tool Server | Admin > Settings > Tools | 8 of 9 |
| `tools/portal_web.json` | MCP Tool Server | Admin > Settings > Tools | 9 of 9 |
| `workspaces/workspace_auto.json` | Workspace Preset | Workspace > Models > Import | 1 of 9 |
| `workspaces/workspace_auto_*.json` | Workspace Preset | Workspace > Models > Import | 2-9 of 9 |
| `workspaces/workspaces_all.json` | Bulk Workspace | Workspace > Models > Import | all 9 |
| `functions/portal_router_pipe.json` | Open WebUI Function | Workspace > Functions > Import | 1 of 1 |
| `mcp-servers.json` | Config source | Used by setup scripts | — |
| `portal_import_bundle.json` | Full bundle | Reference / tooling | — |

**6. macOS vs Linux note:** On Linux Docker, replace `host.docker.internal` with: `$(ip route | awk '/default/{print $3}')`. On macOS with Docker Desktop, `host.docker.internal` resolves automatically.

---

### TASK-ENV-07: Add Makefile Targets

**File:** `Makefile`
**Priority:** LOW
**Effort:** 15 min

```makefile
## Generate Open WebUI import bundle from all import files
.PHONY: imports
imports:
	python scripts/generate_import_bundle.py

## Wipe Open WebUI database volume (preserves Ollama models) for clean test restart
.PHONY: clean-ui
clean-ui:
	bash launch.sh clean-ui

## Re-seed Open WebUI (workspaces + tool servers) against running stack
.PHONY: seed
seed:
	bash launch.sh seed

## Full clean test cycle: wipe UI, restart, wait for seeding
.PHONY: test-clean
test-clean:
	bash launch.sh clean-ui
	bash launch.sh up
	@echo "Stack starting — init container will auto-seed Open WebUI"
	@echo "Open WebUI will be ready at http://localhost:8080 in ~60s"
```

---

## Phase 4 — Verification

Run in order. All must pass before committing.

```bash
# ── 1. All unit tests ─────────────────────────────────────────────────────────
pytest tests/unit/test_openwebui_config.py -v
# Expected: all green

# ── 2. Compile checks ─────────────────────────────────────────────────────────
python3 -m py_compile scripts/openwebui_init.py && echo "openwebui_init.py OK"
python3 -m py_compile scripts/setup_openwebui.py && echo "setup_openwebui.py OK"
python3 -m py_compile scripts/generate_import_bundle.py && echo "generate_import_bundle.py OK"

# ── 3. All JSON files valid ────────────────────────────────────────────────────
python3 -c "
import json, glob
files = glob.glob('imports/openwebui/**/*.json', recursive=True)
errors = []
for f in files:
    try: json.load(open(f))
    except Exception as e: errors.append(f'{f}: {e}')
if errors:
    print('FAILED:'); [print(e) for e in errors]
else:
    print(f'All {len(files)} JSON files valid')
"

# ── 4. Correct API endpoint in both scripts ────────────────────────────────────
python3 -c "
for script in ['scripts/setup_openwebui.py', 'scripts/openwebui_init.py']:
    src = open(script).read()
    assert '/api/v1/tools/server/' in src, f'{script}: missing correct endpoint'
    assert 'configure_mcp_servers' not in src, f'{script}: old broken function present'
    print(f'{script}: API endpoint OK')
"

# ── 5. Docker Compose valid ────────────────────────────────────────────────────
python3 -c "
import yaml
dc = yaml.safe_load(open('deploy/web-ui/openwebui/docker-compose.yml'))
assert 'openwebui-init' in dc['services'], 'Missing openwebui-init service'
init = dc['services']['openwebui-init']
assert init['restart'] == 'no', 'restart must be no'
assert dc['services']['openwebui-init']['depends_on']['open-webui']['condition'] == 'service_healthy'
print('docker-compose.yml: openwebui-init service valid')
"

# ── 6. launch.sh commands exist ───────────────────────────────────────────────
grep -q "clean_ui\(\)" launch.sh && echo "clean_ui() function: OK"
grep -q "seed_openwebui\(\)" launch.sh && echo "seed_openwebui() function: OK"
grep -q '"clean-ui")' launch.sh && echo "clean-ui dispatch: OK"
grep -q '"seed")' launch.sh && echo "seed dispatch: OK"

# ── 7. Final file count ────────────────────────────────────────────────────────
echo ""
echo "=== Final Import File Summary ==="
echo "Tool imports:   $(ls imports/openwebui/tools/*.json 2>/dev/null | wc -l) / 9"
echo "Workspaces:     $(ls imports/openwebui/workspaces/workspace_*.json 2>/dev/null | wc -l) / 9"
echo "Functions:      $(ls imports/openwebui/functions/*.json 2>/dev/null | wc -l) / 1"
echo "Bundle:         $(test -f imports/openwebui/portal_import_bundle.json && echo EXISTS || echo MISSING)"
echo "Init script:    $(test -f scripts/openwebui_init.py && echo EXISTS || echo MISSING)"
echo "clean-ui cmd:   $(grep -q 'clean_ui()' launch.sh && echo EXISTS || echo MISSING)"
echo "seed cmd:       $(grep -q 'seed_openwebui()' launch.sh && echo EXISTS || echo MISSING)"
```

**Required results before proceeding to Phase 5:**
- All pytest tests green
- All 3 scripts compile
- All JSON files valid
- Both scripts use `/api/v1/tools/server/`
- `openwebui-init` in docker-compose with `restart: "no"`
- Both launch.sh commands present
- Tool imports: 9/9, Workspaces: 9/9, Functions: 1/1

---

## Phase 5 — Git

```bash
git checkout main
git pull origin main
git checkout -b feature/openwebui-clean-env-and-imports

git add imports/openwebui/
git add scripts/setup_openwebui.py
git add scripts/openwebui_init.py
git add scripts/generate_import_bundle.py
git add deploy/web-ui/openwebui/docker-compose.yml
git add launch.sh
git add tests/unit/test_openwebui_config.py
git add Makefile
git add .env.example

git commit -m "feat(openwebui): auto-seeding, clean env, and complete import files

Problem A — Import completeness:
- Add 5 missing MCP tool server import JSONs (comfyui, video, whisper, shell, web)
- Update mcp-servers.json from 4 to 9 servers
- Add imports/openwebui/workspaces/ with 9 workspace preset JSONs + bulk file
- Add imports/openwebui/functions/ with portal_router_pipe function
- Add scripts/generate_import_bundle.py for single combined export

Problem B — Clean environment:
- Add openwebui-init one-shot container to openwebui docker-compose.yml
  Seeds workspaces and tool servers automatically on first fresh volume start
- Add scripts/openwebui_init.py — init container entrypoint
  Handles admin account creation, tool server registration, workspace creation
  Idempotent — safe to run against already-configured instance
- Add 'bash launch.sh clean-ui' — wipes open-webui-data volume only
  Preserves ollama_data, qdrant_data, comfyui_models
- Add 'bash launch.sh seed' — manually re-runs seeding against live stack

Bug fix:
- Fix DEFECT-1: setup_openwebui.py used POST /api/v1/settings (wrong endpoint)
  Now uses POST /api/v1/tools/server/ (correct Open WebUI Tool Server API)
  Previous behavior: ran without error, registered zero servers

Testing:
- Add tests/unit/test_openwebui_config.py — validates all import files,
  correct API endpoints, function Python validity, workspace ID coverage

Docs:
- Rewrite imports/openwebui/README.md with full file index and both setup paths
- Add OPENWEBUI_ADMIN_EMAIL/PASSWORD to .env.example
- Add make imports, make clean-ui, make seed, make test-clean targets

Clean test cycle: bash launch.sh clean-ui && bash launch.sh up"

git push origin feature/openwebui-clean-env-and-imports
```

---

## Deliverable Map

```
imports/openwebui/
├── README.md                               ← Full rewrite
├── mcp-servers.json                        ← 4→9 servers
├── portal_import_bundle.json               ← Generated bundle
├── config.env                              ← Unchanged
├── tools/
│   ├── portal_comfyui.json                 ← NEW (port 8910)
│   ├── portal_video.json                   ← NEW (port 8911)
│   ├── portal_music.json                   ← existing
│   ├── portal_documents.json               ← existing
│   ├── portal_code.json                    ← existing
│   ├── portal_whisper.json                 ← NEW (port 8915)
│   ├── portal_tts.json                     ← existing
│   ├── portal_shell.json                   ← NEW (port 8091)
│   └── portal_web.json                     ← NEW (port 8092)
├── workspaces/
│   ├── workspace_auto.json                 ← NEW
│   ├── workspace_auto_coding.json          ← NEW
│   ├── workspace_auto_security.json        ← NEW
│   ├── workspace_auto_creative.json        ← NEW
│   ├── workspace_auto_reasoning.json       ← NEW
│   ├── workspace_auto_documents.json       ← NEW
│   ├── workspace_auto_video.json           ← NEW
│   ├── workspace_auto_music.json           ← NEW
│   ├── workspace_auto_research.json        ← NEW
│   └── workspaces_all.json                 ← NEW (bulk)
└── functions/
    └── portal_router_pipe.json             ← NEW

scripts/
├── setup_openwebui.py                      ← Fixed API endpoint, --skip-* flags
├── openwebui_init.py                       ← NEW (init container entrypoint)
└── generate_import_bundle.py               ← NEW

deploy/web-ui/openwebui/
└── docker-compose.yml                      ← Added openwebui-init service

launch.sh                                   ← Added clean-ui and seed subcommands
.env.example                                ← Added OPENWEBUI_ADMIN_* vars
tests/unit/test_openwebui_config.py         ← NEW
Makefile                                    ← Added 4 targets
```

**End state for each session:**

```bash
# Clean test environment every time:
bash launch.sh clean-ui && bash launch.sh up
# Open WebUI comes up fresh, init container seeds it automatically.
# Admin login: admin@portal.local / portal-admin-change-me (or whatever is in .env)
# All 9 tool servers registered. All 9 workspaces created. Zero manual GUI steps.

# Force re-seed without wipe:
bash launch.sh seed

# Full factory reset (nukes everything including Ollama models — use sparingly):
bash launch.sh reset --full
```
