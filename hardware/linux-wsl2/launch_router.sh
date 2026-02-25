#!/bin/bash
# Portal model router launcher — Linux WSL2
# Wraps the FastAPI router from src/portal/routing/router.py
set -euo pipefail

PORTAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROUTER_VENV="$PORTAL_ROOT/.venv"
PID_FILE="/tmp/portal-router.pid"
LOG_FILE="$HOME/.portal/logs/router.log"

mkdir -p "$(dirname "$LOG_FILE")"

# Early exit if already running
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[portal-router] already running (PID $(cat "$PID_FILE"))"
    exit 0
fi

# Load .env if present
if [ -f "$PORTAL_ROOT/.env" ]; then
    set -a; source "$PORTAL_ROOT/.env"; set +a
fi

source "$ROUTER_VENV/bin/activate"

# Wait for Ollama
echo -n "[portal-router] waiting for Ollama..."
until curl -s http://localhost:11434/api/tags >/dev/null 2>&1; do
    sleep 1; echo -n "."
done
echo " ready"

BIND_IP="${ROUTER_BIND_IP:-0.0.0.0}"
PORT="${ROUTER_PORT:-8000}"

nohup uvicorn portal.routing.router:app \
    --host "$BIND_IP" \
    --port "$PORT" \
    --app-dir "$PORTAL_ROOT/src" \
    >> "$LOG_FILE" 2>&1 &

echo $! > "$PID_FILE"
echo "[portal-router] started (PID $(cat "$PID_FILE")) on $BIND_IP:$PORT"

# Health check
sleep 2
if curl -s "http://localhost:$PORT/health" >/dev/null 2>&1; then
    echo "[portal-router] health check OK"
else
    echo "[portal-router] WARNING: health check failed — check $LOG_FILE"
fi
