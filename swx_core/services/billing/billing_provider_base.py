"""
Billing Provider Abstraction
----------------------------
Defines the interface for billing and payment providers.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import uuid

class BillingProvider(ABC):
    """
    Interface for billing providers (Stripe, etc.)
    """

    @abstractmethod
    async def create_customer(self, email: str, name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Creates a customer in the provider's system and returns the provider's customer ID.
        """
        pass

    @abstractmethod
    async def create_checkout_session(self, customer_id: str, plan_id: str, success_url: str, cancel_url: str) -> str:
        """
        Creates a checkout session and returns the checkout URL.
        """
        pass

    @abstractmethod
    async def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> bool:
        """
        Cancels a subscription in the provider's system.
        """
        pass

    @abstractmethod
    def verify_webhook(self, payload: Any, sig_header: str) -> Any:
        """
        Verifies the webhook signature and returns the event object.
        """
        pass
