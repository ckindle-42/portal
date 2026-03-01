"""WorkspaceRegistry — maps workspace IDs to configured model names."""

from typing import Any


class WorkspaceRegistry:
    """Registry for workspace→model mappings.

    Workspaces are virtual model names that map to a concrete Ollama model,
    optionally with a system prompt override. The proxy router (router.py)
    and the IntelligentRouter can both consult this registry so all interfaces
    (Web, Telegram, Slack) benefit from workspace routing.
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
