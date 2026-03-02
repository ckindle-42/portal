"""WorkspaceRegistry — maps workspace IDs to configured model names and ACLs."""

from dataclasses import dataclass
from typing import Any


@dataclass
class WorkspaceACL:
    """Access Control List for a workspace."""

    allowed_tools: list[str] | None = None  # None means all tools allowed
    rate_limit: int | None = None  # Requests per minute, None means use default
    max_tokens: int | None = None  # Max response tokens, None means use model default
    allowed_users: list[str] | None = None  # None means all users allowed
    blocked_users: list[str] | None = None  # Explicitly blocked users


class WorkspaceRegistry:
    """Registry for workspace→model mappings.

    Workspaces are virtual model names that map to a concrete Ollama model,
    optionally with a system prompt override. The proxy router (router.py)
    and the IntelligentRouter can both consult this registry so all interfaces
    (Web, Telegram, Slack) benefit from workspace routing.

    Supports ACL (Access Control List) rules per workspace for:
    - Tool restrictions
    - Rate limiting
    - User access control
    """

    def __init__(self, workspaces: dict[str, Any]) -> None:
        self._workspaces = workspaces

    def get_model(self, workspace_id: str) -> str | None:
        """Return the model name for *workspace_id*, or None if unknown."""
        ws = self._workspaces.get(workspace_id)
        return ws.get("model") if ws else None

    def list_workspaces(self) -> list[str]:
        """Return names of all registered workspaces."""
        return list(self._workspaces.keys())

    def get_system_prompt(self, workspace_id: str) -> str | None:
        """Return the system prompt override for *workspace_id*, or None if none."""
        ws = self._workspaces.get(workspace_id)
        return ws.get("system_prompt") if ws else None

    def get_acl(self, workspace_id: str) -> WorkspaceACL | None:
        """Return the ACL rules for *workspace_id*, or None if none defined."""
        ws = self._workspaces.get(workspace_id)
        if not ws:
            return None

        acl_data = ws.get("acl")
        if not acl_data:
            return None

        return WorkspaceACL(
            allowed_tools=acl_data.get("allowed_tools"),
            rate_limit=acl_data.get("rate_limit"),
            max_tokens=acl_data.get("max_tokens"),
            allowed_users=acl_data.get("allowed_users"),
            blocked_users=acl_data.get("blocked_users"),
        )

    def is_tool_allowed(self, workspace_id: str, tool_name: str) -> bool:
        """Check if a tool is allowed in a workspace."""
        acl = self.get_acl(workspace_id)
        if acl is None:
            return True  # No ACL means all tools allowed
        if acl.allowed_tools is None:
            return True  # None means all tools allowed
        return tool_name in acl.allowed_tools

    def is_user_allowed(self, workspace_id: str, user_id: str) -> bool:
        """Check if a user is allowed to access a workspace."""
        acl = self.get_acl(workspace_id)
        if acl is None:
            return True  # No ACL means all users allowed

        # Check blocked users first
        if acl.blocked_users and user_id in acl.blocked_users:
            return False

        # If allowed_users is defined, check membership
        if acl.allowed_users is not None:
            return user_id in acl.allowed_users

        return True

    def get_rate_limit(self, workspace_id: str) -> int | None:
        """Get the rate limit for a workspace (requests per minute)."""
        acl = self.get_acl(workspace_id)
        return acl.rate_limit if acl else None

    def get_max_tokens(self, workspace_id: str) -> int | None:
        """Get the max tokens limit for a workspace."""
        acl = self.get_acl(workspace_id)
        return acl.max_tokens if acl else None
