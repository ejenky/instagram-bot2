"""Simple job queue for batch processing.

Uses asyncio for concurrency control without external dependencies.
"""

import asyncio
import logging
import time
from typing import Callable, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Job:
    id: str
    func: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    status: str = 'pending'  # pending, running, completed, failed
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class JobQueue:
    """Async job queue with concurrency control."""

    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._jobs: dict[str, Job] = {}
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"job_{self._counter}"

    async def submit(self, func: Callable, *args, **kwargs) -> str:
        """Submit a job to the queue. Returns job ID."""
        job_id = self._next_id()
        job = Job(id=job_id, func=func, args=args, kwargs=kwargs)
        self._jobs[job_id] = job

        # Start processing in background
        asyncio.create_task(self._run_job(job))
        return job_id

    async def _run_job(self, job: Job):
        """Run a job with concurrency control."""
        async with self._semaphore:
            job.status = 'running'
            job.started_at = time.time()
            try:
                job.result = await job.func(*job.args, **job.kwargs)
                job.status = 'completed'
            except Exception as e:
                job.status = 'failed'
                job.error = str(e)
                logger.error(f"Job {job.id} failed: {e}")
            finally:
                job.completed_at = time.time()

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def get_status(self, job_id: str) -> str:
        job = self._jobs.get(job_id)
        return job.status if job else 'unknown'

    async def submit_batch(self, func: Callable, items: list, **kwargs) -> list[str]:
        """Submit multiple jobs for batch processing. Returns list of job IDs."""
        job_ids = []
        for item in items:
            job_id = await self.submit(func, item, **kwargs)
            job_ids.append(job_id)
        return job_ids

    async def wait_for_jobs(self, job_ids: list[str], callback=None) -> list[Job]:
        """Wait for all specified jobs to complete. Optional progress callback."""
        while True:
            all_done = True
            completed = 0
            for jid in job_ids:
                job = self._jobs.get(jid)
                if job and job.status in ('completed', 'failed'):
                    completed += 1
                else:
                    all_done = False

            if callback:
                await callback(completed, len(job_ids))

            if all_done:
                break
            await asyncio.sleep(0.5)

        return [self._jobs[jid] for jid in job_ids if jid in self._jobs]

    def cleanup(self, max_age: float = 3600):
        """Remove old completed/failed jobs."""
        now = time.time()
        to_remove = [
            jid for jid, job in self._jobs.items()
            if job.completed_at and (now - job.completed_at) > max_age
        ]
        for jid in to_remove:
            del self._jobs[jid]


# Global queue instance
job_queue = JobQueue(max_concurrent=3)
