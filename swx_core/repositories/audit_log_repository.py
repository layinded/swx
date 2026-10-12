"""
Audit Log Repository
---------------------
This module provides CRUD operations for audit logs.
"""

from typing import List, Optional, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func, desc

from swx_core.models.audit_log import AuditLog


async def get_all_audit_logs(
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
) -> List[AuditLog]:
    """
    Retrieve all audit logs with filtering and pagination.
    """
    statement = select(AuditLog)
    
    if actor_type:
        statement = statement.where(AuditLog.actor_type == actor_type)
    if actor_id:
        statement = statement.where(AuditLog.actor_id == actor_id)
    if action:
        statement = statement.where(AuditLog.action == action)
    if resource_type:
        statement = statement.where(AuditLog.resource_type == resource_type)
    if resource_id:
        statement = statement.where(AuditLog.resource_id == resource_id)
    if outcome:
        statement = statement.where(AuditLog.outcome == outcome)
    if start_date:
        statement = statement.where(AuditLog.timestamp >= start_date)
    if end_date:
        statement = statement.where(AuditLog.timestamp <= end_date)
        
    statement = statement.order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_audit_log_count(
    session: AsyncSession,
    actor_type: Optional[str] = None,
    actor_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    outcome: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> int:
    """
    Get the total count of audit logs matching the filters.
    """
    statement = select(func.count()).select_from(AuditLog)
    
    if actor_type:
        statement = statement.where(AuditLog.actor_type == actor_type)
    if actor_id:
        statement = statement.where(AuditLog.actor_id == actor_id)
    if action:
        statement = statement.where(AuditLog.action == action)
    if resource_type:
        statement = statement.where(AuditLog.resource_type == resource_type)
    if resource_id:
        statement = statement.where(AuditLog.resource_id == resource_id)
    if outcome:
        statement = statement.where(AuditLog.outcome == outcome)
    if start_date:
        statement = statement.where(AuditLog.timestamp >= start_date)
    if end_date:
        statement = statement.where(AuditLog.timestamp <= end_date)
        
    result = await session.execute(statement)
    return result.scalar()


async def get_audit_log_by_id(session: AsyncSession, audit_log_id: UUID) -> Optional[AuditLog]:
    """
    Retrieve a specific audit log by ID.
    """
    return await session.get(AuditLog, audit_log_id)


async def get_audit_stats(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> dict[str, Any]:
    """Aggregate audit log statistics grouped by action and outcome."""
    base = select(
        AuditLog.action,
        AuditLog.outcome,
        func.count().label("count"),
    ).group_by(AuditLog.action, AuditLog.outcome)

    if start_date:
        base = base.where(AuditLog.timestamp >= start_date)
    if end_date:
        base = base.where(AuditLog.timestamp <= end_date)

    result = await session.execute(base)
    rows = result.all()

    by_action: dict[str, dict[str, int]] = {}
    total = 0
    for action, outcome, count in rows:
        if action not in by_action:
            by_action[action] = {}
        by_action[action][outcome] = count
        total += count

    total_by_outcome: dict[str, int] = {}
    for action, outcome, count in rows:
        total_by_outcome[outcome] = total_by_outcome.get(outcome, 0) + count

    return {
        "total_events": total,
        "by_action": by_action,
        "by_outcome": total_by_outcome,
    }


async def get_audit_logs_for_export(
    session: AsyncSession,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    actor_type: Optional[str] = None,
    action: Optional[str] = None,
    outcome: Optional[str] = None,
) -> List[AuditLog]:
    """Retrieve all matching audit logs for CSV export (no pagination limit)."""
    statement = select(AuditLog).order_by(desc(AuditLog.timestamp))

    if start_date:
        statement = statement.where(AuditLog.timestamp >= start_date)
    if end_date:
        statement = statement.where(AuditLog.timestamp <= end_date)
    if actor_type:
        statement = statement.where(AuditLog.actor_type == actor_type)
    if action:
        statement = statement.where(AuditLog.action == action)
    if outcome:
        statement = statement.where(AuditLog.outcome == outcome)

    result = await session.execute(statement)
    return list(result.scalars().all())
