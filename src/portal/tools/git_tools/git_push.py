"""
Git Push Tool - Push to remote
"""

import asyncio
import logging
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter
from portal.tools.git_tools._base import GIT_AVAILABLE, GitCommandError, open_repo

logger = logging.getLogger(__name__)


class GitPushTool(BaseTool):
    """Push commits to remote repository"""

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="git_push",
            description="Push commits to remote Git repository",
            category=ToolCategory.DEV,
            requires_confirmation=True,  # Pushes affect remote
            parameters=[
                ToolParameter(
                    name="repo_path",
                    param_type="string",
                    description="Path to repository (default: current directory)",
                    required=False,
                ),
                ToolParameter(
                    name="remote",
                    param_type="string",
                    description="Remote name (default: origin)",
                    required=False,
                ),
                ToolParameter(
                    name="branch",
                    param_type="string",
                    description="Branch to push (default: current branch)",
                    required=False,
                ),
                ToolParameter(
                    name="force",
                    param_type="bool",
                    description="Force push (DANGEROUS - use with caution)",
                    required=False,
                ),
                ToolParameter(
                    name="set_upstream",
                    param_type="bool",
                    description="Set upstream tracking (default: False)",
                    required=False,
                ),
            ],
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Execute git push"""

        if not GIT_AVAILABLE:
            return self._error_response("GitPython not installed. Run: pip install GitPython")

        repo_path = parameters.get("repo_path", ".")
        remote_name = parameters.get("remote", "origin")
        branch = parameters.get("branch")
        force = parameters.get("force", False)
        set_upstream = parameters.get("set_upstream", False)

        repo, err = open_repo(repo_path)
        if err:
            return err

        try:
            # Get remote
            if remote_name not in [r.name for r in repo.remotes]:
                return self._error_response(f"Remote '{remote_name}' not found")

            remote = repo.remote(remote_name)

            # Use current branch if not specified
            if not branch:
                if repo.head.is_detached:
                    return self._error_response("HEAD is detached, specify branch explicitly")
                branch = repo.active_branch.name

            # Build push arguments
            push_kwargs = {}
            if force:
                push_kwargs["force"] = True
            if set_upstream:
                push_kwargs["set_upstream"] = True

            # Execute push asynchronously
            logger.info("Pushing %s to %s", branch, remote_name)

            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            push_info = await loop.run_in_executor(None, lambda: remote.push(branch, **push_kwargs))

            # Check results
            if push_info:
                info = push_info[0]
                if info.flags & info.ERROR:
                    return self._error_response(f"Push failed: {info.summary}")

            return self._success_response(
                result=f"Successfully pushed {branch} to {remote_name}",
                metadata={
                    "remote": remote_name,
                    "branch": branch,
                    "forced": force,
                    "upstream_set": set_upstream,
                },
            )

        except GitCommandError as e:
            return self._error_response(f"Git command failed: {e}")
        except Exception as e:
            return self._error_response(f"Push failed: {str(e)}")
