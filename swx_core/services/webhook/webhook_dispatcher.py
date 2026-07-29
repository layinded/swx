# pyright: reportAny=false, reportExplicitAny=false, reportUnknownMemberType=false, reportUnusedCallResult=false

import json
from datetime import datetime
from typing import Any
from swx_core.utils.time import utc_now

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.config.settings import WEBHOOK_ENABLED
from swx_core.events.dispatcher import event_bus
from swx_core.models.webhook_delivery import WebhookDelivery
from swx_core.models.webhook_endpoint import WebhookEndpoint
from swx_core.repositories import webhook_repository
from swx_core.services.webhook.webhook_retry import calculate_next_retry, get_circuit_breaker, run_with_resilience, should_retry
from swx_core.services.webhook.webhook_signer import sign_payload

def _matches(event_type: str, patterns: list[str]) -> bool:
    for pattern in patterns:
        if pattern == "*" or pattern == event_type:
            return True
        if pattern.endswith(".*") and event_type.startswith(f"{pattern[:-2]}."):
            return True
    return False

def _event_data(payload: dict[str, Any]) -> dict[str, Any]:
    canonical_keys = {"id", "event_type", "created_at", "data"}
    return payload.get("data", payload) if canonical_keys.issubset(payload) else payload

def build_payload(delivery: WebhookDelivery, endpoint: WebhookEndpoint) -> tuple[dict[str, Any], bytes, dict[str, str]]:
    body = {
        "id": str(delivery.id),
        "event_type": delivery.event_type,
        "created_at": delivery.created_at.isoformat(),
        "data": _event_data(delivery.payload),
    }
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = sign_payload(endpoint.secret, raw)
    headers = {
        "content-type": "application/json",
        "x-swx-event": delivery.event_type,
        "x-swx-delivery-id": str(delivery.id),
        "x-swx-signature": signature,
    }
    for key, value in (endpoint.headers or {}).items():
        headers[str(key)] = str(value)
    return body, raw, headers

async def dispatch_event(session: AsyncSession, event_type: str, payload: dict[str, Any]) -> list[WebhookDelivery]:
    if not WEBHOOK_ENABLED:
        return []
    deliveries: list[WebhookDelivery] = []
    active_endpoints = await webhook_repository.list_webhook_endpoints(session, is_active=True, skip=0, limit=1000)
    for endpoint in active_endpoints:
        if not _matches(event_type, endpoint.event_types):
            continue
        delivery = await webhook_repository.create_webhook_delivery(session, {"endpoint_id": endpoint.id, "event_type": event_type, "payload": payload, "status": "pending"})
        await event_bus.dispatch("webhook.delivery_created", payload={"delivery_id": str(delivery.id), "endpoint_id": str(endpoint.id), "event_type": event_type})
        deliveries.append(await deliver_to_endpoint(session, endpoint, delivery))
    return deliveries

async def deliver_to_endpoint(session: AsyncSession, endpoint: WebhookEndpoint, delivery: WebhookDelivery) -> WebhookDelivery:
    body, raw, headers = build_payload(delivery, endpoint)
    update_data = {"payload": body, "attempt_count": delivery.attempt_count + 1, "last_attempt_at": utc_now()}
    await webhook_repository.update_webhook_delivery(session, delivery.id, update_data)
    breaker = get_circuit_breaker(str(endpoint.id))
    try:
        async def post_once() -> httpx.Response:
            async with httpx.AsyncClient() as client:
                return await client.post(endpoint.url, content=raw, headers=headers)

        response = await run_with_resilience(post_once, endpoint_id=str(endpoint.id), timeout_seconds=endpoint.timeout_seconds)
        if response.status_code < 400:
            breaker.record_success()
            updated = await webhook_repository.update_webhook_delivery(session, delivery.id, {"status": "delivered", "response_status_code": response.status_code, "response_body": response.text, "error_message": None, "next_retry_at": None})
            await event_bus.dispatch("webhook.delivery_delivered", payload={"delivery_id": str(delivery.id), "endpoint_id": str(endpoint.id), "status_code": response.status_code})
            return updated or delivery
        breaker.record_failure()
        return await schedule_retry(session, endpoint, delivery.id, response.status_code, response.text, None)
    except Exception as exc:  # noqa: BLE001
        breaker.record_failure()
        return await schedule_retry(session, endpoint, delivery.id, None, None, str(exc))

async def schedule_retry(session: AsyncSession, endpoint: WebhookEndpoint, delivery_id: Any, response_status_code: int | None, response_body: str | None, error_message: str | None) -> WebhookDelivery:
    delivery = await webhook_repository.get_webhook_delivery_by_id(session, delivery_id)
    if delivery is None:
        raise ValueError("Webhook delivery not found")
    if should_retry(response_status_code, error_message, delivery.attempt_count, endpoint.retry_count):
        next_retry_at = calculate_next_retry(endpoint.retry_delay_seconds, delivery.attempt_count)
        retry_data = {"status": "retrying", "next_retry_at": next_retry_at, "response_status_code": response_status_code, "response_body": response_body, "error_message": error_message}
        updated = await webhook_repository.update_webhook_delivery(session, delivery.id, retry_data)
        await event_bus.dispatch("webhook.delivery_retrying", payload={"delivery_id": str(delivery.id), "endpoint_id": str(endpoint.id), "next_retry_at": next_retry_at.isoformat()})
        return updated or delivery
    failure_data = {"status": "failed", "next_retry_at": None, "response_status_code": response_status_code, "response_body": response_body, "error_message": error_message}
    updated = await webhook_repository.update_webhook_delivery(session, delivery.id, failure_data)
    await event_bus.dispatch("webhook.delivery_failed", payload={"delivery_id": str(delivery.id), "endpoint_id": str(endpoint.id), "status_code": response_status_code, "error": error_message})
    return updated or delivery

async def process_pending_retries(session: AsyncSession) -> list[WebhookDelivery]:
    processed: list[WebhookDelivery] = []
    pending_deliveries = await webhook_repository.get_pending_deliveries_for_retry(session, utc_now())
    for delivery in pending_deliveries:
        endpoint = await webhook_repository.get_webhook_endpoint_by_id(session, delivery.endpoint_id)
        if endpoint is None or not endpoint.is_active:
            failed = await webhook_repository.update_webhook_delivery(session, delivery.id, {"status": "failed", "error_message": "Endpoint inactive or missing", "next_retry_at": None})
            processed.append(failed or delivery)
            continue
        processed.append(await deliver_to_endpoint(session, endpoint, delivery))
    return processed
