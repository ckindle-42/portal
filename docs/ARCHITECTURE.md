# Portal Architecture

See the build instructions for the full architecture overview.

## Key Components

- **AgentCore**: Central AI processing engine
- **Model Router**: FastAPI proxy at :8000, routes to Ollama
- **WebInterface**: OpenAI-compatible endpoint at :8081
- **MCP Layer**: Tool integration via mcpo/native protocols
- **Interfaces**: Web, Telegram, Slack
