"""SIEM webhook integration for SOC 2 CC7.2.

Forwards critical audit events to a configured SIEM webhook URL
immediately, and batches non-critical events on a configurable interval.
"""

import asyncio
from collections import deque
from datetime import datetime, timezone

import httpx

from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger

CRITICAL_AUDIT_EVENTS: frozenset[str] = frozenset({
    "auth.login_failure",
    "auth.account_locked",
    "rbac.permission_denied",
    "security.csp_violation",
})

SIEM_MAX_QUEUE_SIZE = 10_000
_batch_queue: deque[dict[str, object]] = deque(maxlen=SIEM_MAX_QUEUE_SIZE)


async def forward_to_siem(event: dict[str, object]) -> None:
    """Forward a single audit event to SIEM immediately (critical path)."""
    if not settings.SIEM_ENABLED:  # pyright: ignore[reportAttributeAccessIssue]
        return

    webhook_url = settings.SIEM_WEBHOOK_URL  # pyright: ignore[reportAttributeAccessIssue]
    if not webhook_url:
        logger.warning("SIEM_ENABLED but SIEM_WEBHOOK_URL not configured")
        return

    payload = {
        **event,
        "siem_timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "swx-core",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(webhook_url, json=payload)
            if response.status_code >= 400:
                logger.warning("SIEM webhook returned %s for event %s", response.status_code, event.get("action"))
    except Exception:
        logger.warning("SIEM webhook delivery failed for event %s", event.get("action"))


async def enqueue_siem_event(action: str, event_data: dict[str, object]) -> None:
    """Route an audit event to immediate SIEM forwarding or batch queue.

    Critical events (auth.login_failure, auth.account_locked, rbac.permission_denied,
    security.csp_violation) are forwarded immediately.
    All other events are queued for batch delivery.
    """
    if not settings.SIEM_ENABLED:  # pyright: ignore[reportAttributeAccessIssue]
        return

    event = {"action": action, **event_data}

    if action in CRITICAL_AUDIT_EVENTS:
        await forward_to_siem(event)
    else:
        _batch_queue.append(event)


async def flush_siem_batch() -> None:
    """Send all queued non-critical events to SIEM as a batch."""
    if not _batch_queue:
        return

    if not settings.SIEM_ENABLED:  # pyright: ignore[reportAttributeAccessIssue]
        return

    webhook_url = settings.SIEM_WEBHOOK_URL  # pyright: ignore[reportAttributeAccessIssue]
    if not webhook_url:
        return

    batch = list(_batch_queue)
    _batch_queue.clear()

    payload = {
        "batch": True,
        "count": len(batch),
        "events": batch,
        "siem_timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "swx-core",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
            if response.status_code >= 400:
                logger.warning("SIEM batch webhook returned %s", response.status_code)
                _batch_queue.extendleft(reversed(batch))
    except Exception:
        logger.warning("SIEM batch delivery failed, re-queuing %d events", len(batch))
        _batch_queue.extendleft(reversed(batch))


async def siem_batch_loop() -> None:
    """Background task that flushes the SIEM batch queue on interval."""
    interval = settings.SIEM_BATCH_INTERVAL  # pyright: ignore[reportAttributeAccessIssue]

    while True:
        await asyncio.sleep(interval)
        try:
            await flush_siem_batch()
        except Exception:
            logger.warning("SIEM batch flush failed, will retry next cycle")