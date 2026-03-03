#!/usr/bin/env python3
"""
Open WebUI Workspace Setup Script

Pre-configures workspaces in Open WebUI with:
- Display names
- System prompts from persona YAML files
- Assigned tool sets per workspace
- Default function calling mode

Usage:
    python scripts/setup_openwebui.py [--url http://localhost:8080] [--api-key KEY]

Requires authentication - either provide API key or set OPENWEBUI_API_KEY env var.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

# Default workspace configurations
WORKSPACES = {
    "auto": {
        "name": "Auto Router",
        "description": "Automatically selects the best model for your task",
        "system_prompt": "You are Portal, an AI assistant that intelligently routes requests to specialized models.",
    },
    "auto-coding": {
        "name": "Code Expert",
        "description": "Specialized in code generation and debugging",
        "system_prompt": "You are an expert programmer. Generate clean, well-documented code. Always prefer idiomatic solutions.",
    },
    "auto-security": {
        "name": "Security Analyst",
        "description": "Security analysis and defensive coding",
        "system_prompt": "You are a security expert. Focus on secure coding practices, vulnerability analysis, and defensive measures.",
    },
    "auto-creative": {
        "name": "Creative Writer",
        "description": "Creative content generation",
        "system_prompt": "You are a creative writer. Generate engaging, imaginative content with vivid descriptions.",
    },
    "auto-reasoning": {
        "name": "Deep Reasoner",
        "description": "Complex reasoning and analysis",
        "system_prompt": "You are a deep reasoning AI. Break down complex problems step-by-step and provide thorough analysis.",
    },
    "auto-documents": {
        "name": "Document Builder",
        "description": "Create documents, spreadsheets, presentations",
        "system_prompt": "You help create professional documents. Use available tools to generate Word, Excel, and PowerPoint files.",
    },
    "auto-video": {
        "name": "Video Creator",
        "description": "Generate videos with Wan2.2",
        "system_prompt": "You create videos. Use ComfyUI to generate videos from text prompts.",
    },
    "auto-music": {
        "name": "Music Producer",
        "description": "Generate music with AudioCraft",
        "system_prompt": "You create music. Use the music generation tool to produce audio clips.",
    },
    "auto-research": {
        "name": "Research Assistant",
        "description": "Web research and information synthesis",
        "system_prompt": "You are a research assistant. Search the web and synthesize information from multiple sources.",
    },
}


def get_auth_headers(api_key: str) -> dict:
    """Get authentication headers for Open WebUI API."""
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def get_csrf_token(client: httpx.Client, url: str, api_key: str) -> str | None:
    """Get CSRF token from Open WebUI."""
    try:
        resp = client.get(f"{url}/api/auth/csrftoken")
        if resp.status_code == 200:
            return resp.json().get("csrftoken")
    except Exception:
        pass
    return None


def login(client: httpx.Client, url: str, email: str, password: str, csrf_token: str | None = None) -> bool:
    """Login to Open WebUI and return session."""
    headers = {"Content-Type": "application/json"}
    if csrf_token:
        headers["x-csrf-token"] = csrf_token

    try:
        resp = client.post(
            f"{url}/api/auth/login",
            json={"email": email, "password": password},
            headers=headers,
        )
        return resp.status_code == 200
    except Exception:
        return False


def get_workspaces(client: httpx.Client, url: str, api_key: str) -> list[dict]:
    """Get existing workspaces."""
    try:
        resp = client.get(f"{url}/api/v1/workspaces", headers=get_auth_headers(api_key))
        if resp.status_code == 200:
            return resp.json().get("data", [])
    except Exception:
        pass
    return []


def create_workspace(client: httpx.Client, url: str, api_key: str, workspace: dict) -> bool:
    """Create a new workspace."""
    try:
        resp = client.post(
            f"{url}/api/v1/workspaces",
            json=workspace,
            headers=get_auth_headers(api_key),
        )
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"  Failed to create workspace {workspace.get('name', 'unknown')}: {e}")
        return False


def update_workspace(client: httpx.Client, url: str, api_key: str, workspace_id: str, workspace: dict) -> bool:
    """Update an existing workspace."""
    try:
        resp = client.put(
            f"{url}/api/v1/workspaces/{workspace_id}",
            json=workspace,
            headers=get_auth_headers(api_key),
        )
        return resp.status_code == 200
    except Exception:
        return False


def configure_mcp_servers(client: httpx.Client, url: str, api_key: str, mcp_file_path: str) -> bool:
    """Read mcp-servers.json and register them via Open WebUI API.

    Note: The MCP server configuration API is not well-documented in Open WebUI.
    This attempts to use the settings endpoint but may need adjustment based on
    the actual Open WebUI version and API structure.
    """
    mcp_file = Path(mcp_file_path)
    if not mcp_file.exists():
        print(f"  MCP config file not found: {mcp_file_path}")
        return False

    if not api_key:
        print("  Skipping MCP config: no API key provided")
        return False

    try:
        with open(mcp_file, "r") as f:
            mcp_data = json.load(f)

        # Get current settings
        settings_url = f"{url}/api/v1/settings"
        resp = client.get(settings_url, headers=get_auth_headers(api_key))

        if resp.status_code == 401 or resp.status_code == 403:
            print("  Skipping MCP config: authentication failed")
            return False

        if resp.status_code != 200:
            print(f"  Failed to fetch settings: {resp.status_code}")
            return False

        current_settings = resp.json()
        mcp_config = current_settings.get("mcp_servers", {})

        # Add each MCP server from the config
        for server in mcp_data.get("tool_servers", []):
            # Use URL as key for the MCP server config
            mcp_config[server["url"]] = {
                "url": server["url"],
                "name": server["name"],
                "api_key": server.get("api_key", ""),
            }
            print(f"  Configuring: {server['name']} ({server['url']})")

        # Push updated settings
        update_resp = client.post(
            settings_url,
            json={"mcp_servers": mcp_config},
            headers=get_auth_headers(api_key),
        )

        if update_resp.status_code == 200:
            print(f"  Successfully configured {len(mcp_data.get('tool_servers', []))} MCP servers")
            return True
        else:
            print(f"  Failed to update settings: {update_resp.status_code}")
            return False

    except Exception as e:
        print(f"  Failed to configure MCP servers: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Setup Open WebUI workspaces")
    parser.add_argument("--url", default=os.environ.get("OPENWEBUI_URL", "http://localhost:8080"), help="Open WebUI URL")
    parser.add_argument("--api-key", default=os.environ.get("OPENWEBUI_API_KEY"), help="Open WebUI API key")
    parser.add_argument("--email", default=os.environ.get("OPENWEBUI_EMAIL"), help="Admin email (for login)")
    parser.add_argument("--password", default=os.environ.get("OPENWEBUI_PASSWORD"), help="Admin password (for login)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created without making changes")
    args = parser.parse_args()

    # Check auth
    if not args.api_key and not (args.email and args.password):
        print("Error: Provide --api-key or set OPENWEBUI_EMAIL + OPENWEBUI_PASSWORD")
        sys.exit(1)

    client = httpx.Client(timeout=30.0)

    # Get CSRF token if using password auth
    csrf_token = None
    if args.email and args.password:
        csrf_token = get_csrf_token(client, args.url, "")
        if not login(client, args.url, args.email, args.password, csrf_token):
            print("Error: Login failed")
            sys.exit(1)
        print("Logged in successfully")

    # Get existing workspaces
    existing = get_workspaces(client, args.url, args.api_key or "")
    existing_names = {ws.get("name", "").lower().replace(" ", "-") for ws in existing}
    print(f"Found {len(existing)} existing workspaces")

    # Create or update workspaces
    created = 0
    for ws_id, ws_config in WORKSPACES.items():
        if ws_id in existing_names:
            print(f"  Skipping {ws_id}: already exists")
            continue

        workspace_data = {
            "name": ws_config["name"],
            "description": ws_config["description"],
            "system_prompt": ws_config["system_prompt"],
            "default_model": ws_id,
        }

        if args.dry_run:
            print(f"  [DRY RUN] Would create: {ws_config['name']}")
            continue

        if create_workspace(client, args.url, args.api_key or "", workspace_data):
            print(f"  Created: {ws_config['name']}")
            created += 1
        else:
            print(f"  Failed: {ws_config['name']}")

    print(f"\nDone. Created {created} workspace(s).")

    # Automate MCP Server Configuration
    script_dir = Path(__file__).parent
    mcp_file = script_dir.parent / "imports" / "openwebui" / "mcp-servers.json"
    if mcp_file.exists():
        print("\nConfiguring MCP Tool Servers...")
        configure_mcp_servers(client, args.url, args.api_key or "", str(mcp_file))

    client.close()


if __name__ == "__main__":
    main()
