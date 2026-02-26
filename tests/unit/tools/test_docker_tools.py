"""
Unit tests for Docker tools
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from portal.tools.docker_tools.docker_compose import DockerComposeTool
from portal.tools.docker_tools.docker_logs import DockerLogsTool
from portal.tools.docker_tools.docker_ps import DockerPSTool
from portal.tools.docker_tools.docker_run import DockerRunTool
from portal.tools.docker_tools.docker_stop import DockerStopTool


def _make_mock_docker_client():
    """Build a fully mocked Docker SDK client."""
    client = MagicMock()

    mock_container = MagicMock()
    mock_container.short_id = "abc123"
    mock_container.name = "nginx"
    mock_container.image.tags = ["nginx:latest"]
    mock_container.status = "running"
    mock_container.ports = {"80/tcp": [{"HostPort": "8080"}]}
    mock_container.logs.return_value = b"Container log output\nLine 2\nLine 3"

    client.containers.list.return_value = [mock_container]
    client.containers.get.return_value = mock_container
    client.containers.run.return_value = mock_container

    return client, mock_container


@pytest.mark.unit
class TestDockerPSTool:
    """Test docker_ps tool"""

    @pytest.mark.asyncio
    async def test_docker_ps_success(self):
        """Test listing Docker containers"""
        tool = DockerPSTool()
        mock_client, _ = _make_mock_docker_client()

        with patch("portal.tools.docker_tools.docker_ps.DOCKER_AVAILABLE", True), \
             patch("portal.tools.docker_tools.docker_ps.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = mock_client
            tool.client = mock_client
            result = await tool.execute({})

        assert result["success"] is True
        assert "containers" in result or "result" in result

    @pytest.mark.asyncio
    async def test_docker_ps_no_docker(self):
        """Test when Docker SDK is not available"""
        tool = DockerPSTool()

        with patch("portal.tools.docker_tools.docker_ps.DOCKER_AVAILABLE", False):
            result = await tool.execute({})

        assert result["success"] is False
        assert "error" in result


@pytest.mark.unit
@pytest.mark.requires_docker
class TestDockerRunTool:
    """Test docker_run tool"""

    @pytest.mark.asyncio
    async def test_docker_run_success(self):
        """Test running a Docker container"""
        tool = DockerRunTool()
        mock_client, mock_container = _make_mock_docker_client()

        with patch("portal.tools.docker_tools.docker_run.DOCKER_AVAILABLE", True), \
             patch("portal.tools.docker_tools.docker_run.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = mock_client
            mock_docker_mod.errors.ImageNotFound = Exception
            mock_docker_mod.errors.APIError = Exception
            tool.client = mock_client
            result = await tool.execute({
                "image": "nginx:latest",
                "name": "test-nginx",
            })

        assert result["success"] is True


@pytest.mark.unit
class TestDockerStopTool:
    """Test docker_stop tool"""

    @pytest.mark.asyncio
    async def test_docker_stop_success(self):
        """Test stopping Docker containers"""
        tool = DockerStopTool()
        mock_client, mock_container = _make_mock_docker_client()
        mock_container.name = "test-container"

        with patch("portal.tools.docker_tools.docker_stop.DOCKER_AVAILABLE", True), \
             patch("portal.tools.docker_tools.docker_stop.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = mock_client
            mock_docker_mod.errors.NotFound = type("NotFound", (Exception,), {})
            tool.client = mock_client
            result = await tool.execute({
                "containers": ["test-container"],
            })

        assert result["success"] is True


@pytest.mark.unit
class TestDockerLogsTool:
    """Test docker_logs tool"""

    @pytest.mark.asyncio
    async def test_docker_logs_success(self):
        """Test viewing Docker container logs"""
        tool = DockerLogsTool()
        mock_client, mock_container = _make_mock_docker_client()
        mock_container.name = "test-container"
        mock_container.short_id = "abc123"

        with patch("portal.tools.docker_tools.docker_logs.DOCKER_AVAILABLE", True), \
             patch("portal.tools.docker_tools.docker_logs.docker") as mock_docker_mod:
            mock_docker_mod.from_env.return_value = mock_client
            mock_docker_mod.errors.NotFound = type("NotFound", (Exception,), {})
            tool.client = mock_client
            result = await tool.execute({
                "container": "test-container",
                "tail": 50,
            })

        assert result["success"] is True
        assert "logs" in result or "result" in result


@pytest.mark.unit
class TestDockerComposeTool:
    """Test docker_compose tool"""

    @pytest.mark.asyncio
    async def test_docker_compose_up(self, tmp_path):
        """Test docker-compose up"""
        tool = DockerComposeTool()

        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3'\nservices: {}\n")

        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"Creating container", b""))
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_process):
            result = await tool.execute({
                "action": "up",
                "compose_file": str(compose_file),
                "detach": True,
            })

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_docker_compose_down(self, tmp_path):
        """Test docker-compose down"""
        tool = DockerComposeTool()

        compose_file = tmp_path / "docker-compose.yml"
        compose_file.write_text("version: '3'\nservices: {}\n")

        mock_process = MagicMock()
        mock_process.communicate = AsyncMock(return_value=(b"Stopping containers", b""))
        mock_process.returncode = 0

        with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=mock_process):
            result = await tool.execute({
                "action": "down",
                "compose_file": str(compose_file),
            })

        assert result["success"] is True
