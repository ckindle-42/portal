
# Portal — Quick Start

> Minimum commands from zero to running. Covers GUI selection, MCP, generation services, and messaging channels.

---

## Prerequisites
Before starting, you need **Git**, **Python 3.11+**, **Docker**, and **Ollama**. Choose your operating system below for installation instructions:

<details open>
<summary><b>🍎 macOS (Apple Silicon / M4)</b></summary>
The easiest way to install the requirements on macOS is using [Homebrew](https://brew.sh/).

1. **Install Homebrew** (if you don't have it):
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
2. **Install Git, Python, and Ollama:**
   ```bash
   brew install git python@3.11 ollama
   ```
3. **Install Docker:** Download and install [Docker Desktop for Mac](https://docs.docker.com/desktop/install/mac-install/).
</details>

<details>
<summary><b>🐧 Linux (Ubuntu / Debian)</b></summary>
1. **Install Git and Python 3.11+:**
   ```bash
   sudo apt update
   sudo apt install git python3 python3-venv python3-pip
   ```
2. **Install Ollama:**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
3. **Install Docker:** Follow the [official Docker Engine installation guide](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository) or use the convenience script:
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   ```
</details>

<details>
<summary><b>🪟 Windows (WSL2)</b></summary>
Portal runs on Windows via the Windows Subsystem for Linux (WSL2).
1. **Enable WSL2:** Open PowerShell as Administrator and run:
   ```powershell
   wsl --install
   ```
   *Restart your computer if prompted, then open the new "Ubuntu" terminal from your Start Menu.*
2. **Install Git and Python (inside Ubuntu terminal):**
   ```bash
   sudo apt update
   sudo apt install git python3 python3-venv python3-pip
   ```
3. **Install Ollama (inside Ubuntu terminal):**
   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```
4. **Install Docker:** Download and install [Docker Desktop for Windows](https://docs.docker.com/desktop/install/windows-install/). Ensure the **"Use the WSL 2 based engine"** option is checked in Docker Desktop settings.
</details>

---

## 1. Clone & Setup
Once the prerequisites are installed, clone the repository:

```bash
git clone https://github.com/ckindle-42/portal && cd portal
```

**Fastest path:** run `bash launch.sh up` and follow first-run prompts. The launcher auto-detects hardware, creates `.env`, generates secrets, and installs dependencies.

**Manual path (if you want explicit setup):**

```bash
cp .env.example .env
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
```

---

## Configure `.env` Before First Boot

Open `.env` and set these **required** values — Portal refuses to start without them:

```bash
# Generate keys (run twice, use different values for each):
python -c "import secrets; print(secrets.token_urlsafe(32))"

PORTAL_BOOTSTRAP_API_KEY=<paste-key-1>
MCP_API_KEY=<paste-key-2>
```

### Choose Your Web UI

Portal supports **Open WebUI** or **LibreChat**. Set one in `.env`:

```bash
# Option A — Open WebUI (default)
WEB_UI=openwebui
MCP_TRANSPORT=mcpo          # MCP tools served via mcpo proxy on :9000

# Option B — LibreChat
WEB_UI=librechat
MCP_TRANSPORT=native        # LibreChat spawns MCP servers as child processes
```

**What's different:**

| | Open WebUI | LibreChat |
|---|---|---|
| MCP delivery | `mcpo` proxy (`:9000`) | Native child processes — no proxy |
| Extra dependency | None | MongoDB (auto-launched) |
| Virtual models | Via Portal API | Pre-configured in `librechat.yaml` (`auto`, `auto-coding`, `auto-reasoning`, `auto-fast`) |
| Docker compose | `deploy/web-ui/openwebui/` | `deploy/web-ui/librechat/` |
| Port mapping | `:8080` → Caddy → Open WebUI | `:8080` → LibreChat (`:3080` internal) |

**LibreChat additional secrets** (add to `.env` if using LibreChat):

```bash
JWT_SECRET=<generate-a-secret>
JWT_REFRESH_SECRET=<generate-another-secret>
```

### Set Your Hardware Backend

```bash
# Apple Silicon
COMPUTE_BACKEND=mps
DOCKER_HOST_IP=host.docker.internal
SUPERVISOR_TYPE=launchagent

# Linux bare metal
COMPUTE_BACKEND=cuda
DOCKER_HOST_IP=172.17.0.1
SUPERVISOR_TYPE=systemd

# WSL2
COMPUTE_BACKEND=cuda
DOCKER_HOST_IP=0.0.0.0
SUPERVISOR_TYPE=nohup
```

---

## 2. Launch Portal

### Apple M4 Mac (Primary)

```bash
bash hardware/m4-mac/launch.sh up
bash hardware/m4-mac/launch.sh doctor
```

Open **http://localhost:8080**. Stop with:

```bash
bash hardware/m4-mac/launch.sh down
```

**API-only mode (no Docker/GUI):**

```bash
bash hardware/m4-mac/launch.sh up --minimal
```

### Linux Bare Metal (NVIDIA CUDA)

```bash
bash hardware/linux-bare/launch.sh up
bash hardware/linux-bare/launch.sh doctor
```

Open **http://localhost:8080**. Stop with:

```bash
bash hardware/linux-bare/launch.sh down
```

> Note: `GENERATION_SERVICES` defaults to `false` on Linux. Set `GENERATION_SERVICES=true` in `.env` to enable ComfyUI/Whisper MCP wrappers.

### Linux WSL2 (NVIDIA CUDA)

```bash
bash hardware/linux-wsl2/launch.sh up
bash hardware/linux-wsl2/launch.sh doctor
```

Open **http://localhost:8080**. Stop with:

```bash
bash hardware/linux-wsl2/launch.sh down
```

---

## Enable All Features

### MCP Tools (Filesystem, Shell, Web Scraping)

Enabled by default when `MCP_ENABLED=true` (the default). Three core servers launch automatically:

| Server | Description |
|---|---|
| `filesystem` | Safe local filesystem access under `/portal/data/user_{user_id}/` |
| `bash` | Sandboxed CLI execution with human-in-the-loop approval |
| `web` | Web search and scraping |

**Open WebUI path:** Portal runs `mcpo` as a proxy on `:9000`. Tools appear automatically in the UI.

**LibreChat path:** MCP servers defined natively in `librechat.yaml` — includes filesystem, memory, sqlite, git, sequential-thinking, time, scrapling, and microsoft-learn out of the box. No proxy needed.

### Scrapling (Optional Web Scraping)

Launches automatically on `up` if MCP is enabled. Verify:

```bash
curl http://localhost:8900/mcp
```

### Generation Services (M4 Mac Default)

Image generation (ComfyUI) and speech-to-text (Whisper) MCP wrappers. Enabled by default on M4, opt-in on Linux.

```bash
# In .env
GENERATION_SERVICES=true
COMFYUI_URL=http://localhost:8188
WHISPER_MODEL=base
```

ComfyUI must be running at `COMFYUI_URL` for image generation. Whisper runs locally inside the MCP wrapper (model size controlled by `WHISPER_MODEL`).

### Telegram Bot

```bash
# In .env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=<from-@BotFather>
TELEGRAM_USER_IDS=123456789          # comma-separated allowed user IDs
```

Restart Portal. The bot shares the same AgentCore brain, routing, MCP tools, and conversation context as the Web UI.

### Slack Integration

```bash
# In .env
SLACK_ENABLED=true
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=<from-slack-app-settings>
SLACK_CHANNEL_WHITELIST=#ai-ops,#dev-tools
```

Restart Portal. Same shared AgentCore brain.

---

## Virtual Models

Portal's router (`:8000`) exposes virtual models that auto-route to the best Ollama model:

| Virtual Model | Purpose |
|---|---|
| `auto` | General — routes by keyword analysis |
| `auto-coding` | Code-optimized routing |
| `auto-reasoning` | Reasoning / chain-of-thought |
| `auto-fast` | Speed-optimized (smallest capable model) |

Override routing with `@model:` prefix in any message (e.g., `@model:llama3.1 explain X`).

Default model is set via `DEFAULT_MODEL` in `.env` (ships as `qwen2.5:7b`).

---

## Security Checklist

| Variable | Action |
|---|---|
| `PORTAL_BOOTSTRAP_API_KEY` | **Required.** Strong random string — Portal won't start with the default |
| `MCP_API_KEY` | Replace `changeme-mcp-secret` before enabling MCP |
| `RATE_LIMIT_PER_MINUTE` | Default `60` — adjust for your use case |
| `APPROVAL_REQUIRED` | Default `true` — shell MCP requires human approval |
| `SANDBOX_ENABLED` | Default `false` — enable for untrusted environments |

---

## Verify Everything

```bash
# Built-in health check (substitute your platform script)
bash hardware/m4-mac/launch.sh doctor
```

Manual endpoint checks:

```bash
curl http://localhost:8081/health        # Portal API + AgentCore
curl http://localhost:8081/v1/models     # Virtual model list
curl http://localhost:8000/health        # Router
curl http://localhost:8080               # Web UI
```

Healthy output (Open WebUI + MCP enabled):

```
=== Portal Doctor ===
[ollama]      OK
[router]      OK
[portal-api]  OK
[web-ui]      OK
[mcpo]        OK
[scrapling]   OK (optional)
```

### Portal API Endpoint

Point any OpenAI-compatible client at:

```
http://localhost:8081/v1
```

### Logs

```bash
bash hardware/m4-mac/launch.sh logs portal
bash hardware/m4-mac/launch.sh logs ollama
```

**Edge-case notes:**  
- First run can take 5–15 minutes (Docker pulls + Ollama model downloads).  
- On Linux/WSL2, if Docker commands fail, log out/in after `usermod` or restart Docker Desktop.  
- For NVIDIA GPU passthrough issues, verify `nvidia-smi` works inside containers.  
- Always run `doctor` after any `.env` change and restart.
```

**Why this updated guide is better (quick review of recommendations):**  
- **Zero-friction start** — exact copy-paste prereq commands per OS (no more "install Python somehow").  
- **Collapsible sections** keep the page clean for users who know their platform.  
- **Fastest path first** — root `launch.sh` still highlighted.  
- **Full original depth preserved** — every table, command, nuance, and feature section is intact, just re-flowed after the improved prereqs.  
- **Added clarity** — platform numbering, stop commands, and brief edge-case reminders for completeness without bloat.

Copy-paste this entire block into `QUICKSTART.md` (or `QUICKSTART (3).md`) and you're done. Users on any of the three target platforms can now go from zero to a running Portal in minutes. Let me know if you'd like a version with even more troubleshooting or a PDF/export variant!
