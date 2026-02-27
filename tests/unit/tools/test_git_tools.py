"""
Unit tests for Git tools
"""

import importlib.util
from unittest.mock import MagicMock, patch

import pytest

from portal.tools.git_tools.git_branch import GitBranchTool
from portal.tools.git_tools.git_clone import GitCloneTool
from portal.tools.git_tools.git_commit import GitCommitTool
from portal.tools.git_tools.git_diff import GitDiffTool
from portal.tools.git_tools.git_log import GitLogTool
from portal.tools.git_tools.git_merge import GitMergeTool
from portal.tools.git_tools.git_pull import GitPullTool
from portal.tools.git_tools.git_push import GitPushTool
from portal.tools.git_tools.git_status import GitStatusTool

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
        remote.push.return_value = []   # falsy → no error check
        remote.pull.return_value = []
        repo.remotes = [remote]
        repo.remote.return_value = remote
    else:
        repo.remotes = remotes

    # branches list with a mock branch object
    mock_branch = MagicMock()
    mock_branch.name = branch
    repo.branches = [mock_branch]

    return repo


@pytest.mark.unit
class TestGitStatusTool:
    """Test git_status tool"""

    @pytest.mark.asyncio
    async def test_git_status_success(self, mock_git_repo):
        """Test git status returns repository status"""
        tool = GitStatusTool()
        mock_repo = _make_mock_repo()

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute({"repo_path": str(mock_git_repo)})

        assert result["success"] is True
        assert "status" in result or "result" in result

    @pytest.mark.asyncio
    async def test_git_status_not_a_repo(self, temp_dir):
        """Test git status fails on non-git directory"""
        from git import InvalidGitRepositoryError
        tool = GitStatusTool()

        with patch(
            "portal.tools.git_tools._base.Repo",
            side_effect=InvalidGitRepositoryError("not a repo"),
        ):
            result = await tool.execute({"repo_path": str(temp_dir)})

        assert result["success"] is False
        assert "error" in result


@pytest.mark.unit
class TestGitBranchTool:
    """Test git_branch tool"""

    @pytest.mark.asyncio
    async def test_git_branch_list(self, mock_git_repo):
        """Test listing git branches"""
        tool = GitBranchTool()
        mock_repo = _make_mock_repo()
        # active_branch comparison used in list action
        mock_repo.active_branch = mock_repo.branches[0]

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute({
                "repo_path": str(mock_git_repo),
                "action": "list",
            })

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_git_branch_create(self, mock_git_repo):
        """Test creating a new branch"""
        tool = GitBranchTool()
        mock_repo = _make_mock_repo()

        new_head = MagicMock()
        new_head.commit.hexsha = "def456789012"
        mock_repo.create_head.return_value = new_head

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute({
                "repo_path": str(mock_git_repo),
                "action": "create",
                "branch_name": "new-feature",
            })

        assert result["success"] is True


@pytest.mark.unit
class TestGitCommitTool:
    """Test git_commit tool"""

    @pytest.mark.asyncio
    async def test_git_commit_success(self, mock_git_repo):
        """Test creating a git commit"""
        tool = GitCommitTool()
        mock_repo = _make_mock_repo()

        # Simulate staged changes so the "nothing to commit" guard passes
        mock_repo.index.diff.return_value = [MagicMock()]

        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123456789"
        mock_commit.message = "Test commit"
        mock_commit.author.name = "Test Author"
        mock_commit.author.email = "test@example.com"
        mock_commit.stats.files = {"file.txt": {"insertions": 1, "deletions": 0}}
        mock_repo.index.commit.return_value = mock_commit

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute({
                "repo_path": str(mock_git_repo),
                "message": "Test commit",
            })

        assert result["success"] is True


@pytest.mark.unit
class TestGitDiffTool:
    """Test git_diff tool"""

    @pytest.mark.asyncio
    async def test_git_diff_success(self, mock_git_repo):
        """Test git diff shows changes"""
        tool = GitDiffTool()
        mock_repo = _make_mock_repo()
        mock_repo.git.diff.return_value = "diff --git a/file.txt b/file.txt\n+new line"
        mock_repo.head.commit = MagicMock()

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute({"repo_path": str(mock_git_repo)})

        assert result["success"] is True


@pytest.mark.unit
class TestGitLogTool:
    """Test git_log tool"""

    @pytest.mark.asyncio
    async def test_git_log_success(self, mock_git_repo):
        """Test git log shows commit history"""
        tool = GitLogTool()
        mock_repo = _make_mock_repo()

        import datetime
        mock_commit = MagicMock()
        mock_commit.hexsha = "abc123456789abcdef"
        mock_commit.message = "Test commit message"
        mock_commit.author.name = "Test Author"
        mock_commit.authored_date = datetime.datetime.now().timestamp()
        mock_repo.iter_commits.return_value = [mock_commit]

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute({
                "repo_path": str(mock_git_repo),
                "max_count": 10,
            })

        assert result["success"] is True


@pytest.mark.unit
class TestGitPushTool:
    """Test git_push tool"""

    @pytest.mark.asyncio
    async def test_git_push_success(self, mock_git_repo):
        """Test pushing to remote repository"""
        tool = GitPushTool()
        mock_repo = _make_mock_repo()

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute({
                "repo_path": str(mock_git_repo),
                "remote": "origin",
                "branch": "main",
            })

        assert result["success"] is True


@pytest.mark.unit
class TestGitPullTool:
    """Test git_pull tool"""

    @pytest.mark.asyncio
    async def test_git_pull_success(self, mock_git_repo):
        """Test pulling from remote repository"""
        tool = GitPullTool()
        mock_repo = _make_mock_repo()

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute({
                "repo_path": str(mock_git_repo),
                "remote": "origin",
                "branch": "main",
            })

        assert result["success"] is True


@pytest.mark.unit
class TestGitMergeTool:
    """Test git_merge tool"""

    @pytest.mark.asyncio
    async def test_git_merge_success(self, mock_git_repo):
        """Test merging branches"""
        tool = GitMergeTool()
        mock_repo = _make_mock_repo()

        # Add the feature-branch to branches list so validation passes
        feature_branch = MagicMock()
        feature_branch.name = "feature-branch"
        mock_repo.branches = [MagicMock(name="main"), feature_branch]

        with patch("portal.tools.git_tools._base.Repo", return_value=mock_repo):
            result = await tool.execute({
                "repo_path": str(mock_git_repo),
                "branch": "feature-branch",
            })

        assert result["success"] is True


@pytest.mark.unit
class TestGitCloneTool:
    """Test git_clone tool"""

    @pytest.mark.asyncio
    async def test_git_clone_success(self, temp_dir):
        """Test cloning a repository"""
        tool = GitCloneTool()

        mock_cloned = MagicMock()
        mock_cloned.working_dir = str(temp_dir / "test-repo")
        mock_cloned.active_branch.name = "main"
        mock_cloned.head.commit.hexsha = "abc123456789"

        with patch(
            "portal.tools.git_tools.git_clone.Repo.clone_from",
            return_value=mock_cloned,
        ):
            result = await tool.execute({
                "url": "https://github.com/test/repo.git",
                "destination": str(temp_dir / "test-repo"),
            })

        assert result["success"] is True
