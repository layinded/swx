from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import settings
from swx_core.events.dispatcher import event_bus
from swx_core.models.email_provider_config import EmailProviderConfigCreate, EmailProviderConfigPublic
from swx_core.models.notification_preference import NotificationPreferencePublic, NotificationPreferenceUpdate
from swx_core.models.notification_template import NotificationTemplateCreate, NotificationTemplatePublic
from swx_core.models.sms_provider_config import SMSProviderConfigCreate, SMSProviderConfigPublic
from swx_core.repositories import notification_repository
from swx_core.security.encryption import encrypt_value, decrypt_value, is_encrypted
from swx_core.services.llm.config_resolver import mask_api_key
from swx_core.services.notifications import provider_factory
from swx_core.services.notifications.provider_cache import invalidate_provider_cache
from swx_core.services.notifications.template_service import invalidate_template_cache
from swx_core.utils.time import utc_now


def _encrypt_field(plaintext: str | None) -> str | None:
    if not plaintext:
        return plaintext
    try:
        return encrypt_value(plaintext)
    except Exception:
        return plaintext


def _decrypt_field(ciphertext: str | None) -> str | None:
    if not ciphertext or not is_encrypted(ciphertext):
        return ciphertext
    try:
        return decrypt_value(ciphertext)
    except Exception:
        return ciphertext


def _mask(value: str | None) -> str | None:
    return mask_api_key(value) if value else None


def _email_public(config: Any) -> EmailProviderConfigPublic:
    data = config.model_dump()
    data["password"] = _mask(_decrypt_field(config.password))
    data["api_key"] = _mask(_decrypt_field(config.api_key))
    return EmailProviderConfigPublic.model_validate(data)


def _sms_public(config: Any) -> SMSProviderConfigPublic:
    data = config.model_dump()
    data["auth_token"] = _mask(_decrypt_field(config.auth_token))
    data["api_key"] = _mask(_decrypt_field(config.api_key))
    return SMSProviderConfigPublic.model_validate(data)


async def list_email_providers(session: AsyncSession) -> list[EmailProviderConfigPublic]:
    providers = await notification_repository.list_email_provider_configs(session)
    return [_email_public(provider) for provider in providers]


async def upsert_email_provider(session: AsyncSession, data: EmailProviderConfigCreate) -> EmailProviderConfigPublic:
    payload = data.model_dump()
    if payload.get("password"):
        payload["password"] = _encrypt_field(payload["password"])
    if payload.get("api_key"):
        payload["api_key"] = _encrypt_field(payload["api_key"])
    config = await notification_repository.upsert_email_provider_config(session, payload)
    invalidate_provider_cache()
    await event_bus.dispatch("notification.email_provider.upserted", payload={"provider_id": str(config.id), "name": config.name})
    return _email_public(config)


async def list_sms_providers(session: AsyncSession) -> list[SMSProviderConfigPublic]:
    providers = await notification_repository.list_sms_provider_configs(session)
    return [_sms_public(provider) for provider in providers]


async def upsert_sms_provider(session: AsyncSession, data: SMSProviderConfigCreate) -> SMSProviderConfigPublic:
    payload = data.model_dump()
    if payload.get("auth_token"):
        payload["auth_token"] = _encrypt_field(payload["auth_token"])
    if payload.get("api_key"):
        payload["api_key"] = _encrypt_field(payload["api_key"])
    config = await notification_repository.upsert_sms_provider_config(session, payload)
    invalidate_provider_cache()
    await event_bus.dispatch("notification.sms_provider.upserted", payload={"provider_id": str(config.id), "name": config.name})
    return _sms_public(config)


async def list_templates(session: AsyncSession) -> list[NotificationTemplatePublic]:
    templates = await notification_repository.list_notification_templates(session)
    return [NotificationTemplatePublic.model_validate(template) for template in templates]


async def upsert_template(session: AsyncSession, data: NotificationTemplateCreate) -> NotificationTemplatePublic:
    template = await notification_repository.upsert_notification_template(session, data.model_dump())
    invalidate_template_cache()
    await event_bus.dispatch("notification.template.upserted", payload={"template_id": str(template.id), "key": template.key})
    return NotificationTemplatePublic.model_validate(template)


async def get_user_preferences(session: AsyncSession, user_id: UUID) -> NotificationPreferencePublic | None:
    preference = await notification_repository.get_user_notification_preference(session, user_id)
    return NotificationPreferencePublic.model_validate(preference) if preference else None


async def update_user_preferences(session: AsyncSession, user_id: UUID, data: NotificationPreferenceUpdate) -> NotificationPreferencePublic:
    preference = await notification_repository.upsert_user_notification_preference(session, user_id, data.model_dump(exclude_unset=True))
    await event_bus.dispatch("notification.preference.updated", payload={"preference_id": str(preference.id), "user_id": str(user_id)})
    return NotificationPreferencePublic.model_validate(preference)


async def test_email_provider(session: AsyncSession, provider_name: str) -> dict[str, Any]:
    providers = await notification_repository.list_email_provider_configs(session)
    provider = next((item for item in providers if item.name == provider_name), None)
    if provider is None:
        return {"provider_name": provider_name, "success": False, "status": "not_found"}
    test_address = provider.reply_to or settings.NOTIFICATION_SUPPORT_EMAIL or provider.from_email
    payload = {
        "to": test_address,
        "subject": f"Health check for {provider.name}",
        "body": f"Provider {provider.name} health check at {utc_now().isoformat()}",
    }
    try:
        resolved_provider, response = await provider_factory.send_via_email(session, payload, preferred_provider=provider.name)
        return {
            "provider_name": resolved_provider.name,
            "success": True,
            "status": "ok",
            "response": response,
            "test_address": test_address,
        }
    except RuntimeError as exc:
        return {
            "provider_name": provider.name,
            "success": False,
            "status": "failed",
            "error": str(exc),
            "test_address": test_address,
        }


async def get_provider_statistics(session: AsyncSession, days: int = 30) -> list[dict[str, Any]]:
    start_date = utc_now() - timedelta(days=days)
    notifications = await notification_repository.list_notifications(session, start_date=start_date, limit=100000)
    statistics_by_provider: dict[str, dict[str, Any]] = {}
    for notification in notifications:
        provider_name = notification.provider_name or "unassigned"
        provider_stats = statistics_by_provider.setdefault(
            provider_name,
            {
                "provider_name": provider_name,
                "total_count": 0,
                "queued_count": 0,
                "sent_count": 0,
                "delivered_count": 0,
                "failed_count": 0,
                "first_sent_at": None,
                "last_sent_at": None,
            },
        )
        provider_stats["total_count"] = int(provider_stats["total_count"]) + 1
        status_key = f"{notification.status}_count"
        if status_key in provider_stats:
            provider_stats[status_key] = int(provider_stats[status_key]) + 1
        if notification.sent_at is not None:
            first_sent_at = provider_stats["first_sent_at"]
            last_sent_at = provider_stats["last_sent_at"]
            if first_sent_at is None or notification.sent_at < first_sent_at:
                provider_stats["first_sent_at"] = notification.sent_at
            if last_sent_at is None or notification.sent_at > last_sent_at:
                provider_stats["last_sent_at"] = notification.sent_at
    return [statistics_by_provider[name] for name in sorted(statistics_by_provider)]
