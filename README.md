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

## Hardware

| Target | Status |
|--------|--------|
| Apple M4 Pro (64GB) | Primary — full generation services |
| NVIDIA CUDA (Linux) | Supported — generation optional |
| NVIDIA CUDA (WSL2) | Supported |

## Quick Start

### 1. Install

```bash
git clone https://github.com/ckindle-42/portal
cd portal
cp .env.example .env          # edit with your real values (see comments inside)
bash scripts/bootstrap_python.sh
pip install -e ".[all]"
```

### 2. Launch

**Apple M4 Mac (recommended):**
```bash
bash hardware/m4-mac/launch.sh up
```

**Linux bare-metal:**
```bash
bash hardware/linux-bare/launch.sh up
```

**Linux WSL2:**
```bash
bash hardware/linux-wsl2/launch.sh up
```

**Minimal (Portal API only, no Docker stack):**
```bash
bash hardware/m4-mac/launch.sh up --minimal
```

### 3. Verify with `portal doctor`

After startup, run the built-in health check to confirm every service is live:

```bash
bash hardware/m4-mac/launch.sh doctor
```

Expected output when everything is healthy:

```
=== Portal Doctor ===
[ollama]      OK
[router]      OK
[portal-api]  OK
[web-ui]      OK
[mcpo]        OK
[scrapling]   OK (optional)
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

### 4. Stop

```bash
bash hardware/m4-mac/launch.sh down
```

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

## Forked From

PocketPortal — the Telegram-first foundation that proved the routing,
security, and tool architecture. Portal rebases it as a web-first platform.
