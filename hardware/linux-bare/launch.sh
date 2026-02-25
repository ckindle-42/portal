#!/bin/bash
# Portal Unified Launcher — Linux Bare Metal
# Usage: ./launch.sh [up|down|doctor|logs] [--minimal]
set -euo pipefail

PORTAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOG_DIR="$HOME/.portal/logs"
mkdir -p "$LOG_DIR"

# Load environment
if [ -f "$PORTAL_ROOT/.env" ]; then
    set -a; source "$PORTAL_ROOT/.env"; set +a
fi

COMMAND="${1:-up}"
MINIMAL="${2:-}"
WEB_UI="${WEB_UI:-openwebui}"
GENERATION_SERVICES="${GENERATION_SERVICES:-false}"
DOCKER_HOST_IP="${DOCKER_HOST_IP:-172.17.0.1}"

case "$COMMAND" in
  up)
    echo "=== Portal Starting (Linux Bare Metal) ==="

    # 1. Ensure Ollama is running
    if ! pgrep -x "ollama" >/dev/null; then
        echo "[ollama] starting via systemd..."
        sudo systemctl start ollama 2>/dev/null || nohup ollama serve >> "$LOG_DIR/ollama.log" 2>&1 &
        sleep 2
    fi
    echo "[ollama] OK"

    # 2. Start model router
    bash "$PORTAL_ROOT/hardware/linux-bare/launch_router.sh"

    if [ "$MINIMAL" != "--minimal" ]; then
        # 3. Start Docker stack (web UI)
        DEPLOY_DIR="$PORTAL_ROOT/deploy/web-ui/$WEB_UI"
        echo "[docker] starting $WEB_UI stack..."
        (cd "$DEPLOY_DIR" && \
            DOCKER_HOST_IP="$DOCKER_HOST_IP" \
            AI_OUTPUT_DIR="$HOME/AI_Output" \
            docker compose up -d)
        echo "[docker] OK"

        # 4. Start mcpo (Open WebUI path only)
        if [ "$WEB_UI" = "openwebui" ] && [ "${MCP_ENABLED:-true}" = "true" ]; then
            bash "$PORTAL_ROOT/mcp/scrapling/launch_scrapling.sh" || true
            if ! pgrep -f "mcpo" >/dev/null; then
                echo "[mcpo] starting..."
                uvx mcpo \
                    --port "${MCPO_PORT:-9000}" \
                    --api-key "${MCP_API_KEY:-changeme-mcp-secret}" \
                    --config "$PORTAL_ROOT/mcp/core/mcp_servers.json" \
                    >> "$LOG_DIR/mcpo.log" 2>&1 &
                echo "[mcpo] OK (PID $!)"
            fi
        fi

        # 5. Start generation MCP wrappers (Linux default: false)
        if [ "$GENERATION_SERVICES" = "true" ]; then
            bash "$PORTAL_ROOT/mcp/generation/launch_generation_mcps.sh" || true
        fi
    fi

    echo ""
    echo "=== Portal Running ==="
    echo "  Web UI:      http://localhost:8080"
    echo "  Router:      http://$DOCKER_HOST_IP:8000/health"
    echo "  Portal API:  http://localhost:8081/health"
    ;;

  down)
    echo "=== Portal Stopping ==="
    (cd "$PORTAL_ROOT/deploy/web-ui/$WEB_UI" && docker compose down) 2>/dev/null || true
    [ -f /tmp/portal-web.pid ]    && kill "$(cat /tmp/portal-web.pid)"    2>/dev/null || true
    [ -f /tmp/portal-router.pid ] && kill "$(cat /tmp/portal-router.pid)" 2>/dev/null || true
    pkill -f "mcpo" 2>/dev/null || true
    rm -f /tmp/portal-web.pid /tmp/portal-router.pid
    echo "=== Portal Stopped ==="
    ;;

  doctor)
    echo "=== Portal Doctor ==="
    curl -s http://localhost:11434/api/tags >/dev/null && echo "[ollama] OK" || echo "[ollama] FAIL"
    curl -s "http://$DOCKER_HOST_IP:8000/health" >/dev/null && echo "[router] OK" || echo "[router] FAIL"
    curl -s http://localhost:8081/health >/dev/null && echo "[portal-api] OK" || echo "[portal-api] FAIL"
    curl -s http://localhost:8080 >/dev/null && echo "[web-ui] OK" || echo "[web-ui] FAIL"
    ;;

  logs)
    SERVICE="${2:-portal}"
    LOG_FILE="$LOG_DIR/${SERVICE}.log"
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo "No log file for service: $SERVICE"
        echo "Available: $(ls "$LOG_DIR" 2>/dev/null | sed 's/\.log//' | tr '\n' ' ')"
    fi
    ;;

  *)
    echo "Usage: launch.sh [up|down|doctor|logs] [--minimal]"
    exit 1
    ;;
esac
