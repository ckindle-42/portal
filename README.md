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

```bash
git clone https://github.com/yourname/portal
cd portal
cp .env.example .env   # edit with your values
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
bash hardware/m4-mac/launch.sh up
```

Then navigate to `http://localhost:8080`.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design.

## Forked From

PocketPortal — the Telegram-first foundation that proved the routing,
security, and tool architecture. Portal rebases it as a web-first platform.
