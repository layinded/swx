# pyright: reportExplicitAny=false, reportAny=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportArgumentType=false, reportUnnecessaryTypeIgnoreComment=false

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import desc, func, select

from swx_core.models.audit_log import AuditLog
from swx_core.models.compliance_audit import ComplianceConfig, DataSubjectRequest, RetentionPolicy
from swx_core.models.consent import UserConsent
from swx_core.models.user import User


async def list_compliance_configs(session: AsyncSession, category: str | None = None, active_only: bool = True) -> list[ComplianceConfig]:
    stmt = select(ComplianceConfig)
    if category:
        stmt = stmt.where(ComplianceConfig.category == category)
    if active_only:
        stmt = stmt.where(ComplianceConfig.is_active == True)
    stmt = stmt.order_by(ComplianceConfig.category, ComplianceConfig.key)
    return list((await session.execute(stmt)).scalars().all())


async def get_compliance_config(session: AsyncSession, key: str, active_only: bool = True) -> ComplianceConfig | None:
    stmt = select(ComplianceConfig).where(ComplianceConfig.key == key)
    if active_only:
        stmt = stmt.where(ComplianceConfig.is_active == True)
    return (await session.execute(stmt)).scalar_one_or_none()


async def upsert_compliance_config(session: AsyncSession, data: dict[str, Any]) -> ComplianceConfig:
    existing_config = await get_compliance_config(session, data["key"], active_only=False)
    config = ComplianceConfig(**data) if existing_config is None else _assign(existing_config, data)
    session.add(config)
    await session.commit()
    await session.refresh(config)
    return config


async def create_data_subject_request(session: AsyncSession, data: dict[str, Any]) -> DataSubjectRequest:
    request = DataSubjectRequest(**data)
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return request


async def get_data_subject_request(session: AsyncSession, request_id: UUID) -> DataSubjectRequest | None:
    return await session.get(DataSubjectRequest, request_id)


async def get_request_by_token(session: AsyncSession, verification_token: str) -> DataSubjectRequest | None:
    stmt = select(DataSubjectRequest).where(DataSubjectRequest.verification_token == verification_token)
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_data_subject_requests(session: AsyncSession, user_id: UUID | None = None, status: str | None = None) -> list[DataSubjectRequest]:
    stmt = select(DataSubjectRequest)
    if user_id:
        stmt = stmt.where(DataSubjectRequest.user_id == user_id)
    if status:
        stmt = stmt.where(DataSubjectRequest.status == status)
    stmt = stmt.order_by(desc(DataSubjectRequest.requested_at))
    return list((await session.execute(stmt)).scalars().all())


async def update_data_subject_request(session: AsyncSession, request_id: UUID, data: dict[str, Any]) -> DataSubjectRequest | None:
    request = await get_data_subject_request(session, request_id)
    if request is None:
        return None
    session.add(_assign(request, data))
    await session.commit()
    await session.refresh(request)
    return request


async def upsert_retention_policy(session: AsyncSession, data: dict[str, Any]) -> RetentionPolicy:
    existing_policy = await get_retention_policy(session, data["resource_type"], active_only=False)
    policy = RetentionPolicy(**data) if existing_policy is None else _assign(existing_policy, data)
    session.add(policy)
    await session.commit()
    await session.refresh(policy)
    return policy


async def list_retention_policies(session: AsyncSession, active_only: bool = True) -> list[RetentionPolicy]:
    stmt = select(RetentionPolicy)
    if active_only:
        stmt = stmt.where(RetentionPolicy.is_active == True)
    stmt = stmt.order_by(RetentionPolicy.resource_type)
    return list((await session.execute(stmt)).scalars().all())


