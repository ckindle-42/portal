"""Tests for portal.tools.dev_tools.python_env_manager"""

import os
from unittest.mock import MagicMock, patch

import pytest

from portal.tools.dev_tools.python_env_manager import PythonEnvManagerTool


class TestPythonEnvManagerMetadata:
    def test_metadata(self):
        tool = PythonEnvManagerTool()
        meta = tool.metadata
        assert meta.name == "python_env_manager"
        assert meta.requires_confirmation is True
        assert len(meta.parameters) >= 2


class TestPythonEnvManagerCreate:
    @pytest.mark.asyncio
    async def test_create_env(self, tmp_path):
        env_path = str(tmp_path / "testenv")
        tool = PythonEnvManagerTool()
        result = await tool.execute({"action": "create", "env_path": env_path})
        assert result["success"] is True
        assert os.path.exists(env_path)

    @pytest.mark.asyncio
    async def test_create_env_already_exists(self, tmp_path):
        env_path = str(tmp_path / "existing")
        os.makedirs(env_path)
        tool = PythonEnvManagerTool()
        result = await tool.execute({"action": "create", "env_path": env_path})
        assert result["success"] is False
        assert "already exists" in result["error"]


class TestPythonEnvManagerList:
    @pytest.mark.asyncio
    async def test_list_envs(self, tmp_path):
        # Create a fake venv
        venv_dir = tmp_path / "myvenv" / "bin"
        venv_dir.mkdir(parents=True)
        (venv_dir / "python").touch()

        tool = PythonEnvManagerTool()
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = await tool.execute({"action": "list"})
            assert result["success"] is True
            assert "myvenv" in result["result"]["environments"]
        finally:
            os.chdir(old_cwd)

    @pytest.mark.asyncio
    async def test_list_no_envs(self, tmp_path):
        tool = PythonEnvManagerTool()
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = await tool.execute({"action": "list"})
            assert result["success"] is True
            assert result["result"]["count"] == 0
        finally:
            os.chdir(old_cwd)


class TestPythonEnvManagerInstall:
    @pytest.mark.asyncio
    async def test_install_no_packages(self, tmp_path):
        tool = PythonEnvManagerTool()
        result = await tool.execute(
            {"action": "install", "env_path": str(tmp_path), "packages": []}
        )
        assert result["success"] is False
        assert "No packages" in result["error"]

    @pytest.mark.asyncio
    async def test_install_no_pip(self, tmp_path):
        tool = PythonEnvManagerTool()
        result = await tool.execute(
            {"action": "install", "env_path": str(tmp_path), "packages": ["numpy"]}
        )
        assert result["success"] is False
        assert "pip not found" in result["error"]

    @pytest.mark.asyncio
    @patch("portal.tools.dev_tools.python_env_manager.subprocess")
    async def test_install_success(self, mock_subprocess, tmp_path):
        # Create fake pip
        pip_dir = tmp_path / "bin"
        pip_dir.mkdir()
        pip_path = pip_dir / "pip"
        pip_path.touch()

        mock_subprocess.run.return_value = MagicMock(
            returncode=0, stdout="Successfully installed numpy"
        )
        tool = PythonEnvManagerTool()
        result = await tool.execute(
            {"action": "install", "env_path": str(tmp_path), "packages": ["numpy"]}
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    @patch("portal.tools.dev_tools.python_env_manager.subprocess")
    async def test_install_failure(self, mock_subprocess, tmp_path):
        pip_dir = tmp_path / "bin"
        pip_dir.mkdir()
        (pip_dir / "pip").touch()

        mock_subprocess.run.return_value = MagicMock(returncode=1, stderr="Could not find")
        tool = PythonEnvManagerTool()
        result = await tool.execute(
            {"action": "install", "env_path": str(tmp_path), "packages": ["badpkg"]}
        )
        assert result["success"] is False


class TestPythonEnvManagerInfo:
    @pytest.mark.asyncio
    async def test_info_not_found(self, tmp_path):
        tool = PythonEnvManagerTool()
        result = await tool.execute({"action": "info", "env_path": str(tmp_path / "missing")})
        assert result["success"] is False

    @pytest.mark.asyncio
    @patch("portal.tools.dev_tools.python_env_manager.subprocess")
    async def test_info_success(self, mock_subprocess, tmp_path):
        python_dir = tmp_path / "bin"
        python_dir.mkdir()
        (python_dir / "python").touch()

        mock_subprocess.run.return_value = MagicMock(returncode=0, stdout="Python 3.11.0")
        tool = PythonEnvManagerTool()
        result = await tool.execute({"action": "info", "env_path": str(tmp_path)})
        assert result["success"] is True
        assert "3.11" in result["result"]["python_version"]


class TestPythonEnvManagerFreeze:
    @pytest.mark.asyncio
    async def test_freeze_not_found(self, tmp_path):
        tool = PythonEnvManagerTool()
        result = await tool.execute({"action": "freeze", "env_path": str(tmp_path / "missing")})
        assert result["success"] is False

    @pytest.mark.asyncio
    @patch("portal.tools.dev_tools.python_env_manager.subprocess")
    async def test_freeze_success(self, mock_subprocess, tmp_path):
        pip_dir = tmp_path / "bin"
        pip_dir.mkdir()
        (pip_dir / "pip").touch()

        mock_subprocess.run.return_value = MagicMock(
            returncode=0, stdout="numpy==1.24.0\npandas==2.0.0"
        )
        tool = PythonEnvManagerTool()
        result = await tool.execute({"action": "freeze", "env_path": str(tmp_path)})
        assert result["success"] is True
        assert result["result"]["count"] == 2

    @pytest.mark.asyncio
    @patch("portal.tools.dev_tools.python_env_manager.subprocess")
    async def test_freeze_empty(self, mock_subprocess, tmp_path):
        pip_dir = tmp_path / "bin"
        pip_dir.mkdir()
        (pip_dir / "pip").touch()

        mock_subprocess.run.return_value = MagicMock(returncode=0, stdout="")
        tool = PythonEnvManagerTool()
        result = await tool.execute({"action": "freeze", "env_path": str(tmp_path)})
        assert result["success"] is True


class TestPythonEnvManagerUnknown:
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        tool = PythonEnvManagerTool()
        result = await tool.execute({"action": "nope"})
        assert result["success"] is False
