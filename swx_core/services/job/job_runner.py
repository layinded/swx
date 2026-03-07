"""
Job Runner
----------
Background worker that processes jobs with locking, retry, and dead-letter handling.

Rules:
- No double execution (locking)
- No infinite retries (max_attempts)
- Exponential backoff for retries
- Dead-letter queue for permanently failed jobs
"""

import asyncio
import uuid
import socket
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Callable, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update, text
from sqlmodel import Session

from swx_core.models.job import Job, JobStatus
from swx_core.database.db import AsyncSessionLocal
from swx_core.middleware.logging_middleware import logger
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome


# Job handler registry
_job_handlers: Dict[str, Callable[[AsyncSession, Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {}


def register_job_handler(
    job_type: str,
    handler: Callable[[AsyncSession, Dict[str, Any]], Awaitable[Dict[str, Any]]]
) -> None:
    """
    Register a handler for a specific job type.
    
    Args:
        job_type: The job type identifier
        handler: Async function that takes (session, payload) and returns result dict
    """
    _job_handlers[job_type] = handler
    logger.info(f"Registered job handler for type: {job_type}")


def get_worker_id() -> str:
    """Generate a unique worker identifier."""
    hostname = socket.gethostname()
    return f"{hostname}-{uuid.uuid4().hex[:8]}"


class JobRunner:
    """
    Background job runner with locking, retry, and dead-letter handling.
    
    Features:
    - Polls for pending/queued jobs
    - Locks jobs to prevent double execution
    - Retries with exponential backoff
    - Moves failed jobs to dead-letter queue
    """
    
    def __init__(
        self,
        worker_id: Optional[str] = None,
        poll_interval: int = 5,
        lock_timeout: int = 300,  # 5 minutes
        max_concurrent: int = 10
    ):
        self.worker_id = worker_id or get_worker_id()
        self.poll_interval = poll_interval
        self.lock_timeout = lock_timeout
        self.max_concurrent = max_concurrent
        self.running = False
        self.active_jobs: Dict[uuid.UUID, asyncio.Task] = {}
        logger.info(f"JobRunner initialized with worker_id: {self.worker_id}")
    
    async def start(self) -> None:
        """Start the job runner."""
        if self.running:
            logger.warning("JobRunner already running")
            return
        
        self.running = True
        logger.info(f"JobRunner started (worker_id: {self.worker_id})")
        
        # Start polling loop
        asyncio.create_task(self._poll_loop())
        
        # Start cleanup loop (release stale locks)
        asyncio.create_task(self._cleanup_loop())
    
    async def stop(self) -> None:
        """Stop the job runner."""
        self.running = False
        logger.info("JobRunner stopping...")
        
        # Wait for active jobs to complete (with timeout)
        if self.active_jobs:
            logger.info(f"Waiting for {len(self.active_jobs)} active jobs to complete...")
            await asyncio.wait_for(
                asyncio.gather(*self.active_jobs.values(), return_exceptions=True),
                timeout=30
            )
        
        logger.info("JobRunner stopped")
    
    async def _poll_loop(self) -> None:
        """Main polling loop for jobs."""
        while self.running:
            try:
                # Only poll if we have capacity
                if len(self.active_jobs) < self.max_concurrent:
                    await self._process_next_job()
                else:
                    await asyncio.sleep(1)  # Wait if at capacity
            except Exception as e:
                logger.error(f"Error in poll loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)
            
            await asyncio.sleep(self.poll_interval)
    
    async def _cleanup_loop(self) -> None:
        """Periodically clean up stale locks."""
        while self.running:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._release_stale_locks()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)
    
    async def _release_stale_locks(self) -> None:
        """Release locks that have timed out."""
        async with AsyncSessionLocal() as session:
            try:
                now = datetime.now(timezone.utc)
                cutoff = (now - timedelta(seconds=self.lock_timeout)).replace(tzinfo=None)
                stmt = (
                    update(Job)
                    .where(
                        and_(
                            Job.status == JobStatus.RUNNING.value,
                            Job.locked_at < cutoff
                        )
                    )
                    .values(
                        status=JobStatus.QUEUED.value,
                        locked_at=None,
                        locked_by=None
                    )
                )
                result = await session.execute(stmt)
                count = result.rowcount
                if count > 0:
                    await session.commit()
                    logger.info(f"Released {count} stale locks")
            except Exception as e:
                logger.error(f"Error releasing stale locks: {e}", exc_info=True)
                await session.rollback()
    
    async def _process_next_job(self) -> None:
        """Process the next available job."""
        async with AsyncSessionLocal() as session:
            try:
                # Find next job to process
                job = await self._acquire_job(session)
                if not job:
                    return
                
                # Process job in background
                task = asyncio.create_task(self._execute_job(job.id))
                self.active_jobs[job.id] = task
                
                # Clean up completed tasks
                task.add_done_callback(lambda t: self.active_jobs.pop(job.id, None))
                
            except Exception as e:
                logger.error(f"Error acquiring job: {e}", exc_info=True)
                await session.rollback()
    
    async def _acquire_job(self, session: AsyncSession) -> Optional[Job]:
        """
        Acquire and lock the next available job.
        
        Uses database-level locking to prevent double execution.
        """
        try:
            now = datetime.now(timezone.utc)
            # Use naive UTC for scheduled_at comparison to avoid asyncpg
            # "can't subtract offset-naive and offset-aware datetimes" with TIMESTAMP WITHOUT TZ.
            now_naive = now.replace(tzinfo=None)

            # Find next job: pending/queued, scheduled_at <= now, ordered by priority.
            # Use raw SQL for status filter so we send 'pending'/'queued' literals;
            # ORM enum binding sends enum names ('PENDING'/'QUEUED'), which violate
            # PostgreSQL jobstatus enum (lowercase values).
            stmt = (
                select(Job)
                .where(
                    and_(
                        text("job.status = ANY(ARRAY['pending','queued']::jobstatus[])"),
                        or_(
                            Job.scheduled_at.is_(None),
                            Job.scheduled_at <= now_naive
                        ),
                        Job.attempts < Job.max_attempts
                    )
                )
                .order_by(Job.priority.asc(), Job.created_at.asc())
                .limit(1)
                .with_for_update(skip_locked=True)  # Skip locked rows
            )
            
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            
            if not job:
                return None
            
            # Lock the job
            job.status = JobStatus.RUNNING
            job.locked_at = now
            job.locked_by = self.worker_id
            job.started_at = now
            job.attempts += 1
            
            session.add(job)
            await session.commit()
            await session.refresh(job)
            
            logger.info(f"Acquired job {job.id} (type: {job.job_type}, attempt: {job.attempts})")
            return job
            
        except Exception as e:
            logger.error(f"Error acquiring job: {e}", exc_info=True)
            await session.rollback()
            return None
    
    async def _execute_job(self, job_id: uuid.UUID) -> None:
        """Execute a job with error handling and retry logic."""
        async with AsyncSessionLocal() as session:
            try:
                # Get job
                job = await session.get(Job, job_id)
                if not job:
                    logger.error(f"Job {job_id} not found")
                    return
                
                # Get handler
                handler = _job_handlers.get(job.job_type)
                if not handler:
                    error_msg = f"No handler registered for job type: {job.job_type}"
                    logger.error(error_msg)
                    await self._mark_job_failed(session, job, error_msg)
                    return
                
                # Execute handler
                logger.info(f"Executing job {job.id} (type: {job.job_type}, attempt: {job.attempts})")
                try:
                    result = await handler(session, job.payload)
                    
                    # Mark as completed
                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.now(timezone.utc)
                    job.result = result
                    job.locked_at = None
                    job.locked_by = None
                    
                    session.add(job)
                    await session.commit()
                    
                    # Audit log
                    audit = get_audit_logger(session)
                    await audit.log_event(
                        action="job.completed",
                        actor_type=ActorType.SYSTEM,
                        actor_id=self.worker_id,
                        resource_type="job",
                        resource_id=str(job.id),
                        outcome=AuditOutcome.SUCCESS,
                        context={"job_type": job.job_type, "attempts": job.attempts}
                    )
                    
                    logger.info(f"Job {job.id} completed successfully")
                    
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Job {job.id} failed: {error_msg}", exc_info=True)
                    
                    # Check if should retry
                    if job.attempts < job.max_attempts:
                        # Retry with exponential backoff
                        backoff_seconds = 2 ** job.attempts  # 2, 4, 8, 16...
                        scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=backoff_seconds)
                        
                        job.status = JobStatus.QUEUED
                        job.scheduled_at = scheduled_at
                        job.last_error = {"error": error_msg, "attempt": job.attempts}
                        job.locked_at = None
                        job.locked_by = None
                        
                        session.add(job)
                        await session.commit()
                        
                        logger.info(f"Job {job.id} scheduled for retry in {backoff_seconds}s (attempt {job.attempts}/{job.max_attempts})")
                    else:
                        # Max attempts reached - move to dead letter
                        await self._mark_job_failed(session, job, error_msg)
                
            except Exception as e:
                logger.error(f"Error executing job {job_id}: {e}", exc_info=True)
                await session.rollback()
    
    async def _mark_job_failed(self, session: AsyncSession, job: Job, error_msg: str) -> None:
        """Mark a job as failed (dead letter)."""
        job.status = JobStatus.DEAD_LETTER
        job.completed_at = datetime.now(timezone.utc)
        job.last_error = {"error": error_msg, "attempt": job.attempts, "final": True}
        job.locked_at = None
        job.locked_by = None
        
        session.add(job)
        await session.commit()
        
        # Audit log
        audit = get_audit_logger(session)
        await audit.log_event(
            action="job.failed",
            actor_type=ActorType.SYSTEM,
            actor_id=self.worker_id,
            resource_type="job",
            resource_id=str(job.id),
            outcome=AuditOutcome.FAILURE,
            context={"job_type": job.job_type, "error": error_msg, "attempts": job.attempts}
        )
        
        logger.warning(f"Job {job.id} moved to dead-letter queue after {job.attempts} attempts")


# Global job runner instance
_job_runner: Optional[JobRunner] = None


def get_job_runner() -> JobRunner:
    """Get or create the global job runner instance."""
    global _job_runner
    if _job_runner is None:
        _job_runner = JobRunner()
    return _job_runner


async def start_job_runner() -> None:
    """Start the global job runner."""
    runner = get_job_runner()
    await runner.start()


async def stop_job_runner() -> None:
    """Stop the global job runner."""
    global _job_runner
    if _job_runner:
        await _job_runner.stop()
        _job_runner = None
