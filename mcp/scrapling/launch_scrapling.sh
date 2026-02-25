#!/bin/bash
# Launch Scrapling MCP server
# Requires: Python 3.11+, scrapling package installed
set -euo pipefail

PORTAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PID_FILE="/tmp/portal-scrapling.pid"
LOG_FILE="$HOME/.portal/logs/scrapling.log"
PORT="${SCRAPLING_PORT:-8900}"

mkdir -p "$(dirname "$LOG_FILE")"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[scrapling] already running (PID $(cat "$PID_FILE"))"
    exit 0
fi

source "$PORTAL_ROOT/.venv/bin/activate"

# Scrapling runs as a standalone HTTP MCP server
nohup python -m scrapling.mcp --port "$PORT" >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
echo "[scrapling] started on :$PORT (PID $(cat "$PID_FILE"))"
