"""
Git Merge Tool - Merge branches
"""

import logging
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter

logger = logging.getLogger(__name__)

try:
    from git import GitCommandError, InvalidGitRepositoryError, Repo
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


class GitMergeTool(BaseTool):
    """Merge Git branches"""

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="git_merge",
            description="Merge one Git branch into another",
            category=ToolCategory.DEV,
            requires_confirmation=True,  # Merges modify history
            parameters=[
                ToolParameter(
                    name="repo_path",
                    param_type="string",
                    description="Path to repository (default: current directory)",
                    required=False
                ),
                ToolParameter(
                    name="branch",
                    param_type="string",
                    description="Branch to merge into current branch",
                    required=True
                ),
                ToolParameter(
                    name="no_ff",
                    param_type="bool",
                    description="Create merge commit even if fast-forward possible",
                    required=False
                ),
                ToolParameter(
                    name="message",
                    param_type="string",
                    description="Custom merge commit message",
                    required=False
                )
            ]
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute git merge"""

        if not GIT_AVAILABLE:
            return self._error_response("GitPython not installed. Run: pip install GitPython")

        repo_path = parameters.get("repo_path", ".")
        branch_name = parameters.get("branch")
        no_ff = parameters.get("no_ff", False)
        message = parameters.get("message")

        if not branch_name:
            return self._error_response("Branch name is required")

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

            # Check if branch exists
            if branch_name not in [b.name for b in repo.branches]:
                return self._error_response(f"Branch '{branch_name}' not found")

            # Get current branch
            current_branch = repo.active_branch.name
            current_commit = repo.head.commit.hexsha[:8]

            # Build merge arguments
            merge_args = [branch_name]
            if no_ff:
                merge_args.extend(['--no-ff'])
            if message:
                merge_args.extend(['-m', message])

            # Execute merge
            logger.info(f"Merging {branch_name} into {current_branch}")

            try:
                repo.git.merge(*merge_args)
                new_commit = repo.head.commit.hexsha[:8]

                # Check if it was a fast-forward
                was_ff = current_commit != new_commit and not no_ff

                return self._success_response(
                    result=f"Successfully merged {branch_name} into {current_branch}",
                    metadata={
                        "current_branch": current_branch,
                        "merged_branch": branch_name,
                        "old_commit": current_commit,
                        "new_commit": new_commit,
                        "fast_forward": was_ff
                    }
                )
            except GitCommandError as e:
                if "CONFLICT" in str(e):
                    return self._error_response(
                        f"Merge conflict detected. Resolve conflicts and commit manually.\n{str(e)}"
                    )
                raise

        except InvalidGitRepositoryError:
            return self._error_response(f"Not a git repository: {repo_path}")
        except GitCommandError as e:
            return self._error_response(f"Git command failed: {e}")
        except Exception as e:
            return self._error_response(f"Merge failed: {str(e)}")
