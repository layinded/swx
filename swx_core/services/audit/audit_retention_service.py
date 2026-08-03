"""Audit Log Retention Service
------------------------------
Batch-delete (or anonymize) audit rows older than
``SWX_AUDIT_RETENTION_DAYS``.  When that setting is configured, the
nightly background job calls ``run_retention()`` automatically.

Usage::

    from swx_core.services.audit.audit_retention_service import run_retention

    result = await run_retention(session)
    # {"deleted": 1234, "anonymized": 0, "cutoff": "2025-01-01T00:00:00Z"}
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.utils.time import utc_now

logger = logging.getLogger(__name__)


async def run_retention(session: AsyncSession, *, dry_run: bool = False) -> dict[str, Any]:
    """Execute audit log retention based on ``SWX_AUDIT_RETENTION_DAYS``.

    If the setting is ``None`` or ``0``, retention is disabled and the
    function returns immediately with an empty result.

    Args:
        session: Async DB session.
        dry_run: If ``True``, compute the cutoff but do not execute deletes.

    Returns:
        A dict with ``deleted``, ``anonymized``, and ``cutoff`` keys.
    """
    retention_days = settings.SWX_AUDIT_RETENTION_DAYS
    if not retention_days:
        logger.debug("Audit retention disabled (SWX_AUDIT_RETENTION_DAYS not set)")
        return {"deleted": 0, "anonymized": 0, "cutoff": None}

    cutoff = utc_now() - timedelta(days=retention_days)
    logger.info("Audit retention: cutoff=%s, dry_run=%s", cutoff.isoformat(), dry_run)

    if dry_run:
        from sqlalchemy import func, select
        from swx_core.models.audit_log import AuditLog
        count_result = await session.execute(select(func.count()).select_from(AuditLog).where(AuditLog.timestamp < cutoff))
        count = count_result.scalar() or 0
        return {"deleted": 0, "anonymized": 0, "cutoff": cutoff.isoformat(), "eligible": count}

    # Use batch delete for efficiency on large tables
    deleted = await _batch_delete_before(session, cutoff)
    logger.info("Audit retention complete: deleted=%d", deleted)

    return {
        "deleted": deleted,
        "anonymized": 0,
        "cutoff": cutoff.isoformat(),
    }


async def _batch_delete_before(session: AsyncSession, cutoff, batch_size: int = 5000) -> int:
    """Delete audit logs older than *cutoff* in batches to avoid long locks."""
    from sqlalchemy import delete, func, select

    from swx_core.models.audit_log import AuditLog

    total_deleted = 0
    while True:
        # Find IDs to delete in this batch
        stmt = select(AuditLog.id).where(AuditLog.timestamp < cutoff).limit(batch_size)
        result = await session.execute(stmt)
        ids = [row[0] for row in result.all()]

        if not ids:
            break

        delete_stmt = delete(AuditLog).where(AuditLog.id.in_(ids))
        result = await session.execute(delete_stmt)
        await session.commit()

        deleted_count = result.rowcount if result.rowcount is not None else len(ids)
        if deleted_count == 0:
            logger.warning("Audit retention: delete reported 0 rows for %d IDs — breaking to prevent infinite loop", len(ids))
            break

        total_deleted += deleted_count
        logger.debug("Audit retention batch: deleted %d rows (total %d)", deleted_count, total_deleted)

    return total_deleted