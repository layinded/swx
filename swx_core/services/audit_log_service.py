"""
Audit Log Service
------------------
This module provides business logic for audit log retrieval.
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from swx_core.models.audit_log import AuditLog, AuditLogsPublic
from swx_core.repositories import audit_log_repository


async def list_audit_logs_service(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    actor_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    outcome: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> AuditLogsPublic:
    """
    Retrieves audit logs with filtering and returns a public schema.
    """
    logs = await audit_log_repository.get_all_audit_logs(
        session, skip, limit, actor_type, actor_id, action,
        resource_type, resource_id, outcome, start_date, end_date
    )
    count = await audit_log_repository.get_audit_log_count(
        session, actor_type, actor_id, action,
        resource_type, resource_id, outcome, start_date, end_date
    )
    return AuditLogsPublic(data=logs, count=count)


async def get_audit_log_service(session: AsyncSession, audit_log_id: UUID) -> AuditLog:
    """
    Retrieves a single audit log by ID.
    """
    log = await audit_log_repository.get_audit_log_by_id(session, audit_log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return log
