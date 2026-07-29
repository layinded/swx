from datetime import datetime, timedelta
import importlib
from typing import Any
from uuid import UUID
from swx_core.utils.time import utc_now

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import NOTIFICATION_ENABLED, NOTIFICATION_RATE_LIMIT_DAILY, NOTIFICATION_RATE_LIMIT_HOURLY
from swx_core.config.settings import settings
from swx_core.events.dispatcher import event_bus
from swx_core.middleware.logging_middleware import logger
from swx_core.models.notification import Notification, NotificationPublic
from swx_core.models.notification_preference import NotificationPreferencePublic
from swx_core.models.user import User
from swx_core.repositories import notification_repository, user_repository
from swx_core.services.notifications import delivery_tracker, provider_factory, template_service

def _allowed(preferences: NotificationPreferencePublic | None, channel: str) -> bool:
    if preferences is None:
        return channel in {"email", "in_app"}
    return bool(getattr(preferences, f"{channel}_enabled", False))

def _in_quiet_hours(preferences: NotificationPreferencePublic | None) -> bool:
    if preferences is None or not preferences.quiet_hours_start or not preferences.quiet_hours_end:
        return False
    current = utc_now().strftime("%H:%M")
    start, end = preferences.quiet_hours_start, preferences.quiet_hours_end
    return start <= current <= end if start <= end else current >= start or current <= end

async def _preferences(session: AsyncSession, user_id: UUID) -> NotificationPreferencePublic | None:
    prefs = await notification_repository.get_user_notification_preference(session, user_id)
    return NotificationPreferencePublic.model_validate(prefs) if prefs else None

async def _require_user(session: AsyncSession, user_id: UUID) -> User:
    user = await user_repository.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

async def _check_rate_limit(session: AsyncSession, user_id: UUID) -> None:
    now = utc_now()
    hourly_window_start = now - timedelta(hours=1)
    daily_window_start = now - timedelta(days=1)
    if await notification_repository.count_notifications(session, user_id=user_id, start_date=hourly_window_start) >= NOTIFICATION_RATE_LIMIT_HOURLY:
        raise HTTPException(status_code=429, detail="Hourly notification limit exceeded")
    if await notification_repository.count_notifications(session, user_id=user_id, start_date=daily_window_start) >= NOTIFICATION_RATE_LIMIT_DAILY:
        raise HTTPException(status_code=429, detail="Daily notification limit exceeded")

async def _deliver(session: AsyncSession, notification_id: UUID, channel: str, payload: dict[str, Any]) -> NotificationPublic:
    if channel == "email":
        provider, response = await provider_factory.send_via_email(session, payload)
    elif channel == "sms":
        provider, response = await provider_factory.send_via_sms(session, payload)
    else:
        provider, response = None, {"provider": channel, "accepted": True}
    await delivery_tracker.record_provider_response(session, notification_id, response)
    sent = await delivery_tracker.update_notification_status(session, notification_id, "sent", provider_config_id=getattr(provider, "id", None), provider_name=getattr(provider, "name", channel), sent_at=utc_now())
    return await delivery_tracker.update_notification_status(session, sent.id, "delivered", delivered_at=utc_now())


async def _deliver_existing_notification(session: AsyncSession, tracked: Notification | NotificationPublic) -> NotificationPublic:
    preferences = await _preferences(session, tracked.user_id)
    if not _allowed(preferences, tracked.channel):
        raise HTTPException(status_code=403, detail=f"{tracked.channel} notifications disabled")
    if _in_quiet_hours(preferences):
        raise HTTPException(status_code=429, detail="Notification blocked by quiet hours")
    await _check_rate_limit(session, tracked.user_id)
    user = await _require_user(session, tracked.user_id)
    queued_payload = tracked.provider_response.get("queued_payload")
    payload = {
        "to": queued_payload.get("to") if isinstance(queued_payload, dict) and queued_payload.get("to") else user.email,
        "subject": tracked.subject,
        "body": tracked.body,
    }
    if isinstance(queued_payload, dict):
        for key in ("country", "preferred_provider"):
            value = queued_payload.get(key)
            if isinstance(value, str) and value:
                payload[key] = value
    delivered = await _deliver(session, tracked.id, tracked.channel, payload)
    await event_bus.dispatch("notification.sent", payload={"notification_id": str(delivered.id), "provider_name": delivered.provider_name, "channel": delivered.channel})
    return delivered


