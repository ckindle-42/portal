"""
Unit tests for Docker tools
"""

import pytest
from unittest.mock import patch, Mock, MagicMock
from portal.tools.docker_tools.docker_ps import DockerPSTool
from portal.tools.docker_tools.docker_run import DockerRunTool
from portal.tools.docker_tools.docker_stop import DockerStopTool
from portal.tools.docker_tools.docker_logs import DockerLogsTool
from portal.tools.docker_tools.docker_compose import DockerComposeTool


@pytest.mark.unit
class TestDockerPSTool:
    """Test docker_ps tool"""

    @pytest.mark.asyncio
    async def test_docker_ps_success(self):
        """Test listing Docker containers"""
        tool = DockerPSTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="CONTAINER ID   IMAGE     STATUS\nabc123         nginx     Up 2 hours",
                stderr=""
            )

            result = await tool.execute({})

            assert result["success"] is True
            assert "containers" in result or "result" in result

    @pytest.mark.asyncio
    async def test_docker_ps_no_docker(self):
        """Test when Docker is not available"""
        tool = DockerPSTool()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

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

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="abc123def456",
                stderr=""
            )

            result = await tool.execute({
                "image": "nginx:latest",
                "name": "test-nginx"
            })

            assert result["success"] is True


@pytest.mark.unit
class TestDockerStopTool:
    """Test docker_stop tool"""

    @pytest.mark.asyncio
    async def test_docker_stop_success(self):
        """Test stopping Docker containers"""
        tool = DockerStopTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="test-container",
                stderr=""
            )

            result = await tool.execute({
                "containers": ["test-container"]
            })

            assert result["success"] is True


@pytest.mark.unit
class TestDockerLogsTool:
    """Test docker_logs tool"""

    @pytest.mark.asyncio
    async def test_docker_logs_success(self):
        """Test viewing Docker container logs"""
        tool = DockerLogsTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Container log output\nLine 2\nLine 3",
                stderr=""
            )

            result = await tool.execute({
                "container": "test-container",
                "tail": 50
            })

            assert result["success"] is True
            assert "logs" in result or "result" in result


@pytest.mark.unit
class TestDockerComposeTool:
    """Test docker_compose tool"""

    @pytest.mark.asyncio
    async def test_docker_compose_up(self):
        """Test docker-compose up"""
        tool = DockerComposeTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Creating network\nCreating container",
                stderr=""
            )

            result = await tool.execute({
                "command": "up",
                "detach": True
            })

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_docker_compose_down(self):
        """Test docker-compose down"""
        tool = DockerComposeTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="Stopping containers\nRemoving containers",
                stderr=""
            )

            result = await tool.execute({
                "command": "down"
            })

            assert result["success"] is True
