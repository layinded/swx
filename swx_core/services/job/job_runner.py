"""
Job Runner
----------
Background worker that processes jobs with locking, retry, and dead-letter handling.

Rules:
- No double execution (locking)
- No infinite retries (max_attempts)
- Exponential backoff for retries
- Dead-letter queue for permanently failed jobs
- Safe session management with proper cleanup
- Timeout protection for long-running jobs
"""

import asyncio
import uuid
import socket
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Callable, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, update, text
from swx_core.utils.time import utc_now

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

def _utc_now() -> datetime:
    """Get current UTC timezone-aware datetime."""
    return utc_now()

class JobRunner:
    """
    Background job runner with locking, retry, and dead-letter handling.
    
    Features:
    - Polls for pending/queued jobs
    - Locks jobs to prevent double execution
    - Retries with exponential backoff
    - Moves failed jobs to dead-letter queue
    - Timeout protection for job execution
    """
    
    def __init__(
        self,
        worker_id: Optional[str] = None,
        poll_interval: int = 5,
        lock_timeout: int = 300,  # 5 minutes
        max_concurrent: int = 10,
        execution_timeout: int = 3600  # 1 hour default timeout
    ):
        self.worker_id = worker_id or get_worker_id()
        self.poll_interval = poll_interval
        self.lock_timeout = lock_timeout
        self.max_concurrent = max_concurrent
        self.execution_timeout = execution_timeout
        self.running = False
        self._active_jobs_lock = asyncio.Lock()
        self._active_jobs: Dict[uuid.UUID, asyncio.Task] = {}
        logger.info(f"JobRunner initialized with worker_id: {self.worker_id}")
    
    @property
    def active_jobs(self) -> Dict[uuid.UUID, asyncio.Task]:
        """Thread-safe access to active jobs dict."""
        return self._active_jobs
    
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
        if self._active_jobs:
            logger.info(f"Waiting for {len(self._active_jobs)} active jobs to complete...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_jobs.values(), return_exceptions=True),
                    timeout=30
                )
            except asyncio.TimeoutError:
                logger.warning("Timed out waiting for active jobs to complete")
        
        logger.info("JobRunner stopped")
    
    async def _poll_loop(self) -> None:
        """Main polling loop for jobs."""
        while self.running:
            try:
                # Only poll if we have capacity
                if len(self._active_jobs) < self.max_concurrent:
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
                now = _utc_now()
                cutoff = now - timedelta(seconds=self.lock_timeout)
                
                stmt = (
                    update(Job)
                    .where(
                        and_(
                            Job.status == JobStatus.running.value,
                            Job.locked_at < cutoff
                        )
                    )
                    .values(
                        status=JobStatus.queued.value,
                        locked_at=None,
                        locked_by=None
                    )
                )
                result = await session.execute(stmt)
                count = result.rowcount
                if count > 0:
                    await session.commit()
                    logger.info(f"Released {count} stale locks")
                else:
                    await session.commit()
            except Exception as e:
                logger.error(f"Error releasing stale locks: {e}", exc_info=True)
                await session.rollback()
    
    async def _process_next_job(self) -> None:
        """Process the next available job."""
        try:
            job_id = await self._acquire_job()
            if not job_id:
                return
            
            # Process job in background
            task = asyncio.create_task(self._execute_job_with_timeout(job_id))
            
            async with self._active_jobs_lock:
                self._active_jobs[job_id] = task
            
            # Clean up completed tasks
            def cleanup_callback(t: asyncio.Task, jid: uuid.UUID = job_id) -> None:
                asyncio.create_task(self._remove_active_job(jid))
            
            task.add_done_callback(cleanup_callback)
            
        except Exception as e:
            logger.error(f"Error acquiring job: {e}", exc_info=True)
    
    async def _remove_active_job(self, job_id: uuid.UUID) -> None:
        """Thread-safe removal of job from active jobs dict."""
        async with self._active_jobs_lock:
            self._active_jobs.pop(job_id, None)
    
    async def _execute_job_with_timeout(self, job_id: uuid.UUID) -> None:
        """Execute a job with timeout protection."""
        try:
            await asyncio.wait_for(
                self._execute_job(job_id),
                timeout=self.execution_timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Job {job_id} timed out after {self.execution_timeout}s")
            await self._mark_job_timeout(job_id)
    
    async def _acquire_job(self) -> Optional[uuid.UUID]:
        """
        Acquire and lock the next available job.
        
        Uses database-level locking to prevent double execution.
        Returns job_id only (not the job object) to avoid session attachment issues.
        """
        async with AsyncSessionLocal() as session:
            try:
                now_naive = _utc_now()

                # Find next job: pending/queued, scheduled_at <= now, ordered by priority.
                # Use raw SQL for status filter so we send 'pending'/'queued' literals;
                # ORM enum binding sends enum names ('PENDING'/'QUEUED'), which violate
                # PostgreSQL jobstatus enum (lowercase values).
                stmt = (
                    select(Job)
                    .where(
                        and_(
                            text("swx_job.status = ANY(ARRAY['pending','queued']::jobstatus[])"),
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
                
                # Store job_id before any operations
                job_id = job.id
                
                # Lock the job
                job.status = JobStatus.running
                job.locked_at = now_naive
                job.locked_by = self.worker_id
                job.started_at = now_naive
                job.attempts += 1
                
                session.add(job)
                await session.commit()
                
                logger.info(f"Acquired job {job_id} (type: {job.job_type}, attempt: {job.attempts})")
                return job_id
                
            except Exception as e:
                logger.error(f"Error acquiring job: {e}", exc_info=True)
                await session.rollback()
                return None
    
    async def _execute_job(self, job_id: uuid.UUID) -> None:
        """Execute a job with error handling and retry logic."""
        async with AsyncSessionLocal() as session:
            job: Optional[Job] = None
            try:
                # Get fresh copy of job from database
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
                
                result = await handler(session, job.payload)
                
                # Validate handler result
                if result is not None and not isinstance(result, dict):
                    logger.warning(f"Job {job.id} handler returned non-dict result: {type(result)}")
                    result = {"result": str(result)}
                
                # Mark as completed
                job.status = JobStatus.completed
                job.completed_at = _utc_now()
                job.result = result if result else {}
                job.locked_at = None
                job.locked_by = None
                
                session.add(job)
                await session.commit()
                
                # Audit log (in separate try to not affect job completion)
                try:
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
                except Exception as audit_error:
                    logger.warning(f"Failed to log audit for job {job.id}: {audit_error}")
                
                logger.info(f"Job {job.id} completed successfully")
                
            except asyncio.CancelledError:
                # Job was cancelled, don't retry
                logger.warning(f"Job {job_id} was cancelled")
                if job:
                    try:
                        job.status = JobStatus.cancelled
                        job.locked_at = None
                        job.locked_by = None
                        session.add(job)
                        await session.commit()
                    except Exception:
                        await session.rollback()
                raise
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Job {job_id} failed: {error_msg}", exc_info=True)
                
                # Refresh job from DB if we have it
                if job:
                    try:
                        await session.refresh(job)
                    except Exception:
                        # Job might not be in session, get fresh copy
                        job = await session.get(Job, job_id)
                
                if not job:
                    logger.error(f"Job {job_id} could not be retrieved for retry handling")
                    return
                
                try:
                    # Check if should retry
                    if job.attempts < job.max_attempts:
                        # Retry with exponential backoff
                        backoff_seconds = 2 ** job.attempts  # 2, 4, 8, 16...
                        scheduled_at = _utc_now() + timedelta(seconds=backoff_seconds)
                        
                        job.status = JobStatus.queued
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
                        
                except Exception as retry_error:
                    logger.error(f"Error handling job {job_id} retry: {retry_error}", exc_info=True)
                    await session.rollback()
    
    async def _mark_job_timeout(self, job_id: uuid.UUID) -> None:
        """Mark a job as timed out."""
        async with AsyncSessionLocal() as session:
            try:
                job = await session.get(Job, job_id)
                if not job:
                    return
                
                error_msg = f"Job timed out after {self.execution_timeout} seconds"
                
                # Check if should retry
                if job.attempts < job.max_attempts:
                    backoff_seconds = 2 ** job.attempts
                    scheduled_at = _utc_now() + timedelta(seconds=backoff_seconds)
                    
                    job.status = JobStatus.queued
                    job.scheduled_at = scheduled_at
                    job.last_error = {"error": error_msg, "attempt": job.attempts}
                    job.locked_at = None
                    job.locked_by = None
                    
                    session.add(job)
                    await session.commit()
                    logger.info(f"Job {job_id} timeout: scheduled for retry")
                else:
                    await self._mark_job_failed(session, job, error_msg)
                    
            except Exception as e:
                logger.error(f"Error marking job {job_id} as timed out: {e}", exc_info=True)
                await session.rollback()
    
    async def _mark_job_failed(self, session: AsyncSession, job: Job, error_msg: str) -> None:
        """Mark a job as failed (dead letter)."""
        try:
            job.status = JobStatus.dead_letter
            job.completed_at = _utc_now()
            job.last_error = {"error": error_msg, "attempt": job.attempts, "final": True}
            job.locked_at = None
            job.locked_by = None
            
            session.add(job)
            await session.commit()
            
            # Audit log
            try:
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
            except Exception as audit_error:
                logger.warning(f"Failed to log audit for failed job {job.id}: {audit_error}")
            
            logger.warning(f"Job {job.id} moved to dead-letter queue after {job.attempts} attempts")
            
        except Exception as e:
            logger.error(f"Error marking job {job.id} as failed: {e}", exc_info=True)
            await session.rollback()
            raise

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