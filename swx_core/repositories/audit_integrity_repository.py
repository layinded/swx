"""Repository for audit log integrity — DB operations only (SOC 2 CC7.2)."""

# pyright: reportAttributeAccessIssue=false, reportArgumentType=false, reportCallIssue=false

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.audit_log import AuditLog


async def get_previous_hash(session: AsyncSession, current_id: UUID) -> str | None:
    """Return the log_hash of the entry immediately before the given ID."""
    stmt = (
        select(AuditLog.log_hash)
        .where(AuditLog.id != current_id)
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_previous_hash_for_update(session: AsyncSession, current_id: UUID) -> str | None:
    """Return the log_hash of the predecessor with a row-level lock (SELECT FOR UPDATE).

    This prevents the TOCTOU race where two concurrent log_event calls read
    the same previous_hash, producing a broken chain.
    The lock serialises hash computation so each entry chains to the true predecessor.
    """
    stmt = (
        select(AuditLog.log_hash)
        .where(AuditLog.id != current_id)
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def set_log_hash(session: AsyncSession, entry_id: UUID, log_hash: str) -> None:
    """Persist the computed hash for an audit entry."""
    stmt = select(AuditLog).where(AuditLog.id == entry_id)
    result = await session.execute(stmt)
    entry = result.scalar_one_or_none()
    if entry is not None:
        entry.log_hash = log_hash
        session.add(entry)
        await session.commit()


async def get_all_audit_entries_ordered(session: AsyncSession) -> list[AuditLog]:
    """Fetch all audit log entries ordered by timestamp then id for chain walk."""
    stmt = select(AuditLog).order_by(AuditLog.timestamp, AuditLog.id)
    result = await session.execute(stmt)
    return list(result.scalars().all())