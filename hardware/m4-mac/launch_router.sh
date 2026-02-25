#!/bin/bash
# Portal services launcher — M4 Mac
# Starts the model router (:8000) and Portal web interface (:8081).
set -euo pipefail

PORTAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROUTER_DIR="$PORTAL_ROOT/src/portal/routing"
ROUTER_VENV="$PORTAL_ROOT/.venv"
PID_FILE="/tmp/portal-router.pid"
LOG_FILE="$HOME/.portal/logs/router.log"
WEB_PID_FILE="/tmp/portal-web.pid"
WEB_LOG_FILE="$HOME/.portal/logs/portal.log"

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

BIND_IP="${ROUTER_BIND_IP:-127.0.0.1}"
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
if curl -s "http://$BIND_IP:$PORT/health" >/dev/null 2>&1; then
    echo "[portal-router] health check OK"
else
    echo "[portal-router] WARNING: health check failed — check $LOG_FILE"
fi

# ── Portal web interface (:8081) ──────────────────────────────────────────────
mkdir -p "$(dirname "$WEB_LOG_FILE")"

if [ -f "$WEB_PID_FILE" ] && kill -0 "$(cat "$WEB_PID_FILE")" 2>/dev/null; then
    echo "[portal-web] already running (PID $(cat "$WEB_PID_FILE"))"
else
    echo "[portal-web] starting..."
    WEB_PORT="${WEB_PORT:-8081}"
    nohup uvicorn portal.interfaces.web.server:app \
        --host 0.0.0.0 \
        --port "$WEB_PORT" \
        --workers 1 \
        --app-dir "$PORTAL_ROOT/src" \
        >> "$WEB_LOG_FILE" 2>&1 &
    echo $! > "$WEB_PID_FILE"
    echo "[portal-web] started (PID $(cat "$WEB_PID_FILE")) on 0.0.0.0:$WEB_PORT"

    sleep 2
    if curl -s "http://localhost:$WEB_PORT/health" >/dev/null 2>&1; then
        echo "[portal-web] health check OK"
    else
        echo "[portal-web] WARNING: health check failed — check $WEB_LOG_FILE"
    fi
fi
