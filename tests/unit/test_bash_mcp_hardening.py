"""
Tests for bash MCP sidecar security hardening (Task 1.1).

Verifies: allowed commands pass, blocked binaries reject (403),
malformed input rejects (400), oversized command rejects (400),
unapproved token rejects (403).
"""

from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client():
    """Import app after patching redis so tests run without a Redis server."""
    import importlib
    import sys

    # Provide a mock redis module
    mock_redis = MagicMock()
    mock_r = MagicMock()
    mock_redis.from_url.return_value = mock_r

    with patch.dict(sys.modules, {"redis": mock_redis}):
        # Force fresh import
        if "scripts.mcp.bash_mcp_server" in sys.modules:
            del sys.modules["scripts.mcp.bash_mcp_server"]
        spec = importlib.util.spec_from_file_location(
            "bash_mcp_server",
            "scripts/mcp/bash_mcp_server.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

    return TestClient(module.app), module, mock_r


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBashMCPHardening:

    def setup_method(self):
        self.client, self.module, self.mock_r = _make_client()

    def _set_approved(self, user_id: str, token: str):
        """Pre-configure mock Redis to return 'approved' for the given key."""
        key = f"portal:approval:{user_id}:{token}"
        self.mock_r.get.side_effect = lambda k: b"approved" if k == key else None

    def test_allowed_command_passes(self):
        """An approved `ls` command should execute (returncode returned)."""
        self._set_approved("user1", "tok1")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="file.txt\n", stderr="", returncode=0)
            resp = self.client.post(
                "/tool/bash",
                json={"user_id": "user1", "command": "ls /tmp", "approval_token": "tok1"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["returncode"] == 0

    def test_unapproved_token_rejects(self):
        """Missing or wrong approval token must return 403."""
        self.mock_r.get.return_value = None  # nothing in Redis
        resp = self.client.post(
            "/tool/bash",
            json={"user_id": "user1", "command": "ls", "approval_token": "bad-token"},
        )
        assert resp.status_code == 403
        assert "approved" in resp.json()["detail"].lower()

    def test_blocked_binary_rejects(self):
        """A binary not in the allowlist (e.g. `rm`) must return 403."""
        self._set_approved("user1", "tok2")
        resp = self.client.post(
            "/tool/bash",
            json={"user_id": "user1", "command": "rm -rf /", "approval_token": "tok2"},
        )
        assert resp.status_code == 403
        assert "not allowed" in resp.json()["detail"].lower()

    def test_oversized_command_rejects(self):
        """Commands longer than _MAX_CMD_LENGTH must return 400."""
        self._set_approved("user1", "tok3")
        resp = self.client.post(
            "/tool/bash",
            json={
                "user_id": "user1",
                "command": "ls " + "a" * 2100,
                "approval_token": "tok3",
            },
        )
        assert resp.status_code == 400
        assert "maximum length" in resp.json()["detail"].lower()

    def test_malformed_command_rejects(self):
        """A shell command with unmatched quotes must return 400."""
        self._set_approved("user1", "tok4")
        resp = self.client.post(
            "/tool/bash",
            json={"user_id": "user1", "command": "ls 'unclosed", "approval_token": "tok4"},
        )
        assert resp.status_code == 400
        assert "malformed" in resp.json()["detail"].lower()

    def test_empty_command_rejects(self):
        """An empty command string must return 400."""
        self._set_approved("user1", "tok5")
        resp = self.client.post(
            "/tool/bash",
            json={"user_id": "user1", "command": "   ", "approval_token": "tok5"},
        )
        assert resp.status_code == 400

    def test_too_many_args_rejects(self):
        """Commands with more than _MAX_ARGS arguments must return 400."""
        self._set_approved("user1", "tok6")
        many_args = "ls " + " ".join([f"arg{i}" for i in range(60)])
        resp = self.client.post(
            "/tool/bash",
            json={"user_id": "user1", "command": many_args, "approval_token": "tok6"},
        )
        assert resp.status_code == 400
        assert "too many arguments" in resp.json()["detail"].lower()

    def test_shell_injection_via_semicolon_blocked(self):
        """Shell injection attempt using `;` — binary `ls;id` is not in allowlist."""
        self._set_approved("user1", "tok7")
        resp = self.client.post(
            "/tool/bash",
            json={"user_id": "user1", "command": "ls; id", "approval_token": "tok7"},
        )
        # shlex.split produces ["ls;", "id"] — "ls;" is not in allowlist
        assert resp.status_code == 403
