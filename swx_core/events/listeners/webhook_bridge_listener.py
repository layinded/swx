import copy
from typing import Any

from swx_core.events.dispatcher import Event, EventPriority, event_bus
from swx_core.events.listener import Listener
from swx_core.middleware.logging_middleware import logger

PII_KEYS: frozenset[str] = frozenset({
    "password", "password_hash", "secret", "token", "access_token",
    "refresh_token", "api_key", "credit_card", "cvv", "ssn",
})

MASK_KEYS: frozenset[str] = frozenset({"email", "ip_address", "phone"})


def _scrub_payload(payload: Any) -> Any:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        return payload
    scrubbed = copy.deepcopy(payload)
    _scrub_dict(scrubbed)
    return scrubbed


def _scrub_dict(data: dict[str, Any]) -> None:
    keys_to_remove: list[str] = []
    for key in data:
        lower = key.lower()
        if lower in PII_KEYS:
            keys_to_remove.append(key)
        elif lower in MASK_KEYS and isinstance(data[key], str):
            val = data[key]
            if len(val) <= 3:
                data[key] = "***"
            else:
                data[key] = val[:2] + "***" + val[-1]
        elif isinstance(data[key], dict):
            _scrub_dict(data[key])
    for key in keys_to_remove:
        del data[key]


class WebhookBridgeListener(Listener):

    event = "*"
    priority = EventPriority.LOWEST

    async def handle(self, event: Event) -> None:
        if event.name.startswith("webhook."):
            return

        scrubbed_payload = _scrub_payload(event.payload)

        try:
            from swx_core.database.db import AsyncSessionLocal
            from swx_core.services.webhook.webhook_dispatcher import dispatch_event

            async with AsyncSessionLocal() as session:
                await dispatch_event(session, event.name, scrubbed_payload)
                await session.commit()
        except Exception as exc:
            logger.error(f"Webhook bridge error for event '{event.name}': {exc}")


def register_webhook_bridge() -> None:
    bridge = WebhookBridgeListener()
    event_bus.listen("*", bridge.handle, priority=EventPriority.LOWEST)
    logger.info("Webhook bridge listener registered (wildcard -> outbound dispatch)")