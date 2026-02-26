#!/bin/bash
# Portal Unified Launcher — zero-config bootstrap & multi-platform management
# Usage: bash launch.sh [up|down|doctor|logs|status|reset-secrets] [--minimal] [--profile X]
set -euo pipefail

PORTAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$HOME/.portal/logs"
mkdir -p "$LOG_DIR"

# ─── Secret generation ────────────────────────────────────────────────────────
generate_secret() {
    # Works on macOS (LibreSSL) and Linux (OpenSSL)
    openssl rand -base64 32 | tr -d '/+=' | head -c 43
}

# ─── Hardware auto-detection ──────────────────────────────────────────────────
detect_hardware_profile() {
    # Explicit override always wins
    if [ -n "${PORTAL_HARDWARE:-}" ]; then
        echo "$PORTAL_HARDWARE"
        return
    fi

    case "$(uname -s)" in
        Darwin)
            echo "m4-mac"
            ;;
        Linux)
            if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null; then
                echo "linux-wsl2"
            else
                echo "linux-bare"
            fi
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# ─── Apply profile defaults (non-destructive — only fills gaps) ───────────────
apply_profile_defaults() {
    local profile="$1"
    case "$profile" in
        m4-mac)
            : "${COMPUTE_BACKEND:=mps}"
            : "${DOCKER_HOST_IP:=host.docker.internal}"
            : "${SUPERVISOR_TYPE:=launchagent}"
            : "${GENERATION_SERVICES:=true}"
            : "${ROUTER_BIND_IP:=127.0.0.1}"
            ;;
        linux-bare)
            : "${COMPUTE_BACKEND:=cuda}"
            : "${DOCKER_HOST_IP:=172.17.0.1}"
            : "${SUPERVISOR_TYPE:=systemd}"
            : "${GENERATION_SERVICES:=false}"
            : "${ROUTER_BIND_IP:=172.17.0.1}"
            ;;
        linux-wsl2)
            : "${COMPUTE_BACKEND:=cuda}"
            : "${DOCKER_HOST_IP:=0.0.0.0}"
            : "${SUPERVISOR_TYPE:=nohup}"
            : "${GENERATION_SERVICES:=false}"
            : "${ROUTER_BIND_IP:=0.0.0.0}"
            ;;
    esac

    # Ollama start command varies by profile
    case "$profile" in
        m4-mac)
            OLLAMA_START="brew services start ollama 2>/dev/null || nohup ollama serve >> \"$LOG_DIR/ollama.log\" 2>&1 &"
            ;;
        linux-bare)
            OLLAMA_START="sudo systemctl start ollama 2>/dev/null || nohup ollama serve >> \"$LOG_DIR/ollama.log\" 2>&1 &"
            ;;
        *)
            OLLAMA_START="nohup ollama serve >> \"$LOG_DIR/ollama.log\" 2>&1 &"
            ;;
    esac

    export COMPUTE_BACKEND DOCKER_HOST_IP SUPERVISOR_TYPE GENERATION_SERVICES ROUTER_BIND_IP
}

