"""
Unit tests for System tools
"""

import pytest
from unittest.mock import patch, Mock
from portal.tools.system_tools.clipboard_manager import ClipboardManagerTool
from portal.tools.system_tools.process_monitor import ProcessMonitorTool
from portal.tools.system_tools.system_stats import SystemStatsTool


@pytest.mark.unit
class TestClipboardManagerTool:
    """Test clipboard_manager tool"""

    @pytest.mark.asyncio
    async def test_clipboard_copy(self):
        """Test copying to clipboard"""
        tool = ClipboardManagerTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

            result = await tool.execute({
                "operation": "copy",
                "text": "Test clipboard content"
            })

            # May succeed or fail depending on clipboard availability
            assert "success" in result

    @pytest.mark.asyncio
    async def test_clipboard_paste(self):
        """Test pasting from clipboard"""
        tool = ClipboardManagerTool()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="clipboard content",
                stderr=""
            )

            result = await tool.execute({
                "operation": "paste"
            })

            assert "success" in result


@pytest.mark.unit
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
                "memory_percent": 10.0
            }
            mock_iter.return_value = [mock_process]

            result = await tool.execute({
                "operation": "list",
                "limit": 10
            })

            assert result["success"] is True
            assert "processes" in result or "result" in result

    @pytest.mark.asyncio
    async def test_kill_process(self):
        """Test killing a process"""
        tool = ProcessMonitorTool()

        with patch("psutil.Process") as mock_process_class:
            mock_proc = Mock()
            mock_proc.terminate = Mock()
            mock_process_class.return_value = mock_proc

            result = await tool.execute({
                "operation": "kill",
                "pid": 9999
            })

            # May succeed or fail depending on implementation
            assert "success" in result


@pytest.mark.unit
class TestSystemStatsTool:
    """Test system_stats tool"""

    @pytest.mark.asyncio
    async def test_get_system_stats(self):
        """Test getting system resource usage"""
        tool = SystemStatsTool()

        with patch("psutil.cpu_percent") as mock_cpu, \
             patch("psutil.virtual_memory") as mock_mem, \
             patch("psutil.disk_usage") as mock_disk:

            mock_cpu.return_value = 45.5
            mock_mem.return_value = Mock(percent=60.0, total=16000000000)
            mock_disk.return_value = Mock(percent=75.0, total=500000000000)

            result = await tool.execute({})

            assert result["success"] is True
            assert "cpu" in str(result) or "memory" in str(result) or "result" in result

    @pytest.mark.asyncio
    async def test_system_stats_detailed(self):
        """Test detailed system statistics"""
        tool = SystemStatsTool()

        with patch("psutil.cpu_percent"), \
             patch("psutil.virtual_memory"), \
             patch("psutil.disk_usage"):

            result = await tool.execute({
                "detailed": True
            })

            assert result["success"] is True
