"""
Git Clone Tool - Clone repositories
"""

import logging
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter
from portal.tools.git_tools._base import GIT_AVAILABLE, GitCommandError, Repo

logger = logging.getLogger(__name__)


class GitCloneTool(BaseTool):
    """Clone Git repositories"""

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="git_clone",
            description="Clone a Git repository to local machine",
            category=ToolCategory.DEV,
            requires_confirmation=True,
            parameters=[
                ToolParameter(
                    name="url",
                    param_type="string",
                    description="Repository URL (HTTPS or SSH)",
                    required=True
                ),
                ToolParameter(
                    name="destination",
                    param_type="string",
                    description="Destination directory (default: repo name)",
                    required=False
                ),
                ToolParameter(
                    name="branch",
                    param_type="string",
                    description="Branch to clone (default: default branch)",
                    required=False
                ),
                ToolParameter(
                    name="depth",
                    param_type="int",
                    description="Clone depth for shallow clone",
                    required=False
                )
            ]
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute git clone"""

        if not GIT_AVAILABLE:
            return self._error_response("GitPython not installed. Run: pip install GitPython")

        url = parameters.get("url")
        destination = parameters.get("destination")
        branch = parameters.get("branch")
        depth = parameters.get("depth")

        try:
            # Prepare clone arguments
            kwargs = {}
            if branch:
                kwargs["branch"] = branch
            if depth:
                kwargs["depth"] = depth

            # Clone repository
            logger.info("Cloning %s", url)
            repo = Repo.clone_from(url, destination or None, **kwargs)

            return self._success_response(
                result=f"Successfully cloned to {repo.working_dir}",
                metadata={
                    "url": url,
                    "path": str(repo.working_dir),
                    "branch": repo.active_branch.name,
                    "commit": repo.head.commit.hexsha[:8]
                }
            )

        except GitCommandError as e:
            return self._error_response(f"Git clone failed: {e}")
        except Exception as e:
            return self._error_response(f"Clone failed: {str(e)}")