# ─── Interactive first-run bootstrap ─────────────────────────────────────────
bootstrap_env() {
    local profile="$1"
    local env_file="$PORTAL_ROOT/.env"

    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║         Portal — First-Time Setup                ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
    echo "  Detected hardware: $profile"
    echo "  All secrets will be auto-generated."
    echo "  This takes about 30 seconds."
    echo ""

    # --- Web UI choice ---
    echo "Which web UI do you want?"
    echo "  1) Open WebUI  (recommended, full-featured)  [default]"
    echo "  2) LibreChat   (multi-provider, plugin ecosystem)"
    echo ""
    read -rp "Choice [1]: " ui_choice
    case "${ui_choice:-1}" in
        2|librechat|LibreChat) WEB_UI="librechat" ;;
        *) WEB_UI="openwebui" ;;
    esac
    echo "  -> $WEB_UI"
    echo ""

    # --- Telegram (optional) ---
    TELEGRAM_ENABLED="false"
    TELEGRAM_BOT_TOKEN=""
    TELEGRAM_USER_IDS=""
    read -rp "Enable Telegram bot? [y/N]: " tg_enable
    if [[ "${tg_enable,,}" =~ ^y ]]; then
        TELEGRAM_ENABLED="true"
        read -rp "  Telegram bot token (from @BotFather): " TELEGRAM_BOT_TOKEN
        read -rp "  Authorized user IDs (comma-separated): " TELEGRAM_USER_IDS
        echo ""
    fi

    # --- Slack (optional) ---
    SLACK_ENABLED="false"
    SLACK_BOT_TOKEN=""
    SLACK_SIGNING_SECRET_VAL=""
    read -rp "Enable Slack bot? [y/N]: " slack_enable
    if [[ "${slack_enable,,}" =~ ^y ]]; then
        SLACK_ENABLED="true"
        read -rp "  Slack bot token (xoxb-...): " SLACK_BOT_TOKEN
        read -rp "  Slack signing secret: " SLACK_SIGNING_SECRET_VAL
        echo ""
    fi

    # --- Auto-generate all secrets ---
    echo "Generating secrets..."
    local MCP_API_KEY PORTAL_BOOTSTRAP_API_KEY WEB_API_KEY
    local WEBUI_SECRET_KEY JWT_SECRET JWT_REFRESH_SECRET

    MCP_API_KEY="$(generate_secret)"
    PORTAL_BOOTSTRAP_API_KEY="$(generate_secret)"
    WEB_API_KEY="$(generate_secret)"
    WEBUI_SECRET_KEY="$(generate_secret)"
    JWT_SECRET="$(generate_secret)"
    JWT_REFRESH_SECRET="$(generate_secret)"

    # --- Apply hardware profile defaults for .env values ---
    local COMPUTE_BACKEND DOCKER_HOST_IP SUPERVISOR_TYPE
    local GENERATION_SERVICES ROUTER_BIND_IP COMFYUI_ARGS
    case "$profile" in
        m4-mac)
            COMPUTE_BACKEND="mps"
            DOCKER_HOST_IP="host.docker.internal"
            SUPERVISOR_TYPE="launchagent"
            GENERATION_SERVICES="true"
            ROUTER_BIND_IP="127.0.0.1"
            COMFYUI_ARGS="--use-pytorch-cross-attention"
            ;;
        linux-bare)
            COMPUTE_BACKEND="cuda"
            DOCKER_HOST_IP="172.17.0.1"
            SUPERVISOR_TYPE="systemd"
            GENERATION_SERVICES="false"
            ROUTER_BIND_IP="172.17.0.1"
            COMFYUI_ARGS=""
            ;;
        linux-wsl2)
            COMPUTE_BACKEND="cuda"
            DOCKER_HOST_IP="0.0.0.0"
            SUPERVISOR_TYPE="nohup"
            GENERATION_SERVICES="false"
            ROUTER_BIND_IP="0.0.0.0"
            COMFYUI_ARGS=""
            ;;
        *)
            COMPUTE_BACKEND="cuda"
            DOCKER_HOST_IP="172.17.0.1"
            SUPERVISOR_TYPE="nohup"
            GENERATION_SERVICES="false"
            ROUTER_BIND_IP="0.0.0.0"
            COMFYUI_ARGS=""
            ;;
    esac

    # --- Write .env ---
    {
        echo "# ============================================================"
        echo "# Portal Configuration — auto-generated $(date +%Y-%m-%d)"
        echo "# Hardware profile: $profile"
        echo "# ============================================================"
        echo ""
        echo "# --- Hardware (auto-detected) ---"
        echo "COMPUTE_BACKEND=$COMPUTE_BACKEND"
        echo "DOCKER_HOST_IP=$DOCKER_HOST_IP"
        echo "SUPERVISOR_TYPE=$SUPERVISOR_TYPE"
        echo ""
        echo "# --- LLM ---"
        echo "OLLAMA_HOST=http://localhost:11434"
        echo "DEFAULT_MODEL=qwen2.5:7b"
        echo ""
        echo "# --- Routing ---"
        echo "ROUTER_PORT=8000"
        echo "ROUTER_BIND_IP=$ROUTER_BIND_IP"
        echo ""
        echo "# --- Web UI ---"
        echo "WEB_UI=$WEB_UI"
        echo ""
        echo "# --- Security (auto-generated — do not share) ---"
        echo "MCP_API_KEY=$MCP_API_KEY"
        echo "PORTAL_BOOTSTRAP_API_KEY=$PORTAL_BOOTSTRAP_API_KEY"
        echo "WEB_API_KEY=$WEB_API_KEY"
        echo "WEBUI_SECRET_KEY=$WEBUI_SECRET_KEY"
        echo "JWT_SECRET=$JWT_SECRET"
        echo "JWT_REFRESH_SECRET=$JWT_REFRESH_SECRET"
        echo ""
        echo "# --- MCP ---"
        echo "MCP_ENABLED=true"
        echo "MCP_TRANSPORT=mcpo"
        echo "MCPO_PORT=9000"
        echo ""
        echo "# --- Generation Services ---"
        echo "GENERATION_SERVICES=$GENERATION_SERVICES"
        if [ -n "$COMFYUI_ARGS" ]; then
            echo "COMFYUI_ARGS=$COMFYUI_ARGS"
        fi
        echo ""
        echo "# --- Telegram ---"
        echo "TELEGRAM_ENABLED=$TELEGRAM_ENABLED"
        if [ "$TELEGRAM_ENABLED" = "true" ]; then
            echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN"
            echo "TELEGRAM_USER_IDS=$TELEGRAM_USER_IDS"
        fi
        echo ""
        echo "# --- Slack ---"
        echo "SLACK_ENABLED=$SLACK_ENABLED"
        if [ "$SLACK_ENABLED" = "true" ]; then
            echo "SLACK_BOT_TOKEN=$SLACK_BOT_TOKEN"
            echo "SLACK_SIGNING_SECRET=$SLACK_SIGNING_SECRET_VAL"
        fi
        echo ""
        echo "# --- Observability ---"
        echo "LOG_LEVEL=INFO"
        echo "METRICS_ENABLED=true"
    } > "$env_file"

    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║  Configuration saved to .env                     ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
    echo "  Hardware:     $profile ($COMPUTE_BACKEND)"
    echo "  Web UI:       $WEB_UI"
    echo "  Telegram:     $TELEGRAM_ENABLED"
    echo "  Slack:        $SLACK_ENABLED"
    echo "  Secrets:      6 keys auto-generated"
    echo ""
    echo "  Starting Portal now..."
    echo ""

    # Export for use in the rest of this run
    export COMPUTE_BACKEND DOCKER_HOST_IP SUPERVISOR_TYPE GENERATION_SERVICES ROUTER_BIND_IP
    export WEB_UI TELEGRAM_ENABLED SLACK_ENABLED
    export MCP_API_KEY PORTAL_BOOTSTRAP_API_KEY WEB_API_KEY
    export WEBUI_SECRET_KEY JWT_SECRET JWT_REFRESH_SECRET
}

