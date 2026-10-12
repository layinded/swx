from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from swx_core.auth.user.dependencies import UserDep
from swx_core.controllers import webhook_controller
from swx_core.database.db import SessionDep
from swx_core.models.webhook_delivery import WebhookDeliveryPublic
from swx_core.models.webhook_endpoint import WebhookEndpointCreate, WebhookEndpointPublic, WebhookEndpointUpdate
from swx_core.models.webhook_event import WebhookEventSubscriptionPublic


class WebhookEventRequest(BaseModel):
    event_types: list[str] = Field(default_factory=list)


router = APIRouter(prefix="/user/webhooks", tags=["user-webhooks"])


@router.get("/endpoints", response_model=list[WebhookEndpointPublic])
async def list_endpoints(session: SessionDep, current_user: UserDep, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)) -> list[WebhookEndpointPublic]:
    return await webhook_controller.list_endpoints_controller(session, current_user.id, skip, limit)


@router.post("/endpoints", response_model=WebhookEndpointPublic, status_code=201)
async def create_endpoint(session: SessionDep, body: WebhookEndpointCreate, current_user: UserDep) -> WebhookEndpointPublic:
    return await webhook_controller.create_endpoint_controller(session, current_user.id, body)


@router.get("/endpoints/{endpoint_id}", response_model=WebhookEndpointPublic)
async def get_endpoint(session: SessionDep, endpoint_id: UUID, current_user: UserDep) -> WebhookEndpointPublic:
    return await webhook_controller.get_endpoint_controller(session, endpoint_id, current_user.id)


@router.put("/endpoints/{endpoint_id}", response_model=WebhookEndpointPublic)
async def update_endpoint(session: SessionDep, endpoint_id: UUID, body: WebhookEndpointUpdate, current_user: UserDep) -> WebhookEndpointPublic:
    return await webhook_controller.update_endpoint_controller(session, endpoint_id, body, current_user.id)


@router.delete("/endpoints/{endpoint_id}", response_model=WebhookEndpointPublic)
async def delete_endpoint(session: SessionDep, endpoint_id: UUID, current_user: UserDep) -> WebhookEndpointPublic:
    return await webhook_controller.delete_endpoint_controller(session, endpoint_id, current_user.id)


@router.post("/endpoints/{endpoint_id}/subscribe", response_model=list[WebhookEventSubscriptionPublic])
async def subscribe(session: SessionDep, endpoint_id: UUID, body: WebhookEventRequest, current_user: UserDep) -> list[WebhookEventSubscriptionPublic]:
    return await webhook_controller.subscribe_controller(session, endpoint_id, body.event_types, current_user.id)


@router.post("/endpoints/{endpoint_id}/unsubscribe", response_model=list[WebhookEventSubscriptionPublic])
async def unsubscribe(session: SessionDep, endpoint_id: UUID, body: WebhookEventRequest, current_user: UserDep) -> list[WebhookEventSubscriptionPublic]:
    return await webhook_controller.unsubscribe_controller(session, endpoint_id, body.event_types, current_user.id)


@router.get("/deliveries", response_model=list[WebhookDeliveryPublic])
async def list_deliveries(session: SessionDep, current_user: UserDep, endpoint_id: UUID | None = None, status: str | None = None, skip: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=1000)) -> list[WebhookDeliveryPublic]:
    return await webhook_controller.list_deliveries_controller(session, user_id=current_user.id, endpoint_id=endpoint_id, status=status, skip=skip, limit=limit)


@router.post("/deliveries/{delivery_id}/retry", response_model=WebhookDeliveryPublic)
async def retry_delivery(session: SessionDep, delivery_id: UUID, current_user: UserDep) -> WebhookDeliveryPublic:
    return await webhook_controller.retry_delivery_controller(session, delivery_id, current_user.id)
