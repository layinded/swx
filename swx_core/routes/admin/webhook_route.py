from fastapi import APIRouter, Depends, Query
from uuid import UUID

from swx_core.auth.admin.dependencies import get_current_admin_user
from swx_core.controllers import webhook_controller
from swx_core.database.db import SessionDep
from swx_core.models.webhook_delivery import WebhookDeliveryPublic
from swx_core.models.webhook_endpoint import WebhookEndpointPublic

router = APIRouter(prefix="/admin/webhooks", tags=["admin-webhooks"], dependencies=[Depends(get_current_admin_user)])


@router.get("/endpoints", response_model=list[WebhookEndpointPublic])
async def list_endpoints(session: SessionDep, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)) -> list[WebhookEndpointPublic]:
    return await webhook_controller.list_endpoints_controller(session, skip=skip, limit=limit)


@router.get("/endpoints/{endpoint_id}", response_model=WebhookEndpointPublic)
async def get_endpoint(session: SessionDep, endpoint_id: UUID) -> WebhookEndpointPublic:
    return await webhook_controller.get_endpoint_controller(session, endpoint_id)


@router.delete("/endpoints/{endpoint_id}", response_model=WebhookEndpointPublic)
async def delete_endpoint(session: SessionDep, endpoint_id: UUID) -> WebhookEndpointPublic:
    return await webhook_controller.delete_endpoint_controller(session, endpoint_id)


@router.get("/deliveries", response_model=list[WebhookDeliveryPublic])
async def list_deliveries(session: SessionDep, status: str | None = None, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)) -> list[WebhookDeliveryPublic]:
    return await webhook_controller.list_deliveries_controller(session, status=status, skip=skip, limit=limit)
