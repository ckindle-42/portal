# Open WebUI MCP Tool Registration

This guide explains how to register Portal's MCP tool servers with Open WebUI for native tool calling support.

## MCP Server Ports

| Service | Port | Description |
|---------|------|-------------|
| Music Generation | 8912 | AudioCraft/MusicGen |
| Document Creation | 8913 | Word/PowerPoint/Excel |
| Code Sandbox | 8914 | Python/Node/Bash execution |
| Text-to-Speech | 8916 | Fish Speech / CosyVoice |

## Registration Steps

### 1. Enable MCP Servers

Ensure the MCP services are running. In docker-compose:

```bash
docker compose up -d mcp-music mcp-documents mcp-tts
```

### 2. Register Each MCP Server in Open WebUI

1. Open Open WebUI at http://localhost:8080
2. Go to **Admin Panel** (gear icon in sidebar)
3. Navigate to **Settings** > **Tools**
4. Click **Add Tool Server**
5. For each service, add:

#### Music Generation
- **Name**: Portal Music
- **URL**: `http://host.docker.internal:8912/mcp`
- **API Key**: (leave empty or set MCP_API_KEY)

#### Document Creation
- **Name**: Portal Documents  
- **URL**: `http://host.docker.internal:8913/mcp`
- **API Key**: (leave empty or set MCP_API_KEY)

#### Code Sandbox
- **Name**: Portal Code
- **URL**: `http://host.docker.internal:8914/mcp`
- **API Key**: (leave empty or set MCP_API_KEY)

#### Text-to-Speech
- **Name**: Portal TTS
- **URL**: `http://host.docker.internal:8916/mcp`
- **API Key**: (leave empty or set MCP_API_KEY)

### 3. Enable Tools in Chat

1. In a new chat, click the **+** icon next to the send button
2. Toggle on the tools you want available
3. Click **Function Calling** and set to **Native** mode

### 4. Test Tools

Try prompts like:
- "Create a document about AI" (triggers document MCP)
- "Generate music with a synthwave beat" (triggers music MCP)
- "Run a Python script to calculate fibonacci" (triggers sandbox MCP)
- "Speak this text aloud" (triggers TTS MCP)

## Troubleshooting

### Connection Failed
- Verify containers are running: `docker ps | grep mcp`
- Check logs: `docker logs portal-mcp-music`
- Ensure host.docker.internal resolves (add to /etc/hosts if needed)

### Tools Not Appearing
- Refresh the page after registration
- Verify Native function calling mode is enabled
- Check browser console for errors

### Authentication Errors
- Set `MCP_API_KEY` in .env and restart containers
- Update the API key in Open WebUI tool settings
