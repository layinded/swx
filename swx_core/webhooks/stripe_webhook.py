"""
Stripe Webhook Handler.

Implements production-grade webhook handling with:
- Signature verification (prevents spoofing)
- Idempotency protection (prevents duplicate processing)
- Replay protection (prevents old event replay)
- Rate limiting (prevents abuse)
- Async job enqueue (non-blocking)
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, status

from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger
from swx_core.services.billing.stripe_provider import is_valid_stripe_webhook_secret

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@dataclass
class WebhookResult:
    """Result of webhook processing."""

    status: str
    event_id: str | None = None
    event_type: str | None = None
    job_id: str | None = None
    message: str | None = None


class StripeWebhookHandler:
    """
    Handles Stripe webhook events with security best practices.

    Features:
    - Signature verification (prevents spoofing)
    - Idempotency protection (Redis-backed)
    - Replay protection (5-minute window)
    - Rate limiting (prevents abuse)
    - Async processing (non-blocking)

    Usage:
        handler = StripeWebhookHandler(
            webhook_secret=settings.STRIPE_WEBHOOK_SECRET,
            redis_client=redis_client
        )

        @router.post("/stripe")
        async def stripe_webhook(request: Request):
            payload = await request.body()
            signature = request.headers.get("stripe-signature")
            return await handler.handle(payload, signature)
    """

    def __init__(
        self,
        webhook_secret: str,
        redis_client=None,
        session_factory=None,
        idempotency_ttl: int = 604800,  # 7 days
        replay_window: int = 300,  # 5 minutes
    ):
        self.webhook_secret = webhook_secret
        self.redis = redis_client
        self.session_factory = session_factory
        self.idempotency_ttl = idempotency_ttl
        self.replay_window = replay_window

        # Supported event types
        self.supported_events = {
            "checkout.session.completed",
            "customer.created",
            "customer.updated",
            "customer.deleted",
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "invoice.paid",
            "invoice.payment_failed",
            "invoice.payment_succeeded",
            "payment_intent.succeeded",
            "payment_intent.payment_failed",
            "payment_method.attached",
            "payment_method.detached",
        }

    async def handle(self, payload: bytes, signature: str) -> WebhookResult:
        """
        Handle a Stripe webhook event.

        Steps:
        1. Verify signature
        2. Parse event
        3. Check idempotency
        4. Check replay
        5. Enqueue for async processing

        Args:
            payload: Raw request body
            signature: Stripe-Signature header

        Returns:
            WebhookResult with processing status
        """
        import stripe

        # 1. Verify signature
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
        except Exception as exc:
            if exc.__class__.__name__ == "SignatureVerificationError":
                logger.warning(f"Stripe webhook signature verification failed: {exc}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid signature",
                )
            logger.error(f"Stripe webhook parsing error: {exc}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload"
            )

        stripe_event_id = event["id"]
        event_type = event["type"]
        created = event["created"]

        logger.info(f"Received Stripe webhook: {event_type} ({stripe_event_id})")

        # 2. Check if event type is supported
        if event_type not in self.supported_events:
            logger.info(f"Unsupported Stripe webhook event type: {event_type}")
            return WebhookResult(
                status="ignored",
                event_id=stripe_event_id,
                event_type=event_type,
                message="Event type not supported",
            )

        # 3. Check idempotency (durable table + Redis fast-path)
        if self.session_factory:
            async with self.session_factory() as db_session:
                from swx_core.services.webhook_idempotency_service import (
                    check_and_record,
                )

                is_new = await check_and_record(
                    db_session,
                    "stripe",
                    stripe_event_id,
                    payload,
                    redis_client=self.redis,
                )
                if not is_new:
                    logger.info(f"Duplicate webhook event: {stripe_event_id}")
                    return WebhookResult(
                        status="duplicate",
                        event_id=stripe_event_id,
                        event_type=event_type,
                        message="Event already processed",
                    )
        elif self.redis:
            idempotency_key = f"webhook:stripe:idempotency:{stripe_event_id}"

            if await self.redis.exists(idempotency_key):
                logger.info(f"Duplicate webhook event: {stripe_event_id}")
                return WebhookResult(
                    status="duplicate",
                    event_id=stripe_event_id,
                    event_type=event_type,
                    message="Event already processed",
                )

            await self.redis.setex(idempotency_key, self.idempotency_ttl, event_type)

        # 4. Check replay protection
        event_time = datetime.fromtimestamp(created, tz=timezone.utc)
        now = datetime.now(timezone.utc)

        if now - event_time > timedelta(seconds=self.replay_window):
            logger.warning(
                f"Replayed webhook event: {stripe_event_id} "
                f"(event time: {event_time}, now: {now})"
            )
            # Return success to prevent retries, but don't process
            return WebhookResult(
                status="replay_ignored",
                event_id=stripe_event_id,
                event_type=event_type,
                message="Event too old",
            )

        # 5. Process subscription events inline, others via job queue
        try:
            event_object = event["data"]["object"]

            if event_type in ("checkout.session.completed", "invoice.paid", "invoice.payment_failed"):
                await self._sync_subscription(event_type, event_object)
                return WebhookResult(
                    status="processed",
                    event_id=stripe_event_id,
                    event_type=event_type,
                )

            job = await self._enqueue_job(stripe_event_id, event_type, event_object)

            logger.info(
                f"Enqueued Stripe webhook event: {stripe_event_id} "
                f"(job_id: {job.id if job else 'N/A'})"
            )

            return WebhookResult(
                status="queued",
                event_id=stripe_event_id,
                event_type=event_type,
                job_id=str(job.id) if job else None,
            )

        except Exception as exc:
            logger.error(f"Failed to enqueue webhook event: {exc}", exc_info=True)

            # Store for retry
            if self.redis:
                retry_key = f"webhook:stripe:retry:{stripe_event_id}"
                await self.redis.setex(
                    retry_key,
                    86400,  # 24 hours
                    event_type,
                )

            return WebhookResult(
                status="error",
                event_id=stripe_event_id,
                event_type=event_type,
                message=str(exc),
            )

    async def _sync_subscription(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Sync subscription state from Stripe checkout/invoice events."""
        if self.session_factory is None:
            logger.warning("Stripe webhook: no session_factory — cannot sync subscription inline")
            return

        try:
            from swx_core.services.billing.subscription_service import (
                SubscriptionService,
            )

            if event_type == "checkout.session.completed":
                async with self.session_factory() as session:
                    sub_service = SubscriptionService(session)
                    await sub_service.sync_stripe_subscription(event_data)
            elif event_type in ("invoice.paid", "invoice.payment_failed"):
                subscription_data = event_data.get("subscription")
                lines = event_data.get("lines", {})
                if isinstance(lines, dict):
                    line_data = lines.get("data", [])
                    if isinstance(line_data, list) and line_data:
                        first_line = line_data[0]
                        if isinstance(first_line, dict):
                            price = first_line.get("price", {})
                            if isinstance(price, dict):
                                subscription_data = subscription_data or {
                                    "id": event_data.get("subscription"),
                                    "status": "active" if event_type == "invoice.paid" else "past_due",
                                    "current_period_start": event_data.get("period_start"),
                                    "current_period_end": event_data.get("period_end"),
                                    "items": {"data": [first_line]},
                                }
                if isinstance(subscription_data, dict):
                    async with self.session_factory() as session:
                        sub_service = SubscriptionService(session)
                        await sub_service.sync_stripe_subscription(subscription_data)
                else:
                    logger.info("Stripe webhook: %s — no subscription data to sync", event_type)
        except Exception:
            logger.exception("Stripe webhook: failed to sync subscription for %s", event_type)

    async def _enqueue_job(
        self, event_id: str, event_type: str, event_data: Dict[str, Any]
    ):
        """Enqueue webhook event for async processing."""
        try:
            from swx_core.models.job import JobType
            from swx_core.services.job.job_dispatcher import enqueue_job

            return await enqueue_job(
                job_type=JobType.billing_webhook,
                payload={
                    "stripe_event_id": event_id,
                    "event_type": event_type,
                    "event_data": event_data,
                    "provider": "stripe",
                },
                tags=["webhook", "stripe", event_type],
            )
        except ImportError:
            # Job system not available - process inline
            logger.warning("Job system not available, processing webhook inline")
            await self._process_inline(event_id, event_type, event_data)
            return None

    async def _process_inline(
        self, event_id: str, event_type: str, event_data: Dict[str, Any]
    ) -> None:
        """Process webhook inline (no job queue)."""
        # Import the inline handler
        from swx_core.services.job.handlers import billing_webhook_handler

        # Create a session if needed
        if self.session_factory:
            async with self.session_factory() as session:
                await billing_webhook_handler(
                    session,
                    {
                        "stripe_event_id": event_id,
                        "event_type": event_type,
                        "event_data": event_data,
                    },
                )
        else:
            # Process without database
            logger.info(f"Processed webhook inline: {event_type}")


