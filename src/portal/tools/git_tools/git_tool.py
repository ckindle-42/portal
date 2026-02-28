"""
Git Tool - Unified repository management

Consolidates git_branch, git_clone, git_commit, git_diff, git_log,
git_merge, git_pull, git_push, and git_status into a single class.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory
from portal.tools.git_tools._base import GIT_AVAILABLE, GitCommandError, Repo, open_repo

logger = logging.getLogger(__name__)


class GitTool(BaseTool):
    """Unified Git repository management (branch, clone, commit, diff, log, merge, pull, push, status)."""

    METADATA = {
        "name": "git",
        "description": (
            "Manage Git repositories: status, log, diff, branch, commit, "
            "clone, pull, push, merge"
        ),
        "category": ToolCategory.DEV,
        "requires_confirmation": False,  # set per-action in execute()
        "parameters": [
            {"name": "action", "param_type": "string", "description": "Action: status, log, diff, branch, commit, clone, pull, push, merge", "required": True},
            {"name": "repo_path", "param_type": "string", "description": "Path to repository (default: current directory)", "required": False},
            # branch params
            {"name": "branch_name", "param_type": "string", "description": "Branch name (branch: create/delete/checkout; merge/pull/push: target branch)", "required": False},
            {"name": "force", "param_type": "bool", "description": "Force operation (branch delete, push)", "required": False},
            # commit params
            {"name": "message", "param_type": "string", "description": "Commit message (commit) or merge commit message (merge)", "required": False},
            {"name": "add_all", "param_type": "bool", "description": "Stage all modified files before committing", "required": False},
            {"name": "files", "param_type": "list", "description": "Specific files to stage before committing", "required": False},
            # diff params
            {"name": "staged", "param_type": "bool", "description": "Show staged changes (diff)", "required": False},
            {"name": "commit", "param_type": "string", "description": "Compare against specific commit (diff)", "required": False},
            {"name": "file_path", "param_type": "string", "description": "Limit diff/log to a specific file path", "required": False},
            # log params
            {"name": "max_count", "param_type": "int", "description": "Maximum commits to show (log, default: 10)", "required": False},
            {"name": "author", "param_type": "string", "description": "Filter commits by author (log)", "required": False},
            {"name": "since", "param_type": "string", "description": "Show commits since date e.g. '2 weeks ago' (log)", "required": False},
            # clone params
            {"name": "url", "param_type": "string", "description": "Repository URL (clone)", "required": False},
            {"name": "destination", "param_type": "string", "description": "Destination directory (clone)", "required": False},
            {"name": "depth", "param_type": "int", "description": "Shallow clone depth (clone)", "required": False},
            # pull/push params
            {"name": "remote", "param_type": "string", "description": "Remote name (pull/push, default: origin)", "required": False},
            {"name": "branch", "param_type": "string", "description": "Remote branch (pull/push, default: current branch)", "required": False},
            {"name": "rebase", "param_type": "bool", "description": "Rebase instead of merge (pull)", "required": False},
            {"name": "set_upstream", "param_type": "bool", "description": "Set upstream tracking (push)", "required": False},
            # merge params
            {"name": "no_ff", "param_type": "bool", "description": "Create merge commit even if fast-forward possible", "required": False},
            # branch sub-action
            {"name": "sub_action", "param_type": "string", "description": "Branch sub-action: list, create, delete, checkout (default: list)", "required": False},
        ],
    }

    _GIT_UNAVAILABLE = {"success": False, "error": "GitPython not installed. Run: pip install GitPython"}

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Dispatch to the appropriate Git action."""
        if not GIT_AVAILABLE:
            return self._GIT_UNAVAILABLE

        action = parameters.get("action", "").lower()
        handler = self._DISPATCH.get(action)
        if not handler:
            return self._error_response(
                f"Unknown action: {action}. Use: {', '.join(self._DISPATCH)}"
            )

        # Clone doesn't need a repo to be opened
        if action == "clone":
            return await handler(self, parameters)

        repo_path = parameters.get("repo_path", ".")
        repo, err = open_repo(repo_path)
        if err:
            return err

        try:
            return await handler(self, parameters, repo)
        except GitCommandError as e:
            return self._error_response(f"Git command failed: {e}")
        except Exception as e:
            return self._error_response(f"Operation failed: {e}")

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    async def _status(self, parameters: dict[str, Any], repo: Any) -> dict[str, Any]:
        """Check repository status."""
        status_info: dict[str, Any] = {
            "branch": repo.active_branch.name if not repo.head.is_detached else "HEAD detached",
            "commit": repo.head.commit.hexsha[:8],
            "clean": not repo.is_dirty(),
            "modified": [item.a_path for item in repo.index.diff(None)],
            "staged": [item.a_path for item in repo.index.diff("HEAD")],
            "untracked": repo.untracked_files,
        }
        try:
            tracking_branch = repo.active_branch.tracking_branch()
            if tracking_branch:
                ahead = len(list(repo.iter_commits(f"{tracking_branch}..{repo.active_branch}")))
                behind = len(list(repo.iter_commits(f"{repo.active_branch}..{tracking_branch}")))
                status_info.update({"ahead": ahead, "behind": behind, "tracking": tracking_branch.name})
        except Exception:
            pass

        parts = [f"On branch {status_info['branch']}"]
        if status_info.get("tracking"):
            if status_info.get("ahead", 0) > 0:
                parts.append(f"Ahead by {status_info['ahead']} commit(s)")
            if status_info.get("behind", 0) > 0:
                parts.append(f"Behind by {status_info['behind']} commit(s)")
        if status_info["clean"]:
            parts.append("Working tree clean")
        else:
            if status_info["staged"]:
                parts.append(f"{len(status_info['staged'])} file(s) staged")
            if status_info["modified"]:
                parts.append(f"{len(status_info['modified'])} file(s) modified")
            if status_info["untracked"]:
                parts.append(f"{len(status_info['untracked'])} file(s) untracked")
        return self._success_response(result="\n".join(parts), metadata=status_info)

    async def _log(self, parameters: dict[str, Any], repo: Any) -> dict[str, Any]:
        """View commit history."""
        max_count = parameters.get("max_count", 10)
        author = parameters.get("author")
        since = parameters.get("since")
        file_path = parameters.get("file_path")
        kwargs: dict[str, Any] = {"max_count": max_count}
        if author:
            kwargs["author"] = author
        if since:
            kwargs["since"] = since
        commits = list(repo.iter_commits(paths=file_path, **kwargs) if file_path else repo.iter_commits(**kwargs))
        if not commits:
            return self._success_response(result="No commits found matching criteria", metadata={"count": 0})
        log_lines = []
        for c in commits:
            commit_date = datetime.fromtimestamp(c.committed_date).strftime("%Y-%m-%d %H:%M")
            log_lines.append(f"• {c.hexsha[:8]} - {c.author.name}\n  {commit_date}\n  {c.message.strip()}\n")
        result = "\n".join(log_lines)
        max_length = 3000
        if len(result) > max_length:
            result = result[:max_length] + f"\n\n... ({len(commits)} total commits)"
        return self._success_response(result=result, metadata={"count": len(commits)})

    async def _diff(self, parameters: dict[str, Any], repo: Any) -> dict[str, Any]:
        """Show repository differences."""
        staged = parameters.get("staged", False)
        commit = parameters.get("commit")
        file_path = parameters.get("file_path")
        if commit:
            diff_text = repo.git.diff(commit, file_path or "")
            diff_type = f"Changes from commit {commit[:8]}"
        elif staged:
            diff_text = repo.git.diff("--cached", file_path or "")
            diff_type = "Staged changes"
        else:
            diff_text = repo.git.diff(file_path or "")
            diff_type = "Unstaged changes"
        if not diff_text:
            return self._success_response(result=f"No {diff_type.lower()} to display", metadata={"diff_type": diff_type, "has_changes": False})
        max_length = 3000
        if len(diff_text) > max_length:
            diff_text = diff_text[:max_length] + f"\n\n... (truncated, {len(diff_text) - max_length} more chars)"
        return self._success_response(
            result=f"{diff_type}:\n\n```diff\n{diff_text}\n```",
            metadata={"diff_type": diff_type, "has_changes": True, "length": len(diff_text)},
        )

    async def _branch(self, parameters: dict[str, Any], repo: Any) -> dict[str, Any]:
        """Manage branches."""
        sub_action = parameters.get("sub_action", parameters.get("action", "list")).lower()
        # When called via _branch, the top-level action is 'branch', so use sub_action
        if sub_action == "branch":
            sub_action = "list"
        branch_name = parameters.get("branch_name")

        if sub_action == "list":
            branches = []
            for b in repo.branches:
                prefix = "* " if b == repo.active_branch else "  "
                branches.append(f"{prefix}{b.name}")
            return self._success_response(
                result="Branches:\n" + "\n".join(branches),
                metadata={"current": repo.active_branch.name, "branches": [b.name for b in repo.branches]},
            )
        elif sub_action == "create":
            if not branch_name:
                return self._error_response("branch_name required for create")
            new_branch = repo.create_head(branch_name)
            return self._success_response(result=f"Created branch: {branch_name}", metadata={"branch": branch_name, "commit": new_branch.commit.hexsha[:8]})
        elif sub_action == "delete":
            if not branch_name:
                return self._error_response("branch_name required for delete")
            force = parameters.get("force", False)
            repo.delete_head(branch_name, force=force)
            return self._success_response(result=f"Deleted branch: {branch_name}", metadata={"branch": branch_name, "forced": force})
        elif sub_action == "checkout":
            if not branch_name:
                return self._error_response("branch_name required for checkout")
            repo.git.checkout(branch_name)
            return self._success_response(result=f"Switched to branch: {branch_name}", metadata={"branch": branch_name})
        else:
            return self._error_response(f"Unknown branch sub_action: {sub_action}. Use: list, create, delete, checkout")

    async def _commit(self, parameters: dict[str, Any], repo: Any) -> dict[str, Any]:
        """Commit staged changes."""
        message = parameters.get("message")
        if not message:
            return self._error_response("Commit message is required")
        add_all = parameters.get("add_all", False)
        files = parameters.get("files", [])
        if add_all:
            repo.git.add(A=True)
        elif files:
            repo.index.add(files)
        if not repo.index.diff("HEAD") and not repo.untracked_files:
            return self._error_response("Nothing to commit (working tree clean)")
        commit = repo.index.commit(message)
        return self._success_response(
            result=f"Created commit {commit.hexsha[:8]}: {message}",
            metadata={"commit": commit.hexsha[:8], "message": message, "author": f"{commit.author.name} <{commit.author.email}>", "files_changed": len(commit.stats.files)},
        )

    async def _clone(self, parameters: dict[str, Any], *_: Any) -> dict[str, Any]:
        """Clone a repository (does not need an existing repo)."""
        url = parameters.get("url")
        if not url:
            return self._error_response("URL is required for clone")
        destination = parameters.get("destination")
        branch = parameters.get("branch")
        depth = parameters.get("depth")
        kwargs: dict[str, Any] = {}
        if branch:
            kwargs["branch"] = branch
        if depth:
            kwargs["depth"] = depth
        try:
            logger.info("Cloning %s", url)
            repo = Repo.clone_from(url, destination or None, **kwargs)
            return self._success_response(
                result=f"Successfully cloned to {repo.working_dir}",
                metadata={"url": url, "path": str(repo.working_dir), "branch": repo.active_branch.name, "commit": repo.head.commit.hexsha[:8]},
            )
        except GitCommandError as e:
            return self._error_response(f"Git clone failed: {e}")
        except Exception as e:
            return self._error_response(f"Clone failed: {e}")

    async def _pull(self, parameters: dict[str, Any], repo: Any) -> dict[str, Any]:
        """Pull from remote."""
        if repo.is_dirty():
            return self._error_response("Working tree has uncommitted changes. Commit or stash them first.")
        remote_name = parameters.get("remote", "origin")
        if remote_name not in [r.name for r in repo.remotes]:
            return self._error_response(f"Remote '{remote_name}' not found")
        remote = repo.remote(remote_name)
        branch = parameters.get("branch")
        if not branch:
            if repo.head.is_detached:
                return self._error_response("HEAD is detached, specify branch explicitly")
            branch = repo.active_branch.name
        rebase = parameters.get("rebase", False)
        old_commit = repo.head.commit.hexsha[:8]
        logger.info("Pulling %s from %s", branch, remote_name)
        loop = asyncio.get_event_loop()
        if rebase:
            await loop.run_in_executor(None, lambda: remote.pull(branch, rebase=True))
        else:
            await loop.run_in_executor(None, lambda: remote.pull(branch))
        new_commit = repo.head.commit.hexsha[:8]
        result = "Already up to date" if old_commit == new_commit else f"Updated from {old_commit} to {new_commit}"
        return self._success_response(result=result, metadata={"remote": remote_name, "branch": branch, "old_commit": old_commit, "new_commit": new_commit, "rebased": rebase})

    async def _push(self, parameters: dict[str, Any], repo: Any) -> dict[str, Any]:
        """Push to remote."""
        remote_name = parameters.get("remote", "origin")
        if remote_name not in [r.name for r in repo.remotes]:
            return self._error_response(f"Remote '{remote_name}' not found")
        remote = repo.remote(remote_name)
        branch = parameters.get("branch")
        if not branch:
            if repo.head.is_detached:
                return self._error_response("HEAD is detached, specify branch explicitly")
            branch = repo.active_branch.name
        force = parameters.get("force", False)
        set_upstream = parameters.get("set_upstream", False)
        push_kwargs: dict[str, Any] = {}
        if force:
            push_kwargs["force"] = True
        if set_upstream:
            push_kwargs["set_upstream"] = True
        logger.info("Pushing %s to %s", branch, remote_name)
        loop = asyncio.get_event_loop()
        push_info = await loop.run_in_executor(None, lambda: remote.push(branch, **push_kwargs))
        if push_info:
            info = push_info[0]
            if info.flags & info.ERROR:
                return self._error_response(f"Push failed: {info.summary}")
        return self._success_response(
            result=f"Successfully pushed {branch} to {remote_name}",
            metadata={"remote": remote_name, "branch": branch, "forced": force, "upstream_set": set_upstream},
        )

    async def _merge(self, parameters: dict[str, Any], repo: Any) -> dict[str, Any]:
        """Merge a branch into the current branch."""
        branch_name = parameters.get("branch") or parameters.get("branch_name")
        if not branch_name:
            return self._error_response("Branch name is required for merge")
        if repo.is_dirty():
            return self._error_response("Working tree has uncommitted changes. Commit or stash them first.")
        if branch_name not in [b.name for b in repo.branches]:
            return self._error_response(f"Branch '{branch_name}' not found")
        current_branch = repo.active_branch.name
        current_commit = repo.head.commit.hexsha[:8]
        no_ff = parameters.get("no_ff", False)
        message = parameters.get("message")
        merge_args = [branch_name]
        if no_ff:
            merge_args.append("--no-ff")
        if message:
            merge_args.extend(["-m", message])
        logger.info("Merging %s into %s", branch_name, current_branch)
        try:
            repo.git.merge(*merge_args)
            new_commit = repo.head.commit.hexsha[:8]
            was_ff = current_commit != new_commit and not no_ff
            return self._success_response(
                result=f"Successfully merged {branch_name} into {current_branch}",
                metadata={"current_branch": current_branch, "merged_branch": branch_name, "old_commit": current_commit, "new_commit": new_commit, "fast_forward": was_ff},
            )
        except GitCommandError as e:
            if "CONFLICT" in str(e):
                return self._error_response(f"Merge conflict detected. Resolve conflicts and commit manually.\n{e}")
            raise

    _DISPATCH: dict[str, Any] = {
        "status": _status,
        "log": _log,
        "diff": _diff,
        "branch": _branch,
        "commit": _commit,
        "clone": _clone,
        "pull": _pull,
        "push": _push,
        "merge": _merge,
    }
