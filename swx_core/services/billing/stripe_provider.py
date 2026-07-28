"""
Stripe Provider Implementation
------------------------------
Implements the BillingProvider interface for Stripe.
"""

from typing import Any, Optional
from swx_core.services.billing.billing_provider_base import BillingProvider
from swx_core.config.settings import settings


def is_valid_stripe_api_key(api_key: str | None) -> bool:
    return bool(api_key) and api_key.startswith(("sk_live_", "sk_test_"))


def is_valid_stripe_webhook_secret(webhook_secret: str | None) -> bool:
    return bool(webhook_secret) and webhook_secret.startswith("whsec_")


def _serialize_metadata(metadata: dict[str, Any] | None) -> dict[str, str] | None:
    if not metadata:
        return None

    return {key: str(value) for key, value in metadata.items()}


class StripeProvider(BillingProvider):
    @property
    def name(self) -> str:
        return "stripe"

    def __init__(self, api_key: str, webhook_secret: str):
        import stripe

        stripe.api_key = api_key
        self.webhook_secret: str = webhook_secret
        self._stripe: Any = stripe

    async def create_customer(
        self,
        email: str,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        customer_kwargs: dict[str, Any] = {"email": email}
        if name is not None:
            customer_kwargs["name"] = name
        normalized_metadata = _serialize_metadata(metadata)
        if normalized_metadata is not None:
            customer_kwargs["metadata"] = normalized_metadata

        customer = self._stripe.Customer.create(**customer_kwargs)
        return str(customer.id)

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        session_kwargs: dict[str, Any] = {
            "customer": customer_id,
            "payment_method_types": ["card"],
            "line_items": [{"price": price_id, "quantity": 1}],
            "mode": "subscription",
            "success_url": success_url,
            "cancel_url": cancel_url,
        }
        normalized_metadata = _serialize_metadata(metadata)
        if normalized_metadata is not None:
            session_kwargs["metadata"] = normalized_metadata

        session = self._stripe.checkout.Session.create(**session_kwargs)
        return str(session.url)

    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        subscription_kwargs: dict[str, Any] = {
            "customer": customer_id,
            "items": [{"price": price_id}],
        }
        normalized_metadata = _serialize_metadata(metadata)
        if normalized_metadata is not None:
            subscription_kwargs["metadata"] = normalized_metadata

        subscription = self._stripe.Subscription.create(**subscription_kwargs)
        return dict(subscription)

    async def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        subscription = self._stripe.Subscription.retrieve(subscription_id)
        return dict(subscription)

    async def get_customer(self, customer_id: str) -> dict[str, Any]:
        customer = self._stripe.Customer.retrieve(customer_id)
        return dict(customer)

    async def create_portal_session(self, customer_id: str, return_url: str) -> str:
        session = self._stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return str(session.url)

    async def cancel_subscription(
        self, subscription_id: str, at_period_end: bool = True
    ) -> bool:
        if at_period_end:
            self._stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        else:
            subscription = self._stripe.Subscription.retrieve(subscription_id)
            subscription.delete()
        return True

    def verify_webhook(self, payload: bytes, sig_header: str) -> Any:
        try:
            event = self._stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return event
        except Exception as exc:
            raise ValueError(f"Webhook verification failed: {exc}")


def get_stripe_provider() -> Optional[StripeProvider]:
    if not settings.is_billing_available:
        return None
    api_key = getattr(settings, "STRIPE_API_KEY", None)
    if not isinstance(api_key, str) or not is_valid_stripe_api_key(api_key):
        return None

    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
    return StripeProvider(
        api_key=api_key,
        webhook_secret=(
            webhook_secret
            if isinstance(webhook_secret, str)
            and is_valid_stripe_webhook_secret(webhook_secret)
            else ""
        ),
    )
