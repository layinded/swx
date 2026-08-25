"""Audit integrity service — SOC 2 CC7.2 tamper-evident hash chain.

Computes and verifies SHA-256 hash chains over audit log entries.
Business logic (hash computation, tamper detection, fail-closed policy)
lives here. Database reads/persists go through the repository.
"""

import hashlib
import json

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.audit_log import AuditLog
from swx_core.repositories.audit_integrity_repository import (
    set_log_hash as repo_set_log_hash,
    get_all_audit_entries_ordered,
)


def compute_log_hash(entry: AuditLog, previous_hash: str | None) -> str:
    """Compute SHA-256 hash of an audit entry chained to the previous hash.

    Includes all security-relevant fields to ensure tamper-evidence
    of metadata (IP, user agent, request ID, context, etc.).
    """
    canonical = json.dumps(
        {
            "id": str(entry.id),
            "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
            "actor_type": entry.actor_type,
            "actor_id": entry.actor_id,
            "action": entry.action,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "outcome": entry.outcome,
            "severity": entry.severity,
            "ip_address": entry.ip_address,
            "masked_ip": entry.masked_ip,
            "user_agent": entry.user_agent,
            "request_id": entry.request_id,
            "context": entry.context,
            "data_classification": entry.data_classification,
            "access_result": entry.access_result,
            "previous_hash": previous_hash or "",
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


async def persist_log_hash(session: AsyncSession, entry: AuditLog) -> None:
    """Compute and persist the hash chain for a new audit entry.

    Uses SELECT ... FOR UPDATE to lock the predecessor row, ensuring
    atomic hash computation even under concurrent writes.
    """
    from swx_core.repositories.audit_integrity_repository import get_previous_hash_for_update
    previous_hash = await get_previous_hash_for_update(session, entry.id)
    log_hash = compute_log_hash(entry, previous_hash)
    await repo_set_log_hash(session, entry.id, log_hash)


async def get_integrity_report(session: AsyncSession) -> dict[str, object]:
    """Walk the audit log chain and report any tampered entries."""
    entries = await get_all_audit_entries_ordered(session)

    if not entries:
        return {"valid": True, "total": 0, "tampered_ids": [], "message": "No audit log entries found."}

    tampered_ids: list[str] = []
    previous_hash: str | None = None

    for entry in entries:
        expected_hash = compute_log_hash(entry, previous_hash)
        if entry.log_hash != expected_hash:
            tampered_ids.append(str(entry.id))
        previous_hash = entry.log_hash

    total = len(entries)
    valid = len(tampered_ids) == 0
    message = "All entries verified successfully." if valid else f"{len(tampered_ids)} tampered entries detected."

    return {
        "valid": valid,
        "total": total,
        "tampered_ids": tampered_ids,
        "message": message,
    }


async def check_startup_integrity(session: AsyncSession) -> None:
    """Verify audit log chain integrity at application startup (fail-closed)."""
    result = await get_integrity_report(session)
    if not result["valid"]:
        raise RuntimeError(
            f"Audit log integrity check failed at startup: {result['message']} "
            f"Tampered IDs: {result['tampered_ids']}"
        )