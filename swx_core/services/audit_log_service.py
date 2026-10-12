"""
Audit Log Service
------------------
This module provides business logic for audit log retrieval,
statistics aggregation, and CSV export.
"""

import csv
import io
from typing import Any, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from swx_core.models.audit_log import AuditLog, AuditLogPublic, AuditLogsPublic
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


async def get_audit_log_service(session: AsyncSession, audit_log_id: UUID) -> AuditLogPublic:
    """
    Retrieves a single audit log by ID and returns the public schema.
    """
    log = await audit_log_repository.get_audit_log_by_id(session, audit_log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return AuditLogPublic.model_validate(log)


async def get_audit_stats_service(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict[str, Any]:
    """Aggregate audit log statistics grouped by action and outcome."""
    return await audit_log_repository.get_audit_stats(session, start_date, end_date)


async def export_audit_logs_service(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    actor_type: Optional[str] = None,
    action: Optional[str] = None,
    outcome: Optional[str] = None,
) -> str:
    """Export matching audit logs as CSV string."""
    logs = await audit_log_repository.get_audit_logs_for_export(
        session, start_date, end_date, actor_type, action, outcome,
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "id", "timestamp", "actor_type", "actor_id", "action",
        "resource_type", "resource_id", "outcome", "severity",
        "data_classification", "access_result", "ip_address",
        "masked_ip", "user_agent", "request_id",
    ])
    for log in logs:
        writer.writerow([
            str(log.id),
            log.timestamp.isoformat() if log.timestamp else "",
            log.actor_type,
            log.actor_id or "",
            log.action,
            log.resource_type or "",
            log.resource_id or "",
            log.outcome,
            log.severity or "",
            log.data_classification or "",
            log.access_result or "",
            log.ip_address or "",
            log.masked_ip or "",
            log.user_agent or "",
            log.request_id or "",
        ])
    return output.getvalue()
