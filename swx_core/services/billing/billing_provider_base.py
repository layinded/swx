"""
Billing Provider Abstraction
----------------------------
Defines the interface for billing and payment providers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BillingProvider(ABC):
    """
    Interface for billing providers (Stripe, etc.)
    """

    @abstractmethod
    async def create_customer(self, email: str, name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Creates a customer in the provider's system and returns the provider's customer ID.
        """
        ...

    @abstractmethod
    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Creates a checkout session and returns the checkout URL.
        """
        ...

    @abstractmethod
    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Creates a subscription and returns the provider subscription payload.
        """
        ...

    @abstractmethod
    async def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> bool:
        """
        Cancels a subscription in the provider's system.
        """
        ...

    @abstractmethod
    def verify_webhook(self, payload: Any, sig_header: str) -> Any:
        """
        Verifies the webhook signature and returns the event object.
        """
        ...

    @abstractmethod
    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Retrieves a subscription from the provider.
        """
        ...

    @abstractmethod
    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Retrieves a customer from the provider.
        """
        ...

    @abstractmethod
    async def create_portal_session(self, customer_id: str, return_url: str) -> str:
        """
        Creates a billing portal session and returns the portal URL.
        """
        ...
