# pyright: reportAny=false, reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false

import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from swx_core.models.webhook_delivery import WebhookDelivery
from swx_core.models.webhook_endpoint import WebhookEndpoint, WebhookEndpointCreate, WebhookEndpointUpdate
from swx_core.services.webhook import webhook_dispatcher, webhook_service
from swx_core.services.webhook.webhook_signer import sign_payload, verify_signature


def now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def endpoint_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "name": "primary",
        "url": "https://example.com/webhook",
        "secret": "${WEBHOOK_SECRET}",
        "description": None,
        "is_active": True,
        "user_id": uuid.uuid4(),
        "event_types": ["user.*"],
        "headers": {"x-test": "1"},
        "retry_count": 3,
        "retry_delay_seconds": 60,
        "timeout_seconds": 30,
        "created_at": now(),
        "updated_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data, model_dump=lambda: data)


def delivery_object(**overrides: object) -> SimpleNamespace:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "endpoint_id": uuid.uuid4(),
        "event_type": "user.created",
        "payload": {"id": "abc", "event_type": "user.created", "created_at": now().isoformat(), "data": {"user_id": "u1"}},
        "status": "failed",
        "attempt_count": 1,
        "created_at": now(),
    }
    for key, value in overrides.items():
        data[key] = value
    return SimpleNamespace(**data)


