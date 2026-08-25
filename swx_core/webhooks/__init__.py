"""
Webhooks package initialization.
"""

from swx_core.webhooks.flutterwave_webhook import (
    FlutterwaveWebhookHandler,
    get_flutterwave_webhook_handler,
)
from swx_core.webhooks.flutterwave_webhook import (
    router as flutterwave_webhook_router,
)
from swx_core.webhooks.paystack_webhook import (
    PaystackWebhookHandler,
    get_paystack_webhook_handler,
)
from swx_core.webhooks.paystack_webhook import (
    router as paystack_webhook_router,
)
from swx_core.webhooks.stripe_webhook import (
    StripeWebhookHandler,
    get_webhook_handler,
)
from swx_core.webhooks.stripe_webhook import (
    router as stripe_webhook_router,
)

__all__ = [
    "FlutterwaveWebhookHandler",
    "PaystackWebhookHandler",
    "StripeWebhookHandler",
    "flutterwave_webhook_router",
    "get_flutterwave_webhook_handler",
    "get_paystack_webhook_handler",
    "get_webhook_handler",
    "paystack_webhook_router",
    "stripe_webhook_router",
]