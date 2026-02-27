"""
Git Branch Tool - Manage branches
"""

import logging
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter
from portal.tools.git_tools._base import GIT_AVAILABLE, GitCommandError, open_repo

logger = logging.getLogger(__name__)


class GitBranchTool(BaseTool):
    """Manage Git branches"""

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="git_branch",
            description="List, create, delete, or switch Git branches",
            category=ToolCategory.DEV,
            requires_confirmation=False,
            parameters=[
                ToolParameter(
                    name="repo_path",
                    param_type="string",
                    description="Path to repository (default: current directory)",
                    required=False
                ),
                ToolParameter(
                    name="action",
                    param_type="string",
                    description="Action: list, create, delete, checkout (default: list)",
                    required=False
                ),
                ToolParameter(
                    name="branch_name",
                    param_type="string",
                    description="Branch name (for create/delete/checkout)",
                    required=False
                ),
                ToolParameter(
                    name="force",
                    param_type="bool",
                    description="Force operation (for delete)",
                    required=False
                )
            ]
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute git branch operations"""

        if not GIT_AVAILABLE:
            return self._error_response("GitPython not installed. Run: pip install GitPython")

        repo_path = parameters.get("repo_path", ".")
        action = parameters.get("action", "list").lower()
        branch_name = parameters.get("branch_name")
        force = parameters.get("force", False)

        repo, err = open_repo(repo_path)
        if err:
            return err

        try:
            if action == "list":
                # List all branches
                branches = []
                for branch in repo.branches:
                    is_current = branch == repo.active_branch
                    prefix = "* " if is_current else "  "
                    branches.append(f"{prefix}{branch.name}")

                return self._success_response(
                    result="Branches:\n" + "\n".join(branches),
                    metadata={
                        "current": repo.active_branch.name,
                        "branches": [b.name for b in repo.branches]
                    }
                )

            elif action == "create":
                if not branch_name:
                    return self._error_response("branch_name required for create")

                # Create new branch
                new_branch = repo.create_head(branch_name)
                return self._success_response(
                    result=f"Created branch: {branch_name}",
                    metadata={"branch": branch_name, "commit": new_branch.commit.hexsha[:8]}
                )

            elif action == "delete":
                if not branch_name:
                    return self._error_response("branch_name required for delete")

                # Delete branch
                repo.delete_head(branch_name, force=force)
                return self._success_response(
                    result=f"Deleted branch: {branch_name}",
                    metadata={"branch": branch_name, "forced": force}
                )

            elif action == "checkout":
                if not branch_name:
                    return self._error_response("branch_name required for checkout")

                # Checkout branch
                repo.git.checkout(branch_name)
                return self._success_response(
                    result=f"Switched to branch: {branch_name}",
                    metadata={"branch": branch_name}
                )

            else:
                return self._error_response(f"Unknown action: {action}. Use list, create, delete, or checkout")

        except GitCommandError as e:
            return self._error_response(f"Git command failed: {e}")
        except Exception as e:
            return self._error_response(f"Branch operation failed: {str(e)}")
