"""
In-Memory Job Queue Implementation
===================================

Thread-safe, async-compatible job queue using asyncio.Queue.
Ideal for development, testing, and single-node deployments.

For production multi-node deployments, use:
- SQLiteJobRepository: Persistent queue with file-based locking
- RedisJobRepository: Distributed queue with pub/sub
- PostgreSQLJobRepository: Enterprise queue with ACID guarantees
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import heapq

from .repositories import (
    Job,
    JobStatus,
    JobPriority,
    JobRepository
)

logger = logging.getLogger(__name__)


class InMemoryJobRepository(JobRepository):
    """
    In-memory job queue implementation.

    Features:
    - Priority queue (higher priority jobs execute first)
    - Thread-safe operations with asyncio locks
    - Job status tracking
    - Worker assignment tracking
    - Automatic stale job detection
    - Cleanup of old completed jobs

    Limitations:
    - Not persistent (jobs lost on restart)
    - Single-node only (no distributed support)
    - Limited scalability (all jobs in memory)

    For production, migrate to Redis or PostgreSQL.
    """

    def __init__(self):
        """Initialize in-memory job repository"""
        self._jobs: Dict[str, Job] = {}
        self._queue: List[tuple[int, int, str]] = []  # (priority, timestamp, job_id)
        self._counter = 0  # For stable sorting
        self._lock = asyncio.Lock()
        self._worker_assignments: Dict[str, str] = {}  # job_id -> worker_id

        logger.info("InMemoryJobRepository initialized")

    async def enqueue(self, job: Job) -> str:
        """Add a job to the queue"""
        async with self._lock:
            # Generate ID if not provided
            if not job.id:
                job.id = str(uuid.uuid4())

            # Set creation timestamp
            if not job.created_at:
                job.created_at = datetime.now()

            # Store job
            self._jobs[job.id] = job

            # Add to priority queue (negative priority for max-heap behavior)
            # Use counter for stable FIFO ordering within same priority
            heapq.heappush(
                self._queue,
                (-job.priority, self._counter, job.id)
            )
            self._counter += 1

            logger.info(
                f"Enqueued job {job.id} (type={job.job_type}, "
                f"priority={job.priority}, queue_size={len(self._queue)})"
            )

            return job.id

    async def dequeue(self, worker_id: str) -> Optional[Job]:
        """Get next job from queue"""
        async with self._lock:
            # Remove completed/cancelled jobs from queue
            while self._queue:
                _, _, job_id = self._queue[0]

                if job_id not in self._jobs:
                    heapq.heappop(self._queue)
                    continue

                job = self._jobs[job_id]

                if job.status not in [JobStatus.PENDING, JobStatus.RETRYING]:
                    heapq.heappop(self._queue)
                    continue

                # Found a valid job
                heapq.heappop(self._queue)

                # Mark as running
                job.status = JobStatus.RUNNING
                job.started_at = datetime.now()

                # Assign to worker
                self._worker_assignments[job_id] = worker_id

                logger.info(
                    f"Dequeued job {job.id} for worker {worker_id} "
                    f"(type={job.job_type}, priority={job.priority})"
                )

                return job

            # Queue is empty
            return None

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        async with self._lock:
            return self._jobs.get(job_id)

    async def update_status(
        self,
        job_id: str,
        status: str,
        result: Optional[Any] = None,
        error: Optional[str] = None
    ) -> bool:
        """Update job status"""
        async with self._lock:
            if job_id not in self._jobs:
                logger.warning(f"Job {job_id} not found")
                return False

            job = self._jobs[job_id]
            job.status = status

            if result is not None:
                job.result = result

            if error is not None:
                job.error = error

            if status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                job.completed_at = datetime.now()

                # Remove worker assignment
                if job_id in self._worker_assignments:
                    del self._worker_assignments[job_id]

            logger.info(f"Updated job {job_id} status to {status}")
            return True

    async def increment_retry(self, job_id: str) -> bool:
        """Increment retry count"""
        async with self._lock:
            if job_id not in self._jobs:
                return False

            job = self._jobs[job_id]
            job.retry_count += 1
            job.status = JobStatus.RETRYING

            # Re-enqueue if under max retries
            if job.retry_count <= job.max_retries:
                heapq.heappush(
                    self._queue,
                    (-job.priority, self._counter, job.id)
                )
                self._counter += 1

                logger.info(
                    f"Job {job_id} retry {job.retry_count}/{job.max_retries}"
                )
            else:
                job.status = JobStatus.FAILED
                job.error = f"Max retries ({job.max_retries}) exceeded"
                logger.warning(f"Job {job_id} exceeded max retries")

            return True

    async def list_jobs(
        self,
        status: Optional[str] = None,
        job_type: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Job]:
        """List jobs with filtering"""
        async with self._lock:
            jobs = list(self._jobs.values())

            # Apply filters
            if status:
                jobs = [j for j in jobs if j.status == status]

            if job_type:
                jobs = [j for j in jobs if j.job_type == job_type]

            # Sort by creation time (newest first)
            jobs.sort(
                key=lambda j: j.created_at or datetime.min,
                reverse=True
            )

            # Apply pagination
            start = offset
            end = offset + limit if limit else None

            return jobs[start:end]

    async def count_jobs(
        self,
        status: Optional[str] = None,
        job_type: Optional[str] = None
    ) -> int:
        """Count jobs with filtering"""
        async with self._lock:
            jobs = list(self._jobs.values())

            if status:
                jobs = [j for j in jobs if j.status == status]

            if job_type:
                jobs = [j for j in jobs if j.job_type == job_type]

            return len(jobs)

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        async with self._lock:
            if job_id not in self._jobs:
                return False

            job = self._jobs[job_id]

            # Can only cancel pending/retrying jobs
            if job.status in [JobStatus.PENDING, JobStatus.RETRYING]:
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now()

                # Remove from worker assignment
                if job_id in self._worker_assignments:
                    del self._worker_assignments[job_id]

                logger.info(f"Cancelled job {job_id}")
                return True

            logger.warning(f"Cannot cancel job {job_id} with status {job.status}")
            return False

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job"""
        async with self._lock:
            if job_id not in self._jobs:
                return False

            # Remove from storage
            del self._jobs[job_id]

            # Remove from worker assignment
            if job_id in self._worker_assignments:
                del self._worker_assignments[job_id]

            logger.info(f"Deleted job {job_id}")
            return True

    async def cleanup_completed(self, older_than_hours: int = 24) -> int:
        """Remove old completed jobs"""
        async with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=older_than_hours)

            to_delete = []
            for job_id, job in self._jobs.items():
                if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    if job.completed_at and job.completed_at < cutoff_time:
                        to_delete.append(job_id)

            # Delete jobs
            for job_id in to_delete:
                del self._jobs[job_id]
                if job_id in self._worker_assignments:
                    del self._worker_assignments[job_id]

            logger.info(
                f"Cleaned up {len(to_delete)} jobs older than {older_than_hours}h"
            )

            return len(to_delete)

    async def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        async with self._lock:
            # Count by status
            status_counts = defaultdict(int)
            type_counts = defaultdict(int)

            for job in self._jobs.values():
                status_counts[job.status] += 1
                type_counts[job.job_type] += 1

            # Calculate average wait time for pending jobs
            pending_jobs = [
                j for j in self._jobs.values()
                if j.status == JobStatus.PENDING and j.created_at
            ]

            avg_wait_time = None
            if pending_jobs:
                total_wait = sum(
                    (datetime.now() - j.created_at).total_seconds()
                    for j in pending_jobs
                )
                avg_wait_time = total_wait / len(pending_jobs)

            return {
                'total_jobs': len(self._jobs),
                'queue_size': len(self._queue),
                'status_counts': dict(status_counts),
                'type_counts': dict(type_counts),
                'active_workers': len(set(self._worker_assignments.values())),
                'avg_wait_time_seconds': avg_wait_time
            }

    async def get_worker_jobs(self, worker_id: str) -> List[Job]:
        """Get jobs assigned to a worker"""
        async with self._lock:
            job_ids = [
                jid for jid, wid in self._worker_assignments.items()
                if wid == worker_id
            ]

            return [self._jobs[jid] for jid in job_ids if jid in self._jobs]

    async def requeue_stale_jobs(self, timeout_minutes: int = 30) -> int:
        """Requeue stale running jobs"""
        async with self._lock:
            cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)

            requeued = 0
            for job in self._jobs.values():
                if job.status == JobStatus.RUNNING and job.started_at:
                    if job.started_at < cutoff_time:
                        # Job has been running too long, requeue it
                        job.status = JobStatus.RETRYING
                        job.error = f"Timed out after {timeout_minutes} minutes"

                        # Remove worker assignment
                        if job.id in self._worker_assignments:
                            del self._worker_assignments[job.id]

                        # Re-enqueue
                        heapq.heappush(
                            self._queue,
                            (-job.priority, self._counter, job.id)
                        )
                        self._counter += 1

                        requeued += 1
                        logger.warning(
                            f"Requeued stale job {job.id} "
                            f"(started {job.started_at}, timeout {timeout_minutes}m)"
                        )

            return requeued