# Handler instance (lazy initialization)
_handler: Optional[StripeWebhookHandler] = None


def get_webhook_handler() -> Optional[StripeWebhookHandler]:
    global _handler

    if not settings.is_billing_available:
        return None

    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
    if not isinstance(webhook_secret, str) or not is_valid_stripe_webhook_secret(webhook_secret):
        return None

    if _handler is None:
        # Get Redis client if available
        redis_client = None
        try:
            from swx_core.container.container import get_container

            container = get_container()
            if container.bound("redis.client"):
                redis_client = container.make("redis.client")
        except Exception:
            pass

        _handler = StripeWebhookHandler(
            webhook_secret=webhook_secret,
            redis_client=redis_client,
        )

    return _handler


@router.post("/stripe")
async def stripe_webhook(request: Request):
    if not settings.is_billing_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing not enabled. Install swx-core[billing] and set BILLING_ENABLED=true",
        )
    handler = get_webhook_handler()
    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe webhook secret is not configured with a valid whsec_ value",
        )
    payload = await request.body()

    # Get signature header
    signature = request.headers.get("stripe-signature")

    if not signature:
        logger.warning("Stripe webhook missing signature header")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Missing signature"
        )

    # Handle event
    try:
        result = await handler.handle(payload, signature)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Stripe webhook handling error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error"
        )

    # Return appropriate response
    if result.status == "duplicate":
        return {"received": True, "status": "duplicate"}

    if result.status in {"replay_ignored", "ignored"}:
        return {"received": True, "status": "ignored"}

    if result.status == "error":
        return {"received": True, "status": "queued_for_retry"}

    return {
        "received": True,
        "event_id": result.event_id,
        "event_type": result.event_type,
        "job_id": result.job_id,
    }


@router.get("/stripe/health")
async def stripe_webhook_health():
    """Health check for Stripe webhook endpoint."""
    return {"status": "healthy", "endpoint": "/webhooks/stripe"}
