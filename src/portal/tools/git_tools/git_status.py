"""
Git Status Tool - Check repository status
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


class GitStatusTool(BaseTool):
    """Check Git repository status"""

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="git_status",
            description="Check the status of a Git repository",
            category=ToolCategory.DEV,
            requires_confirmation=False,
            parameters=[
                ToolParameter(
                    name="repo_path",
                    param_type="string",
                    description="Path to repository (default: current directory)",
                    required=False
                )
            ]
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute git status"""

        if not GIT_AVAILABLE:
            return self._error_response("GitPython not installed. Run: pip install GitPython")

        repo_path = parameters.get("repo_path", ".")

        try:
            # Open repository
            repo = Repo(repo_path)

            # Check if repo is valid
            if repo.bare:
                return self._error_response("Repository is bare")

            # Gather status information
            status_info = {
                "branch": repo.active_branch.name if not repo.head.is_detached else "HEAD detached",
                "commit": repo.head.commit.hexsha[:8],
                "clean": not repo.is_dirty(),
                "modified": [item.a_path for item in repo.index.diff(None)],
                "staged": [item.a_path for item in repo.index.diff("HEAD")],
                "untracked": repo.untracked_files,
            }

            # Get ahead/behind info if tracking remote
            try:
                tracking_branch = repo.active_branch.tracking_branch()
                if tracking_branch:
                    ahead = len(list(repo.iter_commits(f'{tracking_branch}..{repo.active_branch}')))
                    behind = len(list(repo.iter_commits(f'{repo.active_branch}..{tracking_branch}')))
                    status_info["ahead"] = ahead
                    status_info["behind"] = behind
                    status_info["tracking"] = tracking_branch.name
            except Exception:
                # No tracking branch
                pass

            # Create summary message
            summary_parts = []
            summary_parts.append(f"On branch {status_info['branch']}")

            if status_info.get("tracking"):
                if status_info.get("ahead", 0) > 0:
                    summary_parts.append(f"Ahead by {status_info['ahead']} commit(s)")
                if status_info.get("behind", 0) > 0:
                    summary_parts.append(f"Behind by {status_info['behind']} commit(s)")

            if status_info["clean"]:
                summary_parts.append("Working tree clean")
            else:
                if status_info["staged"]:
                    summary_parts.append(f"{len(status_info['staged'])} file(s) staged")
                if status_info["modified"]:
                    summary_parts.append(f"{len(status_info['modified'])} file(s) modified")
                if status_info["untracked"]:
                    summary_parts.append(f"{len(status_info['untracked'])} file(s) untracked")

            return self._success_response(
                result="\n".join(summary_parts),
                metadata=status_info
            )

        except InvalidGitRepositoryError:
            return self._error_response(f"Not a git repository: {repo_path}")
        except GitCommandError as e:
            return self._error_response(f"Git command failed: {e}")
        except Exception as e:
            return self._error_response(f"Status check failed: {str(e)}")
