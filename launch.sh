#!/bin/bash
# Portal Unified Launcher — zero-config bootstrap & multi-platform management
# Usage: bash launch.sh [up|down|doctor|logs|status|reset-secrets] [--minimal] [--profile X]
set -euo pipefail

PORTAL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$HOME/.portal/logs"
mkdir -p "$LOG_DIR"

# Ensure uvx is in PATH (installed via curl -LsSf https://astral.sh/uv/install.sh)
export PATH="$HOME/.local/bin:$PATH"

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

    # --- Multi-user (optional) ---
    WEBUI_AUTH="false"
    read -rp "Enable user accounts and login? [y/N]: " auth_enable
    case "$auth_enable" in
        [Yy]*)
            WEBUI_AUTH="true"
            echo "  -> First user to sign up will be admin"
            ;;
    esac
    echo ""

    # --- Telegram (optional) ---
    TELEGRAM_ENABLED="false"
    TELEGRAM_BOT_TOKEN=""
    TELEGRAM_USER_IDS=""
    read -rp "Enable Telegram bot? [y/N]: " tg_enable
    case "$tg_enable" in
        [Yy]*)
            TELEGRAM_ENABLED="true"
            read -rp "  Telegram bot token (from @BotFather): " TELEGRAM_BOT_TOKEN
            read -rp "  Authorized user IDs (comma-separated): " TELEGRAM_USER_IDS
            echo ""
            ;;
    esac

    # --- Slack (optional) ---
    SLACK_ENABLED="false"
    SLACK_BOT_TOKEN=""
    SLACK_SIGNING_SECRET_VAL=""
    read -rp "Enable Slack bot? [y/N]: " slack_enable
    case "$slack_enable" in
        [Yy]*)
            SLACK_ENABLED="true"
            read -rp "  Slack bot token (xoxb-...): " SLACK_BOT_TOKEN
            read -rp "  Slack signing secret: " SLACK_SIGNING_SECRET_VAL
            echo ""
            ;;
    esac

    # --- HuggingFace (optional) ---
    HF_TOKEN=""
    read -rp "HuggingFace token for private models? [Enter to skip]: " hf_input
    if [ -n "$hf_input" ]; then
        HF_TOKEN="$hf_input"
        echo "  -> Token configured"
    fi
    echo ""

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
        echo "WEBUI_AUTH=$WEBUI_AUTH"
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
        echo "# --- HuggingFace ---"
        if [ -n "$HF_TOKEN" ]; then
            echo "PORTAL_BACKENDS__HUGGINGFACE_TOKEN=$HF_TOKEN"
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
    echo "  Auth:         $WEBUI_AUTH"
    echo "  Telegram:     $TELEGRAM_ENABLED"
    echo "  Slack:        $SLACK_ENABLED"
    if [ -n "$HF_TOKEN" ]; then
        echo "  HuggingFace:  configured"
    else
        echo "  HuggingFace:  not configured"
    fi
    echo "  Secrets:      6 keys auto-generated"
    echo ""
    echo "  Starting Portal now..."
    echo ""

    # Export for use in the rest of this run
    export COMPUTE_BACKEND DOCKER_HOST_IP SUPERVISOR_TYPE GENERATION_SERVICES ROUTER_BIND_IP
    export WEB_UI WEBUI_AUTH TELEGRAM_ENABLED SLACK_ENABLED
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
    local venv_dir="$PORTAL_ROOT/.venv"
    local python_bin="$venv_dir/bin/python"

    # Quick check: can the venv import the main package?
    if [ -f "$python_bin" ] && "$python_bin" -c "import uvicorn; import portal" 2>/dev/null; then
        return 0  # venv is healthy
    fi

    # Venv missing or broken — (re)create it
    if [ -d "$venv_dir" ]; then
        echo "[setup] Existing virtual environment is broken — recreating..."
        rm -rf "$venv_dir"
    fi

    echo "[setup] Creating virtual environment..."
    if command -v uv &>/dev/null; then
        uv venv "$venv_dir"
        echo "[setup] Updating dependency lock file..."
        if ! (cd "$PORTAL_ROOT" && uv lock); then
            echo "WARNING: Failed to update lock file, attempting sync anyway..."
        fi
        echo "[setup] Installing dependencies with uv..."
        if ! (cd "$PORTAL_ROOT" && uv sync); then
            echo "ERROR: Dependency installation failed. Check Python version and try:"
            echo "  rm -rf .venv && bash launch.sh up"
            exit 1
        fi
    else
        python3 -m venv "$venv_dir"
        echo "[setup] Installing dependencies with pip..."
        if ! "$venv_dir/bin/pip" install -q -e "$PORTAL_ROOT/.[all]"; then
            echo "ERROR: Dependency installation failed. Check Python version and try:"
            echo "  rm -rf .venv && bash launch.sh up"
            exit 1
        fi
    fi
    echo "[setup] Dependencies installed."
}

