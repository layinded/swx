from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.models.webhook_delivery import WebhookDeliveryPublic
from swx_core.models.webhook_endpoint import WebhookEndpointCreate, WebhookEndpointPublic, WebhookEndpointUpdate
from swx_core.models.webhook_event import WebhookEventSubscriptionPublic
from swx_core.services.webhook import webhook_service


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    elif isinstance(exc, ValueError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


async def create_endpoint_controller(session: AsyncSession, user_id: UUID, body: WebhookEndpointCreate) -> WebhookEndpointPublic:
    return await webhook_service.create_endpoint(session, user_id, body)


async def update_endpoint_controller(session: AsyncSession, endpoint_id: UUID, body: WebhookEndpointUpdate, user_id: UUID | None = None) -> WebhookEndpointPublic:
    try:
        return await webhook_service.update_endpoint(session, endpoint_id, body, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def delete_endpoint_controller(session: AsyncSession, endpoint_id: UUID, user_id: UUID | None = None) -> WebhookEndpointPublic:
    try:
        return await webhook_service.delete_endpoint(session, endpoint_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def list_endpoints_controller(session: AsyncSession, user_id: UUID | None = None, skip: int = 0, limit: int = 100) -> list[WebhookEndpointPublic]:
    return await webhook_service.list_endpoints(session, user_id, skip, limit)


async def get_endpoint_controller(session: AsyncSession, endpoint_id: UUID, user_id: UUID | None = None) -> WebhookEndpointPublic:
    try:
        return await webhook_service.get_endpoint(session, endpoint_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def subscribe_controller(session: AsyncSession, endpoint_id: UUID, event_types: list[str], user_id: UUID | None = None) -> list[WebhookEventSubscriptionPublic]:
    try:
        return await webhook_service.subscribe_to_events(session, endpoint_id, event_types, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def unsubscribe_controller(session: AsyncSession, endpoint_id: UUID, event_types: list[str], user_id: UUID | None = None) -> list[WebhookEventSubscriptionPublic]:
    try:
        return await webhook_service.unsubscribe_from_events(session, endpoint_id, event_types, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def list_deliveries_controller(session: AsyncSession, *, user_id: UUID | None = None, endpoint_id: UUID | None = None, status: str | None = None, skip: int = 0, limit: int = 100) -> list[WebhookDeliveryPublic]:
    return await webhook_service.list_deliveries(session, user_id=user_id, endpoint_id=endpoint_id, status=status, skip=skip, limit=limit)


async def get_delivery_controller(session: AsyncSession, delivery_id: UUID, user_id: UUID | None = None) -> WebhookDeliveryPublic:
    try:
        return await webhook_service.get_delivery(session, delivery_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


async def retry_delivery_controller(session: AsyncSession, delivery_id: UUID, user_id: UUID | None = None) -> WebhookDeliveryPublic:
    try:
        return await webhook_service.retry_delivery(session, delivery_id, user_id)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