class TestWebhookServices:
    async def test_create_endpoint_emits_event_and_masks_secret(self):
        session = AsyncMock()
        body = WebhookEndpointCreate(name="primary", url="https://example.com/webhook", secret="${WEBHOOK_SECRET}", event_types=["user.*"])
        stored = endpoint_object()
        with patch.object(webhook_service.webhook_repository, "create_webhook_endpoint", new_callable=AsyncMock, return_value=stored):
            with patch.object(webhook_service.webhook_repository, "upsert_webhook_subscriptions", new_callable=AsyncMock) as mock_subs:
                with patch.object(webhook_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    result = await webhook_service.create_endpoint(session, stored.user_id, body)
        assert result.retry_count == 3
        assert result.secret_masked == "${WE...RET}"
        mock_subs.assert_awaited_once()
        assert mock_dispatch.await_args is not None
        assert mock_dispatch.await_args.args[0] == "webhook.endpoint_created"

    async def test_dispatch_event_matches_wildcard_subscriptions(self):
        session = AsyncMock()
        endpoint = endpoint_object(event_types=["user.*"])
        delivery = delivery_object(endpoint_id=endpoint.id, payload={"user_id": "u1"})
        with patch.object(webhook_dispatcher.webhook_repository, "list_webhook_endpoints", new_callable=AsyncMock, return_value=[endpoint]):
            with patch.object(webhook_dispatcher.webhook_repository, "create_webhook_delivery", new_callable=AsyncMock, return_value=delivery):
                with patch.object(webhook_dispatcher, "deliver_to_endpoint", new_callable=AsyncMock, return_value=delivery) as mock_deliver:
                    deliveries = await webhook_dispatcher.dispatch_event(session, "user.created", {"user_id": "u1"})
        assert len(deliveries) == 1
        mock_deliver.assert_awaited_once()

    def test_signer_resolves_env_secret_and_verifies(self):
        os.environ["WEBHOOK_SECRET"] = "super-secret-value"
        payload = {"hello": "world"}
        signature = sign_payload("${WEBHOOK_SECRET}", payload)
        assert verify_signature("${WEBHOOK_SECRET}", payload, signature) is True

    def test_build_payload_reuses_original_event_data_on_retry(self):
        endpoint = WebhookEndpoint(**endpoint_object(secret="plain-secret").model_dump())
        delivery = WebhookDelivery(**delivery_object().__dict__)
        body, raw, headers = webhook_dispatcher.build_payload(delivery, endpoint)
        assert body["data"] == {"user_id": "u1"}
        assert headers["x-swx-event"] == "user.created"
        assert raw

    async def test_update_endpoint_emits_event(self):
        session = AsyncMock()
        endpoint_id = uuid.uuid4()
        user_id = uuid.uuid4()
        stored = endpoint_object(id=endpoint_id, user_id=user_id)
        updated = endpoint_object(id=endpoint_id, user_id=user_id, name="updated")
        body = WebhookEndpointUpdate(name="updated")
        with patch.object(webhook_service.webhook_repository, "get_webhook_endpoint_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(webhook_service.webhook_repository, "update_webhook_endpoint", new_callable=AsyncMock, return_value=updated):
                with patch.object(webhook_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    await webhook_service.update_endpoint(session, endpoint_id, body, user_id)
        assert mock_dispatch.await_args is not None
        assert mock_dispatch.await_args.args[0] == "webhook.endpoint_updated"

    async def test_delete_endpoint_soft_deletes_and_emits_event(self):
        session = AsyncMock()
        endpoint_id = uuid.uuid4()
        user_id = uuid.uuid4()
        stored = endpoint_object(id=endpoint_id, user_id=user_id, is_active=True)
        deactivated = endpoint_object(id=endpoint_id, user_id=user_id, is_active=False)
        with patch.object(webhook_service.webhook_repository, "get_webhook_endpoint_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(webhook_service.webhook_repository, "update_webhook_endpoint", new_callable=AsyncMock, return_value=deactivated):
                with patch.object(webhook_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    await webhook_service.delete_endpoint(session, endpoint_id, user_id)
        assert mock_dispatch.await_args is not None
        assert mock_dispatch.await_args.args[0] == "webhook.endpoint_deleted"

    async def test_delete_endpoint_raises_permission_error_for_wrong_user(self):
        session = AsyncMock()
        endpoint_id = uuid.uuid4()
        other_user_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        stored = endpoint_object(id=endpoint_id, user_id=owner_id)
        with patch.object(webhook_service.webhook_repository, "get_webhook_endpoint_by_id", new_callable=AsyncMock, return_value=stored):
            with pytest.raises(PermissionError):
                await webhook_service.delete_endpoint(session, endpoint_id, other_user_id)

    async def test_get_endpoint_raises_value_error_for_missing(self):
        session = AsyncMock()
        endpoint_id = uuid.uuid4()
        with patch.object(webhook_service.webhook_repository, "get_webhook_endpoint_by_id", new_callable=AsyncMock, return_value=None):
            with pytest.raises(ValueError, match="not found"):
                await webhook_service.get_endpoint(session, endpoint_id)

    async def test_subscribe_to_events_emits_subscription_updated(self):
        session = AsyncMock()
        endpoint_id = uuid.uuid4()
        user_id = uuid.uuid4()
        stored = endpoint_object(id=endpoint_id, user_id=user_id)
        sub = SimpleNamespace(event_type="order.created", is_active=True, id=uuid.uuid4(), endpoint_id=endpoint_id, created_at=now())
        with patch.object(webhook_service.webhook_repository, "get_webhook_endpoint_by_id", new_callable=AsyncMock, return_value=stored):
            with patch.object(webhook_service.webhook_repository, "upsert_webhook_subscriptions", new_callable=AsyncMock, return_value=[sub]):
                with patch.object(webhook_service.webhook_repository, "list_webhook_subscriptions", new_callable=AsyncMock, return_value=[sub]):
                    with patch.object(webhook_service.webhook_repository, "update_webhook_endpoint", new_callable=AsyncMock):
                        with patch.object(webhook_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                            await webhook_service.subscribe_to_events(session, endpoint_id, ["order.created"], user_id)
        assert mock_dispatch.await_args is not None
        assert mock_dispatch.await_args.args[0] == "webhook.subscription_updated"
        assert mock_dispatch.await_args.kwargs["payload"]["event_types"] == ["order.created"]

    async def test_retry_delivery_emits_event(self):
        session = AsyncMock()
        delivery_id = uuid.uuid4()
        endpoint_id = uuid.uuid4()
        user_id = uuid.uuid4()
        endpoint = endpoint_object(id=endpoint_id, user_id=user_id)
        failed_delivery = delivery_object(id=delivery_id, endpoint_id=endpoint_id, status="failed", attempt_count=1)
        retried = delivery_object(id=delivery_id, endpoint_id=endpoint_id, status="delivered")
        with patch.object(webhook_service.webhook_repository, "get_webhook_delivery_by_id", new_callable=AsyncMock, return_value=failed_delivery):
            with patch.object(webhook_service.webhook_repository, "get_webhook_endpoint_by_id", new_callable=AsyncMock, return_value=endpoint):
                with patch.object(webhook_service.event_bus, "dispatch", new_callable=AsyncMock) as mock_dispatch:
                    with patch.object(webhook_dispatcher, "deliver_to_endpoint", new_callable=AsyncMock, return_value=retried):
                        await webhook_service.retry_delivery(session, delivery_id, user_id)
        assert mock_dispatch.await_args is not None
        assert mock_dispatch.await_args.args[0] == "webhook.delivery_retry_requested"

    async def test_retry_delivery_raises_for_non_retryable_status(self):
        session = AsyncMock()
        delivery_id = uuid.uuid4()
        delivered = delivery_object(id=delivery_id, status="delivered")
        with patch.object(webhook_service.webhook_repository, "get_webhook_delivery_by_id", new_callable=AsyncMock, return_value=delivered):
            with pytest.raises(ValueError, match="Only failed"):
                await webhook_service.retry_delivery(session, delivery_id)


class TestWebhookWildcardMatching:
    def test_exact_match(self):
        from swx_core.services.webhook.webhook_dispatcher import _matches
        assert _matches("user.created", ["user.created"]) is True

    def test_wildcard_star_matches_everything(self):
        from swx_core.services.webhook.webhook_dispatcher import _matches
        assert _matches("user.created", ["*"]) is True
        assert _matches("order.paid", ["*"]) is True

    def test_prefix_wildcard_matches_sub_events(self):
        from swx_core.services.webhook.webhook_dispatcher import _matches
        assert _matches("user.created", ["user.*"]) is True
        assert _matches("user.updated", ["user.*"]) is True
        assert _matches("order.paid", ["user.*"]) is False

    def test_no_match_returns_false(self):
        from swx_core.services.webhook.webhook_dispatcher import _matches
        assert _matches("order.created", ["user.created"]) is False


class TestWebhookRetryLogic:
    def test_should_retry_on_server_error(self):
        from swx_core.services.webhook.webhook_retry import should_retry
        assert should_retry(500, None, 1, 3) is True

    def test_should_retry_on_timeout_errors(self):
        from swx_core.services.webhook.webhook_retry import should_retry
        assert should_retry(408, None, 1, 3) is True
        assert should_retry(429, None, 1, 3) is True

    def test_should_not_retry_on_client_errors(self):
        from swx_core.services.webhook.webhook_retry import should_retry
        assert should_retry(400, None, 1, 3) is False
        assert should_retry(404, None, 1, 3) is False

    def test_should_not_retry_when_max_attempts_reached(self):
        from swx_core.services.webhook.webhook_retry import should_retry
        assert should_retry(500, None, 3, 3) is False

    def test_should_retry_on_network_errors(self):
        from swx_core.services.webhook.webhook_retry import should_retry
        assert should_retry(None, "Connection refused", 1, 3) is True

    def test_calculate_next_retry_increases_delay(self):
        from swx_core.services.webhook.webhook_retry import calculate_next_retry, utc_now_naive
        first = calculate_next_retry(60, 1)
        second = calculate_next_retry(60, 2)
        assert second > first

    def test_get_retry_delay_caps_at_max(self):
        from swx_core.services.webhook.webhook_retry import get_retry_delay
        delay = get_retry_delay(60, 10)
        assert delay <= 60 * 16


class TestWebhookSigner:
    def test_sign_and_verify_roundtrip(self):
        os.environ.setdefault("WEBHOOK_SIGNER_KEY", "test-signer-key")
        payload = {"event": "test", "data": {"key": "value"}}
        signature = sign_payload("plain-secret", payload)
        assert verify_signature("plain-secret", payload, signature) is True
        assert verify_signature("wrong-secret", payload, signature) is False

    def test_sign_payload_bytes(self):
        raw = b'{"hello":"world"}'
        signature = sign_payload("secret", raw)
        assert isinstance(signature, str)
        assert verify_signature("secret", raw, signature) is True

    def test_sign_payload_string(self):
        raw = '{"hello":"world"}'
        signature = sign_payload("secret", raw)
        assert isinstance(signature, str)
        assert verify_signature("secret", raw, signature) is True

    def test_tampered_payload_fails_verification(self):
        payload = {"event": "test"}
        signature = sign_payload("secret", payload)
        tampered = {"event": "tampered"}
        assert verify_signature("secret", tampered, signature) is False
