"""
Job Dispatcher
--------------
API for enqueueing jobs.

Usage:
    from swx_core.services.job.job_dispatcher import enqueue_job
    
    await enqueue_job(
        job_type="billing.sync",
        payload={"account_id": "123"},
        priority=50
    )
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.job import Job, JobStatus, JobCreate
from swx_core.database.db import AsyncSessionLocal
from swx_core.middleware.logging_middleware import logger
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome


async def enqueue_job(
    job_type: str,
    payload: Dict[str, Any],
    scheduled_at: Optional[datetime] = None,
    max_attempts: int = 3,
    priority: int = 100,
    tags: Optional[list[str]] = None,
    session: Optional[AsyncSession] = None
) -> Job:
    """
    Enqueue a new job for background processing.
    
    Args:
        job_type: Type identifier for the job
        payload: Job data (must be JSON-serializable)
        scheduled_at: When to execute (None = immediate)
        max_attempts: Maximum retry attempts (default: 3)
        priority: Lower = higher priority (default: 100)
        tags: Optional tags for filtering
        session: Optional database session (creates new if not provided)
    
    Returns:
        Created Job instance
    
    Example:
        ```python
        job = await enqueue_job(
            job_type="billing.sync",
            payload={"account_id": "123"},
            priority=50
        )
        ```
    """
    should_commit = session is None
    
    if session is None:
        session = AsyncSessionLocal()
    
    try:
        # Create job
        job = Job(
            id=uuid.uuid4(),
            job_type=job_type,
            payload=payload,
            status=JobStatus.PENDING if scheduled_at is None else JobStatus.QUEUED,
            scheduled_at=scheduled_at,
            max_attempts=max_attempts,
            priority=priority,
            tags=tags or [],
            attempts=0
        )
        
        session.add(job)
        
        if should_commit:
            await session.commit()
            await session.refresh(job)
        
        # Audit log
        audit = get_audit_logger(session)
        await audit.log_event(
            action="job.enqueued",
            actor_type=ActorType.SYSTEM,
            actor_id="system",
            resource_type="job",
            resource_id=str(job.id),
            outcome=AuditOutcome.SUCCESS,
            context={
                "job_type": job_type,
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
                "priority": priority
            }
        )
        
        if should_commit:
            await session.commit()
        
        logger.info(f"Job enqueued: {job.id} (type: {job_type}, priority: {priority})")
        return job
        
    except Exception as e:
        logger.error(f"Error enqueueing job: {e}", exc_info=True)
        if should_commit:
            await session.rollback()
        raise


async def enqueue_job_delayed(
    job_type: str,
    payload: Dict[str, Any],
    delay_seconds: int,
    max_attempts: int = 3,
    priority: int = 100,
    tags: Optional[list[str]] = None
) -> Job:
    """
    Enqueue a job to run after a delay.
    
    Args:
        job_type: Type identifier for the job
        payload: Job data
        delay_seconds: Seconds to wait before execution
        max_attempts: Maximum retry attempts
        priority: Lower = higher priority
        tags: Optional tags
    
    Returns:
        Created Job instance
    """
    scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    return await enqueue_job(
        job_type=job_type,
        payload=payload,
        scheduled_at=scheduled_at,
        max_attempts=max_attempts,
        priority=priority,
        tags=tags
    )


async def cancel_job(job_id: uuid.UUID, session: Optional[AsyncSession] = None) -> bool:
    """
    Cancel a pending or queued job.
    
    Args:
        job_id: Job ID to cancel
        session: Optional database session
    
    Returns:
        True if cancelled, False if not found or already running/completed
    """
    should_commit = session is None
    
    if session is None:
        session = AsyncSessionLocal()
    
    try:
        job = await session.get(Job, job_id)
        if not job:
            return False
        
        # Only cancel if not already running/completed
        if job.status in (JobStatus.PENDING, JobStatus.QUEUED):
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now(timezone.utc)
            session.add(job)
            
            # Audit log
            audit = get_audit_logger(session)
            await audit.log_event(
                action="job.cancelled",
                actor_type=ActorType.SYSTEM,
                actor_id="system",
                resource_type="job",
                resource_id=str(job.id),
                outcome=AuditOutcome.SUCCESS,
                context={"job_type": job.job_type}
            )
            
            if should_commit:
                await session.commit()
            
            logger.info(f"Job {job_id} cancelled")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
        if should_commit:
            await session.rollback()
        return False
