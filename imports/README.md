# Portal Import Files

This directory contains importable configurations for various services used by Portal.

## Open WebUI

Located in `openwebui/`:

| File | Description |
|------|-------------|
| `mcp-servers.json` | MCP tool server configurations |
| `config.env` | Copy-paste friendly config values |

### Importing MCP Servers into Open WebUI

**Option 1: Manual Entry (using config.env)**
1. Open Open WebUI at http://localhost:8080
2. Go to **Admin Panel** > **Settings** > **Tools**
3. Click **Add Tool Server**
4. Enter values from `config.env`

**Option 2: JSON Import**
If Open WebUI supports JSON import for tools, use `mcp-servers.json`:
1. Look for an **Import** button in the Tools settings
2. Select `mcp-servers.json`

### MCP Server Ports

| Service | Port | Description |
|---------|------|-------------|
| Music Generation | 8912 | AudioCraft/MusicGen |
| Document Creation | 8913 | Word/PowerPoint/Excel |
| Code Sandbox | 8914 | Python/Node/Bash execution |
| Text-to-Speech | 8916 | Fish Speech / CosyVoice |

Note: On macOS, use `host.docker.internal`. On Linux, you may need to use the host machine's IP address instead.