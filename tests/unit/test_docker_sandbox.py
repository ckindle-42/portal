"""Tests for portal.security.sandbox.docker_sandbox"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from portal.security.sandbox.docker_sandbox import (
    DockerfileGenerator,
    SandboxConfig,
)

_has_docker = importlib.util.find_spec("docker") is not None

# ── SandboxConfig ────────────────────────────────────────────────────────


class TestSandboxConfig:
    def test_defaults(self):
        cfg = SandboxConfig()
        assert cfg.memory_limit == "512m"
        assert cfg.cpu_quota == 100000
        assert cfg.timeout_seconds == 30
        assert cfg.network_disabled is True
        assert cfg.read_only is False
        assert cfg.no_new_privileges is True
        assert cfg.python_version == "3.11"
        assert cfg.drop_capabilities == ["ALL"]
        assert "numpy" in cfg.packages

    def test_custom_values(self):
        cfg = SandboxConfig(
            memory_limit="1g",
            timeout_seconds=60,
            network_disabled=False,
            packages=["torch"],
        )
        assert cfg.memory_limit == "1g"
        assert cfg.timeout_seconds == 60
        assert cfg.network_disabled is False
        assert cfg.packages == ["torch"]

    def test_post_init_defaults(self):
        cfg = SandboxConfig()
        # Should auto-populate
        assert cfg.drop_capabilities is not None
        assert cfg.packages is not None

    def test_custom_capabilities(self):
        cfg = SandboxConfig(drop_capabilities=["NET_ADMIN"])
        assert cfg.drop_capabilities == ["NET_ADMIN"]


# ── DockerPythonSandbox ──────────────────────────────────────────────────


@pytest.mark.skipif(not _has_docker, reason="docker not installed")
class TestDockerPythonSandboxInit:
    @patch("portal.security.sandbox.docker_sandbox.DOCKER_AVAILABLE", False)
    def test_raises_without_docker(self):
        from portal.security.sandbox.docker_sandbox import DockerPythonSandbox
        with pytest.raises(RuntimeError, match="Docker package not installed"):
            DockerPythonSandbox()

    @patch("portal.security.sandbox.docker_sandbox.DOCKER_AVAILABLE", True)
    @patch("portal.security.sandbox.docker_sandbox.docker")
    def test_init_with_docker_available(self, mock_docker):
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()

        from portal.security.sandbox.docker_sandbox import DockerPythonSandbox
        sandbox = DockerPythonSandbox()
        assert sandbox.docker_client is mock_client

    @patch("portal.security.sandbox.docker_sandbox.DOCKER_AVAILABLE", True)
    @patch("portal.security.sandbox.docker_sandbox.docker")
    def test_init_docker_failure(self, mock_docker):
        mock_docker.from_env.side_effect = RuntimeError("no docker daemon")

        from portal.security.sandbox.docker_sandbox import DockerPythonSandbox
        with pytest.raises(RuntimeError, match="Docker not available"):
            DockerPythonSandbox()


@pytest.mark.skipif(not _has_docker, reason="docker not installed")
class TestDockerPythonSandboxExecute:
    @patch("portal.security.sandbox.docker_sandbox.DOCKER_AVAILABLE", True)
    @patch("portal.security.sandbox.docker_sandbox.docker")
    @pytest.mark.asyncio
    async def test_execute_code_success(self, mock_docker):
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()

        mock_container = MagicMock()
        mock_container.wait.return_value = {'StatusCode': 0}
        mock_container.logs.return_value = b"Hello World\n"
        mock_client.containers.run.return_value = mock_container

        from portal.security.sandbox.docker_sandbox import DockerPythonSandbox
        sandbox = DockerPythonSandbox()
        result = await sandbox.execute_code('print("Hello World")')
        assert result['success'] is True
        assert 'Hello World' in result['stdout']

    @patch("portal.security.sandbox.docker_sandbox.DOCKER_AVAILABLE", True)
    @patch("portal.security.sandbox.docker_sandbox.docker")
    @pytest.mark.asyncio
    async def test_execute_code_failure(self, mock_docker):
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()

        mock_container = MagicMock()
        mock_container.wait.return_value = {'StatusCode': 1}
        mock_container.logs.return_value = b"NameError: name 'foo' is not defined"
        mock_client.containers.run.return_value = mock_container

        from portal.security.sandbox.docker_sandbox import DockerPythonSandbox
        sandbox = DockerPythonSandbox()
        result = await sandbox.execute_code('foo')
        assert result['success'] is False

    @patch("portal.security.sandbox.docker_sandbox.DOCKER_AVAILABLE", True)
    @patch("portal.security.sandbox.docker_sandbox.docker")
    @pytest.mark.asyncio
    async def test_execute_code_exception(self, mock_docker):
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()
        mock_client.containers.run.side_effect = RuntimeError("container failed")

        from portal.security.sandbox.docker_sandbox import DockerPythonSandbox
        sandbox = DockerPythonSandbox()
        result = await sandbox.execute_code('print("test")')
        assert result['success'] is False
        assert 'container failed' in result['stderr']

    @patch("portal.security.sandbox.docker_sandbox.DOCKER_AVAILABLE", True)
    @patch("portal.security.sandbox.docker_sandbox.docker")
    @pytest.mark.asyncio
    async def test_execute_code_timeout(self, mock_docker):
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()

        mock_container = MagicMock()
        mock_container.wait.side_effect = Exception("timeout")
        mock_container.kill.return_value = None
        mock_container.logs.return_value = b""
        mock_client.containers.run.return_value = mock_container

        from portal.security.sandbox.docker_sandbox import DockerPythonSandbox
        sandbox = DockerPythonSandbox()
        result = await sandbox.execute_code('import time; time.sleep(100)', timeout=1)
        assert result['exit_code'] == -1

    @patch("portal.security.sandbox.docker_sandbox.DOCKER_AVAILABLE", True)
    @patch("portal.security.sandbox.docker_sandbox.docker")
    @pytest.mark.asyncio
    async def test_execute_script_success(self, mock_docker, tmp_path):
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()

        mock_container = MagicMock()
        mock_container.wait.return_value = {'StatusCode': 0}
        mock_container.logs.return_value = b"script output"
        mock_client.containers.run.return_value = mock_container

        script = tmp_path / "test.py"
        script.write_text('print("script output")')

        from portal.security.sandbox.docker_sandbox import DockerPythonSandbox
        sandbox = DockerPythonSandbox()
        result = await sandbox.execute_script(str(script))
        assert result['success'] is True

    @patch("portal.security.sandbox.docker_sandbox.DOCKER_AVAILABLE", True)
    @patch("portal.security.sandbox.docker_sandbox.docker")
    @pytest.mark.asyncio
    async def test_execute_script_missing_file(self, mock_docker):
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()

        from portal.security.sandbox.docker_sandbox import DockerPythonSandbox
        sandbox = DockerPythonSandbox()
        result = await sandbox.execute_script("/nonexistent/script.py")
        assert result['success'] is False

    @patch("portal.security.sandbox.docker_sandbox.DOCKER_AVAILABLE", True)
    @patch("portal.security.sandbox.docker_sandbox.docker")
    def test_cleanup(self, mock_docker):
        mock_client = MagicMock()
        mock_docker.from_env.return_value = mock_client
        mock_client.images.get.return_value = MagicMock()

        from portal.security.sandbox.docker_sandbox import DockerPythonSandbox
        sandbox = DockerPythonSandbox()
        sandbox.cleanup()
        mock_client.close.assert_called_once()


# ── DockerPythonExecutionTool ────────────────────────────────────────────


class TestDockerPythonExecutionTool:
    @patch("portal.security.sandbox.docker_sandbox.DOCKER_AVAILABLE", False)
    def test_init_without_docker(self):
        from portal.security.sandbox.docker_sandbox import DockerPythonExecutionTool
        DockerPythonExecutionTool._sandbox = None
        tool = DockerPythonExecutionTool()
        meta = tool._get_metadata()
        assert meta.name == "python_sandbox"

    @patch("portal.security.sandbox.docker_sandbox.DOCKER_AVAILABLE", False)
    @pytest.mark.asyncio
    async def test_execute_without_docker(self):
        from portal.security.sandbox.docker_sandbox import DockerPythonExecutionTool
        DockerPythonExecutionTool._sandbox = None
        tool = DockerPythonExecutionTool()
        result = await tool.execute({"code": "print('hi')"})
        assert result["success"] is False

    @patch("portal.security.sandbox.docker_sandbox.DOCKER_AVAILABLE", False)
    @pytest.mark.asyncio
    async def test_execute_no_code(self):
        from portal.security.sandbox.docker_sandbox import DockerPythonExecutionTool
        DockerPythonExecutionTool._sandbox = None
        tool = DockerPythonExecutionTool()
        result = await tool.execute({})
        assert result["success"] is False


# ── DockerfileGenerator ──────────────────────────────────────────────────


class TestDockerfileGenerator:
    def test_generate_minimal(self):
        df = DockerfileGenerator.generate_minimal()
        assert "FROM python" in df
        assert "alpine" in df

    def test_generate_data_science(self):
        df = DockerfileGenerator.generate_data_science()
        assert "numpy" in df
        assert "pandas" in df

    def test_generate_web(self):
        df = DockerfileGenerator.generate_web()
        assert "requests" in df
        assert "beautifulsoup4" in df

    def test_save_dockerfile(self, tmp_path):
        content = DockerfileGenerator.generate_minimal()
        path = str(tmp_path / "Dockerfile")
        DockerfileGenerator.save_dockerfile(content, path)
        assert Path(path).read_text() == content
