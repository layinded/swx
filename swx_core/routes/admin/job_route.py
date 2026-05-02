"""
Job Management Routes
--------------------
Admin-only APIs for job visibility and management.
"""

from typing import List, Optional, Any
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Request

from swx_core.database.db import SessionDep
from swx_core.models.job import Job, JobStatus, JobPublic
from swx_core.models.common import Message
from swx_core.auth.admin.dependencies import get_current_admin_user, AdminUserDep
from swx_core.controllers import job_controller
from swx_core.services.audit_logger import get_audit_logger, ActorType, AuditOutcome

router = APIRouter(
    prefix="/admin/job",
    tags=["admin-job"],
    dependencies=[Depends(get_current_admin_user)],
)

@router.get("/", response_model=List[JobPublic])
async def list_jobs(
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    status: Optional[JobStatus] = Query(None),
    job_type: Optional[str] = Query(None),
    tags: Optional[List[str]] = Query(None),
) -> Any:
    """List jobs with optional filters."""
    return await job_controller.list_jobs_controller(
        session, skip, limit, status, job_type, tags
    )


@router.get("/stats", response_model=dict)
async def get_job_stats(session: SessionDep) -> Any:
    """Get job statistics."""
    return await job_controller.get_job_stats_controller(session)


@router.get("/{job_id}", response_model=JobPublic)
async def get_job(
    job_id: UUID,
    session: SessionDep,
    current_admin: AdminUserDep,
) -> Any:
    """Get a job by ID."""
    return await job_controller.get_job_controller(session, job_id)


@router.post("/{job_id}/retry", response_model=JobPublic)
async def retry_job(
    job_id: UUID,
    session: SessionDep,
    current_admin: AdminUserDep,
    request: Request,
) -> Any:
    """Retry a failed or dead-letter job."""
    audit = get_audit_logger(session)
    try:
        job = await job_controller.retry_job_controller(session, job_id)
        await audit.log_event(
            action="job.retry",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="job",
            resource_id=str(job_id),
            outcome=AuditOutcome.SUCCESS,
            context={"job_type": job.job_type},
            request=request
        )
        return job
    except Exception as e:
        await audit.log_event(
            action="job.retry",
            actor_type=ActorType.ADMIN,
            actor_id=str(current_admin.id),
            resource_type="job",
            resource_id=str(job_id),
            outcome=AuditOutcome.FAILURE,
            context={"error": str(e)},
            request=request
        )
        raise