# ─── Prerequisite checks ──────────────────────────────────────────────────────
check_prerequisites() {
    local missing=()

    if ! command -v python3 &>/dev/null; then
        missing+=("python3 (3.11+)")
    else
        local py_ver
        py_ver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        local py_major py_minor
        py_major=$(echo "$py_ver" | cut -d. -f1)
        py_minor=$(echo "$py_ver" | cut -d. -f2)
        if [ "$py_major" -lt 3 ] || { [ "$py_major" -eq 3 ] && [ "$py_minor" -lt 11 ]; }; then
            missing+=("python3 >= 3.11 (found $py_ver)")
        fi
    fi

    if ! command -v docker &>/dev/null; then
        missing+=("docker")
    fi

    if ! command -v ollama &>/dev/null; then
        missing+=("ollama (https://ollama.ai)")
    fi

    if [ ${#missing[@]} -gt 0 ]; then
        echo "ERROR: Missing prerequisites:"
        for dep in "${missing[@]}"; do
            echo "  - $dep"
        done
        echo ""
        echo "Install the above, then re-run: bash launch.sh up"
        exit 1
    fi
}

# ─── Virtual environment setup ────────────────────────────────────────────────
setup_venv() {
    if [ ! -d "$PORTAL_ROOT/.venv" ]; then
        echo "[setup] Creating virtual environment..."
        if command -v uv &>/dev/null; then
            uv venv "$PORTAL_ROOT/.venv"
            echo "[setup] Installing dependencies with uv..."
            (cd "$PORTAL_ROOT" && uv sync)
        else
            python3 -m venv "$PORTAL_ROOT/.venv"
            echo "[setup] Installing dependencies..."
            "$PORTAL_ROOT/.venv/bin/pip" install -q -e "$PORTAL_ROOT/.[all]"
        fi
        echo "[setup] Dependencies installed."
    fi
}

# ─── Start router + Portal web interface ─────────────────────────────────────
start_core_services() {
    local profile="$1"

    # Activate venv if present
    local python_bin="python3"
    if [ -f "$PORTAL_ROOT/.venv/bin/python" ]; then
        python_bin="$PORTAL_ROOT/.venv/bin/python"
    fi

    # Start Ollama
    if ! pgrep -x "ollama" >/dev/null 2>&1; then
        echo "[ollama] starting..."
        case "$profile" in
            m4-mac)
                brew services start ollama 2>/dev/null \
                    || nohup ollama serve >> "$LOG_DIR/ollama.log" 2>&1 &
                ;;
            linux-bare)
                sudo systemctl start ollama 2>/dev/null \
                    || nohup ollama serve >> "$LOG_DIR/ollama.log" 2>&1 &
                ;;
            *)
                nohup ollama serve >> "$LOG_DIR/ollama.log" 2>&1 &
                ;;
        esac
        sleep 2
    fi
    echo "[ollama] OK"

    # Start router (port 8000)
    if [ ! -f /tmp/portal-router.pid ] || ! kill -0 "$(cat /tmp/portal-router.pid)" 2>/dev/null; then
        echo "[router] starting..."
        nohup "$python_bin" -m uvicorn portal.routing.router:app \
            --host "${ROUTER_BIND_IP:-127.0.0.1}" \
            --port "${ROUTER_PORT:-8000}" \
            >> "$LOG_DIR/router.log" 2>&1 &
        echo $! > /tmp/portal-router.pid
        echo "[router] OK (PID $!)"
    else
        echo "[router] already running"
    fi

    # Start Portal web interface (port 8081)
    if [ ! -f /tmp/portal-web.pid ] || ! kill -0 "$(cat /tmp/portal-web.pid)" 2>/dev/null; then
        echo "[portal-api] starting..."
        nohup "$python_bin" -m uvicorn portal.interfaces.web.server:app \
            --host "${ROUTER_BIND_IP:-127.0.0.1}" \
            --port 8081 \
            >> "$LOG_DIR/portal-api.log" 2>&1 &
        echo $! > /tmp/portal-web.pid
        echo "[portal-api] OK (PID $!)"
    else
        echo "[portal-api] already running"
    fi
}

