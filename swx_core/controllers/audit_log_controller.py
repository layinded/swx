"""
Audit Log Controller
---------------------
This module serves as the controller layer for audit log endpoints.
"""

from typing import Any, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.audit_log import AuditLogsPublic, AuditLogPublic
from swx_core.services import audit_log_service


async def list_audit_logs_controller(
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
    Controller for listing audit logs.
    """
    return await audit_log_service.list_audit_logs_service(
        session, skip, limit, actor_type, actor_id, action,
        resource_type, resource_id, outcome, start_date, end_date
    )


async def get_audit_log_controller(session: AsyncSession, audit_log_id: UUID) -> AuditLogPublic:
    """
    Controller for retrieving a single audit log.
    """
    return await audit_log_service.get_audit_log_service(session, audit_log_id)


async def get_audit_stats_controller(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict[str, Any]:
    """Controller for retrieving aggregated audit log statistics."""
    return await audit_log_service.get_audit_stats_service(session, start_date, end_date)


async def export_audit_logs_controller(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    actor_type: Optional[str] = None,
    action: Optional[str] = None,
    outcome: Optional[str] = None,
) -> str:
    """Controller for exporting audit logs as CSV."""
    return await audit_log_service.export_audit_logs_service(
        session, start_date, end_date, actor_type, action, outcome,
    )
