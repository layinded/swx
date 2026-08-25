from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from swx_core.auth.admin.dependencies import get_current_admin_user
from swx_core.controllers import compliance_audit_controller
from swx_core.controllers import access_review_controller
from swx_core.controllers import backup_status_controller
from swx_core.database.db import SessionDep
from swx_core.models.audit_log import AuditLogsPublic
from swx_core.models.compliance_audit import ComplianceConfigCreate, ComplianceConfigPublic, DataSubjectRequestPublic, RetentionPolicyCreate, RetentionPolicyPublic

router = APIRouter(prefix="/admin/compliance", tags=["admin-compliance"], dependencies=[Depends(get_current_admin_user)])


@router.get("/logs", response_model=AuditLogsPublic)
async def list_compliance_logs(session: SessionDep, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000), actor_type: str | None = None, actor_id: str | None = None, action: str | None = None, resource_type: str | None = None, resource_id: str | None = None, outcome: str | None = None, severity: str | None = None, data_classification: str | None = None, access_result: str | None = None, start_date: datetime | None = None, end_date: datetime | None = None) -> AuditLogsPublic:
    return await compliance_audit_controller.list_compliance_logs_controller(
        session,
        skip=skip,
        limit=limit,
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        outcome=outcome,
        severity=severity,
        data_classification=data_classification,
        access_result=access_result,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/report")
async def get_compliance_report(session: SessionDep, start_date: datetime | None = None, end_date: datetime | None = None) -> dict[str, object]:
    return await compliance_audit_controller.get_compliance_report_controller(session, start_date, end_date)


@router.get("/config", response_model=list[ComplianceConfigPublic])
async def list_compliance_configs(session: SessionDep, category: str | None = None) -> list[ComplianceConfigPublic]:
    return await compliance_audit_controller.list_compliance_configs_controller(session, category)


@router.put("/config", response_model=ComplianceConfigPublic)
async def upsert_compliance_config(session: SessionDep, body: ComplianceConfigCreate) -> ComplianceConfigPublic:
    return await compliance_audit_controller.upsert_compliance_config_controller(session, body)


@router.get("/retention-policies", response_model=list[RetentionPolicyPublic])
async def list_retention_policies(session: SessionDep) -> list[RetentionPolicyPublic]:
    return await compliance_audit_controller.list_retention_policies_controller(session)


@router.put("/retention-policies", response_model=RetentionPolicyPublic)
async def upsert_retention_policy(session: SessionDep, body: RetentionPolicyCreate) -> RetentionPolicyPublic:
    return await compliance_audit_controller.upsert_retention_policy_controller(session, body)


@router.post("/retention/apply")
async def apply_retention(session: SessionDep, resource_type: str | None = None) -> dict[str, object]:
    return await compliance_audit_controller.apply_retention_controller(session, resource_type)


@router.get("/data-subject-requests", response_model=list[DataSubjectRequestPublic])
async def list_data_subject_requests(session: SessionDep) -> list[DataSubjectRequestPublic]:
    return await compliance_audit_controller.list_data_subject_requests_controller(session)


@router.post("/data-subject-requests/{request_id}/process")
async def process_data_subject_request(session: SessionDep, request_id: UUID, admin_notes: str | None = None) -> dict[str, object]:
    return await compliance_audit_controller.process_data_subject_request_controller(session, request_id, admin_notes)


# ── Access Review (SOC 2 CC6.2) ────────────────────────────────────


@router.get("/access-review")
async def get_access_review(
    session: SessionDep,
    days_inactive: int = Query(90, ge=1, description="Days without login to flag as orphaned"),
    days_unused: int = Query(90, ge=1, description="Days without RBAC activity to flag role as unused"),
    days_stale: int = Query(30, ge=1, description="Days for refresh tokens to be considered stale"),
    days_over_provisioned: int = Query(30, ge=1, description="Days without admin activity to flag over-provisioned"),
) -> dict[str, object]:
    """Generate a comprehensive SOC 2 access review report."""
    return await access_review_controller.get_access_review_controller(
        session,
        days_inactive=days_inactive,
        days_unused=days_unused,
        days_stale=days_stale,
        days_over_provisioned=days_over_provisioned,
    )


@router.get("/access-review/orphaned-accounts")
async def get_orphaned_accounts(
    session: SessionDep,
    days_inactive: int = Query(90, ge=1),
) -> list[dict]:
    """List active users with no login within the given period."""
    return await access_review_controller.get_orphaned_accounts_controller(session, days_inactive)


@router.get("/access-review/unused-roles")
async def get_unused_roles(
    session: SessionDep,
    days_unused: int = Query(90, ge=1),
) -> list[dict]:
    """List role assignments with no recent RBAC audit activity."""
    return await access_review_controller.get_unused_roles_controller(session, days_unused)


@router.get("/access-review/stale-tokens")
async def get_stale_tokens(
    session: SessionDep,
    days_old: int = Query(30, ge=1),
) -> list[dict]:
    """List refresh tokens older than threshold that are still valid."""
    return await access_review_controller.get_stale_tokens_controller(session, days_old)


@router.get("/access-review/over-provisioned-users")
async def get_over_provisioned_users(
    session: SessionDep,
    days: int = Query(30, ge=1),
) -> list[dict]:
    """List users with admin roles but no admin audit activity."""
    return await access_review_controller.get_over_provisioned_users_controller(session, days)


# ── Erasure & Retention (SOC 2 CC6.5) ──────────────────────────────


@router.post("/execute-scheduled-erasions")
async def execute_scheduled_erasions(session: SessionDep) -> dict:
    """Manually trigger scheduled GDPR erasure execution."""
    return await compliance_audit_controller.execute_scheduled_erasions_controller(session)


@router.post("/purge-audit-logs")
async def purge_audit_logs(
    session: SessionDep,
    retention_days: int | None = Query(None, ge=1, description="Override retention days (default from settings)"),
) -> dict:
    """Purge audit logs older than the retention period."""
    return await compliance_audit_controller.purge_audit_logs_controller(session, retention_days)


@router.post("/purge-sessions")
async def purge_sessions(
    session: SessionDep,
    retention_days: int | None = Query(None, ge=1, description="Override session retention days (default from settings)"),
) -> dict:
    """Purge refresh tokens older than the retention period."""
    return await compliance_audit_controller.purge_sessions_controller(session, retention_days)


# ── Backup Status (SOC 2 CC6.5) ────────────────────────────────────


@router.get("/backup-status")
async def get_backup_status(session: SessionDep) -> dict[str, object]:
    """Return backup verification status for SOC 2 auditors."""
    return await backup_status_controller.get_backup_status_controller(session)


# ── Audit Integrity (SOC 2 CC7.2) ─────────────────────────────────


@router.get("/audit-logs/verify-integrity")
async def verify_audit_integrity(session: SessionDep) -> dict[str, object]:
    """Walk the audit log hash chain and report any tampered entries."""
    return await compliance_audit_controller.verify_audit_integrity_controller(session)
