# Portal Enhancement Implementation Plan

1. Add unified long-term memory module at `portal/memory` with Mem0-first provider selection and SQLite fallback.
2. Inject memory retrieval into AgentCore before model execution for all interfaces.
3. Add OpenAI-compatible endpoint enhancements (`/v1/chat/completions`, streaming, vision auto-model, `/v1/audio/transcriptions`).
4. Add RBAC/quotas datastore (`users`, `api_keys`, `quotas`) and wire into web auth.
5. Add runtime Prometheus metrics (`/metrics`) and dashboard route (`/dashboard`).
6. Add HITL middleware with Redis 60-second approval tokens for dangerous MCP tools.
7. Add pre-bundled MCP sidecar servers for filesystem, bash, and web search/scrape.
8. Add production-ready docker-compose stack for Ollama, Portal API, Open WebUI, Redis, Qdrant, Whisper, and MCP sidecars.
9. Add OpenAPI document and a smoke-test script for clients (Cursor/Continue/Windsurf).
10. Validate with unit tests and endpoint import checks.

## Migration checklist

- Copy `.env.example` to `.env` and set production secrets.
- Run `docker compose up -d --build`.
- Optionally generate API keys from `UserStore.create_api_key` helper.
- Point Open WebUI/LibreChat to `http://portal-api:8081/v1`.
- Update Telegram/Slack to pass user_id header mapping.
- Run `python scripts/test_openai_compat.py`.