# ─── Start optional/extended services ────────────────────────────────────────
start_extended_services() {
    local profile="$1"

    # Start Docker stack for selected web UI
    local DEPLOY_DIR="$PORTAL_ROOT/deploy/web-ui/${WEB_UI:-openwebui}"
    if [ -d "$DEPLOY_DIR" ]; then
        echo "[docker] starting ${WEB_UI:-openwebui} stack..."
        (cd "$DEPLOY_DIR" && \
            DOCKER_HOST_IP="$DOCKER_HOST_IP" \
            AI_OUTPUT_DIR="$HOME/AI_Output" \
            docker compose up -d)
        echo "[docker] OK"
    else
        echo "[docker] deploy dir not found: $DEPLOY_DIR (skipping)"
    fi

    # Start mcpo (Open WebUI + MCP enabled only)
    if [ "${WEB_UI:-openwebui}" = "openwebui" ] && [ "${MCP_ENABLED:-true}" = "true" ]; then
        # Start scrapling if script exists
        local scrapling_script="$PORTAL_ROOT/mcp/scrapling/launch_scrapling.sh"
        if [ -f "$scrapling_script" ]; then
            bash "$scrapling_script" || true
        fi

        if ! pgrep -f "mcpo" >/dev/null 2>&1; then
            echo "[mcpo] starting..."
            nohup uvx mcpo \
                --port "${MCPO_PORT:-9000}" \
                --api-key "${MCP_API_KEY}" \
                --config "$PORTAL_ROOT/mcp/core/mcp_servers.json" \
                >> "$LOG_DIR/mcpo.log" 2>&1 &
            echo "[mcpo] OK (PID $!)"
        else
            echo "[mcpo] already running"
        fi
    fi

    # Start generation services if enabled
    if [ "${GENERATION_SERVICES:-false}" = "true" ]; then
        local gen_script="$PORTAL_ROOT/hardware/$profile/launch_generation.sh"
        if [ -f "$gen_script" ]; then
            echo "[generation] starting..."
            bash "$gen_script" || true
        fi
    fi
}

