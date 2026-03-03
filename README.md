# Portal

> Local-first AI platform. Web-primary. Multi-interface. Hardware-agnostic.

One URL. Everything on-device. Zero subscriptions. Zero cloud.

## What It Is

Portal is a self-hosted AI platform that runs entirely on your hardware.
It provides a unified brain (AgentCore) behind whichever interface you prefer:

- **Open WebUI** or **LibreChat** as the primary browser interface
- **Telegram** as an optional push notification channel
- **Slack** as an optional team channel

All interfaces share the same routing system, MCP tools, and conversation context.
Adding a 4th interface is ~50 lines of Python.

## Capabilities

| Feature | Description |
|---------|-------------|
| **Chat** | OpenAI-compatible `/v1/chat/completions` with streaming (SSE) |
| **Image Generation** | ComfyUI integration for AI image generation |
| **Video Generation** | Video generation via video_mcp |
| **Music Generation** | Music/audio generation via music_mcp |
| **Document Creation** | Word, PowerPoint, Excel via document_mcp |
| **Code Sandbox** | Secure Python/Node/Bash execution in Docker |
| **Web Research** | Targeted web search when models need current info |
| **Multi-Step Tasks** | Task orchestrator for sequential multi-step requests |
| **File Delivery** | Download generated files via `/v1/files` |
| **Voice** | Audio transcription via Whisper |

## Hardware

| Target | Status |
|--------|--------|
| Apple M4 Mac Mini Pro (64–128GB) | Primary — full generation services |
| NVIDIA CUDA (Linux) | Supported — generation optional |
| NVIDIA CUDA (WSL2) | Supported |

## Quick Start

### 1. Clone & Launch

```bash
git clone https://github.com/ckindle-42/portal
cd portal
bash launch.sh up
```

On first run, Portal will:
- Auto-detect your hardware (M4 Mac / Linux / WSL2)
- Ask which web UI you prefer (Open WebUI or LibreChat)
- Ask if you want Telegram or Slack (optional, press Enter to skip)
- Auto-generate all security keys
- Install dependencies, start all services

**That's it.** Open http://localhost:8080 when it finishes.

### Other commands

```bash
bash launch.sh doctor          # health check all services
bash launch.sh down            # stop everything
bash launch.sh logs portal-api # tail a service log
bash launch.sh status          # one-line service status
bash launch.sh reset-secrets   # rotate all auto-generated keys
```

### Manual setup (if you prefer)

<details>
<summary>Click to expand manual .env setup</summary>

```bash
cp .env.example .env
# Edit .env with your values — see comments inside for guidance
# Then use per-platform launcher:
bash hardware/m4-mac/launch.sh up      # Apple Silicon
bash hardware/linux-bare/launch.sh up  # Linux with NVIDIA
bash hardware/linux-wsl2/launch.sh up  # Windows WSL2
```
</details>

### Development Setup

```bash
git clone https://github.com/ckindle-42/portal
cd portal
pip install -e ".[dev]"   # installs all deps + test/lint tools
make test                  # run full test suite
make lint                  # run linter
make ci                    # full CI pipeline locally
```

### Verify with `portal doctor`

After startup, run the built-in health check to confirm every service is live:

```bash
bash launch.sh doctor
```

Expected output when everything is healthy:

```
=== Portal Doctor ===
[ollama      ] OK
[router      ] OK
[portal-api  ] OK
[web-ui      ] OK (optional)
[mcpo        ] OK (optional)
[scrapling   ] NOT RUNNING (optional)
```

You can also hit each endpoint manually:

```bash
# Portal API health (version + agent_core status)
curl http://localhost:8081/health

# Virtual model list
curl http://localhost:8081/v1/models

# Router health
curl http://localhost:8000/health

# Open WebUI
open http://localhost:8080
```

The Portal API endpoint for Open WebUI / LibreChat is:
```
http://localhost:8081/v1
```

### Stop

```bash
bash launch.sh down
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | System health — version, agent_core status, MCP status |
| `GET` | `/v1/models` | OpenAI-compatible model list |
| `POST` | `/v1/chat/completions` | Chat completions — streaming and non-streaming |
| `POST` | `/v1/audio/transcriptions` | Audio transcription via Whisper |
| `WS` | `/ws` | WebSocket streaming chat |

## Security Notes

| Setting | What to do |
|---------|-----------|
| `MCP_API_KEY` | **Required**: must not be `changeme-mcp-secret` (runtime now refuses to start if unchanged) |
| `WEB_API_KEY` | Set to a strong random string before exposing `:8081` outside localhost |
| `ALLOWED_ORIGINS` | Already defaults to `localhost:8080`; extend only when needed |

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## Origin

Originally based on [PocketPortal](https://github.com/ckindle-42/pocketportal), a Telegram-first AI agent.
Portal is a complete rewrite as a web-first, multi-interface platform.
