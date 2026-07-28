# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnusedCallResult=false

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import WEBHOOK_DEFAULT_RETRY_COUNT, WEBHOOK_DEFAULT_RETRY_DELAY, WEBHOOK_DEFAULT_TIMEOUT, WEBHOOK_MAX_RETRIES
from swx_core.events.dispatcher import event_bus
from swx_core.models.webhook_delivery import WebhookDeliveryPublic
from swx_core.models.webhook_endpoint import WebhookEndpointCreate, WebhookEndpointPublic, WebhookEndpointUpdate
from swx_core.models.webhook_event import WebhookEventSubscriptionPublic
from swx_core.repositories import webhook_repository
from swx_core.services.llm.config_resolver import mask_api_key
import swx_core.services.webhook.webhook_dispatcher as webhook_dispatcher


def _endpoint_public(endpoint: Any) -> WebhookEndpointPublic:
    endpoint_data = endpoint.model_dump()
    endpoint_data["secret_masked"] = mask_api_key(endpoint.secret)
    return WebhookEndpointPublic.model_validate(endpoint_data)


async def _owned_endpoint(session: AsyncSession, endpoint_id: UUID, user_id: UUID | None = None):
    endpoint = await webhook_repository.get_webhook_endpoint_by_id(session, endpoint_id)
    if endpoint is None:
        raise ValueError("Webhook endpoint not found")
    if user_id is not None and endpoint.user_id != user_id:
        raise PermissionError("Webhook endpoint access denied")
    return endpoint


def _endpoint_defaults(data: dict[str, Any]) -> dict[str, Any]:
    retry_count = data.get("retry_count") or WEBHOOK_DEFAULT_RETRY_COUNT
    retry_delay_seconds = data.get("retry_delay_seconds") or WEBHOOK_DEFAULT_RETRY_DELAY
    timeout_seconds = data.get("timeout_seconds") or WEBHOOK_DEFAULT_TIMEOUT
    return {**data, "retry_count": min(retry_count, WEBHOOK_MAX_RETRIES), "retry_delay_seconds": retry_delay_seconds, "timeout_seconds": timeout_seconds}


async def _sync_event_types(session: AsyncSession, endpoint_id: UUID, event_types: list[str], enabled: bool) -> list[WebhookEventSubscriptionPublic]:
    saved = await webhook_repository.upsert_webhook_subscriptions(session, endpoint_id, event_types, enabled)
    active_subscriptions = await webhook_repository.list_webhook_subscriptions(session, endpoint_id, is_active=True)
    await webhook_repository.update_webhook_endpoint(session, endpoint_id, {"event_types": [item.event_type for item in active_subscriptions]})
    await event_bus.dispatch("webhook.subscription_updated", payload={"endpoint_id": str(endpoint_id), "event_types": event_types, "active": enabled})
    return [WebhookEventSubscriptionPublic.model_validate(item) for item in saved]


async def create_endpoint(session: AsyncSession, user_id: UUID, body: WebhookEndpointCreate) -> WebhookEndpointPublic:
    endpoint = await webhook_repository.create_webhook_endpoint(session, _endpoint_defaults({**body.model_dump(), "user_id": user_id}))
    if endpoint.event_types:
        await webhook_repository.upsert_webhook_subscriptions(session, endpoint.id, endpoint.event_types, True)
    await event_bus.dispatch("webhook.endpoint_created", payload={"endpoint_id": str(endpoint.id), "user_id": str(user_id)})
    return _endpoint_public(endpoint)


async def update_endpoint(session: AsyncSession, endpoint_id: UUID, body: WebhookEndpointUpdate, user_id: UUID | None = None) -> WebhookEndpointPublic:
    endpoint = await _owned_endpoint(session, endpoint_id, user_id)
    updated_endpoint = await webhook_repository.update_webhook_endpoint(session, endpoint.id, _endpoint_defaults(body.model_dump(exclude_unset=True)))
    await event_bus.dispatch("webhook.endpoint_updated", payload={"endpoint_id": str(endpoint.id), "user_id": str(endpoint.user_id)})
    return _endpoint_public(updated_endpoint or endpoint)


async def delete_endpoint(session: AsyncSession, endpoint_id: UUID, user_id: UUID | None = None) -> WebhookEndpointPublic:
    endpoint = await _owned_endpoint(session, endpoint_id, user_id)
    updated_endpoint = await webhook_repository.update_webhook_endpoint(session, endpoint.id, {"is_active": False})
    await event_bus.dispatch("webhook.endpoint_deleted", payload={"endpoint_id": str(endpoint.id), "user_id": str(endpoint.user_id)})
    return _endpoint_public(updated_endpoint or endpoint)


async def list_endpoints(session: AsyncSession, user_id: UUID | None = None, skip: int = 0, limit: int = 100) -> list[WebhookEndpointPublic]:
    endpoints = await webhook_repository.list_webhook_endpoints(session, user_id=user_id, skip=skip, limit=limit)
    return [_endpoint_public(item) for item in endpoints]


async def get_endpoint(session: AsyncSession, endpoint_id: UUID, user_id: UUID | None = None) -> WebhookEndpointPublic:
    return _endpoint_public(await _owned_endpoint(session, endpoint_id, user_id))


async def subscribe_to_events(session: AsyncSession, endpoint_id: UUID, event_types: list[str], user_id: UUID | None = None) -> list[WebhookEventSubscriptionPublic]:
    endpoint = await _owned_endpoint(session, endpoint_id, user_id)
    return await _sync_event_types(session, endpoint.id, event_types, True)


async def unsubscribe_from_events(session: AsyncSession, endpoint_id: UUID, event_types: list[str], user_id: UUID | None = None) -> list[WebhookEventSubscriptionPublic]:
    endpoint = await _owned_endpoint(session, endpoint_id, user_id)
    return await _sync_event_types(session, endpoint.id, event_types, False)


async def list_deliveries(session: AsyncSession, *, user_id: UUID | None = None, endpoint_id: UUID | None = None, status: str | None = None, skip: int = 0, limit: int = 100) -> list[WebhookDeliveryPublic]:
    deliveries = await webhook_repository.list_webhook_deliveries(session, user_id=user_id, endpoint_id=endpoint_id, status=status, skip=skip, limit=limit)
    return [WebhookDeliveryPublic.model_validate(item) for item in deliveries]


async def get_delivery(session: AsyncSession, delivery_id: UUID, user_id: UUID | None = None) -> WebhookDeliveryPublic:
    delivery = await webhook_repository.get_webhook_delivery_by_id(session, delivery_id)
    if delivery is None:
        raise ValueError("Webhook delivery not found")
    await _owned_endpoint(session, delivery.endpoint_id, user_id)
    return WebhookDeliveryPublic.model_validate(delivery)


async def retry_delivery(session: AsyncSession, delivery_id: UUID, user_id: UUID | None = None) -> WebhookDeliveryPublic:
    delivery = await webhook_repository.get_webhook_delivery_by_id(session, delivery_id)
    if delivery is None:
        raise ValueError("Webhook delivery not found")
    if delivery.status not in {"failed", "retrying"}:
        raise ValueError("Only failed webhook deliveries can be retried")
    endpoint = await _owned_endpoint(session, delivery.endpoint_id, user_id)
    await event_bus.dispatch("webhook.delivery_retry_requested", payload={"delivery_id": str(delivery.id), "endpoint_id": str(endpoint.id)})
    retried = await webhook_dispatcher.deliver_to_endpoint(session, endpoint, delivery)
    return WebhookDeliveryPublic.model_validate(retried)
