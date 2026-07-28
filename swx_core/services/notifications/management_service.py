from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.models.email_provider_config import EmailProviderConfigCreate, EmailProviderConfigPublic
from swx_core.models.notification_preference import NotificationPreferencePublic, NotificationPreferenceUpdate
from swx_core.models.notification_template import NotificationTemplateCreate, NotificationTemplatePublic
from swx_core.models.sms_provider_config import SMSProviderConfigCreate, SMSProviderConfigPublic
from swx_core.repositories import notification_repository
from swx_core.services.llm.config_resolver import mask_api_key
from swx_core.services.notifications.provider_cache import invalidate_provider_cache
from swx_core.services.notifications.template_service import invalidate_template_cache


def _mask(value: str | None) -> str | None:
    return mask_api_key(value) if value else None


def _email_public(config: Any) -> EmailProviderConfigPublic:
    data = config.model_dump()
    data["password"] = _mask(config.password)
    data["api_key"] = _mask(config.api_key)
    return EmailProviderConfigPublic.model_validate(data)


def _sms_public(config: Any) -> SMSProviderConfigPublic:
    data = config.model_dump()
    data["auth_token"] = _mask(config.auth_token)
    data["api_key"] = _mask(config.api_key)
    return SMSProviderConfigPublic.model_validate(data)


async def list_email_providers(session: AsyncSession) -> list[EmailProviderConfigPublic]:
    providers = await notification_repository.list_email_provider_configs(session)
    return [_email_public(provider) for provider in providers]


async def upsert_email_provider(session: AsyncSession, data: EmailProviderConfigCreate) -> EmailProviderConfigPublic:
    config = await notification_repository.upsert_email_provider_config(session, data.model_dump())
    invalidate_provider_cache()
    await event_bus.dispatch("notification.email_provider.upserted", payload={"provider_id": str(config.id), "name": config.name})
    return _email_public(config)


async def list_sms_providers(session: AsyncSession) -> list[SMSProviderConfigPublic]:
    providers = await notification_repository.list_sms_provider_configs(session)
    return [_sms_public(provider) for provider in providers]


async def upsert_sms_provider(session: AsyncSession, data: SMSProviderConfigCreate) -> SMSProviderConfigPublic:
    config = await notification_repository.upsert_sms_provider_config(session, data.model_dump())
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
