"""
Flutterwave Webhook Handler.

Implements webhook handling for Flutterwave payment events with:
- HMAC-SHA256 signature verification
- Major-unit → nano conversion
- Reference prefix routing (plan-{key} → subscription, pack-{key} → wallet credit)
- Idempotent wallet credit (by Flutterwave tx_ref)
- Redis fast-path idempotency (falls back to ledger idempotency)

Shared apply logic lives in ``payment_confirmation_service`` so both
the webhook and the /confirm endpoint use the same subscription/wallet
creation code without double-processing.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request, status

from swx_core.config.settings import settings
from swx_core.database.db import AsyncSessionLocal
from swx_core.middleware.logging_middleware import logger
from swx_core.services.billing.payment_confirmation_service import (
    apply_payment,
    find_user_by_email,
    parse_reference_prefix,
)
from swx_core.utils.currency import provider_amount_to_nano

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

_SUPPORTED_EVENTS = {"charge.completed"}


@dataclass
class FlutterwaveWebhookResult:
    status: str
    reference: str | None = None
    event_type: str | None = None
    message: str | None = None


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _extract_payload_fields(data: dict[str, Any]) -> tuple[str, int, str, str, str] | None:
    reference = data.get("tx_ref")
    amount = data.get("amount")
    customer = data.get("customer")
    email = customer.get("email") if isinstance(customer, dict) else None
    currency = data.get("currency", settings.DEFAULT_BASE_CURRENCY)
    status_value = data.get("status", "")

    if not isinstance(reference, str) or not isinstance(amount, (int, float)):
        return None
    if not isinstance(email, str) or not email:
        return None

    return reference, int(amount), email, currency, status_value


class FlutterwaveWebhookHandler:
    def __init__(self, secret_key: str, redis_client=None):
        self.secret_key = secret_key
        self.redis = redis_client

    async def handle(self, payload: bytes, signature: str) -> FlutterwaveWebhookResult:
        if not signature:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing signature",
            )

        if not _verify_signature(payload, signature, self.secret_key):
            logger.warning("Flutterwave webhook signature verification failed")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid signature",
            )

        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payload",
            )

        event_type = event.get("event", "")
        data = event.get("data", {})
        if not isinstance(data, dict):
            return FlutterwaveWebhookResult(status="ignored", event_type=event_type, message="No data object")

        if event_type not in _SUPPORTED_EVENTS:
            logger.info("Flutterwave webhook: unsupported event %s", event_type)
            return FlutterwaveWebhookResult(status="ignored", event_type=event_type, message="Event not supported")

        fields = _extract_payload_fields(data)
        if fields is None:
            logger.warning("Flutterwave webhook: could not extract fields from data")
            return FlutterwaveWebhookResult(status="error", event_type=event_type, message="Missing required fields")

        reference, amount_major, email, currency, flw_status = fields

        if flw_status != "successful":
            logger.info("Flutterwave webhook: reference %s status %s, skipping", reference, flw_status)
            return FlutterwaveWebhookResult(
                status="ignored", reference=reference, event_type=event_type,
                message=f"Payment status {flw_status}",
            )

        if self.redis is not None:
            dedup_key = f"webhook:flutterwave:idempotency:{reference}"
            if await self.redis.exists(dedup_key):
                logger.info("Flutterwave webhook: duplicate reference %s", reference)
                return FlutterwaveWebhookResult(
                    status="duplicate", reference=reference, event_type=event_type,
                    message="Already processed",
                )

        amount_nano = provider_amount_to_nano(amount_major, currency, "flutterwave")
        purchase_type, item_key = parse_reference_prefix(reference)

        try:
            async with AsyncSessionLocal() as session:
                user = await find_user_by_email(session, email)
                if user is None:
                    logger.warning("Flutterwave webhook: no user for email %s", email)
                    return FlutterwaveWebhookResult(
                        status="error", reference=reference, event_type=event_type,
                        message="User not found",
                    )

                await apply_payment(
                    session, user.id, reference, amount_nano, currency,
                    purchase_type, item_key,
                )
                await session.commit()
        except Exception:
            logger.exception("Flutterwave webhook: failed to process reference %s", reference)
            return FlutterwaveWebhookResult(
                status="error", reference=reference, event_type=event_type,
                message="Processing failed",
            )

        if self.redis is not None:
            await self.redis.setex(
                f"webhook:flutterwave:idempotency:{reference}", settings.WEBHOOK_IDEMPOTENCY_TTL, event_type
            )

        return FlutterwaveWebhookResult(
            status="success", reference=reference, event_type=event_type
        )


def _resolve_webhook_secret() -> str | None:
    """Resolve the Flutterwave webhook secret, falling back to the API secret key.

    Handles ${ENV_VAR} placeholders that pydantic-settings returns when the
    env var is not set.
    """
    webhook_secret = settings.FLUTTERWAVE_WEBHOOK_SECRET
    if webhook_secret and not webhook_secret.startswith("${"):
        return webhook_secret

    api_secret = settings.FLUTTERWAVE_SECRET_KEY
    if api_secret and not api_secret.startswith("${"):
        return api_secret

    return None


_handler: Optional[FlutterwaveWebhookHandler] = None


def get_flutterwave_webhook_handler() -> Optional[FlutterwaveWebhookHandler]:
    global _handler

    secret = _resolve_webhook_secret()
    if secret is None:
        return None

    if _handler is None:
        redis_client = None
        try:
            from swx_core.container.container import get_container

            container = get_container()
            if container.bound("redis.client"):
                redis_client = container.make("redis.client")
        except Exception:
            logger.debug("Redis client unavailable, webhook idempotency will use ledger fallback")

        _handler = FlutterwaveWebhookHandler(secret_key=secret, redis_client=redis_client)

    return _handler


@router.post("/flutterwave")
async def flutterwave_webhook(request: Request):
    handler = get_flutterwave_webhook_handler()
    if handler is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Flutterwave webhook secret is not configured",
        )

    payload = await request.body()
    signature = request.headers.get("verif-hash", "")

    try:
        result = await handler.handle(payload, signature)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Flutterwave webhook handling error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error",
        )

    if result.status == "duplicate":
        return {"status": "success", "message": "Duplicate event"}

    if result.status == "ignored":
        return {"status": "success", "message": result.message}

    if result.status == "error":
        return {"status": "success", "message": "Processing failed"}

    return {"status": "success", "reference": result.reference}


@router.get("/flutterwave/health")
async def flutterwave_webhook_health():
    return {"status": "healthy", "endpoint": "/webhooks/flutterwave"}
