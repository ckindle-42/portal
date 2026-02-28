"""Job Scheduler Tool - Schedule recurring tasks"""

from datetime import UTC, datetime
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
                    required=True,
                ),
                ToolParameter(
                    name="job_id",
                    param_type="string",
                    description="Job ID (for delete/pause/resume)",
                    required=False,
                ),
                ToolParameter(
                    name="name", param_type="string", description="Job name", required=False
                ),
                ToolParameter(
                    name="schedule",
                    param_type="string",
                    description="Cron expression or interval (e.g., '*/5 * * * *' or '5m')",
                    required=False,
                ),
                ToolParameter(
                    name="command",
                    param_type="string",
                    description="Command or task to execute",
                    required=False,
                ),
            ],
            examples=["Schedule backup every hour"],
        )

    async def execute(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Manage scheduled jobs"""
        action = parameters.get("action", "").lower()
        handler = self._DISPATCH.get(action)
        if not handler:
            return self._error_response(
                f"Unknown action: {action}. Use: {', '.join(self._DISPATCH)}"
            )
        try:
            return await handler(self, parameters)
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
            "created_at": datetime.now(tz=UTC).isoformat(),
            "last_run": None,
            "next_run": self._calculate_next_run(schedule),
            "run_count": 0,
        }

        JobSchedulerTool._jobs[job_id] = job

        return self._success_response({"message": f"Job created: {name}", "job": job})

    async def _list_jobs(self, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        """List all jobs"""
        jobs = list(JobSchedulerTool._jobs.values())
        return self._success_response({"total": len(jobs), "jobs": jobs})

    async def _delete_job(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Delete a job"""
        job_id = parameters.get("job_id")
        if not job_id or job_id not in JobSchedulerTool._jobs:
            return self._error_response(f"Job not found: {job_id}")

        job = JobSchedulerTool._jobs.pop(job_id)
        return self._success_response({"message": f"Job deleted: {job['name']}", "job_id": job_id})

    async def _pause_job(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Pause a job"""
        job_id = parameters.get("job_id")
        if not job_id or job_id not in JobSchedulerTool._jobs:
            return self._error_response(f"Job not found: {job_id}")

        JobSchedulerTool._jobs[job_id]["status"] = "paused"
        return self._success_response(
            {"message": f"Job paused: {JobSchedulerTool._jobs[job_id]['name']}", "job_id": job_id}
        )

    async def _resume_job(self, parameters: dict[str, Any]) -> dict[str, Any]:
        """Resume a paused job"""
        job_id = parameters.get("job_id")
        if not job_id or job_id not in JobSchedulerTool._jobs:
            return self._error_response(f"Job not found: {job_id}")

        JobSchedulerTool._jobs[job_id]["status"] = "active"
        return self._success_response(
            {"message": f"Job resumed: {JobSchedulerTool._jobs[job_id]['name']}", "job_id": job_id}
        )

    _DISPATCH: dict[str, Any] = {
        "create": _create_job,
        "list": _list_jobs,
        "delete": _delete_job,
        "pause": _pause_job,
        "resume": _resume_job,
    }

    def _calculate_next_run(self, schedule: str) -> str:
        """Calculate next run time from a cron expression or interval shorthand.

        Supports:
        - Interval shorthand: '5m', '1h', '30s'
        - Cron expressions: '*/5 * * * *' (minute field only for next-run estimate)
        """
        now = datetime.now(tz=UTC)

        # Handle interval shorthand (e.g., '5m', '1h', '30s')
        if schedule and schedule[-1] in ("s", "m", "h") and schedule[:-1].isdigit():
            from datetime import timedelta

            value = int(schedule[:-1])
            unit = schedule[-1]
            deltas = {
                "s": timedelta(seconds=value),
                "m": timedelta(minutes=value),
                "h": timedelta(hours=value),
            }
            return (now + deltas[unit]).isoformat()

        # Handle basic cron: extract minute field for simple next-run estimate
        parts = schedule.strip().split()
        if len(parts) >= 5:
            minute_field = parts[0]
            if minute_field.startswith("*/") and minute_field[2:].isdigit():
                from datetime import timedelta

                interval = int(minute_field[2:])
                minutes_until = interval - (now.minute % interval)
                return (
                    (now + timedelta(minutes=minutes_until))
                    .replace(second=0, microsecond=0)
                    .isoformat()
                )

        # Fallback: next run in 1 hour
        from datetime import timedelta

        return (now + timedelta(hours=1)).isoformat()
