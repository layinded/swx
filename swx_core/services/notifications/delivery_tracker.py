from typing import Any
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.events.dispatcher import event_bus
from swx_core.models.notification import Notification, NotificationPublic
from swx_core.repositories import notification_repository


async def track_notification(session: AsyncSession, data: dict[str, object]) -> NotificationPublic:
    notification = await notification_repository.create_notification(session, data)
    await event_bus.dispatch(
        "notification.created",
        payload={"notification_id": str(notification.id), "user_id": str(notification.user_id), "channel": notification.channel, "type": notification.notification_type},
    )
    return NotificationPublic.model_validate(notification)


def _status_update_data(
    status: str,
    *,
    provider_config_id: UUID | None = None,
    provider_name: str | None = None,
    sent_at: datetime | None = None,
    delivered_at: datetime | None = None,
    retry_count: int | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {"status": status}
    for key, value in {
        "provider_config_id": provider_config_id,
        "provider_name": provider_name,
        "sent_at": sent_at,
        "delivered_at": delivered_at,
        "retry_count": retry_count,
    }.items():
        if value is not None:
            data[key] = value
    return data


async def update_notification_status(session: AsyncSession, notification_id: UUID, status: str, *, provider_config_id: UUID | None = None, provider_name: str | None = None, sent_at: datetime | None = None, delivered_at: datetime | None = None, retry_count: int | None = None) -> NotificationPublic:
    notification = await notification_repository.update_notification(
        session,
        notification_id,
        _status_update_data(
            status,
            provider_config_id=provider_config_id,
            provider_name=provider_name,
            sent_at=sent_at,
            delivered_at=delivered_at,
            retry_count=retry_count,
        ),
    )
    if notification is None:
        raise ValueError("Notification not found")
    await event_bus.dispatch("notification.status_updated", payload={"notification_id": str(notification.id), "status": status, "provider_name": provider_name})
    return NotificationPublic.model_validate(notification)


async def record_provider_response(session: AsyncSession, notification_id: UUID, provider_response: dict[str, Any]) -> NotificationPublic:
    notification = await notification_repository.update_notification(session, notification_id, {"provider_response": provider_response})
    if notification is None:
        raise ValueError("Notification not found")
    await event_bus.dispatch("notification.provider_response_recorded", payload={"notification_id": str(notification.id), "provider_name": notification.provider_name})
    return NotificationPublic.model_validate(notification)


async def get_notification(session: AsyncSession, notification_id: UUID) -> Notification | None:
    return await notification_repository.get_notification_by_id(session, notification_id)
