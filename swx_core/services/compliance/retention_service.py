from datetime import datetime, timedelta
from typing import Any
from swx_core.utils.time import utc_now

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.models.compliance_audit import RetentionPolicyCreate, RetentionPolicyPublic
from swx_core.repositories import compliance_audit_repository
from swx_core.services.job.job_dispatcher import enqueue_job

def _utc_now() -> datetime:
    return utc_now()

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
        cutoff = _utc_now() - timedelta(days=policy.retention_days)
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
