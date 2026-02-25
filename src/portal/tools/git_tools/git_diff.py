"""
Git Diff Tool - Show differences in repository
"""

import asyncio
import logging
from typing import Dict, Any
from pathlib import Path

from portal.core.interfaces.tool import BaseTool, ToolMetadata, ToolCategory, ToolParameter

logger = logging.getLogger(__name__)

try:
    from git import Repo, GitCommandError, InvalidGitRepositoryError
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


class GitDiffTool(BaseTool):
    """Show Git repository differences"""

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="git_diff",
            description="Show differences in Git repository (staged, unstaged, or commits)",
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
                    name="staged",
                    param_type="bool",
                    description="Show staged changes (default: False)",
                    required=False
                ),
                ToolParameter(
                    name="commit",
                    param_type="string",
                    description="Compare with specific commit",
                    required=False
                ),
                ToolParameter(
                    name="file_path",
                    param_type="string",
                    description="Show diff for specific file only",
                    required=False
                )
            ]
        )

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute git diff"""

        if not GIT_AVAILABLE:
            return self._error_response("GitPython not installed. Run: pip install GitPython")

        repo_path = parameters.get("repo_path", ".")
        staged = parameters.get("staged", False)
        commit = parameters.get("commit")
        file_path = parameters.get("file_path")

        try:
            # Open repository
            repo = Repo(repo_path)

            if repo.bare:
                return self._error_response("Repository is bare")

            # Determine what diff to show
            diff_text = ""
            diff_type = ""

            if commit:
                # Diff against specific commit
                diff_text = repo.git.diff(commit, file_path or "")
                diff_type = f"Changes from commit {commit[:8]}"
            elif staged:
                # Diff of staged changes
                diff_text = repo.git.diff("--cached", file_path or "")
                diff_type = "Staged changes"
            else:
                # Diff of unstaged changes
                diff_text = repo.git.diff(file_path or "")
                diff_type = "Unstaged changes"

            if not diff_text:
                return self._success_response(
                    result=f"No {diff_type.lower()} to display",
                    metadata={"diff_type": diff_type, "has_changes": False}
                )

            # Truncate if too long for Telegram
            max_length = 3000
            if len(diff_text) > max_length:
                diff_text = diff_text[:max_length] + f"\n\n... (truncated, {len(diff_text) - max_length} more chars)"

            return self._success_response(
                result=f"{diff_type}:\n\n```diff\n{diff_text}\n```",
                metadata={
                    "diff_type": diff_type,
                    "has_changes": True,
                    "length": len(diff_text)
                }
            )

        except InvalidGitRepositoryError:
            return self._error_response(f"Not a git repository: {repo_path}")
        except GitCommandError as e:
            return self._error_response(f"Git command failed: {e}")
        except Exception as e:
            return self._error_response(f"Diff failed: {str(e)}")
