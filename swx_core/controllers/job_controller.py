"""
Job Controller
-------------
Controller layer for Job management operations.
"""

from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.job import Job, JobStatus
from swx_core.services import job_service


async def list_jobs_controller(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    status: Optional[JobStatus] = None,
    job_type: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> List[Job]:
    """List jobs with optional filters."""
    return await job_service.list_jobs_service(
        session, skip, limit, status, job_type, tags
    )


async def get_job_controller(session: AsyncSession, job_id: UUID) -> Job:
    """Get a job by ID."""
    return await job_service.get_job_service(session, job_id)


async def get_job_stats_controller(session: AsyncSession) -> dict:
    """Get job statistics."""
    return await job_service.get_job_stats_service(session)


async def retry_job_controller(session: AsyncSession, job_id: UUID) -> Job:
    """Retry a failed or dead-letter job."""
    return await job_service.retry_job_service(session, job_id)
