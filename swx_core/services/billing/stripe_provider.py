"""
Stripe Provider Implementation
------------------------------
Implements the BillingProvider interface for Stripe.
"""

from typing import Any, Optional
from swx_core.services.billing.billing_provider_base import BillingProvider
from swx_core.config.settings import settings


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
        serialized_metadata = _serialize_metadata(metadata)
        if serialized_metadata is not None:
            customer_kwargs["metadata"] = serialized_metadata

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
        serialized_metadata = _serialize_metadata(metadata)
        if serialized_metadata is not None:
            session_kwargs["metadata"] = serialized_metadata

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
        serialized_metadata = _serialize_metadata(metadata)
        if serialized_metadata is not None:
            subscription_kwargs["metadata"] = serialized_metadata

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
            _ = self._stripe.Subscription.modify(
                subscription_id, cancel_at_period_end=True
            )
        else:
            subscription = self._stripe.Subscription.retrieve(subscription_id)
            _ = subscription.delete()
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
    return StripeProvider(
        api_key=getattr(settings, "STRIPE_API_KEY", "sk_test_mock"),
        webhook_secret=getattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_mock"),
    )
