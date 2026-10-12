# pyright: reportExplicitAny=false, reportAny=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false

import io
import json
import zipfile
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.middleware.logging_middleware import logger
from swx_core.services.audit_logger import AuditLogger, ActorType, AuditOutcome, AuditAction
from swx_core.models.conversation import Conversation
from swx_core.repositories import gdpr_export_repository


def _model_to_dict(obj: object) -> dict[str, object]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    result: dict[str, object] = {}
    for key, value in vars(obj).items():
        if key.startswith("_"):
            continue
        if isinstance(value, UUID):
            result[key] = str(value)
        elif hasattr(value, "isoformat"):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def _models_to_dicts(items: Sequence[object]) -> list[dict[str, object]]:
    return [_model_to_dict(item) for item in items]


async def export_user_data_zip(session: AsyncSession, user_id: UUID) -> bytes:
    """Collect all user data and return as a ZIP archive (GDPR Article 20)."""
    user = await gdpr_export_repository.get_user_profile(session, user_id)
    if user is None:
        return b""

    sections: dict[str, object] = {"profile": _model_to_dict(user)}

    fetch_tasks = [
        ("social_accounts", gdpr_export_repository.get_user_social_accounts),
        ("consents", gdpr_export_repository.get_user_consents),
        ("notifications", gdpr_export_repository.get_user_notifications),
        ("notification_preferences", gdpr_export_repository.get_user_notification_preferences),
        ("api_keys", gdpr_export_repository.get_user_api_keys),
        ("webhook_endpoints", gdpr_export_repository.get_user_webhook_endpoints),
        ("devices", gdpr_export_repository.get_user_devices),
        ("exports", gdpr_export_repository.get_user_exports),
        ("imports", gdpr_export_repository.get_user_imports),
        ("roles", gdpr_export_repository.get_user_roles),
        ("team_memberships", gdpr_export_repository.get_user_team_memberships),
        ("org_memberships", gdpr_export_repository.get_user_org_memberships),
        ("referral_codes", gdpr_export_repository.get_user_referral_codes),
        ("referral_events", gdpr_export_repository.get_user_referral_events),
        ("onboarding_steps", gdpr_export_repository.get_user_onboarding_steps),
        ("flag_evaluations", gdpr_export_repository.get_user_flag_evaluations),
        ("audit_logs", lambda s, uid: gdpr_export_repository.get_user_audit_logs(s, str(uid))),
    ]

    for section_name, fetch_fn in fetch_tasks:
        try:
            items = await fetch_fn(session, user_id)
            sections[section_name] = _models_to_dicts(items)
        except Exception as e:
            logger.warning("Failed to export %s for user %s: %s", section_name, user_id, e)
            sections[section_name] = []

    try:
        conversations = await gdpr_export_repository.get_user_conversations(session, user_id)
        sections["conversations"] = _models_to_dicts(conversations)
    except Exception as e:
        logger.warning("Failed to export conversations for user %s: %s", user_id, e)
        sections["conversations"] = []
        conversations = []

    conv_ids = [c.id for c in conversations if isinstance(c, Conversation)]
    if conv_ids:
        try:
            messages = await gdpr_export_repository.get_conversation_messages(session, conv_ids)
            sections["conversation_messages"] = _models_to_dicts(messages)
        except Exception as e:
            logger.warning("Failed to export conversation_messages for user %s: %s", user_id, e)
            sections["conversation_messages"] = []
    else:
        sections["conversation_messages"] = []

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for section_name, data in sections.items():
            zf.writestr(f"{section_name}.json", json.dumps(data, indent=2, default=str))

    buffer.seek(0)
    logger.info("GDPR export completed for user %s", user_id)
    await event_bus.dispatch("gdpr.export_completed", payload={"user_id": str(user_id)})

    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.GDPR_EXPORT_REQUESTED,
        actor_type=ActorType.USER,
        actor_id=str(user_id),
        resource_type="user",
        resource_id=str(user_id),
        outcome=AuditOutcome.SUCCESS,
    )

    return buffer.getvalue()


async def request_deletion(session: AsyncSession, user_id: UUID) -> dict[str, object]:
    """Request account deletion with grace period.

    Delegates to ErasureService which deactivates the account immediately
    and sets gdpr_deleted_at to the scheduled hard-deletion date.
    """
    from swx_core.services.compliance.erasure_service import request_erasure

    cert = await request_erasure(session, user_id)

    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.GDPR_ERASURE_REQUESTED,
        actor_type=ActorType.USER,
        actor_id=str(user_id),
        resource_type="user",
        resource_id=str(user_id),
        outcome=AuditOutcome.SUCCESS,
        context={"certificate_id": str(cert.id), "erasure_type": cert.erasure_type},
    )

    return {
        "status": "deactivated",
        "certificate_id": str(cert.id),
        "erasure_type": cert.erasure_type,
        "created_at": cert.created_at.isoformat(),
    }


async def cancel_deletion(session: AsyncSession, user_id: UUID) -> dict[str, object]:
    """Cancel a pending deletion during the grace period."""
    from swx_core.services.compliance.erasure_service import cancel_erasure

    result = await cancel_erasure(session, user_id)

    audit = AuditLogger(session)
    await audit.log_event(
        action=AuditAction.GDPR_ERASURE_CANCELLED,
        actor_type=ActorType.USER,
        actor_id=str(user_id),
        resource_type="user",
        resource_id=str(user_id),
        outcome=AuditOutcome.SUCCESS,
    )

    return result