# ─── Print access URLs ────────────────────────────────────────────────────────
print_access_urls() {
    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║  Portal is running                               ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
    echo "  Web UI:       http://localhost:8080"
    echo "  Portal API:   http://localhost:8081/v1"
    echo "  Router:       http://localhost:${ROUTER_PORT:-8000}"
    echo "  Ollama:       http://localhost:11434"
    if [ "${MCP_ENABLED:-true}" = "true" ] && [ "${WEB_UI:-openwebui}" = "openwebui" ]; then
        echo "  MCP proxy:    http://localhost:${MCPO_PORT:-9000}"
    fi
    echo ""
}

# ─── Doctor (health check) ────────────────────────────────────────────────────
run_doctor() {
    local all_ok=true

    check_service() {
        local name="$1"
        local url="$2"
        local optional="${3:-false}"
        if curl -sf "$url" >/dev/null 2>&1; then
            printf "  [%-12s] \033[32mOK\033[0m\n" "$name"
        else
            if [ "$optional" = "true" ]; then
                printf "  [%-12s] \033[33mUNREACHABLE\033[0m (optional)\n" "$name"
            else
                printf "  [%-12s] \033[31mFAIL\033[0m\n" "$name"
                all_ok=false
            fi
        fi
    }

    check_process() {
        local name="$1"
        local pattern="$2"
        local optional="${3:-false}"
        if pgrep -f "$pattern" >/dev/null 2>&1; then
            printf "  [%-12s] \033[32mrunning\033[0m\n" "$name"
        else
            if [ "$optional" = "true" ]; then
                printf "  [%-12s] \033[33mNOT RUNNING\033[0m (optional)\n" "$name"
            else
                printf "  [%-12s] \033[31mNOT RUNNING\033[0m\n" "$name"
                all_ok=false
            fi
        fi
    }

    echo ""
    echo "=== Portal Doctor ==="
    check_service "ollama" "http://localhost:11434/api/tags"
    check_service "router" "http://localhost:${ROUTER_PORT:-8000}/health"
    check_service "portal-api" "http://localhost:8081/health"
    check_service "web-ui" "http://localhost:8080" "true"

    if [ "${MCP_ENABLED:-true}" = "true" ]; then
        check_service "mcpo" "http://localhost:${MCPO_PORT:-9000}" "true"
        check_process "scrapling" "scrapling" "true"
    fi

    echo ""
    if [ "$all_ok" = "true" ]; then
        echo "  All required services are healthy."
    else
        echo "  One or more required services are not responding."
        echo "  Check logs: bash launch.sh logs <service>"
    fi
    echo ""
}

