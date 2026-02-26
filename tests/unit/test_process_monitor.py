"""Tests for portal.tools.system_tools.process_monitor"""

from unittest.mock import MagicMock, patch

import pytest

from portal.tools.system_tools.process_monitor import ProcessMonitorTool


class TestProcessMonitorMetadata:
    def test_metadata(self):
        tool = ProcessMonitorTool()
        meta = tool._get_metadata()
        assert meta.name == "process_monitor"
        assert len(meta.parameters) >= 3


class TestProcessMonitorNoPS:
    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", False)
    @pytest.mark.asyncio
    async def test_no_psutil(self):
        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "list"})
        assert result["success"] is False
        assert "psutil" in result["error"]


class TestProcessMonitorList:
    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @patch("portal.tools.system_tools.process_monitor.psutil")
    @pytest.mark.asyncio
    async def test_list_by_cpu(self, mock_psutil):
        proc1 = MagicMock()
        proc1.info = {"pid": 1, "name": "python", "cpu_percent": 50.0, "memory_percent": 10.0}
        proc2 = MagicMock()
        proc2.info = {"pid": 2, "name": "bash", "cpu_percent": 5.0, "memory_percent": 2.0}
        mock_psutil.process_iter.return_value = [proc1, proc2]

        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "list", "sort_by": "cpu", "limit": 5})
        assert result["success"] is True
        assert "python" in result["result"]

    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @patch("portal.tools.system_tools.process_monitor.psutil")
    @pytest.mark.asyncio
    async def test_list_by_memory(self, mock_psutil):
        proc1 = MagicMock()
        proc1.info = {"pid": 1, "name": "python", "cpu_percent": 5.0, "memory_percent": 80.0}
        mock_psutil.process_iter.return_value = [proc1]

        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "list", "sort_by": "memory"})
        assert result["success"] is True

    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @patch("portal.tools.system_tools.process_monitor.psutil")
    @pytest.mark.asyncio
    async def test_list_by_name(self, mock_psutil):
        proc1 = MagicMock()
        proc1.info = {"pid": 1, "name": "alpha", "cpu_percent": 0, "memory_percent": 0}
        proc2 = MagicMock()
        proc2.info = {"pid": 2, "name": "zeta", "cpu_percent": 0, "memory_percent": 0}
        mock_psutil.process_iter.return_value = [proc2, proc1]

        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "list", "sort_by": "name"})
        assert result["success"] is True

    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @patch("portal.tools.system_tools.process_monitor.psutil")
    @pytest.mark.asyncio
    async def test_list_handles_none_cpu(self, mock_psutil):
        proc1 = MagicMock()
        proc1.info = {"pid": 1, "name": "idle", "cpu_percent": None, "memory_percent": None}
        mock_psutil.process_iter.return_value = [proc1]

        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "list"})
        assert result["success"] is True


class TestProcessMonitorSearch:
    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @patch("portal.tools.system_tools.process_monitor.psutil")
    @pytest.mark.asyncio
    async def test_search_found(self, mock_psutil):
        proc1 = MagicMock()
        proc1.info = {"pid": 1, "name": "python3", "cpu_percent": 10.0, "memory_percent": 5.0}
        proc2 = MagicMock()
        proc2.info = {"pid": 2, "name": "bash", "cpu_percent": 1.0, "memory_percent": 1.0}
        mock_psutil.process_iter.return_value = [proc1, proc2]

        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "search", "query": "python"})
        assert result["success"] is True
        assert "python" in result["result"].lower()

    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @patch("portal.tools.system_tools.process_monitor.psutil")
    @pytest.mark.asyncio
    async def test_search_not_found(self, mock_psutil):
        proc1 = MagicMock()
        proc1.info = {"pid": 1, "name": "bash", "cpu_percent": 1.0, "memory_percent": 1.0}
        mock_psutil.process_iter.return_value = [proc1]

        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "search", "query": "nonexistent"})
        assert result["success"] is True
        assert "No processes found" in result["result"]

    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @pytest.mark.asyncio
    async def test_search_no_query(self):
        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "search"})
        assert result["success"] is False
        assert "Query" in result["error"]


