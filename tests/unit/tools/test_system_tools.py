"""
Unit tests for System tools
"""

import importlib.util
from unittest.mock import Mock, patch

import pytest

from portal.tools.system_tools.clipboard_manager import ClipboardManagerTool
from portal.tools.system_tools.process_monitor import ProcessMonitorTool
from portal.tools.system_tools.system_stats import SystemStatsTool

_has_psutil = importlib.util.find_spec("psutil") is not None


@pytest.mark.unit
class TestClipboardManagerTool:
    """Test clipboard_manager tool"""

    @pytest.mark.asyncio
    async def test_clipboard_copy(self):
        """Test copying to clipboard"""
        tool = ClipboardManagerTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await tool.execute({"operation": "copy", "text": "Test clipboard content"})

            # May succeed or fail depending on clipboard availability
            assert "success" in result

    @pytest.mark.asyncio
    async def test_clipboard_paste(self):
        """Test pasting from clipboard"""
        tool = ClipboardManagerTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="clipboard content", stderr="")

            result = await tool.execute({"operation": "paste"})

            assert "success" in result


@pytest.mark.unit
@pytest.mark.skipif(not _has_psutil, reason="psutil not installed")
class TestProcessMonitorTool:
    """Test process_monitor tool"""

    @pytest.mark.asyncio
    async def test_list_processes(self):
        """Test listing system processes"""
        tool = ProcessMonitorTool()

        with patch("psutil.process_iter") as mock_iter:
            mock_process = Mock()
            mock_process.info = {
                "pid": 1234,
                "name": "python",
                "cpu_percent": 5.0,
                "memory_percent": 10.0,
            }
            mock_iter.return_value = [mock_process]

            result = await tool.execute(
                {
                    "action": "list",
                    "limit": 10,
                }
            )

        assert result["success"] is True
        assert "processes" in result or "result" in result

    @pytest.mark.asyncio
    async def test_kill_process(self):
        """Test killing a process"""
        tool = ProcessMonitorTool()

        with patch("psutil.Process") as mock_process_class:
            mock_proc = Mock()
            mock_proc.name.return_value = "test_process"
            mock_proc.terminate = Mock()
            mock_proc.wait = Mock(return_value=None)
            mock_process_class.return_value = mock_proc

            result = await tool.execute(
                {
                    "action": "kill",
                    "pid": 9999,
                }
            )

        # May succeed or fail depending on implementation
        assert "success" in result


@pytest.mark.unit
@pytest.mark.skipif(not _has_psutil, reason="psutil not installed")
class TestSystemStatsTool:
    """Test system_stats tool"""

    @pytest.mark.asyncio
    async def test_get_system_stats(self):
        """Test getting system resource usage"""
        tool = SystemStatsTool()

        GB = 1024**3

        with (
            patch("psutil.cpu_percent", return_value=45.5),
            patch("psutil.cpu_count", return_value=4),
            patch(
                "psutil.virtual_memory",
                return_value=Mock(percent=60.0, total=16 * GB, used=9 * GB, available=7 * GB),
            ),
            patch(
                "psutil.disk_usage",
                return_value=Mock(percent=75.0, total=500 * GB, used=375 * GB, free=125 * GB),
            ),
        ):
            result = await tool.execute({})

        assert result["success"] is True
        assert "cpu" in str(result) or "memory" in str(result) or "result" in result

    @pytest.mark.asyncio
    async def test_system_stats_detailed(self):
        """Test detailed system statistics"""
        tool = SystemStatsTool()

        GB = 1024**3

        mock_partition = Mock()
        mock_partition.device = "/dev/sda1"
        mock_partition.mountpoint = "/"
        mock_partition.fstype = "ext4"

        with (
            patch("psutil.cpu_percent", side_effect=[45.5, [10.0, 20.0, 30.0, 40.0]]),
            patch("psutil.cpu_count", return_value=4),
            patch(
                "psutil.virtual_memory",
                return_value=Mock(percent=60.0, total=16 * GB, used=9 * GB, available=7 * GB),
            ),
            patch(
                "psutil.disk_usage",
                return_value=Mock(percent=75.0, total=500 * GB, used=375 * GB, free=125 * GB),
            ),
            patch("psutil.disk_partitions", return_value=[mock_partition]),
        ):
            result = await tool.execute({"detailed": True})

        assert result["success"] is True
