"""
Test Job Queue System
======================

Comprehensive tests for Phase 2: Async Job Queue

Tests:
1. Job Repository (enqueue, dequeue, status updates)
2. Job Workers (execution, retries, failures)
3. Worker Pool (concurrent processing, cleanup)
4. Event Bus Integration
"""

import asyncio
import pytest
from datetime import datetime
from typing import Any

from portal.persistence.repositories import Job, JobStatus, JobPriority
from portal.persistence.inmemory_impl import InMemoryJobRepository
from portal.core.job_worker import JobHandler, JobRegistry, JobWorker, JobWorkerPool
from portal.core.event_bus import EventBus, EventType


# =============================================================================
# TEST JOB HANDLERS
# =============================================================================


class SimpleJobHandler(JobHandler):
    """Simple job handler for testing"""

    async def execute(self, job: Job) -> Any:
        """Execute job - just return parameters"""
        await asyncio.sleep(0.1)  # Simulate work
        return {"status": "success", "data": job.parameters}

    def can_handle(self, job_type: str) -> bool:
        return job_type == "simple_job"


class FailingJobHandler(JobHandler):
    """Job handler that always fails (for testing retries)"""

    async def execute(self, job: Job) -> Any:
        """Execute job - always fail"""
        await asyncio.sleep(0.1)
        raise ValueError("Intentional failure for testing")

    def can_handle(self, job_type: str) -> bool:
        return job_type == "failing_job"


class SlowJobHandler(JobHandler):
    """Slow job handler (for testing timeouts)"""

    async def execute(self, job: Job) -> Any:
        """Execute job - takes a long time"""
        await asyncio.sleep(5)  # 5 seconds
        return {"status": "completed"}

    def can_handle(self, job_type: str) -> bool:
        return job_type == "slow_job"


# =============================================================================
# REPOSITORY TESTS
# =============================================================================


@pytest.mark.unit
async def test_job_repository_enqueue_dequeue():
    """Test basic enqueue/dequeue operations"""
    repo = InMemoryJobRepository()

    # Create a job
    job = Job(
        id="",
        job_type="simple_job",
        parameters={"message": "Hello"},
        priority=JobPriority.NORMAL
    )

    # Enqueue
    job_id = await repo.enqueue(job)
    assert job_id is not None
    assert len(job_id) > 0

    # Dequeue
    dequeued = await repo.dequeue("worker-1")
    assert dequeued is not None
    assert dequeued.id == job_id
    assert dequeued.status == JobStatus.RUNNING

    # Queue should be empty now
    empty = await repo.dequeue("worker-1")
    assert empty is None


@pytest.mark.unit
async def test_job_repository_priority():
    """Test priority queue behavior"""
    repo = InMemoryJobRepository()

    # Enqueue jobs with different priorities
    low_job = Job(id="", job_type="test", parameters={}, priority=JobPriority.LOW)
    normal_job = Job(id="", job_type="test", parameters={}, priority=JobPriority.NORMAL)
    high_job = Job(id="", job_type="test", parameters={}, priority=JobPriority.HIGH)

    await repo.enqueue(low_job)
    await repo.enqueue(normal_job)
    await repo.enqueue(high_job)

    # Should dequeue in priority order (high first)
    first = await repo.dequeue("worker-1")
    assert first.priority == JobPriority.HIGH

    second = await repo.dequeue("worker-1")
    assert second.priority == JobPriority.NORMAL

    third = await repo.dequeue("worker-1")
    assert third.priority == JobPriority.LOW


@pytest.mark.unit
async def test_job_repository_update_status():
    """Test status updates"""
    repo = InMemoryJobRepository()

    job = Job(id="", job_type="test", parameters={})
    job_id = await repo.enqueue(job)

    # Update to completed
    success = await repo.update_status(
        job_id,
        JobStatus.COMPLETED,
        result={"output": "done"}
    )
    assert success

    # Get job and verify
    updated = await repo.get_job(job_id)
    assert updated.status == JobStatus.COMPLETED
    assert updated.result == {"output": "done"}


@pytest.mark.unit
async def test_job_repository_retry():
    """Test retry mechanism"""
    repo = InMemoryJobRepository()

    job = Job(id="", job_type="test", parameters={}, max_retries=3)
    job_id = await repo.enqueue(job)

    # Dequeue and fail
    dequeued = await repo.dequeue("worker-1")
    await repo.increment_retry(job_id)

    # Should be requeued
    retrieved = await repo.get_job(job_id)
    assert retrieved.retry_count == 1
    assert retrieved.status == JobStatus.RETRYING


@pytest.mark.unit
async def test_job_repository_stats():
    """Test statistics"""
    repo = InMemoryJobRepository()

    # Create various jobs
    await repo.enqueue(Job(id="", job_type="type_a", parameters={}))
    await repo.enqueue(Job(id="", job_type="type_a", parameters={}))
    await repo.enqueue(Job(id="", job_type="type_b", parameters={}))

    stats = await repo.get_stats()

    assert stats['total_jobs'] == 3
    assert stats['status_counts'][JobStatus.PENDING] == 3
    assert stats['type_counts']['type_a'] == 2
    assert stats['type_counts']['type_b'] == 1


# =============================================================================
# WORKER TESTS
# =============================================================================


