"""Payment Confirmation Service (SWX-021).

Verifies a payment with the provider AND applies the result — creating
the subscription or crediting the wallet.  Idempotent with the webhook
path via a shared Redis dedup key.

This is the bridge between "Paystack/Flutterwave says you paid" and
"your account actually reflects it".  Without it, /verify returns
"success" but the user's plan never changes because the webhook may
not have arrived yet.

The apply logic is extracted from the webhook handlers so that both
the /confirm endpoint and the webhook can share it without
double-processing.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger
from swx_core.models.billing import BillingAccountType
from swx_core.models.user import User
from swx_core.services.billing import wallet_service
from swx_core.services.billing.provider_factory import get_local_payment_provider
from swx_core.services.billing.subscription_service import SubscriptionService
from swx_core.services.compliance.pii_encryption_service import (
    decrypt_user_pii,
    encrypt_email,
    pii_encryption_enabled,
    should_encrypt_pii,
)
from swx_core.utils.currency import kobo_to_nano


@dataclass
class PaymentConfirmResult:
    status: str
    reference: str | None = None
    provider: str | None = None
    purchase_type: str | None = None
    item_key: str | None = None
    applied: bool = False
    message: str | None = None


def parse_reference_prefix(reference: str) -> tuple[str, str | None]:
    """Parse a payment reference to determine what was purchased.

    References are formatted as ``{prefix}-{key}-{uuid}`` where the key
    itself may contain hyphens (e.g. ``plan-pro-v1-a1b2c3d4``).

    Returns ``(prefix, key)`` where prefix is "plan", "pack", or "" for
    unrecognized references (treated as generic wallet credits).
    """
    parts = reference.split("-")
    if len(parts) < 3:
        return "", None
    prefix = parts[0]
    if prefix not in ("plan", "pack"):
        return "", None
    key = "-".join(parts[1:-1])
    return prefix, key


async def find_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Look up a user by email, handling PII encryption if enabled."""
    if should_encrypt_pii():
        stmt = select(User).where(User.email_encrypted == encrypt_email(email))
    else:
        stmt = select(User).where(User.email == email)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if user and pii_encryption_enabled():
        decrypt_user_pii(user)
    return user


async def apply_payment(
    session: AsyncSession,
    user_id: UUID,
    reference: str,
    amount_nano: int,
    currency: str,
    purchase_type: str,
    item_key: str | None,
) -> None:
    """Apply a confirmed payment — create subscription or credit wallet.

    Shared mutation logic used by both /confirm and webhooks.
    The caller is responsible for idempotency (Redis dedup key).
    """
    sub_service = SubscriptionService(session)
    account = await sub_service.get_or_create_account(user_id, BillingAccountType.USER)

    if purchase_type == "plan" and item_key is not None:
        await sub_service.create_subscription(account.id, item_key, allow_paid=True)
        logger.info("Payment applied: subscription for plan %s (ref %s)", item_key, reference)
    else:
        await wallet_service.credit_wallet(session, account.id, currency, amount_nano, reference, reference)
        logger.info("Payment applied: %d nano credited (ref %s)", amount_nano, reference)


def _provider_amount_to_nano(provider: str, amount_minor: int) -> int:
    """Convert a provider-specific minor unit amount to nano."""
    if provider in ("paystack", "flutterwave"):
        return kobo_to_nano(amount_minor)
    return amount_minor


async def confirm_payment(
    session: AsyncSession,
    user_id: UUID,
    provider: str,
    reference: str,
    redis_client=None,
) -> PaymentConfirmResult:
    """Verify a payment with the provider and apply the result.

    1. Verifies the payment with the provider (Paystack/Flutterwave)
    2. Checks Redis idempotency to avoid double-processing with the webhook
    3. Parses the reference to determine plan vs pack
    4. Applies the payment (subscription creation or wallet credit)
    5. Sets the Redis idempotency key (shared with webhook)
    """
    # 1. Verify with provider
    try:
        provider_result = await get_local_payment_provider(provider).verify_payment(reference)
    except Exception as exc:
        logger.exception("Payment confirmation: provider verification failed for %s", reference)
        return PaymentConfirmResult(
            status="error", reference=reference, provider=provider,
            message=f"Provider verification failed: {exc}",
        )

    if not provider_result.get("paid"):
        return PaymentConfirmResult(
            status="not_paid", reference=reference, provider=provider,
            message=f"Payment status: {provider_result.get('status', 'unknown')}",
        )

    # 2. Redis idempotency check (shared with webhook)
    dedup_key = f"webhook:{provider}:idempotency:{reference}"
    if redis_client is not None and await redis_client.exists(dedup_key):
        logger.info("Payment confirmation: reference %s already processed (Redis dedup)", reference)
        return PaymentConfirmResult(
            status="duplicate", reference=reference, provider=provider,
            applied=True, message="Already processed",
        )

    # 3. Parse reference and determine amount
    purchase_type, item_key = parse_reference_prefix(reference)
    raw_data = provider_result.get("raw", {})
    amount_minor = raw_data.get("amount", 0)
    currency = raw_data.get("currency", settings.DEFAULT_BASE_CURRENCY)
    amount_nano = _provider_amount_to_nano(provider, amount_minor)

    # 4. Apply the payment
    try:
        await apply_payment(
            session, user_id, reference, amount_nano, currency,
            purchase_type, item_key,
        )
    except Exception:
        logger.exception("Payment confirmation: failed to apply reference %s", reference)
        await session.rollback()
        return PaymentConfirmResult(
            status="error", reference=reference, provider=provider,
            purchase_type=purchase_type, item_key=item_key,
            message="Failed to apply payment",
        )

    # 5. Set Redis idempotency key (shared with webhook)
    if redis_client is not None:
        await redis_client.setex(dedup_key, settings.WEBHOOK_IDEMPOTENCY_TTL, "confirmed")

    return PaymentConfirmResult(
        status="success", reference=reference, provider=provider,
        purchase_type=purchase_type, item_key=item_key, applied=True,
    )