"""
Unit tests for Git tools
"""

import pytest
from unittest.mock import patch, Mock
from portal.tools.git_tools.git_status import GitStatusTool
from portal.tools.git_tools.git_branch import GitBranchTool
from portal.tools.git_tools.git_commit import GitCommitTool
from portal.tools.git_tools.git_diff import GitDiffTool
from portal.tools.git_tools.git_log import GitLogTool
from portal.tools.git_tools.git_push import GitPushTool
from portal.tools.git_tools.git_pull import GitPullTool
from portal.tools.git_tools.git_merge import GitMergeTool
from portal.tools.git_tools.git_clone import GitCloneTool


@pytest.mark.unit
class TestGitStatusTool:
    """Test git_status tool"""

    @pytest.mark.asyncio
    async def test_git_status_success(self, mock_git_repo):
        """Test git status returns repository status"""
        tool = GitStatusTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="On branch main\nnothing to commit",
                stderr=""
            )

            result = await tool.execute({"path": str(mock_git_repo)})

            assert result["success"] is True
            assert "status" in result or "result" in result
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_git_status_not_a_repo(self, temp_dir):
        """Test git status fails on non-git directory"""
        tool = GitStatusTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=128,
                stdout="",
                stderr="not a git repository"
            )

            result = await tool.execute({"path": str(temp_dir)})

            assert result["success"] is False
            assert "error" in result


@pytest.mark.unit
class TestGitBranchTool:
    """Test git_branch tool"""

    @pytest.mark.asyncio
    async def test_git_branch_list(self, mock_git_repo):
        """Test listing git branches"""
        tool = GitBranchTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="* main\n  develop\n  feature-branch",
                stderr=""
            )

            result = await tool.execute({
                "path": str(mock_git_repo),
                "operation": "list"
            })

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_git_branch_create(self, mock_git_repo):
        """Test creating a new branch"""
        tool = GitBranchTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await tool.execute({
                "path": str(mock_git_repo),
                "operation": "create",
                "branch_name": "new-feature"
            })

            assert result["success"] is True


@pytest.mark.unit
class TestGitCommitTool:
    """Test git_commit tool"""

    @pytest.mark.asyncio
    async def test_git_commit_success(self, mock_git_repo):
        """Test creating a git commit"""
        tool = GitCommitTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="[main abc1234] Test commit",
                stderr=""
            )

            result = await tool.execute({
                "path": str(mock_git_repo),
                "message": "Test commit"
            })

            assert result["success"] is True


@pytest.mark.unit
class TestGitDiffTool:
    """Test git_diff tool"""

    @pytest.mark.asyncio
    async def test_git_diff_success(self, mock_git_repo):
        """Test git diff shows changes"""
        tool = GitDiffTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="diff --git a/file.txt b/file.txt\n+new line",
                stderr=""
            )

            result = await tool.execute({"path": str(mock_git_repo)})

            assert result["success"] is True


@pytest.mark.unit
class TestGitLogTool:
    """Test git_log tool"""

    @pytest.mark.asyncio
    async def test_git_log_success(self, mock_git_repo):
        """Test git log shows commit history"""
        tool = GitLogTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="commit abc1234\nAuthor: Test\n",
                stderr=""
            )

            result = await tool.execute({
                "path": str(mock_git_repo),
                "max_count": 10
            })

            assert result["success"] is True


@pytest.mark.unit
class TestGitPushTool:
    """Test git_push tool"""

    @pytest.mark.asyncio
    async def test_git_push_success(self, mock_git_repo):
        """Test pushing to remote repository"""
        tool = GitPushTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Everything up-to-date",
                stderr=""
            )

            result = await tool.execute({
                "path": str(mock_git_repo),
                "remote": "origin",
                "branch": "main"
            })

            assert result["success"] is True


@pytest.mark.unit
class TestGitPullTool:
    """Test git_pull tool"""

    @pytest.mark.asyncio
    async def test_git_pull_success(self, mock_git_repo):
        """Test pulling from remote repository"""
        tool = GitPullTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Already up to date.",
                stderr=""
            )

            result = await tool.execute({
                "path": str(mock_git_repo),
                "remote": "origin",
                "branch": "main"
            })

            assert result["success"] is True


@pytest.mark.unit
class TestGitMergeTool:
    """Test git_merge tool"""

    @pytest.mark.asyncio
    async def test_git_merge_success(self, mock_git_repo):
        """Test merging branches"""
        tool = GitMergeTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Merge made by the 'recursive' strategy.",
                stderr=""
            )

            result = await tool.execute({
                "path": str(mock_git_repo),
                "branch": "feature-branch"
            })

            assert result["success"] is True


@pytest.mark.unit
class TestGitCloneTool:
    """Test git_clone tool"""

    @pytest.mark.asyncio
    async def test_git_clone_success(self, temp_dir):
        """Test cloning a repository"""
        tool = GitCloneTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Cloning into 'test-repo'...",
                stderr=""
            )

            result = await tool.execute({
                "url": "https://github.com/test/repo.git",
                "destination": str(temp_dir / "test-repo")
            })

            assert result["success"] is True
