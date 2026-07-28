from uuid import UUID

from fastapi import APIRouter, Query

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers import notification_controller
from swx_core.database.db import SessionDep
from swx_core.models.notification import NotificationPublic
from swx_core.models.notification_preference import NotificationPreferencePublic, NotificationPreferenceUpdate

router = APIRouter(prefix="/user/notifications", tags=["user-notifications"])


@router.get("", response_model=list[NotificationPublic])
async def list_notifications(session: SessionDep, current_user: UserDep, status: str | None = None, channel: str | None = None, notification_type: str | None = None, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)) -> list[NotificationPublic]:
    return await notification_controller.list_user_notifications_controller(session, user_id=current_user.id, status=status, channel=channel, notification_type=notification_type, skip=skip, limit=limit)


@router.get("/preferences", response_model=NotificationPreferencePublic | None)
async def get_preferences(session: SessionDep, current_user: UserDep) -> NotificationPreferencePublic | None:
    return await notification_controller.get_user_preferences_controller(session, current_user.id)


@router.put("/preferences", response_model=NotificationPreferencePublic)
async def update_preferences(session: SessionDep, body: NotificationPreferenceUpdate, current_user: UserDep) -> NotificationPreferencePublic:
    return await notification_controller.update_user_preferences_controller(session, current_user.id, body)


@router.get("/{notification_id}", response_model=NotificationPublic)
async def get_notification_status(session: SessionDep, notification_id: UUID, current_user: UserDep) -> NotificationPublic:
    return await notification_controller.get_notification_status_controller(session, notification_id, current_user.id)
