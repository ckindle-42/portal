"""
Process Monitor Tool - Monitor system processes
"""

import logging
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter

logger = logging.getLogger(__name__)

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class ProcessMonitorTool(BaseTool):
    """Monitor system processes"""

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="process_monitor",
            description="Monitor and manage system processes",
            category=ToolCategory.UTILITY,
            requires_confirmation=False,
            parameters=[
                ToolParameter(
                    name="action",
                    param_type="string",
                    description="Action: list, search, info, kill (default: list)",
                    required=False,
                ),
                ToolParameter(
                    name="query",
                    param_type="string",
                    description="Search query for process name (for search action)",
                    required=False,
                ),
                ToolParameter(
                    name="pid",
                    param_type="int",
                    description="Process ID (for info/kill actions)",
                    required=False,
                ),
                ToolParameter(
                    name="sort_by",
                    param_type="string",
                    description="Sort by: cpu, memory, name (default: cpu)",
                    required=False,
                ),
                ToolParameter(
                    name="limit",
                    param_type="int",
                    description="Limit number of results (default: 10)",
                    required=False,
                ),
            ],
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Monitor processes"""

        if not PSUTIL_AVAILABLE:
            return self._error_response("psutil not installed. Run: pip install psutil")

        action = parameters.get("action", "list").lower()
        query = parameters.get("query", "")
        pid = parameters.get("pid")
        sort_by = parameters.get("sort_by", "cpu").lower()
        limit = parameters.get("limit", 10)

        try:
            if action == "list":
                return await self._list_processes(sort_by, limit)

            elif action == "search":
                if not query:
                    return self._error_response("Query is required for search action")
                return await self._search_processes(query, limit)

            elif action == "info":
                if not pid:
                    return self._error_response("PID is required for info action")
                return await self._process_info(pid)

            elif action == "kill":
                if not pid:
                    return self._error_response("PID is required for kill action")
                return await self._kill_process(pid)

            else:
                return self._error_response(
                    f"Unknown action: {action}. Use: list, search, info, kill"
                )

        except Exception as e:
            return self._error_response(f"Process monitoring failed: {str(e)}")

    async def _list_processes(self, sort_by: str, limit: int) -> dict[str, Any]:
        """List top processes"""
        processes = []

        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                pinfo = proc.info
                processes.append(
                    {
                        "pid": pinfo["pid"],
                        "name": pinfo["name"],
                        "cpu": pinfo["cpu_percent"] or 0,
                        "memory": pinfo["memory_percent"] or 0,
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        # Sort processes
        if sort_by == "memory":
            processes.sort(key=lambda x: x["memory"], reverse=True)
        elif sort_by == "name":
            processes.sort(key=lambda x: x["name"])
        else:  # default to cpu
            processes.sort(key=lambda x: x["cpu"], reverse=True)

        # Limit results
        top_processes = processes[:limit]

        # Format output
        result_lines = [f"Top {limit} processes (by {sort_by}):\n"]
        for p in top_processes:
            result_lines.append(
                f"PID {p['pid']}: {p['name']}\n  CPU: {p['cpu']:.1f}% | Memory: {p['memory']:.1f}%"
            )

        return self._success_response(
            result="\n\n".join(result_lines),
            metadata={
                "total_processes": len(processes),
                "showing": len(top_processes),
                "sort_by": sort_by,
            },
        )

    async def _search_processes(self, query: str, limit: int) -> dict[str, Any]:
        """Search for processes by name"""
        matches = []
        query_lower = query.lower()

        for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                pinfo = proc.info
                if query_lower in pinfo["name"].lower():
                    matches.append(
                        {
                            "pid": pinfo["pid"],
                            "name": pinfo["name"],
                            "cpu": pinfo["cpu_percent"] or 0,
                            "memory": pinfo["memory_percent"] or 0,
                        }
                    )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if not matches:
            return self._success_response(
                result=f"No processes found matching '{query}'",
                metadata={"query": query, "matches": 0},
            )

        # Limit results
        limited_matches = matches[:limit]

        # Format output
        result_lines = [f"Processes matching '{query}' ({len(matches)} found):\n"]
        for p in limited_matches:
            result_lines.append(
                f"PID {p['pid']}: {p['name']}\n  CPU: {p['cpu']:.1f}% | Memory: {p['memory']:.1f}%"
            )

        return self._success_response(
            result="\n\n".join(result_lines),
            metadata={
                "query": query,
                "total_matches": len(matches),
                "showing": len(limited_matches),
            },
        )

    async def _process_info(self, pid: int) -> dict[str, Any]:
        """Get detailed info about a process"""
        try:
            proc = psutil.Process(pid)

            # Gather detailed info
            with proc.oneshot():
                info = {
                    "pid": proc.pid,
                    "name": proc.name(),
                    "status": proc.status(),
                    "cpu_percent": proc.cpu_percent(interval=0.1),
                    "memory_percent": proc.memory_percent(),
                    "memory_mb": proc.memory_info().rss / 1024 / 1024,
                    "num_threads": proc.num_threads(),
                    "create_time": proc.create_time(),
                }

            # Try to get additional info (may fail for some processes)
            try:
                info["username"] = proc.username()
            except psutil.AccessDenied:
                info["username"] = "N/A"

            try:
                info["cmdline"] = " ".join(proc.cmdline())
            except psutil.AccessDenied:
                info["cmdline"] = "N/A"

            # Format output
            import datetime

            create_time = datetime.datetime.fromtimestamp(info["create_time"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            result = (
                f"Process Information:\n\n"
                f"PID: {info['pid']}\n"
                f"Name: {info['name']}\n"
                f"Status: {info['status']}\n"
                f"User: {info['username']}\n"
                f"CPU: {info['cpu_percent']:.1f}%\n"
                f"Memory: {info['memory_percent']:.1f}% ({info['memory_mb']:.1f} MB)\n"
                f"Threads: {info['num_threads']}\n"
                f"Started: {create_time}\n"
                f"Command: {info['cmdline'][:100]}"
            )

            return self._success_response(result=result, metadata=info)

        except psutil.NoSuchProcess:
            return self._error_response(f"Process {pid} not found")
        except psutil.AccessDenied:
            return self._error_response(f"Access denied to process {pid}")

    async def _kill_process(self, pid: int) -> dict[str, Any]:
        """Kill a process"""
        try:
            proc = psutil.Process(pid)
            name = proc.name()

            # Terminate the process
            proc.terminate()

            # Wait for termination (with timeout)
            try:
                proc.wait(timeout=3)
                return self._success_response(
                    result=f"Process {pid} ({name}) terminated successfully",
                    metadata={"pid": pid, "name": name},
                )
            except psutil.TimeoutExpired:
                # Force kill if termination failed
                proc.kill()
                return self._success_response(
                    result=f"Process {pid} ({name}) forcefully killed",
                    metadata={"pid": pid, "name": name, "forced": True},
                )

        except psutil.NoSuchProcess:
            return self._error_response(f"Process {pid} not found")
        except psutil.AccessDenied:
            return self._error_response(f"Access denied to kill process {pid}")
