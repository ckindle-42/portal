"""
System Stats Tool - Monitor system resources
"""

import asyncio
import logging
from typing import Dict, Any
from pathlib import Path

from portal.core.interfaces.tool import BaseTool, ToolMetadata, ToolCategory, ToolParameter

logger = logging.getLogger(__name__)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class SystemStatsTool(BaseTool):
    """Monitor system resources"""
    
    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="system_stats",
            description="Get system resource usage (CPU, RAM, disk)",
            category=ToolCategory.UTILITY,
            parameters=[
                ToolParameter(
                    name="detailed",
                    param_type="bool",
                    description="Include detailed per-core/disk stats",
                    required=False
                )
            ]
        )

    async def execute(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get system stats"""

        if not PSUTIL_AVAILABLE:
            return self._error_response("psutil not installed. Run: pip install psutil or pip install portal[automation]")

        detailed = parameters.get("detailed", False)

        try:
            # CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # Memory
            mem = psutil.virtual_memory()
            
            # Disk
            disk = psutil.disk_usage('/')
            
            result = {
                "cpu": {
                    "percent": cpu_percent,
                    "count": cpu_count
                },
                "memory": {
                    "total_gb": round(mem.total / (1024**3), 2),
                    "used_gb": round(mem.used / (1024**3), 2),
                    "available_gb": round(mem.available / (1024**3), 2),
                    "percent": mem.percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent": disk.percent
                }
            }
            
            if detailed:
                result["cpu"]["per_core"] = psutil.cpu_percent(interval=1, percpu=True)
                result["disk"]["partitions"] = [
                    {
                        "device": p.device,
                        "mountpoint": p.mountpoint,
                        "fstype": p.fstype
                    }
                    for p in psutil.disk_partitions()
                ]
            
            return self._success_response(result=result)
        
        except Exception as e:
            return self._error_response(f"Failed to get system stats: {str(e)}")
