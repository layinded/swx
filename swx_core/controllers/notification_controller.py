from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.email_provider_config import EmailProviderConfigCreate, EmailProviderConfigPublic
from swx_core.models.notification import NotificationPublic
from swx_core.models.notification_preference import NotificationPreferencePublic, NotificationPreferenceUpdate
from swx_core.models.notification_template import NotificationTemplateCreate, NotificationTemplatePublic
from swx_core.models.sms_provider_config import SMSProviderConfigCreate, SMSProviderConfigPublic
from swx_core.services.notifications import notification_service
from swx_core.services.notifications import management_service


async def send_notification_controller(session: AsyncSession, **kwargs: Any) -> NotificationPublic:
    return await notification_service.send_notification(session, **kwargs)


async def list_user_notifications_controller(session: AsyncSession, *, user_id: UUID | None = None, status: str | None = None, channel: str | None = None, notification_type: str | None = None, skip: int = 0, limit: int = 100) -> list[NotificationPublic]:
    return await notification_service.list_user_notifications(session, user_id=user_id, status=status, channel=channel, notification_type=notification_type, skip=skip, limit=limit)


async def get_notification_status_controller(session: AsyncSession, notification_id: UUID, user_id: UUID | None = None) -> NotificationPublic:
    return await notification_service.get_notification_status(session, notification_id, user_id)


async def list_email_providers_controller(session: AsyncSession) -> list[EmailProviderConfigPublic]:
    return await management_service.list_email_providers(session)


async def upsert_email_provider_controller(session: AsyncSession, data: EmailProviderConfigCreate) -> EmailProviderConfigPublic:
    return await management_service.upsert_email_provider(session, data)


async def list_sms_providers_controller(session: AsyncSession) -> list[SMSProviderConfigPublic]:
    return await management_service.list_sms_providers(session)


async def upsert_sms_provider_controller(session: AsyncSession, data: SMSProviderConfigCreate) -> SMSProviderConfigPublic:
    return await management_service.upsert_sms_provider(session, data)


async def list_templates_controller(session: AsyncSession) -> list[NotificationTemplatePublic]:
    return await management_service.list_templates(session)


async def upsert_template_controller(session: AsyncSession, data: NotificationTemplateCreate) -> NotificationTemplatePublic:
    return await management_service.upsert_template(session, data)


async def get_user_preferences_controller(session: AsyncSession, user_id: UUID) -> NotificationPreferencePublic | None:
    return await management_service.get_user_preferences(session, user_id)


async def update_user_preferences_controller(session: AsyncSession, user_id: UUID, data: NotificationPreferenceUpdate) -> NotificationPreferencePublic:
    return await management_service.update_user_preferences(session, user_id, data)