# ─── Ensure default Ollama model is available ────────────────────────────────
ensure_default_model() {
    local model="${DEFAULT_MODEL:-qwen2.5:7b}"

    # Wait for Ollama to be ready (it may still be starting)
    local retries=10
    while ! curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; do
        retries=$((retries - 1))
        if [ "$retries" -le 0 ]; then
            echo "[models] WARNING: Ollama not responding — skipping model check"
            return
        fi
        sleep 1
    done

    # Check if default model is already pulled
    if ollama list 2>/dev/null | grep -q "^${model}"; then
        echo "[models] $model already available"
        return
    fi

    echo "[models] Pulling default model: $model (this may take a few minutes on first run)..."
    if ollama pull "$model"; then
        echo "[models] $model ready"
    else
        echo "[models] WARNING: Failed to pull $model — you can pull it manually:"
        echo "  ollama pull $model"
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

    # Verify uvicorn is importable before starting services
    if ! "$python_bin" -c "import uvicorn" 2>/dev/null; then
        echo "ERROR: uvicorn not found in venv. Run: rm -rf .venv && bash launch.sh up"
        exit 1
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
        if ! docker info &>/dev/null; then
            echo "[docker] Docker is not running. Start Docker Desktop and re-run: bash launch.sh up"
            echo "[docker] Skipping web UI — Portal API is still available at http://localhost:8081/v1"
        else
            echo "[docker] starting ${WEB_UI:-openwebui} stack..."
            (cd "$DEPLOY_DIR" && \
                DOCKER_HOST_IP="$DOCKER_HOST_IP" \
                AI_OUTPUT_DIR="$HOME/AI_Output" \
                docker compose up -d)
            echo "[docker] OK"
        fi
    else
        echo "[docker] deploy dir not found: $DEPLOY_DIR (skipping)"
    fi

    # Start mcpo (MCP enabled)
    if [ "${MCP_ENABLED:-true}" = "true" ]; then
        # Start scrapling if script exists
        local scrapling_script="$PORTAL_ROOT/portal_mcp/scrapling/launch_scrapling.sh"
        if [ -f "$scrapling_script" ]; then
            bash "$scrapling_script" || true
        fi

        if ! pgrep -f "mcpo" >/dev/null 2>&1; then
            echo "[mcpo] starting..."
            if command -v uvx &>/dev/null; then
                nohup uvx mcpo \
                    --port "${MCPO_PORT:-9000}" \
                    --api-key "${MCP_API_KEY}" \
                    --config "$PORTAL_ROOT/portal_mcp/core/mcp_servers.json" \
                    >> "$LOG_DIR/mcpo.log" 2>&1 &
            else
                # uvx not available — install mcpo into venv and run directly
                local mcpo_bin="$PORTAL_ROOT/.venv/bin/mcpo"
                if [ ! -f "$mcpo_bin" ]; then
                    echo "[mcpo] uvx not found — installing mcpo into venv..."
                    "$PORTAL_ROOT/.venv/bin/pip" install -q mcpo
                fi
                if [ -f "$mcpo_bin" ]; then
                    nohup "$mcpo_bin" \
                        --port "${MCPO_PORT:-9000}" \
                        --api-key "${MCP_API_KEY}" \
                        --config "$PORTAL_ROOT/portal_mcp/core/mcp_servers.json" \
                        >> "$LOG_DIR/mcpo.log" 2>&1 &
                else
                    echo "[mcpo] WARNING: Failed to install mcpo. MCP tools will be unavailable."
                    echo "  Install manually: pip install mcpo  OR  install uv: https://docs.astral.sh/uv/"
                fi
            fi
            echo "[mcpo] started (PID $!) — logs: bash launch.sh logs mcpo"
        else
            echo "[mcpo] already running"
        fi
    fi

    # Start generation services if enabled
    if [ "${GENERATION_SERVICES:-false}" = "true" ]; then
        # Start ComfyUI first (required for image generation)
        start_comfyui "$profile"

        # Then start the MCP bridges
        local gen_script="$PORTAL_ROOT/portal_mcp/generation/launch_generation_mcps.sh"
        if [ -f "$gen_script" ]; then
            echo "[generation-mcp] starting..."
            if ! bash "$gen_script" 2>&1; then
                echo "[generation-mcp] WARNING: failed to start — check logs: bash launch.sh logs mcp-comfyui"
            fi
        else
            echo "[generation-mcp] ERROR: script not found: $gen_script"
        fi
    fi
}

