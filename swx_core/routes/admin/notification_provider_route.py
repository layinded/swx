from fastapi import APIRouter, Depends, Query

from swx_core.auth.admin.dependencies import get_current_admin_user
from swx_core.controllers import notification_controller
from swx_core.database.db import SessionDep
from swx_core.models.email_provider_config import EmailProviderConfigCreate, EmailProviderConfigPublic
from swx_core.models.notification import NotificationPublic
from swx_core.models.notification_template import NotificationTemplateCreate, NotificationTemplatePublic
from swx_core.models.sms_provider_config import SMSProviderConfigCreate, SMSProviderConfigPublic

router = APIRouter(prefix="/admin/notifications", tags=["admin-notifications"], dependencies=[Depends(get_current_admin_user)])


@router.get("/providers/email", response_model=list[EmailProviderConfigPublic])
async def list_email_providers(session: SessionDep) -> list[EmailProviderConfigPublic]:
    return await notification_controller.list_email_providers_controller(session)


@router.put("/providers/email", response_model=EmailProviderConfigPublic)
async def upsert_email_provider(session: SessionDep, body: EmailProviderConfigCreate) -> EmailProviderConfigPublic:
    return await notification_controller.upsert_email_provider_controller(session, body)


@router.get("/providers/sms", response_model=list[SMSProviderConfigPublic])
async def list_sms_providers(session: SessionDep) -> list[SMSProviderConfigPublic]:
    return await notification_controller.list_sms_providers_controller(session)


@router.put("/providers/sms", response_model=SMSProviderConfigPublic)
async def upsert_sms_provider(session: SessionDep, body: SMSProviderConfigCreate) -> SMSProviderConfigPublic:
    return await notification_controller.upsert_sms_provider_controller(session, body)


@router.get("/templates", response_model=list[NotificationTemplatePublic])
async def list_templates(session: SessionDep) -> list[NotificationTemplatePublic]:
    return await notification_controller.list_templates_controller(session)


@router.put("/templates", response_model=NotificationTemplatePublic)
async def upsert_template(session: SessionDep, body: NotificationTemplateCreate) -> NotificationTemplatePublic:
    return await notification_controller.upsert_template_controller(session, body)


@router.get("", response_model=list[NotificationPublic])
async def list_notifications(session: SessionDep, status: str | None = None, channel: str | None = None, notification_type: str | None = None, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)) -> list[NotificationPublic]:
    return await notification_controller.list_user_notifications_controller(session, status=status, channel=channel, notification_type=notification_type, skip=skip, limit=limit)
