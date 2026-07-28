from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.models.audit_log import AuditLog, AuditLogPublic, AuditLogsPublic
from swx_core.models.compliance_audit import ComplianceConfigCreate, ComplianceConfigPublic
from swx_core.repositories import compliance_audit_repository
from swx_core.services.compliance.config_cache import invalidate_compliance_config_cache, serialize_config_value, get_cached_configs, resolve_config_value


async def record_compliance_audit(session: AsyncSession, log: AuditLog) -> AuditLog:
    payload = {"action": log.action, "classification": log.data_classification, "access_result": log.access_result, "actor_id": log.actor_id}
    await event_bus.dispatch("compliance.data_accessed", payload=payload)
    if log.access_result == "DENIED_CONSENT_REQUIRED":
        await event_bus.dispatch("compliance.consent_violation", payload={"action": log.action, "actor_id": log.actor_id, "resource_id": log.resource_id})
    return log


async def check_data_access(session: AsyncSession, actor_type: str, data_classification: str, context: dict[str, Any] | None = None) -> str:
    context = context or {}
    for config in await get_cached_configs(session, category="general"):
        if config.key != "classification_access_rules":
            continue
        classification_rules = resolve_config_value(config.value)
        if isinstance(classification_rules, dict):
            allowed_actor_types = classification_rules.get(data_classification, [])
            if actor_type not in allowed_actor_types:
                return "DENIED_DATA_CLASSIFICATION"
    if context.get("consent_required") and not context.get("consent_granted"):
        return "DENIED_CONSENT_REQUIRED"
    return "ALLOWED"


async def get_compliance_logs(session: AsyncSession, **filters: Any) -> AuditLogsPublic:
    logs = await compliance_audit_repository.get_compliance_logs(session, **filters)
    count_filters = {key: value for key, value in filters.items() if key not in {"skip", "limit"}}
    count = await compliance_audit_repository.get_compliance_log_count(session, **count_filters)
    return AuditLogsPublic(data=[AuditLogPublic.model_validate(log) for log in logs], count=count)


async def generate_compliance_report(session: AsyncSession, start_date: datetime | None = None, end_date: datetime | None = None) -> dict[str, object]:
    logs = await compliance_audit_repository.get_compliance_logs(session, skip=0, limit=1000, start_date=start_date, end_date=end_date)
    by_severity: dict[str, int] = {}
    by_classification: dict[str, int] = {}
    by_access_result: dict[str, int] = {}
    by_outcome: dict[str, int] = {}
    for log in logs:
        severity = log.severity or "info"
        classification = log.data_classification or "UNSPECIFIED"
        access_result = log.access_result or "UNSPECIFIED"
        by_severity[severity] = by_severity.get(severity, 0) + 1
        by_classification[classification] = by_classification.get(classification, 0) + 1
        by_access_result[access_result] = by_access_result.get(access_result, 0) + 1
        by_outcome[log.outcome] = by_outcome.get(log.outcome, 0) + 1
    await event_bus.dispatch("compliance.data_exported", payload={"report": True, "start_date": start_date.isoformat() if start_date else None, "end_date": end_date.isoformat() if end_date else None})
    return {"total": len(logs), "by_severity": by_severity, "by_classification": by_classification, "by_access_result": by_access_result, "by_outcome": by_outcome}


async def list_compliance_configs(session: AsyncSession, category: str | None = None) -> list[ComplianceConfigPublic]:
    configs = await compliance_audit_repository.list_compliance_configs(session, category=category, active_only=False)
    return [
        ComplianceConfigPublic.model_validate({**config.model_dump(), "value": str(serialize_config_value(config.key, config.value))})
        for config in configs
    ]


async def upsert_compliance_config(session: AsyncSession, data: ComplianceConfigCreate) -> ComplianceConfigPublic:
    config = await compliance_audit_repository.upsert_compliance_config(session, data.model_dump())
    invalidate_compliance_config_cache()
    await event_bus.dispatch("compliance.config_updated", payload={"key": config.key, "category": config.category})
    return ComplianceConfigPublic.model_validate({**config.model_dump(), "value": str(serialize_config_value(config.key, config.value))})
