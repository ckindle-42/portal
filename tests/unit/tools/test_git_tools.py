"""
Unit tests for Git tools - consolidated GitTool
"""

import importlib.util
from unittest.mock import MagicMock, patch

import pytest

from portal.tools.git_tools.git_tool import GitTool

pytestmark = pytest.mark.skipif(
    not importlib.util.find_spec("git"),
    reason="GitPython not installed",
)


def _make_mock_repo(branch="main", hexsha="abc123456789", dirty=False, remotes=None):
    """Build a fully mocked GitPython Repo object."""
    repo = MagicMock()
    repo.bare = False
    repo.head.is_detached = False
    repo.active_branch.name = branch
    repo.head.commit.hexsha = hexsha
    repo.is_dirty.return_value = dirty
    repo.index.diff.return_value = []
    repo.untracked_files = []

    if remotes is None:
        remote = MagicMock()
        remote.name = "origin"
        remote.push.return_value = []  # falsy → no error check
        remote.pull.return_value = []
        repo.remotes = [remote]
        repo.remote.return_value = remote
    else:
        repo.remotes = remotes

    mock_branch = MagicMock()
    mock_branch.name = branch
    repo.branches = [mock_branch]

    return repo


@pytest.mark.unit
class TestGitStatusTool:
    """Test git status action"""

    @pytest.mark.asyncio
    async def test_git_status_success(self, mock_git_repo):
        tool = GitTool()
        mock_repo = _make_mock_repo()

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute({"action": "status", "repo_path": str(mock_git_repo)})

        assert result["success"] is True
        assert "result" in result

    @pytest.mark.asyncio
    async def test_git_status_not_a_repo(self, temp_dir):
        from git import InvalidGitRepositoryError

        tool = GitTool()

        with patch(
            "portal.tools.git_tools._base.Repo",
            side_effect=InvalidGitRepositoryError("not a repo"),
        ):
            result = await tool.execute({"action": "status", "repo_path": str(temp_dir)})

        assert result["success"] is False
        assert "error" in result


@pytest.mark.unit
class TestGitBranchTool:
    """Test git branch actions"""

    @pytest.mark.asyncio
    async def test_git_branch_list(self, mock_git_repo):
        tool = GitTool()
        mock_repo = _make_mock_repo()
        mock_repo.active_branch = mock_repo.branches[0]

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute(
                {"action": "branch", "sub_action": "list", "repo_path": str(mock_git_repo)}
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_git_branch_create(self, mock_git_repo):
        tool = GitTool()
        mock_repo = _make_mock_repo()

        new_head = MagicMock()
        new_head.commit.hexsha = "def456789012"
        mock_repo.create_head.return_value = new_head

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute(
                {
                    "action": "branch",
                    "sub_action": "create",
                    "branch_name": "new-feature",
                    "repo_path": str(mock_git_repo),
                }
            )

        assert result["success"] is True


@pytest.mark.unit
class TestGitCommitTool:
    """Test git commit action"""

    @pytest.mark.asyncio
    async def test_git_commit_success(self, mock_git_repo):
        tool = GitTool()
        mock_repo = _make_mock_repo()

        # Simulate staged changes
        mock_repo.index.diff.return_value = [MagicMock()]

        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123456789"
        mock_commit.message = "Test commit"
        mock_commit.author.name = "Test Author"
        mock_commit.author.email = "test@example.com"
        mock_commit.stats.files = {"file.txt": {"insertions": 1, "deletions": 0}}
        mock_repo.index.commit.return_value = mock_commit

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute(
                {"action": "commit", "message": "Test commit", "repo_path": str(mock_git_repo)}
            )

        assert result["success"] is True


@pytest.mark.unit
class TestGitDiffTool:
    """Test git diff action"""

    @pytest.mark.asyncio
    async def test_git_diff_success(self, mock_git_repo):
        tool = GitTool()
        mock_repo = _make_mock_repo()
        mock_repo.git.diff.return_value = "diff --git a/file.txt b/file.txt\n+new line"
        mock_repo.head.commit = MagicMock()

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute({"action": "diff", "repo_path": str(mock_git_repo)})

        assert result["success"] is True


@pytest.mark.unit
class TestGitLogTool:
    """Test git log action"""

    @pytest.mark.asyncio
    async def test_git_log_success(self, mock_git_repo):
        tool = GitTool()
        mock_repo = _make_mock_repo()

        import datetime

        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123456789abcdef"
        mock_commit.message = "Test commit message"
        mock_commit.author.name = "Test Author"
        mock_commit.committed_date = datetime.datetime.now().timestamp()
        mock_repo.iter_commits.return_value = [mock_commit]

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute(
                {"action": "log", "max_count": 10, "repo_path": str(mock_git_repo)}
            )

        assert result["success"] is True


@pytest.mark.unit
class TestGitPushTool:
    """Test git push action"""

    @pytest.mark.asyncio
    async def test_git_push_success(self, mock_git_repo):
        tool = GitTool()
        mock_repo = _make_mock_repo()

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute(
                {"action": "push", "remote": "origin", "branch": "main", "repo_path": str(mock_git_repo)}
            )

        assert result["success"] is True


@pytest.mark.unit
class TestGitPullTool:
    """Test git pull action"""

    @pytest.mark.asyncio
    async def test_git_pull_success(self, mock_git_repo):
        tool = GitTool()
        mock_repo = _make_mock_repo()

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute(
                {"action": "pull", "remote": "origin", "branch": "main", "repo_path": str(mock_git_repo)}
            )

        assert result["success"] is True


@pytest.mark.unit
class TestGitMergeTool:
    """Test git merge action"""

    @pytest.mark.asyncio
    async def test_git_merge_success(self, mock_git_repo):
        tool = GitTool()
        mock_repo = _make_mock_repo()

        feature_branch = MagicMock()
        feature_branch.name = "feature-branch"
        mock_repo.branches = [MagicMock(name="main"), feature_branch]

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute(
                {"action": "merge", "branch": "feature-branch", "repo_path": str(mock_git_repo)}
            )

        assert result["success"] is True


@pytest.mark.unit
class TestGitCloneTool:
    """Test git clone action"""

    @pytest.mark.asyncio
    async def test_git_clone_success(self, temp_dir):
        tool = GitTool()

        mock_cloned = MagicMock()
        mock_cloned.working_dir = str(temp_dir / "test-repo")
        mock_cloned.active_branch.name = "main"
        mock_cloned.head.commit.hexsha = "abc123456789"

        with patch(
            "portal.tools.git_tools.git_tool.Repo.clone_from",
            return_value=mock_cloned,
        ):
            result = await tool.execute(
                {
                    "action": "clone",
                    "url": "https://github.com/test/repo.git",
                    "destination": str(temp_dir / "test-repo"),
                }
            )

        assert result["success"] is True
