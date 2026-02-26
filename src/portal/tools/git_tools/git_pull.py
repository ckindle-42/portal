"""
Git Pull Tool - Pull from remote
"""

import asyncio
import logging
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter

logger = logging.getLogger(__name__)

try:
    from git import GitCommandError, InvalidGitRepositoryError, Repo
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


class GitPullTool(BaseTool):
    """Pull changes from remote repository"""

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="git_pull",
            description="Pull and merge changes from remote Git repository",
            category=ToolCategory.DEV,
            requires_confirmation=True,  # Pull can modify working tree
            parameters=[
                ToolParameter(
                    name="repo_path",
                    param_type="string",
                    description="Path to repository (default: current directory)",
                    required=False
                ),
                ToolParameter(
                    name="remote",
                    param_type="string",
                    description="Remote name (default: origin)",
                    required=False
                ),
                ToolParameter(
                    name="branch",
                    param_type="string",
                    description="Branch to pull (default: current branch)",
                    required=False
                ),
                ToolParameter(
                    name="rebase",
                    param_type="bool",
                    description="Rebase instead of merge (default: False)",
                    required=False
                )
            ]
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute git pull"""

        if not GIT_AVAILABLE:
            return self._error_response("GitPython not installed. Run: pip install GitPython")

        repo_path = parameters.get("repo_path", ".")
        remote_name = parameters.get("remote", "origin")
        branch = parameters.get("branch")
        rebase = parameters.get("rebase", False)

        try:
            # Open repository
            repo = Repo(repo_path)

            if repo.bare:
                return self._error_response("Repository is bare")

            # Check for uncommitted changes
            if repo.is_dirty():
                return self._error_response(
                    "Working tree has uncommitted changes. Commit or stash them first."
                )

            # Get remote
            if remote_name not in [r.name for r in repo.remotes]:
                return self._error_response(f"Remote '{remote_name}' not found")

            remote = repo.remote(remote_name)

            # Use current branch if not specified
            if not branch:
                if repo.head.is_detached:
                    return self._error_response("HEAD is detached, specify branch explicitly")
                branch = repo.active_branch.name

            # Record current HEAD for comparison
            old_commit = repo.head.commit.hexsha[:8]

            # Execute pull asynchronously
            logger.info(f"Pulling {branch} from {remote_name}")

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            if rebase:
                pull_info = await loop.run_in_executor(
                    None,
                    lambda: remote.pull(branch, rebase=True)
                )
            else:
                pull_info = await loop.run_in_executor(
                    None,
                    lambda: remote.pull(branch)
                )

            # Get new commit
            new_commit = repo.head.commit.hexsha[:8]

            # Check if anything changed
            if old_commit == new_commit:
                result = "Already up to date"
            else:
                result = f"Updated from {old_commit} to {new_commit}"

            return self._success_response(
                result=result,
                metadata={
                    "remote": remote_name,
                    "branch": branch,
                    "old_commit": old_commit,
                    "new_commit": new_commit,
                    "rebased": rebase
                }
            )

        except InvalidGitRepositoryError:
            return self._error_response(f"Not a git repository: {repo_path}")
        except GitCommandError as e:
            return self._error_response(f"Git command failed: {e}")
        except Exception as e:
            return self._error_response(f"Pull failed: {str(e)}")
