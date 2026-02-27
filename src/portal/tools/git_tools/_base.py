"""Shared helpers for git tools — avoids per-file try/except import boilerplate."""
from __future__ import annotations

from typing import Any

try:
    from git import GitCommandError, InvalidGitRepositoryError, Repo

    GIT_AVAILABLE = True
except ImportError:
    GIT_AVAILABLE = False

    class GitCommandError(Exception):  # type: ignore[no-redef]
        pass

    class InvalidGitRepositoryError(Exception):  # type: ignore[no-redef]
        pass

    Repo = None  # type: ignore[assignment]


def open_repo(repo_path: str) -> tuple[Any, dict[str, Any] | None]:
    """Open a git repository, returning (repo, None) or (None, error_dict).

    Handles InvalidGitRepositoryError and bare repository checks so callers
    don't need to repeat this boilerplate in every tool's execute() method.
    """
    try:
        repo = Repo(repo_path)
        if repo.bare:
            return None, {"success": False, "error": "Repository is bare"}
        return repo, None
    except InvalidGitRepositoryError:
        return None, {"success": False, "error": f"Not a git repository: {repo_path}"}


__all__ = ["GIT_AVAILABLE", "GitCommandError", "InvalidGitRepositoryError", "Repo", "open_repo"]