# ─── Start ComfyUI ──────────────────────────────────────────────────────────────
start_comfyui() {
    local profile="$1"
    local comfy_dir="${COMFYUI_DIR:-$HOME/ComfyUI}"
    local comfy_port="${COMFYUI_PORT:-8188}"

    # Check if ComfyUI is already running
    if nc -z localhost "$comfy_port" 2>/dev/null; then
        echo "[comfyui] already running on port $comfy_port"
        return 0
    fi

    # Check if ComfyUI is installed
    if [ ! -d "$comfy_dir" ]; then
        echo "[comfyui] not found at $comfy_dir"
        echo "[comfyui] skipping auto-install (requires manual setup on first run)"
        echo "[comfyui] To install manually:"
        echo "    pip3 install comfy-cli"
        echo "    comfy install"
        echo "[comfyui] Then restart: bash launch.sh up"
        return 0  # Don't fail - let user install manually
    fi

    # Build ComfyUI launch args based on profile
    local comfy_args="--listen 0.0.0.0 --port $comfy_port"
    case "$profile" in
        m4-mac)
            comfy_args="$comfy_args --use-pytorch-cross-attention --mps --highvram"
            ;;
        linux-bare)
            comfy_args="$comfy_args --cuda"
            ;;
        linux-wsl2)
            comfy_args="$comfy_args --cuda"
            ;;
    esac

    # Start ComfyUI
    echo "[comfyui] starting on port $comfy_port..."
    cd "$comfy_dir"
    nohup python main.py $comfy_args >> "$LOG_DIR/comfyui.log" 2>&1 &
    local comfy_pid=$!
    echo "$comfy_pid" > /tmp/portal-comfyui.pid

    # Wait for ComfyUI to be ready (with timeout)
    local attempts=0
    local max_attempts=30
    while [ $attempts -lt $max_attempts ]; do
        if nc -z localhost "$comfy_port" 2>/dev/null; then
            # Verify the API is responsive
            if curl -sf "http://localhost:$comfy_port/object_info" >/dev/null 2>&1; then
                echo "[comfyui] ready (PID $comfy_pid)"
                return 0
            fi
        fi
        sleep 2
        attempts=$((attempts + 1))
        echo "[comfyui] waiting for startup... ($attempts/$max_attempts)"
    done

    echo "[comfyui] WARNING: failed to start within 60s — check logs: bash launch.sh logs comfyui"
    return 1
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
    if [ "${MCP_ENABLED:-true}" = "true" ]; then
        echo "  MCP proxy:    http://localhost:${MCPO_PORT:-9000}"
        echo "  Scrapling:    http://localhost:${SCRAPLING_PORT:-8900}"
    fi
    if [ "${GENERATION_SERVICES:-false}" = "true" ]; then
        echo "  ComfyUI:      http://localhost:${COMFYUI_PORT:-8188}"
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
        local log_hint="${4:-}"
        local retries="${5:-1}"  # Number of retry attempts
        local delay="${6:-2}"     # Delay between retries in seconds

        local attempt=0
        local success=false

        while [ $attempt -lt $retries ]; do
            if curl -sf "$url" >/dev/null 2>&1; then
                success=true
                break
            fi
            attempt=$((attempt + 1))
            if [ $attempt -lt $retries ]; then
                sleep "$delay"
            fi
        done

        if [ "$success" = "true" ]; then
            printf "  [%-12s] \033[32mOK\033[0m\n" "$name"
        else
            if [ "$optional" = "true" ]; then
                printf "  [%-12s] \033[33mUNREACHABLE\033[0m (optional)\n" "$name"
            else
                printf "  [%-12s] \033[31mFAIL\033[0m\n" "$name"
                if [ -n "$log_hint" ]; then
                    printf "               -> logs: bash launch.sh logs %s\n" "$log_hint"
                fi
                all_ok=false
            fi
        fi
    }

    check_process() {
        local name="$1"
        local pattern="$2"
        local optional="${3:-false}"
        local log_hint="${4:-}"
        if pgrep -f "$pattern" >/dev/null 2>&1; then
            printf "  [%-12s] \033[32mrunning\033[0m\n" "$name"
        else
            if [ "$optional" = "true" ]; then
                printf "  [%-12s] \033[33mNOT RUNNING\033[0m (optional)\n" "$name"
            else
                printf "  [%-12s] \033[31mNOT RUNNING\033[0m\n" "$name"
                if [ -n "$log_hint" ]; then
                    printf "               -> logs: bash launch.sh logs %s\n" "$log_hint"
                fi
                all_ok=false
            fi
        fi
    }

    # Check if a TCP port is listening
    check_port() {
        local name="$1"
        local port="$2"
        local optional="${3:-false}"

        if nc -z localhost "$port" 2>/dev/null; then
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

    echo ""
    echo "=== Portal Doctor ==="
    check_service "ollama" "http://localhost:11434/api/tags"
    check_service "router" "http://localhost:${ROUTER_PORT:-8000}/health"
    check_service "portal-api" "http://localhost:8081/health"
    check_service "web-ui" "http://localhost:8080" "true"

    # Check ComfyUI (required for image generation)
    if [ "${GENERATION_SERVICES:-false}" = "true" ]; then
        check_service "comfyui" "http://localhost:${COMFYUI_PORT:-8188}/object_info" "true" "comfyui" "3" "5"
    fi

    if [ "${MCP_ENABLED:-true}" = "true" ]; then
        # mcpo can take 30-50s to start, so retry up to 5 times with 10s delay
        check_service "mcpo" "http://localhost:${MCPO_PORT:-9000}/openapi.json" "false" "mcpo" "5" "10"
        check_process "scrapling" "scrapling" "false" "scrapling"
        # Docker MCP services - check port is open (they don't expose /health endpoints)
        # Docker MCP services - required when GENERATION_SERVICES=true
        local mcp_optional="true"
        if [ "${GENERATION_SERVICES:-false}" = "true" ]; then
            mcp_optional="false"
        fi
        check_port "mcp-music" "${MUSIC_MCP_PORT:-8912}" "$mcp_optional"
        check_port "mcp-documents" "${DOCUMENTS_MCP_PORT:-8913}" "$mcp_optional"
        check_port "mcp-tts" "${TTS_MCP_PORT:-8916}" "$mcp_optional"
        # Native generation MCP services (when GENERATION_SERVICES=true)
        if [ "${GENERATION_SERVICES:-false}" = "true" ]; then
            check_port "mcp-comfyui" "${COMFYUI_MCP_PORT:-8910}" "false"
            check_port "mcp-video" "${VIDEO_MCP_PORT:-8911}" "false"
            check_port "mcp-whisper" "${WHISPER_MCP_PORT:-8915}" "false"
        fi
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
    pkill -f "video_mcp" 2>/dev/null && echo "[video_mcp] stopped" || true
    pkill -f "music_mcp" 2>/dev/null && echo "[music_mcp] stopped" || true
    pkill -f "tts_mcp" 2>/dev/null && echo "[tts_mcp] stopped" || true
    pkill -f "document_mcp" 2>/dev/null && echo "[document_mcp] stopped" || true
    pkill -f "code_sandbox_mcp" 2>/dev/null && echo "[code_sandbox_mcp] stopped" || true
    pkill -f "ComfyUI" 2>/dev/null && echo "[comfyui] stopped" || true
    rm -f /tmp/portal-comfyui.pid

    # Broad fallback for uvicorn processes
    pkill -f "uvicorn.*portal\." 2>/dev/null || true

    echo "Portal stopped."
}