class TestProcessMonitorInfo:
    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @patch("portal.tools.system_tools.process_monitor.psutil")
    @pytest.mark.asyncio
    async def test_info_success(self, mock_psutil):
        mock_proc = MagicMock()
        mock_proc.pid = 42
        mock_proc.name.return_value = "python"
        mock_proc.status.return_value = "running"
        mock_proc.cpu_percent.return_value = 10.5
        mock_proc.memory_percent.return_value = 5.2
        mock_proc.memory_info.return_value = MagicMock(rss=100 * 1024 * 1024)
        mock_proc.num_threads.return_value = 4
        mock_proc.create_time.return_value = 1700000000.0
        mock_proc.username.return_value = "testuser"
        mock_proc.cmdline.return_value = ["python", "app.py"]
        mock_proc.oneshot.return_value = MagicMock(__enter__=MagicMock(), __exit__=MagicMock())
        mock_psutil.Process.return_value = mock_proc

        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "info", "pid": 42})
        assert result["success"] is True
        assert "python" in result["result"]

    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @pytest.mark.asyncio
    async def test_info_no_pid(self):
        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "info"})
        assert result["success"] is False
        assert "PID" in result["error"]

    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @patch("portal.tools.system_tools.process_monitor.psutil")
    @pytest.mark.asyncio
    async def test_info_not_found(self, mock_psutil):
        import psutil
        mock_psutil.Process.side_effect = psutil.NoSuchProcess(999)
        mock_psutil.NoSuchProcess = psutil.NoSuchProcess
        mock_psutil.AccessDenied = psutil.AccessDenied

        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "info", "pid": 999})
        assert result["success"] is False


class TestProcessMonitorKill:
    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @patch("portal.tools.system_tools.process_monitor.psutil")
    @pytest.mark.asyncio
    async def test_kill_success(self, mock_psutil):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "test_proc"
        mock_proc.terminate.return_value = None
        mock_proc.wait.return_value = None
        mock_psutil.Process.return_value = mock_proc

        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "kill", "pid": 42})
        assert result["success"] is True
        assert "terminated" in result["result"]

    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @patch("portal.tools.system_tools.process_monitor.psutil")
    @pytest.mark.asyncio
    async def test_kill_force(self, mock_psutil):
        import psutil
        mock_proc = MagicMock()
        mock_proc.name.return_value = "stubborn"
        mock_proc.terminate.return_value = None
        mock_proc.wait.side_effect = psutil.TimeoutExpired(3)
        mock_proc.kill.return_value = None
        mock_psutil.Process.return_value = mock_proc
        mock_psutil.TimeoutExpired = psutil.TimeoutExpired

        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "kill", "pid": 42})
        assert result["success"] is True
        assert "killed" in result["result"].lower()

    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @pytest.mark.asyncio
    async def test_kill_no_pid(self):
        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "kill"})
        assert result["success"] is False

    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @patch("portal.tools.system_tools.process_monitor.psutil")
    @pytest.mark.asyncio
    async def test_kill_not_found(self, mock_psutil):
        import psutil
        mock_psutil.Process.side_effect = psutil.NoSuchProcess(999)
        mock_psutil.NoSuchProcess = psutil.NoSuchProcess
        mock_psutil.AccessDenied = psutil.AccessDenied

        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "kill", "pid": 999})
        assert result["success"] is False


class TestProcessMonitorUnknownAction:
    @patch("portal.tools.system_tools.process_monitor.PSUTIL_AVAILABLE", True)
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        tool = ProcessMonitorTool()
        result = await tool.execute({"action": "explode"})
        assert result["success"] is False
        assert "Unknown" in result["error"]