@pytest.mark.integration
async def test_job_worker_simple_execution():
    """Test basic job execution"""
    repo = InMemoryJobRepository()
    registry = JobRegistry()
    registry.register("simple_job", SimpleJobHandler())

    # Create worker
    worker = JobWorker(
        worker_id="test-worker",
        job_repository=repo,
        job_registry=registry,
        poll_interval=0.1
    )

    # Enqueue a job
    job = Job(id="", job_type="simple_job", parameters={"test": "data"})
    job_id = await repo.enqueue(job)

    # Start worker
    await worker.start()

    # Wait for job to complete
    for _ in range(50):  # Max 5 seconds
        job_status = await repo.get_job(job_id)
        if job_status.status == JobStatus.COMPLETED:
            break
        await asyncio.sleep(0.1)

    # Stop worker
    await worker.stop()

    # Verify job completed
    final_job = await repo.get_job(job_id)
    assert final_job.status == JobStatus.COMPLETED
    assert final_job.result is not None


@pytest.mark.integration
async def test_job_worker_retry_on_failure():
    """Test retry mechanism on failure"""
    repo = InMemoryJobRepository()
    registry = JobRegistry()
    registry.register("failing_job", FailingJobHandler())

    worker = JobWorker(
        worker_id="test-worker",
        job_repository=repo,
        job_registry=registry,
        poll_interval=0.1
    )

    # Enqueue a failing job with max 2 retries
    job = Job(id="", job_type="failing_job", parameters={}, max_retries=2)
    job_id = await repo.enqueue(job)

    # Start worker
    await worker.start()

    # Wait for job to fail after retries
    for _ in range(100):  # Max 10 seconds
        job_status = await repo.get_job(job_id)
        if job_status.status == JobStatus.FAILED:
            break
        await asyncio.sleep(0.1)

    # Stop worker
    await worker.stop()

    # Verify job failed after retries
    final_job = await repo.get_job(job_id)
    assert final_job.status == JobStatus.FAILED
    assert final_job.retry_count == 2  # Should have retried 2 times


# =============================================================================
# WORKER POOL TESTS
# =============================================================================


@pytest.mark.integration
async def test_worker_pool_concurrent_processing():
    """Test concurrent job processing with worker pool"""
    repo = InMemoryJobRepository()
    registry = JobRegistry()
    registry.register("simple_job", SimpleJobHandler())

    # Create worker pool with 3 workers
    pool = JobWorkerPool(
        job_repository=repo,
        job_registry=registry,
        num_workers=3,
        poll_interval=0.1
    )

    # Enqueue 10 jobs
    job_ids = []
    for i in range(10):
        job = Job(id="", job_type="simple_job", parameters={"index": i})
        job_id = await repo.enqueue(job)
        job_ids.append(job_id)

    # Start pool
    await pool.start()

    # Wait for all jobs to complete
    for _ in range(100):  # Max 10 seconds
        stats = await repo.get_stats()
        if stats['status_counts'].get(JobStatus.COMPLETED, 0) == 10:
            break
        await asyncio.sleep(0.1)

    # Stop pool
    await pool.stop()

    # Verify all jobs completed
    stats = await repo.get_stats()
    assert stats['status_counts'].get(JobStatus.COMPLETED, 0) == 10


@pytest.mark.integration
async def test_event_bus_integration():
    """Test event bus integration with workers"""
    repo = InMemoryJobRepository()
    registry = JobRegistry()
    registry.register("simple_job", SimpleJobHandler())

    event_bus = EventBus()
    events_received = []

    # Subscribe to events
    async def event_handler(event):
        events_received.append(event)

    event_bus.subscribe(EventType.TOOL_STARTED, event_handler)
    event_bus.subscribe(EventType.TOOL_COMPLETED, event_handler)

    # Create worker with event bus
    worker = JobWorker(
        worker_id="test-worker",
        job_repository=repo,
        job_registry=registry,
        event_bus=event_bus,
        poll_interval=0.1
    )

    # Enqueue a job with chat_id (required for events)
    job = Job(
        id="",
        job_type="simple_job",
        parameters={},
        chat_id="test-chat",
        trace_id="test-trace"
    )
    job_id = await repo.enqueue(job)

    # Start worker
    await worker.start()

    # Wait for job to complete
    for _ in range(50):
        job_status = await repo.get_job(job_id)
        if job_status.status == JobStatus.COMPLETED:
            break
        await asyncio.sleep(0.1)

    # Stop worker
    await worker.stop()

    # Verify events were emitted
    assert len(events_received) >= 2  # At least STARTED and COMPLETED
    assert any(e.event_type == EventType.TOOL_STARTED for e in events_received)
    assert any(e.event_type == EventType.TOOL_COMPLETED for e in events_received)


# =============================================================================
# RUN ALL TESTS
# =============================================================================


async def main():
    """Run all tests"""
    print("=" * 80)
    print("PHASE 2: JOB QUEUE SYSTEM TESTS")
    print("=" * 80)

    tests = [
        ("Repository: Enqueue/Dequeue", test_job_repository_enqueue_dequeue),
        ("Repository: Priority Queue", test_job_repository_priority),
        ("Repository: Status Updates", test_job_repository_update_status),
        ("Repository: Retry Mechanism", test_job_repository_retry),
        ("Repository: Statistics", test_job_repository_stats),
        ("Worker: Simple Execution", test_job_worker_simple_execution),
        ("Worker: Retry on Failure", test_job_worker_retry_on_failure),
        ("Worker Pool: Concurrent Processing", test_worker_pool_concurrent_processing),
        ("Worker: Event Bus Integration", test_event_bus_integration),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            print(f"\n🔍 Running: {name}")
            await test_func()
            print(f"✅ PASSED: {name}")
            passed += 1
        except Exception as e:
            print(f"❌ FAILED: {name}")
            print(f"   Error: {e}")
            failed += 1

    print("\n" + "=" * 80)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 80)

    if failed == 0:
        print("\n🎉 All tests passed! Phase 2 implementation is working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed. Please review the errors above.")


if __name__ == "__main__":
    asyncio.run(main())
