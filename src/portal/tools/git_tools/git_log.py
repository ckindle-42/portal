"""
Git Log Tool - View commit history
"""

import logging
from datetime import datetime
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter

logger = logging.getLogger(__name__)

try:
    from git import GitCommandError, InvalidGitRepositoryError, Repo
    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False


class GitLogTool(BaseTool):
    """View Git commit history"""

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="git_log",
            description="View Git commit history with various options",
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
                    name="max_count",
                    param_type="int",
                    description="Maximum number of commits to show (default: 10)",
                    required=False
                ),
                ToolParameter(
                    name="author",
                    param_type="string",
                    description="Filter by author name",
                    required=False
                ),
                ToolParameter(
                    name="since",
                    param_type="string",
                    description="Show commits since date (e.g., '2 weeks ago')",
                    required=False
                ),
                ToolParameter(
                    name="file_path",
                    param_type="string",
                    description="Show commits affecting specific file",
                    required=False
                )
            ]
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute git log"""

        if not GIT_AVAILABLE:
            return self._error_response("GitPython not installed. Run: pip install GitPython")

        repo_path = parameters.get("repo_path", ".")
        max_count = parameters.get("max_count", 10)
        author = parameters.get("author")
        since = parameters.get("since")
        file_path = parameters.get("file_path")

        try:
            # Open repository
            repo = Repo(repo_path)

            if repo.bare:
                return self._error_response("Repository is bare")

            # Build git log arguments
            kwargs = {"max_count": max_count}
            if author:
                kwargs["author"] = author
            if since:
                kwargs["since"] = since

            # Get commits
            if file_path:
                commits = list(repo.iter_commits(paths=file_path, **kwargs))
            else:
                commits = list(repo.iter_commits(**kwargs))

            if not commits:
                return self._success_response(
                    result="No commits found matching criteria",
                    metadata={"count": 0}
                )

            # Format commit history
            log_lines = []
            for commit in commits:
                commit_date = datetime.fromtimestamp(commit.committed_date).strftime('%Y-%m-%d %H:%M')
                log_lines.append(
                    f"• {commit.hexsha[:8]} - {commit.author.name}\n"
                    f"  {commit_date}\n"
                    f"  {commit.message.strip()}\n"
                )

            result = "\n".join(log_lines)

            # Truncate if too long
            max_length = 3000
            if len(result) > max_length:
                result = result[:max_length] + f"\n\n... ({len(commits)} total commits, showing first {len(log_lines[:20])})"

            return self._success_response(
                result=result,
                metadata={
                    "count": len(commits),
                    "showing": min(len(commits), 20)
                }
            )

        except InvalidGitRepositoryError:
            return self._error_response(f"Not a git repository: {repo_path}")
        except GitCommandError as e:
            return self._error_response(f"Git command failed: {e}")
        except Exception as e:
            return self._error_response(f"Log retrieval failed: {str(e)}")
