"""
Job Service
-----------
Business logic for Job management.
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from swx_core.models.job import Job, JobStatus
from swx_core.repositories import job_repository


async def list_jobs_service(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    status: Optional[JobStatus] = None,
    job_type: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> List[Job]:
    """List jobs with optional filters."""
    return await job_repository.list_jobs(
        session, skip, limit, status, job_type, tags
    )


async def get_job_service(session: AsyncSession, job_id: UUID) -> Job:
    """Get a job by ID."""
    job = await job_repository.get_job_by_id(session, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found"
        )
    return job


async def get_job_stats_service(session: AsyncSession) -> dict:
    """Get job statistics."""
    return await job_repository.get_job_stats(session)


async def retry_job_service(session: AsyncSession, job_id: UUID) -> Job:
    """Retry a failed or dead-letter job."""
    job = await job_repository.get_job_by_id(session, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found"
        )
    
    if job.status not in (JobStatus.FAILED, JobStatus.DEAD_LETTER):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry job with status '{job.status}'"
        )
    
    # Reset job for retry
    job.status = JobStatus.QUEUED
    job.attempts = 0
    job.scheduled_at = None
    job.locked_at = None
    job.locked_by = None
    job.last_error = None
    
    session.add(job)
    await session.commit()
    await session.refresh(job)
    
    return job
