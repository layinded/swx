from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from swx_core.auth.admin.dependencies import get_current_admin_user
from swx_core.controllers import compliance_audit_controller
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
