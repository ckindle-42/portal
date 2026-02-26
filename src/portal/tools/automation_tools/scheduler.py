"""Job Scheduler Tool - Schedule recurring tasks"""

from datetime import datetime
from typing import Any

from portal.core.interfaces.tool import BaseTool, ToolCategory, ToolMetadata, ToolParameter


class JobSchedulerTool(BaseTool):
    """Schedule and manage recurring tasks"""

    # In-memory job storage (for demo - use persistent storage in production)
    _jobs: dict[str, dict[str, Any]] = {}
    _job_counter: int = 0

    def _get_metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="job_scheduler",
            description="Schedule, list, and manage recurring tasks",
            category=ToolCategory.AUTOMATION,
            version="1.0.0",
            requires_confirmation=False,
            parameters=[
                ToolParameter(
                    name="action",
                    param_type="string",
                    description="Action: create, list, delete, pause, resume",
                    required=True
                ),
                ToolParameter(
                    name="job_id",
                    param_type="string",
                    description="Job ID (for delete/pause/resume)",
                    required=False
                ),
                ToolParameter(
                    name="name",
                    param_type="string",
                    description="Job name",
                    required=False
                ),
                ToolParameter(
                    name="schedule",
                    param_type="string",
                    description="Cron expression or interval (e.g., '*/5 * * * *' or '5m')",
                    required=False
                ),
                ToolParameter(
                    name="command",
                    param_type="string",
                    description="Command or task to execute",
                    required=False
                )
            ],
            examples=["Schedule backup every hour"]
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Manage scheduled jobs"""
        try:
            action = parameters.get("action", "").lower()

            if action == "create":
                return await self._create_job(parameters)
            elif action == "list":
                return await self._list_jobs()
            elif action == "delete":
                return await self._delete_job(parameters.get("job_id"))
            elif action == "pause":
                return await self._pause_job(parameters.get("job_id"))
            elif action == "resume":
                return await self._resume_job(parameters.get("job_id"))
            else:
                return self._error_response(f"Unknown action: {action}")

        except Exception as e:
            return self._error_response(str(e))

    async def _create_job(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Create a new scheduled job"""
        name = parameters.get("name", "Unnamed Job")
        schedule = parameters.get("schedule", "")
        command = parameters.get("command", "")

        if not schedule:
            return self._error_response("Schedule is required")
        if not command:
            return self._error_response("Command is required")

        JobSchedulerTool._job_counter += 1
        job_id = f"job_{JobSchedulerTool._job_counter}"

        job = {
            "id": job_id,
            "name": name,
            "schedule": schedule,
            "command": command,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "next_run": self._calculate_next_run(schedule),
            "run_count": 0
        }

        JobSchedulerTool._jobs[job_id] = job

        return self._success_response({
            "message": f"Job created: {name}",
            "job": job
        })

    async def _list_jobs(self) -> dict[str, Any]:
        """List all jobs"""
        jobs = list(JobSchedulerTool._jobs.values())
        return self._success_response({
            "total": len(jobs),
            "jobs": jobs
        })

    async def _delete_job(self, job_id: str | None) -> dict[str, Any]:
        """Delete a job"""
        if not job_id or job_id not in JobSchedulerTool._jobs:
            return self._error_response(f"Job not found: {job_id}")

        job = JobSchedulerTool._jobs.pop(job_id)
        return self._success_response({
            "message": f"Job deleted: {job['name']}",
            "job_id": job_id
        })

    async def _pause_job(self, job_id: str | None) -> dict[str, Any]:
        """Pause a job"""
        if not job_id or job_id not in JobSchedulerTool._jobs:
            return self._error_response(f"Job not found: {job_id}")

        JobSchedulerTool._jobs[job_id]["status"] = "paused"
        return self._success_response({
            "message": f"Job paused: {JobSchedulerTool._jobs[job_id]['name']}",
            "job_id": job_id
        })

    async def _resume_job(self, job_id: str | None) -> dict[str, Any]:
        """Resume a paused job"""
        if not job_id or job_id not in JobSchedulerTool._jobs:
            return self._error_response(f"Job not found: {job_id}")

        JobSchedulerTool._jobs[job_id]["status"] = "active"
        return self._success_response({
            "message": f"Job resumed: {JobSchedulerTool._jobs[job_id]['name']}",
            "job_id": job_id
        })

    def _calculate_next_run(self, schedule: str) -> str:
        """Calculate next run time (simplified)"""
        # In production, use croniter or APScheduler for accurate calculation
        return datetime.now().isoformat()
