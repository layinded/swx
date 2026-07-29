from datetime import datetime
from typing import Any
from uuid import UUID
from swx_core.utils.time import utc_now

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.models.email_provider_config import EmailProviderConfig
from swx_core.models.notification import Notification
from swx_core.models.notification_preference import NotificationPreference
from swx_core.models.notification_template import NotificationTemplate
from swx_core.models.sms_provider_config import SMSProviderConfig
from swx_core.models.user import User

def _apply(instance: Any, data: dict[str, Any]) -> Any:
    for key, value in data.items():
        setattr(instance, key, value)
    return instance

def _apply_filters(stmt: Any, model: type[Any], filters: dict[str, Any]) -> Any:
    for field, value in filters.items():
        if value is not None:
            stmt = stmt.where(getattr(model, field) == value)
    return stmt

async def _get_by_id(session: AsyncSession, model: type[Any], item_id: UUID) -> Any | None:
    return await session.get(model, item_id)

async def _list(session: AsyncSession, model: type[Any], order_by: tuple[str, ...]) -> list[Any]:
    stmt = select(model)
    for field in order_by:
        stmt = stmt.order_by(getattr(model, field))
    return list((await session.execute(stmt)).scalars().all())

def _notification_filters(
    *,
    user_id: UUID | None = None,
    status: str | None = None,
    channel: str | None = None,
    notification_type: str | None = None,
) -> dict[str, Any]:
    return {"user_id": user_id, "status": status, "channel": channel, "notification_type": notification_type}

async def _upsert_by(session: AsyncSession, model: type[Any], field: str, value: Any, data: dict[str, Any]) -> Any:
    stmt = select(model).where(getattr(model, field) == value)
    instance = (await session.execute(stmt)).scalar_one_or_none()
    entity = model(**data) if instance is None else _apply(instance, {**data, "updated_at": utc_now()})
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return entity

async def _delete(session: AsyncSession, model: type[Any], item_id: UUID) -> bool:
    instance = await _get_by_id(session, model, item_id)
    if instance is None:
        return False
    await session.delete(instance)
    await session.commit()
    return True

async def list_email_provider_configs(session: AsyncSession) -> list[EmailProviderConfig]:
    return await _list(session, EmailProviderConfig, ("priority", "name"))

async def upsert_email_provider_config(session: AsyncSession, data: dict[str, Any]) -> EmailProviderConfig:
    return await _upsert_by(session, EmailProviderConfig, "name", data["name"], data)

async def delete_email_provider_config(session: AsyncSession, item_id: UUID) -> bool:
    return await _delete(session, EmailProviderConfig, item_id)

async def get_active_email_providers(session: AsyncSession) -> list[EmailProviderConfig]:
    stmt = select(EmailProviderConfig).where(EmailProviderConfig.is_active == True).order_by(EmailProviderConfig.priority, EmailProviderConfig.name)  # pyright: ignore[reportArgumentType]
    return list((await session.execute(stmt)).scalars().all())

async def list_sms_provider_configs(session: AsyncSession) -> list[SMSProviderConfig]:
    return await _list(session, SMSProviderConfig, ("priority", "name"))

async def upsert_sms_provider_config(session: AsyncSession, data: dict[str, Any]) -> SMSProviderConfig:
    return await _upsert_by(session, SMSProviderConfig, "name", data["name"], data)

async def delete_sms_provider_config(session: AsyncSession, item_id: UUID) -> bool:
    return await _delete(session, SMSProviderConfig, item_id)

async def get_active_sms_providers(session: AsyncSession) -> list[SMSProviderConfig]:
    stmt = select(SMSProviderConfig).where(SMSProviderConfig.is_active == True).order_by(SMSProviderConfig.priority, SMSProviderConfig.name)  # pyright: ignore[reportArgumentType]
    return list((await session.execute(stmt)).scalars().all())

async def create_notification(session: AsyncSession, data: dict[str, Any]) -> Notification:
    instance = Notification(**data)
    session.add(instance)
    await session.commit()
    await session.refresh(instance)
    return instance

async def get_notification_by_id(session: AsyncSession, notification_id: UUID) -> Notification | None:
    return await _get_by_id(session, Notification, notification_id)

async def list_notifications(session: AsyncSession, *, user_id: UUID | None = None, status: str | None = None, channel: str | None = None, notification_type: str | None = None, start_date: datetime | None = None, end_date: datetime | None = None, skip: int = 0, limit: int = 100) -> list[Notification]:
    stmt = select(Notification)
    stmt = _apply_filters(stmt, Notification, _notification_filters(user_id=user_id, status=status, channel=channel, notification_type=notification_type))
    if start_date is not None:
        stmt = stmt.where(Notification.created_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(Notification.created_at <= end_date)
    created_at_column = getattr(Notification, "created_at")
    stmt = stmt.order_by(created_at_column.desc()).offset(skip).limit(limit)
    return list((await session.execute(stmt)).scalars().all())

async def count_notifications(session: AsyncSession, *, user_id: UUID | None = None, status: str | None = None, channel: str | None = None, notification_type: str | None = None, start_date: datetime | None = None, end_date: datetime | None = None) -> int:
    stmt = select(func.count()).select_from(Notification)
    stmt = _apply_filters(stmt, Notification, _notification_filters(user_id=user_id, status=status, channel=channel, notification_type=notification_type))
    if start_date is not None:
        stmt = stmt.where(Notification.created_at >= start_date)
    if end_date is not None:
        stmt = stmt.where(Notification.created_at <= end_date)
    return int((await session.execute(stmt)).scalar() or 0)

async def update_notification(session: AsyncSession, notification_id: UUID, data: dict[str, Any]) -> Notification | None:
    instance = await get_notification_by_id(session, notification_id)
    if instance is None:
        return None
    session.add(_apply(instance, {**data, "updated_at": utc_now()}))
    await session.commit()
    await session.refresh(instance)
    return instance

async def delete_notification(session: AsyncSession, notification_id: UUID) -> bool:
    return await _delete(session, Notification, notification_id)

async def get_user_notification_preference(session: AsyncSession, user_id: UUID) -> NotificationPreference | None:
    stmt = select(NotificationPreference).where(NotificationPreference.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()

async def upsert_user_notification_preference(session: AsyncSession, user_id: UUID, data: dict[str, Any]) -> NotificationPreference:
    return await _upsert_by(session, NotificationPreference, "user_id", user_id, {**data, "user_id": user_id})

async def list_notification_templates(session: AsyncSession) -> list[NotificationTemplate]:
    return await _list(session, NotificationTemplate, ("channel", "key"))

async def get_template_by_key(session: AsyncSession, key: str) -> NotificationTemplate | None:
    stmt = select(NotificationTemplate).where(NotificationTemplate.key == key)
    return (await session.execute(stmt)).scalar_one_or_none()

async def upsert_notification_template(session: AsyncSession, data: dict[str, Any]) -> NotificationTemplate:
    return await _upsert_by(session, NotificationTemplate, "key", data["key"], data)

async def delete_notification_template(session: AsyncSession, item_id: UUID) -> bool:
    return await _delete(session, NotificationTemplate, item_id)

async def list_users_for_notification(session: AsyncSession, user_ids: list[UUID] | None = None) -> list[User]:
    stmt = select(User).where(User.is_active == True)  # pyright: ignore[reportArgumentType]
    if user_ids:
        stmt = stmt.where(getattr(User, "id").in_(user_ids))  # pyright: ignore[reportArgumentType]
    return list((await session.execute(stmt.order_by(getattr(User, "created_at")))).scalars().all())