# ─── Down (stop all services) ─────────────────────────────────────────────────
stop_all() {
    echo "=== Stopping Portal ==="

    # Stop Docker stack
    local DEPLOY_DIR="$PORTAL_ROOT/deploy/web-ui/${WEB_UI:-openwebui}"
    if [ -d "$DEPLOY_DIR" ]; then
        echo "[docker] stopping..."
        (cd "$DEPLOY_DIR" && docker compose down) 2>/dev/null || true
        echo "[docker] stopped"
    fi

    # Kill router via PID file
    if [ -f /tmp/portal-router.pid ]; then
        local pid
        pid=$(cat /tmp/portal-router.pid)
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null && echo "[router] stopped (PID $pid)"
        fi
        rm -f /tmp/portal-router.pid
    fi

    # Kill portal web via PID file
    if [ -f /tmp/portal-web.pid ]; then
        local pid
        pid=$(cat /tmp/portal-web.pid)
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null && echo "[portal-api] stopped (PID $pid)"
        fi
        rm -f /tmp/portal-web.pid
    fi

    # Kill extras
    pkill -f "mcpo" 2>/dev/null && echo "[mcpo] stopped" || true
    pkill -f "scrapling" 2>/dev/null && echo "[scrapling] stopped" || true
    pkill -f "comfyui_mcp" 2>/dev/null && echo "[comfyui_mcp] stopped" || true
    pkill -f "whisper_mcp" 2>/dev/null && echo "[whisper_mcp] stopped" || true

    # Broad fallback for uvicorn processes
    pkill -f "uvicorn.*portal\." 2>/dev/null || true

    echo "Portal stopped."
}

