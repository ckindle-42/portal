"""Tests for portal.tools.automation_tools.scheduler — JobSchedulerTool"""

import pytest

from portal.tools.automation_tools.scheduler import JobSchedulerTool


@pytest.fixture(autouse=True)
def reset_scheduler():
    """Reset shared state between tests."""
    JobSchedulerTool._jobs = {}
    JobSchedulerTool._job_counter = 0
    yield
    JobSchedulerTool._jobs = {}
    JobSchedulerTool._job_counter = 0


class TestJobSchedulerToolMetadata:
    def test_metadata_name(self):
        tool = JobSchedulerTool()
        meta = tool._get_metadata()
        assert meta.name == "job_scheduler"
        assert meta.requires_confirmation is False
        assert len(meta.parameters) >= 3


class TestJobSchedulerToolCreate:
    @pytest.mark.asyncio
    async def test_create_job(self):
        tool = JobSchedulerTool()
        result = await tool.execute({
            "action": "create",
            "name": "Backup",
            "schedule": "0 * * * *",
            "command": "backup.sh",
        })
        assert result["success"] is True
        assert "Backup" in result["result"]["message"]
        job = result["result"]["job"]
        assert job["status"] == "active"
        assert job["run_count"] == 0

    @pytest.mark.asyncio
    async def test_create_job_without_schedule(self):
        tool = JobSchedulerTool()
        result = await tool.execute({
            "action": "create",
            "name": "Bad",
            "command": "run.sh",
        })
        assert result["success"] is False
        assert "Schedule" in result["error"]

    @pytest.mark.asyncio
    async def test_create_job_without_command(self):
        tool = JobSchedulerTool()
        result = await tool.execute({
            "action": "create",
            "schedule": "0 * * * *",
        })
        assert result["success"] is False
        assert "Command" in result["error"]

    @pytest.mark.asyncio
    async def test_create_multiple_jobs(self):
        tool = JobSchedulerTool()
        for i in range(3):
            await tool.execute({
                "action": "create",
                "name": f"Job {i}",
                "schedule": "* * * * *",
                "command": f"cmd_{i}",
            })
        assert len(JobSchedulerTool._jobs) == 3


class TestJobSchedulerToolList:
    @pytest.mark.asyncio
    async def test_list_empty(self):
        tool = JobSchedulerTool()
        result = await tool.execute({"action": "list"})
        assert result["success"] is True
        assert result["result"]["total"] == 0

    @pytest.mark.asyncio
    async def test_list_with_jobs(self):
        tool = JobSchedulerTool()
        await tool.execute({
            "action": "create", "name": "J1",
            "schedule": "* * * * *", "command": "cmd1",
        })
        result = await tool.execute({"action": "list"})
        assert result["success"] is True
        assert result["result"]["total"] == 1


class TestJobSchedulerToolDelete:
    @pytest.mark.asyncio
    async def test_delete_job(self):
        tool = JobSchedulerTool()
        r = await tool.execute({
            "action": "create", "name": "Del",
            "schedule": "* * * * *", "command": "cmd",
        })
        job_id = r["result"]["job"]["id"]
        result = await tool.execute({"action": "delete", "job_id": job_id})
        assert result["success"] is True
        assert job_id not in JobSchedulerTool._jobs

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        tool = JobSchedulerTool()
        result = await tool.execute({"action": "delete", "job_id": "nope"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_no_id(self):
        tool = JobSchedulerTool()
        result = await tool.execute({"action": "delete"})
        assert result["success"] is False


class TestJobSchedulerToolPauseResume:
    @pytest.mark.asyncio
    async def test_pause_job(self):
        tool = JobSchedulerTool()
        r = await tool.execute({
            "action": "create", "name": "P",
            "schedule": "* * * * *", "command": "c",
        })
        job_id = r["result"]["job"]["id"]
        result = await tool.execute({"action": "pause", "job_id": job_id})
        assert result["success"] is True
        assert JobSchedulerTool._jobs[job_id]["status"] == "paused"

    @pytest.mark.asyncio
    async def test_resume_job(self):
        tool = JobSchedulerTool()
        r = await tool.execute({
            "action": "create", "name": "R",
            "schedule": "* * * * *", "command": "c",
        })
        job_id = r["result"]["job"]["id"]
        await tool.execute({"action": "pause", "job_id": job_id})
        result = await tool.execute({"action": "resume", "job_id": job_id})
        assert result["success"] is True
        assert JobSchedulerTool._jobs[job_id]["status"] == "active"

    @pytest.mark.asyncio
    async def test_pause_nonexistent(self):
        tool = JobSchedulerTool()
        result = await tool.execute({"action": "pause", "job_id": "nope"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_resume_nonexistent(self):
        tool = JobSchedulerTool()
        result = await tool.execute({"action": "resume", "job_id": "nope"})
        assert result["success"] is False


class TestJobSchedulerToolEdge:
    @pytest.mark.asyncio
    async def test_unknown_action(self):
        tool = JobSchedulerTool()
        result = await tool.execute({"action": "explode"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_empty_action(self):
        tool = JobSchedulerTool()
        result = await tool.execute({"action": ""})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_calculate_next_run(self):
        tool = JobSchedulerTool()
        # Currently returns "now" — just verify it returns a string
        result = tool._calculate_next_run("0 * * * *")
        assert isinstance(result, str)
