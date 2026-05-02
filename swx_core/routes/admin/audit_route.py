"""
Audit Log Routes
-----------------
This module defines API routes for viewing audit logs (Admin only).
"""

from typing import Any, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, Query

from swx_core.database.db import SessionDep
from swx_core.models.audit_log import AuditLogsPublic, AuditLogPublic
from swx_core.auth.admin.dependencies import get_current_admin_user, AdminUserDep
from swx_core.controllers import audit_log_controller

router = APIRouter(
    prefix="/admin/audit",
    tags=["admin-audit"],
    dependencies=[Depends(get_current_admin_user)],
)


@router.get("/", response_model=AuditLogsPublic)
async def list_audit_logs(
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    actor_type: Optional[str] = Query(None, description="Filter by actor type (system|admin|user)"),
    actor_id: Optional[str] = Query(None, description="Filter by actor ID"),
    action: Optional[str] = Query(None, description="Filter by action name"),
    resource_type: Optional[str] = Query(None, description="Filter by resource type"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
    outcome: Optional[str] = Query(None, description="Filter by outcome (success|failure)"),
    start_date: Optional[datetime] = Query(None, description="Filter by start timestamp (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="Filter by end timestamp (ISO format)"),
) -> Any:
    """
    Retrieve audit logs with filtering and pagination. (Admin only)
    """
    return await audit_log_controller.list_audit_logs_controller(
        session, skip, limit, actor_type, actor_id, action,
        resource_type, resource_id, outcome, start_date, end_date
    )


@router.get("/{audit_log_id}", response_model=AuditLogPublic)
async def get_audit_log(
    session: SessionDep,
    audit_log_id: UUID,
) -> Any:
    """
    Retrieve a specific audit log by ID. (Admin only)
    """
    return await audit_log_controller.get_audit_log_controller(session, audit_log_id)
