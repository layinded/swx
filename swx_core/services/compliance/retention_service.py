from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.events.dispatcher import event_bus
from swx_core.middleware.logging_middleware import logger
from swx_core.models.compliance_audit import RetentionPolicyCreate, RetentionPolicyPublic
from swx_core.repositories import compliance_audit_repository
from swx_core.services.job.job_dispatcher import enqueue_job
from swx_core.utils.time import utc_now

async def get_retention_policies(session: AsyncSession) -> list[RetentionPolicyPublic]:
    return [RetentionPolicyPublic.model_validate(item) for item in await compliance_audit_repository.list_retention_policies(session)]

async def get_retention_policy(session: AsyncSession, resource_type: str) -> RetentionPolicyPublic | None:
    policy = await compliance_audit_repository.get_retention_policy(session, resource_type)
    return RetentionPolicyPublic.model_validate(policy) if policy else None

async def upsert_retention_policy(session: AsyncSession, data: RetentionPolicyCreate) -> RetentionPolicyPublic:
    policy = await compliance_audit_repository.upsert_retention_policy(session, data.model_dump())
    await event_bus.dispatch("compliance.retention_policy_updated", payload={"resource_type": policy.resource_type})
    return RetentionPolicyPublic.model_validate(policy)

async def apply_retention(session: AsyncSession, resource_type: str | None = None) -> dict[str, Any]:
    policies = await compliance_audit_repository.list_retention_policies(session)
    results: dict[str, Any] = {}
    for policy in policies:
        if resource_type and policy.resource_type != resource_type:
            continue
        cutoff = utc_now() - timedelta(days=policy.retention_days)
        policy_action = policy.action_on_expiry
        resource_name = policy.resource_type
        if resource_name == "audit_log" and policy_action == "anonymize":
            affected = await compliance_audit_repository.anonymize_audit_logs_before(session, cutoff)
        elif resource_name == "data_subject_request" and policy_action == "delete":
            affected = await compliance_audit_repository.delete_data_subject_requests_before(session, cutoff)
        elif policy_action == "archive":
            affected = 0
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported retention action for {resource_name}")
        results[resource_name] = {"action": policy_action, "affected": affected}
        await event_bus.dispatch("compliance.retention_policy_applied", payload={"resource_type": resource_name, "action": policy_action, "affected": affected})
    return results

async def schedule_retention_check(session: AsyncSession, resource_type: str | None = None) -> dict[str, str]:
    job = await enqueue_job("compliance.retention.apply", {"resource_type": resource_type}, session=session, tags=["compliance", "retention"])
    return {"job_id": str(job.id), "status": job.status}


async def purge_expired_audit_logs(session: AsyncSession, retention_days: int | None = None) -> dict[str, int]:
    """Delete audit logs older than the retention period.

    SOC 2 CC6.5: Enforces audit log retention policy. Uses
    SWX_AUDIT_RETENTION_DAYS from settings if no override provided.
    """
    days = retention_days or settings.SWX_AUDIT_RETENTION_DAYS or 365
    cutoff = utc_now() - timedelta(days=days)

    count = await compliance_audit_repository.delete_expired_audit_logs(session, cutoff)
    logger.info(f"Purged {count} audit logs older than {days} days (cutoff: {cutoff.isoformat()})")

    await event_bus.dispatch(
        "compliance.audit_logs_purged",
        payload={"retention_days": days, "purged_count": count},
    )

    return {"retention_days": days, "purged_count": count}


async def purge_expired_sessions(session: AsyncSession, retention_days: int | None = None) -> dict[str, int]:
    """Delete expired refresh tokens older than the retention period.

    SOC 2 CC6.5: Removes stale session data. Uses
    SESSION_RETENTION_DAYS from settings if no override provided.
    """
    days = retention_days if retention_days is not None else settings.SESSION_RETENTION_DAYS
    cutoff = utc_now() - timedelta(days=days)

    count = await compliance_audit_repository.delete_expired_refresh_tokens(session, cutoff)
    logger.info(f"Purged {count} refresh tokens older than {days} days (cutoff: {cutoff.isoformat()})")

    await event_bus.dispatch(
        "compliance.sessions_purged",
        payload={"retention_days": days, "purged_count": count},
    )

    return {"retention_days": days, "purged_count": count}


async def purge_expired_exports(session: AsyncSession, retention_days: int | None = None) -> dict[str, int]:
    """Delete data export records older than the retention period.

    SOC 2 CC6.5: Removes stale export data. Uses
    DATA_EXPORT_EXPIRY_DAYS from settings if no override provided.
    """
    days = retention_days if retention_days is not None else settings.DATA_EXPORT_EXPIRY_DAYS
    cutoff = utc_now() - timedelta(days=days)

    count = await compliance_audit_repository.delete_expired_data_exports(session, cutoff)
    logger.info(f"Purged {count} data export records older than {days} days (cutoff: {cutoff.isoformat()})")

    await event_bus.dispatch(
        "compliance.exports_purged",
        payload={"retention_days": days, "purged_count": count},
    )

    return {"retention_days": days, "purged_count": count}
