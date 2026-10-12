"""
Control FastAPI Project - Background Jobs
Manual async task queue for benchmarking against SwX.
"""

import asyncio
import uuid
from typing import Callable, Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Job status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(Enum):
    """Job priority (lower = higher priority)."""
    CRITICAL = 0
    HIGH = 10
    NORMAL = 50
    LOW = 100


@dataclass
class Job:
    """Job definition."""
    id: str
    name: str
    handler: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus = JobStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class JobQueue:
    """Simple async job queue."""
    
    def __init__(self):
        self._queue: asyncio.PriorityQueue = None
        self._jobs: Dict[str, Job] = {}
        self._results: Dict[str, asyncio.Future] = {}
        self._running = False
        self._workers: List[asyncio.Task] = []
        self._num_workers = 4
    
    def _get_queue(self) -> asyncio.PriorityQueue:
        if self._queue is None:
            self._queue = asyncio.PriorityQueue()
        return self._queue
    
    async def enqueue(
        self,
        name: str,
        handler: Callable,
        *args,
        priority: JobPriority = JobPriority.NORMAL,
        max_attempts: int = 3,
        **kwargs
    ) -> str:
        """Enqueue a job."""
        job_id = str(uuid.uuid4())
        
        job = Job(
            id=job_id,
            name=name,
            handler=handler,
            args=args,
            kwargs=kwargs,
            priority=priority,
            max_attempts=max_attempts
        )
        
        self._jobs[job_id] = job
        
        # Create future for result
        future = asyncio.get_event_loop().create_future()
        self._results[job_id] = future
        
        # Add to queue with priority
        await self._get_queue().put((priority.value, job_id))
        
        logger.info(f"Enqueued job {job_id}: {name}")
        
        return job_id
    
    async def start(self) -> None:
        """Start job queue workers."""
        if self._running:
            return
        
        self._running = True
        
        for i in range(self._num_workers):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)
        
        logger.info(f"Started {self._num_workers} job workers")
    
    async def stop(self) -> None:
        """Stop job queue workers."""
        self._running = False
        
        # Wait for queue to drain
        await self._get_queue().join()
        
        # Cancel workers
        for worker in self._workers:
            worker.cancel()
        
        self._workers.clear()
        logger.info("Stopped job queue workers")
    
    async def _worker(self, worker_id: int) -> None:
        """Worker coroutine."""
        logger.info(f"Worker {worker_id} started")
        
        while self._running:
            try:
                # Get job from queue
                priority, job_id = await asyncio.wait_for(
                    self._get_queue().get(),
                    timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            
            job = self._jobs.get(job_id)
            if not job:
                self._get_queue().task_done()
                continue
            
            # Execute job
            await self._execute_job(job)
            
            self._get_queue().task_done()
    
    async def _execute_job(self, job: Job) -> None:
        """Execute a job."""
        job.status = JobStatus.RUNNING
        job.started_at = datetime.now()
        job.attempts += 1
        
        logger.info(f"Executing job {job.id}: {job.name} (attempt {job.attempts})")
        
        try:
            # Execute handler
            if asyncio.iscoroutinefunction(job.handler):
                result = await job.handler(*job.args, **job.kwargs)
            else:
                result = job.handler(*job.args, **job.kwargs)
            
            job.status = JobStatus.COMPLETED
            job.result = result
            job.completed_at = datetime.now()
            
            # Resolve future
            future = self._results.get(job.id)
            if future and not future.done():
                future.set_result(result)
            
            logger.info(f"Job {job.id} completed successfully")
            
        except Exception as e:
            job.error = str(e)
            
            if job.attempts < job.max_attempts:
                # Re-queue for retry
                job.status = JobStatus.PENDING
                await self._get_queue().put((job.priority.value, job.id))
                logger.warning(f"Job {job.id} failed, retrying (attempt {job.attempts})")
            else:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now()
                
                # Reject future
                future = self._results.get(job.id)
                if future and not future.done():
                    future.set_exception(e)
                
                logger.error(f"Job {job.id} failed after {job.attempts} attempts: {e}")
    
    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return self._jobs.get(job_id)
    
    async def wait_for_result(self, job_id: str, timeout: float = 30.0) -> Any:
        """Wait for job result."""
        future = self._results.get(job_id)
        if not future:
            raise ValueError(f"Job {job_id} not found")
        
        return await asyncio.wait_for(future, timeout=timeout)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending job."""
        job = self._jobs.get(job_id)
        if not job or job.status != JobStatus.PENDING:
            return False
        
        job.status = JobStatus.CANCELLED
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        stats = {
            "total": len(self._jobs),
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }
        
        for job in self._jobs.values():
            stats[job.status.value] += 1
        
        return stats


# Global job queue
job_queue = JobQueue()


# Convenience functions
async def dispatch_job(
    name: str,
    handler: Callable,
    *args,
    priority: JobPriority = JobPriority.NORMAL,
    **kwargs
) -> str:
    """Dispatch a job to the queue."""
    return await job_queue.enqueue(name, handler, *args, priority=priority, **kwargs)


def schedule_job(
    delay: float,
    name: str,
    handler: Callable,
    *args,
    **kwargs
) -> str:
    """Schedule a job to run after delay."""
    async def delayed():
        await asyncio.sleep(delay)
        return await dispatch_job(name, handler, *args, **kwargs)
    
    return asyncio.create_task(delayed())
