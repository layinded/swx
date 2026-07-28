from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.compliance_audit import ComplianceConfigCreate
from swx_core.repositories import compliance_audit_repository
from swx_core.services.compliance.config_cache import get_cached_configs, invalidate_compliance_config_cache, resolve_config_value
from swx_core.events.dispatcher import event_bus

_RULES = {
    "ssn": "***-**-****",
    "password": "[REDACTED]",
}


def _mask_email(value: str) -> str:
    name, _, domain = value.partition("@")
    return f"{name[:1]}***@{domain}" if domain else "[REDACTED]"


def _mask_phone(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    return f"***-***-{digits[-4:]}" if len(digits) >= 4 else "***-***-****"


def _mask_credit_card(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    return f"****-****-****-{digits[-4:]}" if len(digits) >= 4 else "****-****-****-****"


def _mask_dob(value: str) -> str:
    year = value[-4:] if len(value) >= 4 else "YYYY"
    return f"XX/XX/{year}"


_FIELD_MASKERS = {
    "credit_card": _mask_credit_card,
    "email": _mask_email,
    "phone": _mask_phone,
    "dob": _mask_dob,
}


async def get_redaction_rules(session: AsyncSession) -> dict[str, str]:
    rules = {**_RULES, **{field_name: "__dynamic__" for field_name in _FIELD_MASKERS}}
    for config in await get_cached_configs(session, category="redaction"):
        value = resolve_config_value(config.value)
        if isinstance(value, dict):
            rules.update({str(key): str(item) for key, item in value.items()})
        else:
            rules[config.key] = str(value)
    return rules


async def add_redaction_rule(session: AsyncSession, key: str, value: str, description: str | None = None) -> ComplianceConfigCreate:
    config = await compliance_audit_repository.upsert_compliance_config(session, {"key": key, "value": value, "category": "redaction", "description": description, "is_active": True})
    invalidate_compliance_config_cache()
    await event_bus.dispatch("compliance.redaction_rule_updated", payload={"key": key})
    return ComplianceConfigCreate.model_validate(config)


async def redact_fields(session: AsyncSession, data: dict[str, object], classification: str | None = None) -> dict[str, object]:
    rules = await get_redaction_rules(session)
    redacted: dict[str, object] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            redacted[key] = await redact_fields(session, value, classification)
            continue

        lower = key.lower()
        mask = _FIELD_MASKERS.get(lower)
        if mask and isinstance(value, str):
            redacted[key] = mask(value)
        elif lower in rules:
            redacted[key] = rules[lower]
        else:
            redacted[key] = value
    return redacted
