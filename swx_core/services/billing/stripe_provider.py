"""
Stripe Provider Implementation
------------------------------
Implements the BillingProvider interface for Stripe.
"""

from typing import Optional, Dict, Any, TYPE_CHECKING
from swx_core.services.billing.billing_provider_base import BillingProvider
from swx_core.config.settings import settings

if TYPE_CHECKING:
    import stripe


class StripeProvider(BillingProvider):
    def __init__(self, api_key: str, webhook_secret: str):
        import stripe

        stripe.api_key = api_key
        self.webhook_secret = webhook_secret
        self._stripe = stripe

    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        import stripe

        customer = stripe.Customer.create(email=email, name=name, metadata=metadata)
        return str(customer.id)

    async def create_checkout_session(
        self, customer_id: str, plan_id: str, success_url: str, cancel_url: str
    ) -> str:
        import stripe

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": plan_id,
                    "quantity": 1,
                }
            ],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return str(session.url)

    async def cancel_subscription(
        self, subscription_id: str, at_period_end: bool = True
    ) -> bool:
        import stripe

        if at_period_end:
            stripe.Subscription.modify(subscription_id, cancel_at_period_end=True)
        else:
            stripe.Subscription.delete(subscription_id)
        return True

    def verify_webhook(self, payload: Any, sig_header: str) -> Any:
        import stripe

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, self.webhook_secret
            )
            return event
        except Exception as e:
            raise ValueError(f"Webhook verification failed: {e}")


def get_stripe_provider() -> Optional[StripeProvider]:
    if not settings.is_billing_available:
        return None
    return StripeProvider(
        api_key=getattr(settings, "STRIPE_API_KEY", "sk_test_mock"),
        webhook_secret=getattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_mock"),
    )