async def deliver_notification_by_id(session: AsyncSession, notification_id: UUID) -> NotificationPublic:
    tracked = await notification_repository.get_notification_by_id(session, notification_id)
    if tracked is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    try:
        return await _deliver_existing_notification(session, tracked)
    except Exception as exc:  # noqa: BLE001
        await delivery_tracker.record_provider_response(session, tracked.id, {"error": str(exc)})
        failed = await delivery_tracker.update_notification_status(session, tracked.id, "failed")
        await event_bus.dispatch("notification.failed", payload={"notification_id": str(failed.id), "error": str(exc), "channel": failed.channel})
        raise

async def send_notification(session: AsyncSession, *, user_id: UUID, channel: str, notification_type: str, template_key: str | None = None, context: dict[str, Any] | None = None, subject: str | None = None, body: str | None = None, recipient: str | None = None, scheduled_at: datetime | None = None, queue: bool = False) -> NotificationPublic:
    if not NOTIFICATION_ENABLED:
        raise HTTPException(status_code=503, detail="Notifications are disabled")
    user = await _require_user(session, user_id)
    template_data = await template_service.render_template(session, template_key, context or {}) if template_key else {"channel": channel, "subject": subject, "body": body}
    resolved_channel = str(template_data.get("channel") or channel)
    payload = {"to": recipient or user.email, "subject": template_data.get("subject"), "body": template_data.get("body") or body or ""}
    tracked = await delivery_tracker.track_notification(
        session,
        {"user_id": user_id, "channel": resolved_channel, "notification_type": notification_type, "subject": payload["subject"], "body": payload["body"], "status": "queued", "scheduled_at": scheduled_at},
    )
    await event_bus.dispatch("notification.send_requested", payload={"notification_id": str(tracked.id), "user_id": str(user_id), "channel": resolved_channel})
    try:
        if queue:
            await delivery_tracker.record_provider_response(session, tracked.id, {"queued_payload": payload})
            try:
                celery_module = importlib.import_module("celery")
                current_app = getattr(celery_module, "current_app")
                send_task = getattr(current_app, "send_task")
                send_task(settings.NOTIFICATION_CELERY_TASK_PATH, args=[str(tracked.id)], kwargs={})
                refreshed = await notification_repository.get_notification_by_id(session, tracked.id)
                return NotificationPublic.model_validate(refreshed or tracked)
            except ImportError:
                logger.warning("Celery not installed, falling back to synchronous send")
        return await _deliver_existing_notification(session, tracked)
    except Exception as exc:  # noqa: BLE001
        await delivery_tracker.record_provider_response(session, tracked.id, {"error": str(exc)})
        failed = await delivery_tracker.update_notification_status(session, tracked.id, "failed")
        await event_bus.dispatch("notification.failed", payload={"notification_id": str(failed.id), "error": str(exc), "channel": failed.channel})
        raise

async def send_notification_to_user(session: AsyncSession, user_id: UUID, **kwargs: Any) -> NotificationPublic:
    return await send_notification(session, user_id=user_id, **kwargs)

async def broadcast_notification(session: AsyncSession, *, user_ids: list[UUID] | None = None, **kwargs: Any) -> list[NotificationPublic]:
    await event_bus.dispatch("notification.broadcast_requested", payload={"user_count": len(user_ids or []) if user_ids else None, "channel": kwargs.get("channel")})
    sent: list[NotificationPublic] = []
    for user in await notification_repository.list_users_for_notification(session, user_ids):
        sent.append(await send_notification(session, user_id=user.id, **kwargs))
    return sent

async def get_notification_status(session: AsyncSession, notification_id: UUID, user_id: UUID | None = None) -> NotificationPublic:
    notification = await delivery_tracker.get_notification(session, notification_id)
    if notification is None or (user_id is not None and notification.user_id != user_id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return NotificationPublic.model_validate(notification)

async def list_user_notifications(session: AsyncSession, *, user_id: UUID | None = None, status: str | None = None, channel: str | None = None, notification_type: str | None = None, skip: int = 0, limit: int = 100) -> list[NotificationPublic]:
    items = await notification_repository.list_notifications(session, user_id=user_id, status=status, channel=channel, notification_type=notification_type, skip=skip, limit=limit)
    return [NotificationPublic.model_validate(item) for item in items]
