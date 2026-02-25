# PocketPortal - Installation & Setup Guide

**Production-Grade AI Agent Platform - Complete Setup in 30 Minutes**

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Installation](#quick-installation)
3. [Configuration](#configuration)
4. [Verification](#verification)
5. [Running PocketPortal](#running-pocketportal)
6. [Optional Features](#optional-features)
7. [Troubleshooting](#troubleshooting)
8. [Production Deployment](#production-deployment)

---

## Prerequisites

### System Requirements

**Minimum:**
- Python 3.11 or 3.12
- 8GB RAM (16GB recommended)
- 20GB free disk space (50GB+ recommended for models)
- Linux, macOS, or Windows with WSL2

**Recommended for Production:**
- Python 3.12
- 32GB RAM (64GB+ for multiple models)
- 100GB+ free disk space
- Ubuntu 22.04 LTS or macOS 14+

### Check Your System

```bash
# Verify Python version
python3 --version
# Output should be: Python 3.11.x or Python 3.12.x

# Check available disk space
df -h ~
# Should show at least 20GB free

# Check memory (Linux)
free -h
# Or on macOS
sysctl hw.memsize
```

### Required External Dependencies

**1. LLM Backend (Choose One)**

**Option A: Ollama (Recommended)**
```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama
ollama serve

# Pull a model (in a new terminal)
ollama pull qwen2.5:7b-instruct-q4_K_M
```

**Option B: LM Studio**
- Download from https://lmstudio.ai/
- Install and start the local server
- Download your preferred model

**Option C: MLX (Apple Silicon Only)**
- Automatically installed with optional dependencies
- Best performance on M1/M2/M3 Macs

---

## Quick Installation

### Step 1: Clone or Extract the Repository

```bash
# Clone from Git
git clone https://github.com/ckindle-42/pocketportal.git
cd pocketportal

# Or if you have a release tarball
tar -xzf pocketportal-<version>.tar.gz
cd pocketportal-<version>
```

### Step 2: Install PocketPortal

**Basic Installation (Core Features)**
```bash
pip install -e .
```

**Full Installation (All Features)**
```bash
pip install -e ".[all]"
```

**Custom Installation (Select Features)**
```bash
# Install specific feature sets
pip install -e ".[tools,data,documents,audio]"

# Available feature sets:
# - tools: Basic tool support (QR, images, web scraping)
# - data: Data processing (pandas, numpy, matplotlib)
# - documents: Document processing (Word, Excel, PowerPoint, PDF)
# - audio: Audio transcription (Whisper)
# - knowledge: Knowledge base and RAG (semantic search)
# - automation: Scheduling and cron
# - browser: Browser automation (Playwright)
# - mlx: Apple Silicon acceleration
# - mcp: Model Context Protocol
# - security: Docker sandboxing
# - observability: OpenTelemetry, Prometheus
# - distributed: Redis for distributed features
# - dev: Development tools (pytest, black, ruff, mypy)
# - all: Everything above
```

**Tool categories and required extras**

The `pocketportal list-tools` output is grouped by tool category. Use this mapping to install
the extras needed for each category:

| Tool category | Extra(s) | Notes |
| --- | --- | --- |
| utility | `tools`, `documents` | QR/image utilities use `tools`; document conversion utilities use `documents`. |
| data | `data`, `documents` | Data analysis tools use `data`; Excel processing uses `documents`. |
| web | (core) | Web/HTTP tools rely on core dependencies. |
| audio | `audio` | Audio transcription tools. |
| automation | `automation` | Scheduling and cron tools. |
| knowledge | `knowledge` | RAG and embedding tools. |
| dev | `security` | Docker tools require `security`; Git tools use system `git`. |

### Step 3: Verify Installation

```bash
# Check that PocketPortal CLI is available
pocketportal --help

# You should see the command-line interface help
```

---

## Configuration

### Configuration Precedence Hierarchy

**IMPORTANT:** PocketPortal loads configuration from multiple sources with the following priority order (highest to lowest):

1. **Environment Variables** (highest priority)
   - Loaded from system environment or `.env` file
   - Example: `TELEGRAM_BOT_TOKEN`, `OLLAMA_HOST`, `LOG_LEVEL`
   - Best for: Secrets, deployment-specific settings, Docker/Kubernetes

2. **Configuration File** (`config.yaml`)
   - Loaded from `~/.config/pocketportal/config.yaml` or `POCKETPORTAL_CONFIG_DIR`
   - Example: Interface settings, LLM backends, tool configurations
   - Best for: Structured settings, production deployments

3. **Default Values** (lowest priority)
   - Built-in defaults defined in code
   - Example: `LOG_LEVEL=INFO`, `RATE_LIMIT_MESSAGES_PER_MINUTE=30`
   - Best for: Sensible defaults that work out-of-the-box

**Configuration Resolution Example:**
```bash
# If you have:
# - Default: LOG_LEVEL=INFO
# - config.yaml: LOG_LEVEL=DEBUG
# - Environment: LOG_LEVEL=ERROR

# Result: LOG_LEVEL=ERROR (environment wins)
```

**Startup Logging:**
PocketPortal logs the active configuration source at startup:
```
INFO - Configuration loaded from: environment variables
INFO - Using LLM backend: ollama (http://localhost:11434)
INFO - Log level: INFO (from environment)
```

### Recommended Dependency Groups

**For Production Deployments:**
```bash
# Minimal production image (excludes dev tools)
pip install -e ".[tools,data,documents,audio,knowledge,mcp,observability,distributed]"

# This excludes:
# - dev: pytest, black, ruff, mypy (development tools)
# - browser: Playwright (heavy dependency, ~200MB)
# - security: Docker client (if sandboxing not needed)
```

**For Development:**
```bash
# Full installation including dev tools
pip install -e ".[all]"
```

### Step 1: Create Configuration Directory

```bash
# Create config directory
mkdir -p ~/.config/pocketportal

# Or use environment variable to set custom location
export POCKETPORTAL_CONFIG_DIR=/path/to/config
```

### Step 2: Get Telegram Bot Token (For Telegram Interface)

1. Open Telegram and message **@BotFather**
2. Send: `/newbot`
3. Follow the prompts to choose a bot name and username
4. **Copy the token** (format: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Get your Telegram User ID from **@userinfobot**

### Step 3: Create Configuration File

**Option A: Environment Variables (.env file)**

```bash
# Create .env file
cat > .env << 'EOF'
# Required: Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_USER_ID=your_user_id_here

# Required: LLM Backend Configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b-instruct-q4_K_M

# Optional: Alternative LLM Backends
# LM_STUDIO_HOST=http://localhost:1234
# MLX_MODEL=mlx-community/Qwen2.5-7B-Instruct-4bit

# Optional: Rate Limiting
RATE_LIMIT_MESSAGES_PER_MINUTE=30
RATE_LIMIT_TOKENS_PER_HOUR=100000

# Optional: Observability
ENABLE_TELEMETRY=false
ENABLE_METRICS=false
LOG_LEVEL=INFO

# Optional: Watchdog & Reliability
WATCHDOG_ENABLED=true
LOG_ROTATION_ENABLED=true
CIRCUIT_BREAKER_ENABLED=true
EOF

# Edit the file with your actual values
nano .env
```

**Option B: YAML Configuration (config.yaml)**

```bash
# Create config.yaml
cat > ~/.config/pocketportal/config.yaml << 'EOF'
# PocketPortal Configuration

interfaces:
  telegram:
    enabled: true
    bot_token: "YOUR_BOT_TOKEN_HERE"
    allowed_user_ids:
      - YOUR_USER_ID_HERE

  web:
    enabled: false
    host: "0.0.0.0"
    port: 8000
    cors_origins:
      - "http://localhost:3000"

llm:
  default_backend: "ollama"
  ollama:
    host: "http://localhost:11434"
    model: "qwen2.5:7b-instruct-q4_K_M"
    timeout: 120
  circuit_breaker_enabled: true

security:
  rate_limit:
    messages_per_minute: 30
    tokens_per_hour: 100000
  sandbox:
    enabled: false
    docker_image: "python:3.11-slim"

observability:
  logging:
    level: "INFO"
    format: "json"
  watchdog:
    enabled: true
    check_interval: 60
  log_rotation:
    enabled: true
    max_bytes: 10485760  # 10MB
    backup_count: 5

shutdown_timeout_seconds: 30
EOF

# Edit with your values
nano ~/.config/pocketportal/config.yaml
```

### Step 4: Validate Configuration

```bash
# Validate your configuration
pocketportal validate-config

# Expected output:
# ✅ Configuration validation passed
# ✅ All required settings present
# ✅ Telegram bot token format valid
# ✅ LLM backend reachable
```

---

## Verification

### System Health Check

```bash
# Run quick readiness/liveness health check
pocketportal health

# Expected output shows system status and validation results
```

For a comprehensive dependency and system check, run `pocketportal verify`.

### List Available Tools

```bash
# List all available tools
pocketportal list-tools

# Expected output shows all installed tools with descriptions
```

### Test LLM Connection

You can verify LLM connectivity by running the agent and sending a test message through the configured interface (Telegram or Web).

---

## Running PocketPortal

### Start Telegram Interface

```bash
# Start PocketPortal with Telegram interface
pocketportal start --interface telegram

# You should see:
# INFO - Starting PocketPortal <version>
# INFO - Initializing Telegram interface
# INFO - Bot started: @YourBotName
# INFO - Loaded 33 tools
# INFO - Waiting for messages...
```

### Start Web Interface

**Note:** The web interface currently requires running directly via uvicorn:

```bash
# Start the web interface (FastAPI app)
uvicorn pocketportal.interfaces.web.server:app --host 0.0.0.0 --port 8000

# You should see:
# INFO:     Started server process
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:8000
```

Open your browser and navigate to `http://localhost:8000`

**Why not `pocketportal start --interface web`?**
The web interface is currently implemented as a standalone FastAPI application, not wrapped in the BaseInterface pattern. This is being tracked for future implementation.

### Start All Interfaces

```bash
# Start all configured interfaces (currently only Telegram)
pocketportal start --all

# Note: Currently only starts Telegram interface
# Web interface must be started separately via uvicorn (see above)
```

### Background Mode

To run PocketPortal in the background, use standard Unix tools:

```bash
# Start in background using nohup
nohup pocketportal start --interface telegram > pocketportal.log 2>&1 &

# Check if running
ps aux | grep pocketportal

# Stop
pkill -f pocketportal
```

For production deployments, see the [Production Deployment](#production-deployment) section for systemd/launchd service configuration.

---

## Optional Features

### 1. Enable Observability

```bash
# Install observability dependencies
pip install -e ".[observability]"

# Enable in configuration
cat >> .env << 'EOF'
ENABLE_TELEMETRY=true
ENABLE_METRICS=true
ENABLE_HEALTH_CHECKS=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
EOF

# Start with observability
pocketportal start --interface telegram

# Metrics available at http://localhost:8000/metrics (when ENABLE_METRICS=true)
# Health checks at http://localhost:8000/health (when ENABLE_HEALTH_CHECKS=true)
```

### 2. Enable MCP (Model Context Protocol)

```bash
# Install MCP support
pip install -e ".[mcp]"

# Note: MCP server CLI command not yet implemented
# MCP server functionality available via Python API
# See docs/PLUGIN_DEVELOPMENT.md for MCP server setup
```

### 3. Enable Docker Sandboxing

```bash
# Install security features
pip install -e ".[security]"

# Verify Docker is running
docker ps

# Enable in configuration
cat >> .env << 'EOF'
POCKETPORTAL_SANDBOX_ENABLED=true
POCKETPORTAL_SANDBOX_TIMEOUT_SECONDS=30
EOF
```

**Note:** Docker image for sandbox is hardcoded in the implementation. Custom image configuration is tracked for future enhancement.

### 4. Install Additional Models

```bash
# Fast model (good for simple queries)
ollama pull qwen2.5:3b-instruct-q4_K_M

# Balanced model (recommended)
ollama pull qwen2.5:7b-instruct-q4_K_M

# High quality model (best reasoning)
ollama pull qwen2.5:14b-instruct-q4_K_M

# Code specialist
ollama pull qwen2.5-coder:7b-instruct-q4_K_M

# List installed models
ollama list
```

---

## Troubleshooting

### Issue: "Command not found: pocketportal"

```bash
# Ensure pip install completed successfully
pip install -e .

# Check if script is in PATH
which pocketportal

# If not found, use full path
python -m pocketportal.cli --help
```

### Issue: "Cannot connect to Ollama"

```bash
# Verify Ollama is running
curl http://localhost:11434/api/tags

# If not running, start Ollama
ollama serve

# Check firewall settings
# Ensure port 11434 is not blocked
```

### Issue: "Telegram bot not responding"

```bash
# Verify bot token
grep TELEGRAM_BOT_TOKEN .env

# Test bot token with curl
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe

# Check user ID is correct
# Message @userinfobot to get your correct user ID
```

### Issue: "Import errors after installation"

```bash
# The project uses strict src-layout (v4.6.0+)
# You MUST install the package:
pip install -e .

# Direct Python file execution will NOT work
# Always use: pocketportal <command>
```

### Issue: "Database locked" errors

```bash
# Stop all PocketPortal instances
pkill -f pocketportal

# Remove lock files
rm ~/.local/share/pocketportal/*.db-wal
rm ~/.local/share/pocketportal/*.db-shm

# Restart
pocketportal start --interface telegram
```

### Issue: "Memory leaks / High RAM usage"

```bash
# Check EventBus history setting (v4.5.1+)
# EventBus history is now opt-in by default
# Long-running agents should NOT enable history

# Restart the agent periodically
# Use systemd or launchd for automatic restarts
```

---

## Production Deployment

### systemd Service (Linux)

```bash
# Create service file
sudo nano /etc/systemd/system/pocketportal.service
```

```ini
[Unit]
Description=PocketPortal AI Agent Platform
After=network.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME/pocketportal
Environment="PATH=/home/YOUR_USERNAME/pocketportal/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=/home/YOUR_USERNAME/pocketportal/venv/bin/pocketportal start --interface telegram
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Watchdog and monitoring
WatchdogSec=300
NotifyAccess=all

# Resource limits
MemoryMax=4G
CPUQuota=200%

[Install]
WantedBy=multi-user.target
```

```bash
# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable pocketportal
sudo systemctl start pocketportal

# Check status
sudo systemctl status pocketportal

# View logs
sudo journalctl -u pocketportal -f
```

### launchd Service (macOS)

```bash
# Create plist file
nano ~/Library/LaunchAgents/com.pocketportal.agent.plist
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.pocketportal.agent</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/pocketportal</string>
        <string>start</string>
        <string>--interface</string>
        <string>telegram</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/pocketportal</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/pocketportal/logs/stdout.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/pocketportal/logs/stderr.log</string>
</dict>
</plist>
```

```bash
# Load service
launchctl load ~/Library/LaunchAgents/com.pocketportal.agent.plist

# Check status
launchctl list | grep pocketportal

# View logs
tail -f ~/pocketportal/logs/stdout.log
```

### Docker Deployment

```bash
# Create Dockerfile
cat > Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application
COPY . /app

# Install PocketPortal
RUN pip install -e ".[all]"

# Health check (using health command)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD pocketportal health || exit 1

# Run application
CMD ["pocketportal", "start", "--all"]
EOF

# Build image
docker build -t pocketportal:latest .

# Run container
docker run -d \
    --name pocketportal \
    --restart unless-stopped \
    -e TELEGRAM_BOT_TOKEN=your_token \
    -e TELEGRAM_USER_ID=your_id \
    -e OLLAMA_HOST=http://host.docker.internal:11434 \
    -v pocketportal-data:/root/.local/share/pocketportal \
    pocketportal:latest

# Check logs
docker logs -f pocketportal
```

---

## Next Steps

### Testing Your Setup

```bash
# 1. Message your Telegram bot
# Open Telegram and send: /start

# 2. Test basic queries
# Send: "Hello!"
# Send: "What's 2+2?"

# 3. Test tools
# Send: "Generate a QR code for https://example.com"
# Send: "Show system stats"

# 4. Test help
# Send: /help
```

### Monitoring

```bash
# View queue status
pocketportal queue stats

# View system health
pocketportal health

# View metrics (requires ENABLE_METRICS=true for the web server)
curl http://localhost:8000/metrics

# Monitor logs (if running in background with nohup)
tail -f pocketportal.log
```

### Upgrading

```bash
# Pull latest code
git pull origin main

# Reinstall
pip install -e ".[all]" --upgrade

# Verify version
pocketportal --version

# Restart (if running in background)
pkill -f pocketportal
nohup pocketportal start --interface telegram > pocketportal.log 2>&1 &
```

---

## Documentation

- **Architecture**: [docs/architecture.md](./architecture.md)
- **Changelog**: [CHANGELOG.md](../CHANGELOG.md)
- **Legacy v3.x Setup**: [docs/archive/SETUP_V3.md](./archive/SETUP_V3.md)
- **Security**: [docs/security/](./security/)

---

## Support

- **Issues**: https://github.com/ckindle-42/pocketportal/issues
- **Documentation**: https://github.com/ckindle-42/pocketportal/tree/main/docs

---

**Last Updated**: December 2025
**Installation Time**: ~30 minutes

**Welcome to PocketPortal - Your Privacy-First AI Agent Platform!** 🚀
