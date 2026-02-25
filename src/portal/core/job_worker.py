"""
Background Job Worker System
==============================

Async worker pool that processes jobs from the queue.

Features:
- Multiple concurrent workers
- Event bus integration for real-time status updates
- Automatic retry on failure
- Graceful shutdown
- Stale job detection and recovery
- Pluggable job handler registry

Architecture:
- JobWorker: Individual worker that processes one job at a time
- JobWorkerPool: Manages multiple workers
- JobHandler: Interface for job execution logic
- JobRegistry: Maps job types to handlers
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, Callable, Awaitable
from abc import ABC, abstractmethod
from datetime import datetime

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from persistence.repositories import Job, JobStatus, JobRepository
from core.event_bus import EventBus, EventType

logger = logging.getLogger(__name__)


# =============================================================================
# JOB HANDLER INTERFACE
# =============================================================================


class JobHandler(ABC):
    """
    Abstract interface for job handlers.

    Each job type (e.g., 'tool_execution', 'batch_operation', 'scheduled_task')
    should have a corresponding handler that implements this interface.
    """

    @abstractmethod
    async def execute(self, job: Job) -> Any:
        """
        Execute the job and return the result.

        Args:
            job: Job to execute

        Returns:
            Job result (will be stored in job.result)

        Raises:
            Exception: On job failure (will be caught and stored in job.error)
        """
        pass

    @abstractmethod
    def can_handle(self, job_type: str) -> bool:
        """Check if this handler can handle the given job type"""
        pass


class JobRegistry:
    """
    Registry for job handlers.

    Maps job types to their handlers.
    """

    def __init__(self):
        """Initialize job registry"""
        self._handlers: Dict[str, JobHandler] = {}
        logger.info("JobRegistry initialized")

    def register(self, job_type: str, handler: JobHandler):
        """Register a job handler"""
        self._handlers[job_type] = handler
        logger.info(f"Registered handler for job type: {job_type}")

    def get_handler(self, job_type: str) -> Optional[JobHandler]:
        """Get handler for job type"""
        return self._handlers.get(job_type)

    def list_handlers(self) -> Dict[str, JobHandler]:
        """List all registered handlers"""
        return self._handlers.copy()


# =============================================================================
# JOB WORKER
# =============================================================================


class JobWorker:
    """
    Individual worker that processes jobs from the queue.

    Each worker:
    - Polls the queue for jobs
    - Executes jobs using registered handlers
    - Updates job status
    - Emits events for real-time feedback
    - Handles retries on failure
    """

    def __init__(
        self,
        worker_id: str,
        job_repository: JobRepository,
        job_registry: JobRegistry,
        event_bus: Optional[EventBus] = None,
        poll_interval: float = 1.0
    ):
        """
        Initialize job worker.

        Args:
            worker_id: Unique worker identifier
            job_repository: Repository for job queue operations
            job_registry: Registry of job handlers
            event_bus: Optional event bus for status updates
            poll_interval: How often to poll queue (seconds)
        """
        self.worker_id = worker_id
        self.job_repository = job_repository
        self.job_registry = job_registry
        self.event_bus = event_bus
        self.poll_interval = poll_interval

        self._running = False
        self._current_job: Optional[Job] = None
        self._task: Optional[asyncio.Task] = None

        logger.info(f"JobWorker {worker_id} initialized")

    async def start(self):
        """Start the worker"""
        if self._running:
            logger.warning(f"Worker {self.worker_id} already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info(f"Worker {self.worker_id} started")

    async def stop(self, timeout: float = 30.0):
        """
        Stop the worker gracefully.

        Args:
            timeout: Maximum time to wait for current job to complete
        """
        if not self._running:
            return

        logger.info(f"Stopping worker {self.worker_id}...")

        self._running = False

        # Wait for current job to complete (with timeout)
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Worker {self.worker_id} did not stop within {timeout}s, "
                    "cancelling task"
                )
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

        logger.info(f"Worker {self.worker_id} stopped")

    async def _run(self):
        """Main worker loop"""
        logger.info(f"Worker {self.worker_id} entering main loop")

        while self._running:
            try:
                # Get next job from queue
                job = await self.job_repository.dequeue(self.worker_id)

                if job is None:
                    # Queue is empty, wait before polling again
                    await asyncio.sleep(self.poll_interval)
                    continue

                # Process the job
                await self._process_job(job)

            except asyncio.CancelledError:
                logger.info(f"Worker {self.worker_id} cancelled")
                break

            except Exception as e:
                logger.exception(f"Worker {self.worker_id} error in main loop: {e}")
                # Continue running despite errors
                await asyncio.sleep(self.poll_interval)

        logger.info(f"Worker {self.worker_id} exited main loop")

    async def _process_job(self, job: Job):
        """Process a single job"""
        self._current_job = job

        logger.info(
            f"Worker {self.worker_id} processing job {job.id} "
            f"(type={job.job_type}, priority={job.priority})"
        )

        # Emit job started event
        if self.event_bus and job.chat_id:
            await self.event_bus.publish(
                EventType.TOOL_STARTED,
                job.chat_id,
                {
                    'job_id': job.id,
                    'job_type': job.job_type,
                    'worker_id': self.worker_id
                },
                trace_id=job.trace_id
            )

        try:
            # Get handler for job type
            handler = self.job_registry.get_handler(job.job_type)

            if handler is None:
                raise ValueError(f"No handler registered for job type: {job.job_type}")

            # Execute the job
            result = await handler.execute(job)

            # Mark as completed
            await self.job_repository.update_status(
                job.id,
                JobStatus.COMPLETED,
                result=result
            )

            # Emit completion event
            if self.event_bus and job.chat_id:
                await self.event_bus.publish(
                    EventType.TOOL_COMPLETED,
                    job.chat_id,
                    {
                        'job_id': job.id,
                        'job_type': job.job_type,
                        'result': str(result)[:200],  # Truncate for event
                        'worker_id': self.worker_id
                    },
                    trace_id=job.trace_id
                )

            logger.info(f"Job {job.id} completed successfully")

        except Exception as e:
            logger.exception(f"Job {job.id} failed: {e}")

            # Check if we should retry
            if job.retry_count < job.max_retries:
                # Increment retry count and requeue
                await self.job_repository.increment_retry(job.id)

                logger.info(
                    f"Job {job.id} will be retried "
                    f"({job.retry_count + 1}/{job.max_retries})"
                )

                # Emit retry event
                if self.event_bus and job.chat_id:
                    await self.event_bus.publish(
                        EventType.TOOL_PROGRESS,
                        job.chat_id,
                        {
                            'job_id': job.id,
                            'message': f"Retrying... ({job.retry_count + 1}/{job.max_retries})",
                            'error': str(e)
                        },
                        trace_id=job.trace_id
                    )
            else:
                # Max retries exceeded, mark as failed
                await self.job_repository.update_status(
                    job.id,
                    JobStatus.FAILED,
                    error=str(e)
                )

                # Emit failure event
                if self.event_bus and job.chat_id:
                    await self.event_bus.publish(
                        EventType.TOOL_FAILED,
                        job.chat_id,
                        {
                            'job_id': job.id,
                            'job_type': job.job_type,
                            'error': str(e),
                            'worker_id': self.worker_id
                        },
                        trace_id=job.trace_id
                    )

                logger.error(f"Job {job.id} failed after {job.max_retries} retries")

        finally:
            self._current_job = None

    def get_current_job(self) -> Optional[Job]:
        """Get currently processing job"""
        return self._current_job

    def is_running(self) -> bool:
        """Check if worker is running"""
        return self._running


# =============================================================================
# JOB WORKER POOL
# =============================================================================


class JobWorkerPool:
    """
    Pool of job workers.

    Manages multiple workers for concurrent job processing.
    """

    def __init__(
        self,
        job_repository: JobRepository,
        job_registry: JobRegistry,
        event_bus: Optional[EventBus] = None,
        num_workers: int = 4,
        poll_interval: float = 1.0
    ):
        """
        Initialize worker pool.

        Args:
            job_repository: Repository for job queue operations
            job_registry: Registry of job handlers
            event_bus: Optional event bus for status updates
            num_workers: Number of concurrent workers
            poll_interval: How often workers poll queue (seconds)
        """
        self.job_repository = job_repository
        self.job_registry = job_registry
        self.event_bus = event_bus
        self.num_workers = num_workers
        self.poll_interval = poll_interval

        self._workers: Dict[str, JobWorker] = {}
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None

        logger.info(f"JobWorkerPool initialized with {num_workers} workers")

    async def start(self):
        """Start all workers"""
        if self._running:
            logger.warning("Worker pool already running")
            return

        self._running = True

        # Create and start workers
        for i in range(self.num_workers):
            worker_id = f"worker-{i}-{uuid.uuid4().hex[:8]}"

            worker = JobWorker(
                worker_id=worker_id,
                job_repository=self.job_repository,
                job_registry=self.job_registry,
                event_bus=self.event_bus,
                poll_interval=self.poll_interval
            )

            self._workers[worker_id] = worker
            await worker.start()

        # Start cleanup task (requeues stale jobs)
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

        logger.info(f"Worker pool started with {len(self._workers)} workers")

    async def stop(self, timeout: float = 30.0):
        """Stop all workers gracefully"""
        if not self._running:
            return

        logger.info("Stopping worker pool...")

        self._running = False

        # Stop cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Stop all workers
        stop_tasks = [
            worker.stop(timeout=timeout)
            for worker in self._workers.values()
        ]

        await asyncio.gather(*stop_tasks, return_exceptions=True)

        logger.info("Worker pool stopped")

    async def _cleanup_loop(self):
        """Periodic cleanup task to requeue stale jobs"""
        while self._running:
            try:
                # Sleep for 5 minutes between cleanup runs
                await asyncio.sleep(300)

                if not self._running:
                    break

                # Requeue jobs that have been running too long (30 min default)
                requeued = await self.job_repository.requeue_stale_jobs(
                    timeout_minutes=30
                )

                if requeued > 0:
                    logger.warning(f"Requeued {requeued} stale jobs")

                # Cleanup old completed jobs (older than 24 hours)
                cleaned = await self.job_repository.cleanup_completed(
                    older_than_hours=24
                )

                if cleaned > 0:
                    logger.info(f"Cleaned up {cleaned} old completed jobs")

            except asyncio.CancelledError:
                break

            except Exception as e:
                logger.exception(f"Error in cleanup loop: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get worker pool statistics"""
        active_workers = sum(1 for w in self._workers.values() if w.is_running())
        busy_workers = sum(
            1 for w in self._workers.values()
            if w.get_current_job() is not None
        )

        return {
            'total_workers': len(self._workers),
            'active_workers': active_workers,
            'busy_workers': busy_workers,
            'idle_workers': active_workers - busy_workers
        }

    def is_running(self) -> bool:
        """Check if pool is running"""
        return self._running
