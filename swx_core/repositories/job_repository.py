"""
Job Repository
--------------
Database operations for Job model.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlmodel import Session

from swx_core.models.job import Job, JobStatus


async def get_job_by_id(session: AsyncSession, job_id: UUID) -> Optional[Job]:
    """Get a job by its ID."""
    return await session.get(Job, job_id)


async def list_jobs(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    status: Optional[JobStatus] = None,
    job_type: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> List[Job]:
    """List jobs with optional filters."""
    stmt = select(Job)
    
    conditions = []
    if status:
        conditions.append(Job.status == status)
    if job_type:
        conditions.append(Job.job_type == job_type)
    if tags:
        # Filter by tags (JSONB contains)
        for tag in tags:
            conditions.append(Job.tags.contains([tag]))
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    stmt = stmt.order_by(Job.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def count_jobs(
    session: AsyncSession,
    status: Optional[JobStatus] = None,
    job_type: Optional[str] = None
) -> int:
    """Count jobs with optional filters."""
    from sqlalchemy import func
    
    stmt = select(func.count(Job.id))
    
    conditions = []
    if status:
        conditions.append(Job.status == status)
    if job_type:
        conditions.append(Job.job_type == job_type)
    
    if conditions:
        stmt = stmt.where(and_(*conditions))
    
    result = await session.execute(stmt)
    return result.scalar_one() or 0


async def get_job_stats(session: AsyncSession) -> dict:
    """Get job statistics."""
    from sqlalchemy import func, case
    
    stmt = select(
        func.count(Job.id).label("total"),
        func.sum(case((Job.status == JobStatus.PENDING, 1), else_=0)).label("pending"),
        func.sum(case((Job.status == JobStatus.QUEUED, 1), else_=0)).label("queued"),
        func.sum(case((Job.status == JobStatus.RUNNING, 1), else_=0)).label("running"),
        func.sum(case((Job.status == JobStatus.COMPLETED, 1), else_=0)).label("completed"),
        func.sum(case((Job.status == JobStatus.FAILED, 1), else_=0)).label("failed"),
        func.sum(case((Job.status == JobStatus.DEAD_LETTER, 1), else_=0)).label("dead_letter"),
    )
    
    result = await session.execute(stmt)
    row = result.first()
    
    return {
        "total": row.total or 0,
        "pending": row.pending or 0,
        "queued": row.queued or 0,
        "running": row.running or 0,
        "completed": row.completed or 0,
        "failed": row.failed or 0,
        "dead_letter": row.dead_letter or 0,
    }