# ─── Logs ─────────────────────────────────────────────────────────────────────
tail_logs() {
    local service="${1:-portal-api}"
    local log_file="$LOG_DIR/${service}.log"
    if [ ! -f "$log_file" ]; then
        echo "No log file found: $log_file"
        echo "Available logs:"
        ls "$LOG_DIR"/*.log 2>/dev/null | xargs -I{} basename {} .log || echo "  (none)"
        exit 1
    fi
    tail -f "$log_file"
}

# ─── Status ───────────────────────────────────────────────────────────────────
show_status() {
    local profile
    profile=$(detect_hardware_profile)

    # Source .env to get WEB_UI and COMPUTE_BACKEND if available
    if [ -f "$PORTAL_ROOT/.env" ]; then
        set -a; source "$PORTAL_ROOT/.env"; set +a
    fi

    echo "Portal | profile=$profile | compute=${COMPUTE_BACKEND:-unknown} | web_ui=${WEB_UI:-unknown}"
    echo -n "Services: "
    pgrep -x ollama >/dev/null 2>&1 && echo -n "ollama:OK " || echo -n "ollama:DOWN "
    { [ -f /tmp/portal-router.pid ] && kill -0 "$(cat /tmp/portal-router.pid)" 2>/dev/null; } \
        && echo -n "router:OK " || echo -n "router:DOWN "
    { [ -f /tmp/portal-web.pid ] && kill -0 "$(cat /tmp/portal-web.pid)" 2>/dev/null; } \
        && echo -n "api:OK " || echo -n "api:DOWN "
    docker ps --format '{{.Names}}' 2>/dev/null \
        | grep -q "portal-open-webui\|portal-librechat" \
        && echo -n "webui:OK " || echo -n "webui:DOWN "
    echo ""
}

# ─── Reset secrets ────────────────────────────────────────────────────────────
reset_secrets() {
    local env_file="$PORTAL_ROOT/.env"
    if [ ! -f "$env_file" ]; then
        echo "ERROR: .env not found. Run 'bash launch.sh up' first to create it."
        exit 1
    fi

    echo "Regenerating all auto-generated secrets..."

    # Use a temp file to avoid issues with sed -i on different platforms
    local tmp_file
    tmp_file=$(mktemp)
    cp "$env_file" "${env_file}.bak"

    sed \
        -e "s|^MCP_API_KEY=.*|MCP_API_KEY=$(generate_secret)|" \
        -e "s|^PORTAL_BOOTSTRAP_API_KEY=.*|PORTAL_BOOTSTRAP_API_KEY=$(generate_secret)|" \
        -e "s|^WEB_API_KEY=.*|WEB_API_KEY=$(generate_secret)|" \
        -e "s|^WEBUI_SECRET_KEY=.*|WEBUI_SECRET_KEY=$(generate_secret)|" \
        -e "s|^JWT_SECRET=.*|JWT_SECRET=$(generate_secret)|" \
        -e "s|^JWT_REFRESH_SECRET=.*|JWT_REFRESH_SECRET=$(generate_secret)|" \
        "$env_file" > "$tmp_file"

    mv "$tmp_file" "$env_file"
    rm -f "${env_file}.bak"

    echo "Done. Restart Portal to apply new secrets:"
    echo "  bash launch.sh down && bash launch.sh up"
}

# ─── Main entrypoint ──────────────────────────────────────────────────────────
COMMAND="${1:-up}"
MINIMAL="false"
PROFILE_OVERRIDE=""

# Parse flags
shift || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --minimal) MINIMAL="true" ;;
        --profile)
            shift
            PROFILE_OVERRIDE="${1:-}"
            ;;
        --profile=*)
            PROFILE_OVERRIDE="${1#--profile=}"
            ;;
    esac
    shift || true
done

case "$COMMAND" in
    up)
        echo "=== Portal Starting ==="

        # 1. Detect hardware profile
        if [ -n "$PROFILE_OVERRIDE" ]; then
            PORTAL_HARDWARE="$PROFILE_OVERRIDE"
            export PORTAL_HARDWARE
        fi
        PROFILE=$(detect_hardware_profile)

        # 2. Check if .env exists; run bootstrap if not
        if [ ! -f "$PORTAL_ROOT/.env" ]; then
            bootstrap_env "$PROFILE"
        fi

        # 3. Source .env + apply profile defaults for any gaps
        set -a; source "$PORTAL_ROOT/.env"; set +a
        apply_profile_defaults "$PROFILE"

        # 4. Check prerequisites
        check_prerequisites

        # 5. Create venv + install deps if missing
        setup_venv

        # 6-8. Start services
        start_core_services "$PROFILE"

        if [ "$MINIMAL" != "true" ]; then
            start_extended_services "$PROFILE"
        fi

        # 9. Print access URLs
        print_access_urls

        # 10. Run doctor check automatically
        run_doctor
        ;;

    down)
        # Source .env for WEB_UI context if present
        if [ -f "$PORTAL_ROOT/.env" ]; then
            set -a; source "$PORTAL_ROOT/.env"; set +a
        fi
        stop_all
        ;;

    doctor)
        if [ -f "$PORTAL_ROOT/.env" ]; then
            set -a; source "$PORTAL_ROOT/.env"; set +a
        fi
        PROFILE=$(detect_hardware_profile)
        apply_profile_defaults "$PROFILE"
        run_doctor
        ;;

    logs)
        tail_logs "${1:-portal-api}"
        ;;

    status)
        show_status
        ;;

    reset-secrets)
        reset_secrets
        ;;

    *)
        echo "Portal Unified Launcher"
        echo ""
        echo "Usage: bash launch.sh <command> [options]"
        echo ""
        echo "Commands:"
        echo "  up [--minimal] [--profile X]  Start all services (bootstrap on first run)"
        echo "  down                           Stop all services"
        echo "  doctor                         Health check all components"
        echo "  logs [service]                 Tail a service log"
        echo "  status                         One-line service overview"
        echo "  reset-secrets                  Rotate all auto-generated keys"
        echo ""
        echo "Hardware profiles: m4-mac | linux-bare | linux-wsl2"
        echo "  Use PORTAL_HARDWARE=<profile> env var or --profile flag to override detection."
        echo ""
        exit 1
        ;;
esac