async def get_retention_policy(session: AsyncSession, resource_type: str, active_only: bool = True) -> RetentionPolicy | None:
    stmt = select(RetentionPolicy).where(RetentionPolicy.resource_type == resource_type)
    if active_only:
        stmt = stmt.where(RetentionPolicy.is_active == True)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_compliance_logs(session: AsyncSession, **filters: Any) -> list[AuditLog]:
    skip = filters.pop("skip", 0)
    limit = filters.pop("limit", 100)
    stmt = _apply_log_filters(select(AuditLog), filters)
    stmt = stmt.order_by(desc(AuditLog.timestamp)).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def get_compliance_log_count(session: AsyncSession, **filters: Any) -> int:
    stmt = _apply_log_filters(select(func.count()).select_from(AuditLog), filters)
    return int((await session.execute(stmt)).scalar() or 0)


async def export_user_data(session: AsyncSession, user_id: UUID) -> dict[str, Any]:
    user = await session.get(User, user_id)
    consents = list((await session.execute(select(UserConsent).where(UserConsent.user_id == user_id))).scalars().all())
    requests = await list_data_subject_requests(session, user_id=user_id)
    log_stmt = select(AuditLog).where((AuditLog.actor_id == str(user_id)) | (AuditLog.resource_id == str(user_id))).order_by(desc(AuditLog.timestamp)).limit(500)
    logs = list((await session.execute(log_stmt)).scalars().all())
    return {
        "user": user.model_dump() if user else None,
        "consents": [item.model_dump() for item in consents],
        "requests": [item.model_dump() for item in requests],
        "audit_logs": [item.model_dump() for item in logs],
    }


async def anonymize_audit_logs_before(session: AsyncSession, cutoff: datetime) -> int:
    stmt = update(AuditLog).where(AuditLog.timestamp < cutoff).values(actor_id=None, ip_address=None, user_agent=None, masked_ip=None, context={})
    result = await session.execute(stmt)
    await session.commit()
    return int(result.rowcount or 0)


async def delete_data_subject_requests_before(session: AsyncSession, cutoff: datetime) -> int:
    from sqlalchemy import delete as sql_delete
    stmt = sql_delete(DataSubjectRequest).where(DataSubjectRequest.requested_at < cutoff)
    result = await session.execute(stmt)
    await session.commit()
    return int(result.rowcount or 0)


def _assign(model: Any, data: dict[str, Any]) -> Any:
    for field_name, field_value in data.items():
        setattr(model, field_name, field_value)
    return model


def _apply_log_filters(stmt: Any, filters: dict[str, Any]) -> Any:
    for field_name in ("actor_type", "actor_id", "action", "resource_type", "resource_id", "outcome", "severity", "data_classification", "access_result"):
        value = filters.get(field_name)
        if value:
            stmt = stmt.where(getattr(AuditLog, field_name) == value)
    if filters.get("start_date"):
        stmt = stmt.where(AuditLog.timestamp >= filters["start_date"])
    if filters.get("end_date"):
        stmt = stmt.where(AuditLog.timestamp <= filters["end_date"])
    return stmt


async def delete_expired_audit_logs(session: AsyncSession, cutoff: datetime) -> int:
    """Delete audit logs older than the given cutoff datetime."""
    from sqlalchemy import delete as sql_delete
    stmt = sql_delete(AuditLog).where(AuditLog.timestamp < cutoff)
    result = await session.execute(stmt)
    await session.commit()
    return int(result.rowcount or 0)


async def delete_expired_refresh_tokens(session: AsyncSession, cutoff: datetime) -> int:
    """Delete refresh tokens older than the given cutoff datetime."""
    from sqlalchemy import delete as sql_delete
    from swx_core.models.refresh_token import RefreshToken
    stmt = sql_delete(RefreshToken).where(RefreshToken.created_at < cutoff)
    result = await session.execute(stmt)
    await session.commit()
    return int(result.rowcount or 0)


async def delete_expired_data_exports(session: AsyncSession, cutoff: datetime) -> int:
    """Delete data export records older than the given cutoff datetime."""
    from sqlalchemy import delete as sql_delete
    from swx_core.models.data_export import DataExport
    stmt = sql_delete(DataExport).where(DataExport.created_at < cutoff)
    result = await session.execute(stmt)
    await session.commit()
    return int(result.rowcount or 0)
