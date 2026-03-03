# Portal + Open WebUI Setup Guide

This guide covers the complete setup for running Portal with Open WebUI using the hybrid architecture.

## Architecture Overview

Portal provides the AI brain (routing, classification, MCP tools), while Open WebUI handles the UI (image generation, tool calling, TTS, RAG).

**Key change:** Open WebUI connects ONLY to Portal (not direct Ollama). This ensures all requests go through Portal's intelligent routing.

---

## Quick Start

### 1. Start the Stack

```bash
cd deploy/web-ui/openwebui
docker compose up -d
```

Wait for all services to be healthy (~30 seconds).

### 2. Create Admin Account

1. Open http://localhost:8080
2. Click **Sign Up**
3. Enter email and password
4. **First user becomes admin automatically**

---

## Configure Image Generation (ComfyUI)

Portal supports FLUX, SDXL, and Wan2.2 video generation via ComfyUI.

### Start ComfyUI

```bash
# In a separate terminal
cd deploy/comfyui
docker compose up -d
```

### Configure Open WebUI

1. Go to **Admin Panel** > **Settings** > **Images**
2. Enable **Enable Image Generation**
3. Select **ComfyUI** as the engine
4. Enter ComfyUI URL: `http://host.docker.internal:8188`

### Upload Workflows (Optional)

For custom workflows:

1. Download workflow JSONs from `workflows/` directory
2. In Open WebUI Images settings, upload each JSON
3. Map node IDs if prompted (see `workflows/README.md`)

### Test Image Generation

Send a prompt like:
- "A futuristic city at sunset, cinematic"
- "A cat sitting on a windowsill, photorealistic"

Images appear inline in the chat.

---

## Configure MCP Tools

Portal provides MCP servers for music, documents, code sandbox, and TTS.

### Start MCP Services

```bash
docker compose up -d mcp-music mcp-documents mcp-tts
```

### Register in Open WebUI

1. Go to **Admin Panel** > **Settings** > **Tools**
2. Click **Add Tool Server** for each:

| Name | URL |
|------|-----|
| Portal Music | http://host.docker.internal:8912/mcp |
| Portal Documents | http://host.docker.internal:8913/mcp |
| Portal Code | http://host.docker.internal:8914/mcp |
| Portal TTS | http://host.docker.internal:8916/mcp |

3. Click **Save**

### Enable Tools in Chat

1. In chat, click the **+** icon next to the send button
2. Toggle on desired tools
3. Set **Function Calling** to **Native** mode

### Test Tools

- "Generate a synthwave music clip"
- "Create a Word document about AI"
- "Run Python code: print('Hello')"

---

## Configure Text-to-Speech

1. Go to **Admin Panel** > **Settings** > **Audio**
2. Enable TTS provider
3. Set to use Portal's TTS endpoint or native Open WebUI TTS

---

## Workspaces & Personas

Portal provides intelligent workspace routing:

| Workspace | Purpose |
|-----------|---------|
| auto | Auto-select best model |
| auto-coding | Code generation |
| auto-security | Security tasks |
| auto-creative | Creative writing |
| auto-reasoning | Complex reasoning |
| auto-documents | Document creation |
| auto-video | Video generation |
| auto-music | Music generation |
| auto-research | Web research |

### Select Workspace

Use the workspace dropdown in the chat header to switch between modes.

---

## Model Selection

When connected only to Portal, the model dropdown shows:

- **Workspace models** (e.g., `auto`, `auto-coding`) — trigger intelligent routing
- **Persona models** — switch persona for different interaction styles

**Do NOT select raw Ollama models** (e.g., `llama3.2:3b`) — these bypass Portal's routing and tools.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBUI_AUTH` | `true` | Enable authentication |
| `WEBUI_SECRET_KEY` | auto-generated | Session secret |
| `ENABLE_IMAGE_GENERATION` | `true` | Enable ComfyUI images |
| `IMAGE_GENERATION_ENGINE` | `comfyui` | Image engine |
| `COMFYUI_BASE_URL` | host.docker.internal:8188 | ComfyUI API |

Override in `.env`:
```bash
WEBUI_AUTH=false docker compose up -d
```

---

## Troubleshooting

### Tools Not Working
- Verify MCP containers running: `docker ps | grep mcp`
- Check logs: `docker logs portal-mcp-music`
- Ensure Native function calling mode enabled

### Image Generation Failed
- Verify ComfyUI running: `docker ps | grep comfyui`
- Check ComfyUI logs: `docker logs portal-comfyui`
- Verify COMFYUI_BASE_URL is correct

### Can't See Models
- Portal should be sole model source (no OLLAMA_BASE_URL)
- Check Portal health: `curl http://localhost:8081/health`
- Refresh Open WebUI

### Connection Issues
- Ensure host.docker.internal resolves
- Check firewall settings

---

## Access Points

| Service | URL |
|---------|-----|
| Open WebUI | http://localhost:8080 |
| Portal API | http://localhost:8081 |
| ComfyUI | http://localhost:8188 |
| Music MCP | http://localhost:8912 |
| Documents MCP | http://localhost:8913 |
| TTS MCP | http://localhost:8916 |

---

## Reset

To reset all data:
```bash
docker compose down
docker volume rm deploy_web-ui_openwebui_open-webui-data
docker compose up -d
```