# ─── Logs ─────────────────────────────────────────────────────────────────────
tail_logs() {
    local service="${1:-}"
    if [ -z "$service" ]; then
        echo "Usage: bash launch.sh logs <service>"
        echo ""
        echo "Available services:"
        ls -1 "$LOG_DIR"/*.log 2>/dev/null | xargs -I{} basename {} .log | sort | while read -r log; do
            echo "  $log"
        done
        echo ""
        echo "Examples:"
        echo "  bash launch.sh logs portal-api"
        echo "  bash launch.sh logs router"
        echo "  bash launch.sh logs mcpo"
        echo "  bash launch.sh logs mcp-comfyui"
        echo "  bash launch.sh logs scrapling"
        exit 0
    fi

    local log_file="$LOG_DIR/${service}.log"
    if [ ! -f "$log_file" ]; then
        echo "No log file found: $log_file"
        echo ""
        echo "Available logs:"
        ls -1 "$LOG_DIR"/*.log 2>/dev/null | xargs -I{} basename {} .log | sort | while read -r log; do
            echo "  $log"
        done
        exit 1
    fi
    echo "Tailing: $log_file (Ctrl+C to exit)"
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

# ─── Switch web UI ────────────────────────────────────────────────────────────
switch_ui() {
    local env_file="$PORTAL_ROOT/.env"
    if [ ! -f "$env_file" ]; then
        echo "ERROR: .env not found. Run 'bash launch.sh up' first."
        exit 1
    fi

    local new_ui="${1:-}"
    if [ -z "$new_ui" ]; then
        echo "Which web UI do you want?"
        echo "  1) Open WebUI  (recommended, full-featured)"
        echo "  2) LibreChat   (multi-provider, plugin ecosystem)"
        echo ""
        read -rp "Choice [1]: " ui_choice
        case "${ui_choice:-1}" in
            2|librechat|LibreChat) new_ui="librechat" ;;
            *) new_ui="openwebui" ;;
        esac
    fi

    # Validate
    case "$new_ui" in
        openwebui|librechat) ;;
        *) echo "ERROR: Unknown UI '$new_ui'. Options: openwebui, librechat"; exit 1 ;;
    esac

    # Source current config to find old UI
    set -a; source "$env_file"; set +a
    local old_ui="${WEB_UI:-openwebui}"

    if [ "$old_ui" = "$new_ui" ]; then
        echo "Already using $new_ui. Nothing to change."
        return
    fi

    echo "Switching: $old_ui → $new_ui"

    # Stop old UI stack and remove volumes
    local old_dir="$PORTAL_ROOT/deploy/web-ui/$old_ui"
    if [ -d "$old_dir" ] && docker info &>/dev/null; then
        echo "[docker] stopping $old_ui stack..."
        (cd "$old_dir" && docker compose down -v) 2>/dev/null || true
    fi

    # Update .env
    local tmp_file
    tmp_file=$(mktemp)
    sed "s|^WEB_UI=.*|WEB_UI=$new_ui|" "$env_file" > "$tmp_file"
    mv "$tmp_file" "$env_file"

    echo ""
    echo "Done. Web UI set to: $new_ui"
    echo "Restart to apply: bash launch.sh down && bash launch.sh up"
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

# ─── Reset portal state ───────────────────────────────────────────────────────
reset_portal() {
    local full="${1:-}"

    echo "=== Portal Reset ==="

    # Always: remove venv
    if [ -d "$PORTAL_ROOT/.venv" ]; then
        echo "[reset] Removing virtual environment..."
        rm -rf "$PORTAL_ROOT/.venv"
    fi

    # Always: remove PID files
    rm -f /tmp/portal-router.pid /tmp/portal-web.pid

    # Always: kill any stale Portal processes
    pkill -f "uvicorn.*portal\." 2>/dev/null || true
    pkill -f "mcpo" 2>/dev/null || true

    if [ "$full" = "--full" ]; then
        # Full reset: also nuke .env, data, Docker volumes
        echo "[reset] Removing .env (will re-run bootstrap on next 'up')..."
        rm -f "$PORTAL_ROOT/.env"

        echo "[reset] Removing data directory..."
        rm -rf "$PORTAL_ROOT/data"

        # Stop and remove Docker volumes for both UIs
        for ui_dir in "$PORTAL_ROOT/deploy/web-ui/openwebui" "$PORTAL_ROOT/deploy/web-ui/librechat"; do
            if [ -d "$ui_dir" ] && docker info &>/dev/null; then
                (cd "$ui_dir" && docker compose down -v) 2>/dev/null || true
            fi
        done
        echo "[reset] Full reset complete. Run 'bash launch.sh up' to start fresh."
    else
        echo "[reset] Light reset complete (venv + processes cleared)."
        echo "  Run 'bash launch.sh up' to reinstall and restart."
        echo ""
        echo "  For a full factory reset (deletes .env, data, Docker volumes):"
        echo "    bash launch.sh reset --full"
    fi
}

# ─── Main entrypoint ──────────────────────────────────────────────────────────
COMMAND="${1:-up}"
MINIMAL="false"
PROFILE_OVERRIDE=""
SUBARG=""

# Parse flags and capture first positional sub-argument
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
        *)
            if [ -z "$SUBARG" ]; then
                SUBARG="$1"
            fi
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

        # 5.5 Start core services first so Ollama is available for model check
        start_core_services "$PROFILE"

        # 5.6 Ensure default model is available in Ollama
        ensure_default_model

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
        tail_logs "${SUBARG:-portal-api}"
        ;;

    status)
        show_status
        ;;

    reset-secrets)
        reset_secrets
        ;;

    switch-ui)
        switch_ui "$SUBARG"
        ;;

    reset)
        reset_portal "$SUBARG"
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
        echo "  switch-ui [name]               Switch web UI (openwebui or librechat)"
        echo "  reset [--full]                 Reset venv + processes (--full: also .env, data, Docker)"
        echo ""
        echo "Hardware profiles: m4-mac | linux-bare | linux-wsl2"
        echo "  Use PORTAL_HARDWARE=<profile> env var or --profile flag to override detection."
        echo ""
        exit 1
        ;;
esac
