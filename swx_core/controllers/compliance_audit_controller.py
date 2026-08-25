from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.audit_log import AuditLogsPublic
from swx_core.models.compliance_audit import ComplianceConfigCreate, ComplianceConfigPublic, DataSubjectRequestCreate, DataSubjectRequestPublic, RetentionPolicyCreate, RetentionPolicyPublic
from swx_core.services.compliance import compliance_audit_service
from swx_core.services.compliance import data_subject_service
from swx_core.services.compliance import retention_service
from swx_core.services.compliance.erasure_scheduler_service import execute_scheduled_erasures
from swx_core.services.compliance.audit_integrity_service import get_integrity_report


async def list_compliance_logs_controller(session: AsyncSession, **filters: object) -> AuditLogsPublic:
    return await compliance_audit_service.get_compliance_logs(session, **filters)


async def get_compliance_report_controller(session: AsyncSession, start_date: datetime | None = None, end_date: datetime | None = None) -> dict[str, object]:
    return await compliance_audit_service.generate_compliance_report(session, start_date, end_date)


async def list_data_subject_requests_controller(session: AsyncSession, user_id: UUID | None = None) -> list[DataSubjectRequestPublic]:
    return await data_subject_service.get_data_subject_requests(session, user_id=user_id)


async def create_data_subject_request_controller(session: AsyncSession, user_id: UUID, data: DataSubjectRequestCreate) -> DataSubjectRequestPublic:
    return await data_subject_service.create_data_subject_request(session, user_id, data)


async def verify_data_subject_request_controller(session: AsyncSession, request_id: UUID, token: str, user_id: UUID | None = None) -> DataSubjectRequestPublic:
    return await data_subject_service.verify_request(session, request_id, token, user_id=user_id)


async def process_data_subject_request_controller(session: AsyncSession, request_id: UUID, admin_notes: str | None = None) -> dict[str, object]:
    return await data_subject_service.process_data_subject_request(session, request_id, admin_notes=admin_notes)


async def cancel_data_subject_request_controller(session: AsyncSession, request_id: UUID, user_id: UUID) -> DataSubjectRequestPublic:
    return await data_subject_service.cancel_data_subject_request(session, request_id, user_id)


async def export_own_data_controller(session: AsyncSession, user_id: UUID) -> dict[str, object]:
    return await data_subject_service.export_own_data(session, user_id)


async def list_retention_policies_controller(session: AsyncSession) -> list[RetentionPolicyPublic]:
    return await retention_service.get_retention_policies(session)


async def upsert_retention_policy_controller(session: AsyncSession, data: RetentionPolicyCreate) -> RetentionPolicyPublic:
    return await retention_service.upsert_retention_policy(session, data)


async def apply_retention_controller(session: AsyncSession, resource_type: str | None = None) -> dict[str, object]:
    return await retention_service.apply_retention(session, resource_type)


async def list_compliance_configs_controller(session: AsyncSession, category: str | None = None) -> list[ComplianceConfigPublic]:
    return await compliance_audit_service.list_compliance_configs(session, category)


async def upsert_compliance_config_controller(session: AsyncSession, data: ComplianceConfigCreate) -> ComplianceConfigPublic:
    return await compliance_audit_service.upsert_compliance_config(session, data)


async def execute_scheduled_erasures_controller(session: AsyncSession) -> dict:
    return await execute_scheduled_erasures(session)


async def purge_audit_logs_controller(session: AsyncSession, retention_days: int | None = None) -> dict:
    return await retention_service.purge_expired_audit_logs(session, retention_days)


async def purge_sessions_controller(session: AsyncSession, retention_days: int | None = None) -> dict:
    return await retention_service.purge_expired_sessions(session, retention_days)


async def verify_audit_integrity_controller(session: AsyncSession) -> dict[str, object]:
    return await get_integrity_report(session)
