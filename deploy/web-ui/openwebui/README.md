# Open WebUI Setup

## First-Time Setup (2 minutes)

1. **Start the stack:**
   ```bash
   cd deploy/web-ui/openwebui
   docker compose up -d
   ```

2. **Create admin user:**
   - Open http://localhost:8080
   - Click **Sign Up**
   - Enter any email/password
   - **First user becomes admin automatically**

3. **Create workspaces (as admin):**
   - Click your username (bottom left) → **Admin Panel**
   - Go to **Workspaces**
   - Click **+ New Workspace**
   - Configure name, models, users

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WEBUI_AUTH` | `true` | Enable user authentication |
| `WEBUI_SECRET_KEY` | auto-generated | Session secret |
| `OLLAMA_BASE_URL` | host.docker.internal:11434 | Ollama server |

Override in `.env` or docker-compose:
```bash
WEBUI_AUTH=false docker compose up -d  # Disable auth (no workspaces)
```

## Access

- **Open WebUI:** http://localhost:8080
- **Portal API:** http://localhost:8081 (proxied via Caddy at /portal)
- **Generated files:** http://localhost:8080/images, /audio, /docs, etc.

## Reset

To reset users/workspaces:
```bash
docker compose down
docker volume rm portal-open-webui-data
docker compose up -d
```
