"""
Billing Contracts.

Defines interfaces for billing providers, subscription management, and entitlements.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class SubscriptionStatus(str, Enum):
    """Subscription status enum."""
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    TRIALING = "trialing"
    UNPAID = "unpaid"


class BillingProvider(ABC):
    """
    Abstract base class for billing providers.
    
    Implement this interface to add support for different payment providers
    (Stripe, PayPal, Braintree, etc.).
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get the provider name (e.g., "stripe", "paypal")."""
        pass
    
    @abstractmethod
    async def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a customer in the provider's system.
        
        Args:
            email: Customer email
            name: Customer name
            metadata: Additional metadata
            
        Returns:
            str: Provider customer ID
        """
        pass
    
    @abstractmethod
    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a checkout session.
        
        Args:
            customer_id: Provider customer ID
            price_id: Provider price/plan ID
            success_url: URL to redirect on success
            cancel_url: URL to redirect on cancel
            metadata: Additional metadata
            
        Returns:
            str: Checkout URL
        """
        pass
    
    @abstractmethod
    async def create_subscription(
        self,
        customer_id: str,
        price_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a subscription directly.
        
        Args:
            customer_id: Provider customer ID
            price_id: Provider price/plan ID
            metadata: Additional metadata
            
        Returns:
            Dict: Subscription data including ID and status
        """
        pass
    
    @abstractmethod
    async def cancel_subscription(
        self,
        subscription_id: str,
        at_period_end: bool = True
    ) -> bool:
        """
        Cancel a subscription.
        
        Args:
            subscription_id: Provider subscription ID
            at_period_end: Cancel at period end or immediately
            
        Returns:
            bool: True if cancellation succeeded
        """
        pass
    
    @abstractmethod
    async def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Get subscription details.
        
        Args:
            subscription_id: Provider subscription ID
            
        Returns:
            Dict: Subscription data
        """
        pass
    
    @abstractmethod
    def verify_webhook(self, payload: bytes, signature: str) -> Dict[str, Any]:
        """
        Verify a webhook signature and return the event data.
        
        Args:
            payload: Raw request body
            signature: Webhook signature header
            
        Returns:
            Dict: Verified event data
            
        Raises:
            WebhookVerificationError: If signature is invalid
        """
        pass
    
    @abstractmethod
    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        """
        Get customer details.
        
        Args:
            customer_id: Provider customer ID
            
        Returns:
            Dict: Customer data
        """
        pass
    
    @abstractmethod
    async def create_portal_session(
        self,
        customer_id: str,
        return_url: str
    ) -> str:
        """
        Create a billing portal session.
        
        Args:
            customer_id: Provider customer ID
            return_url: URL to return after portal session
            
        Returns:
            str: Portal URL
        """
        pass


class SubscriptionRepository(ABC):
    """
    Abstract base class for subscription data access.
    """
    
    @abstractmethod
    async def get_by_id(self, subscription_id: str) -> Optional[Any]:
        """Get subscription by ID."""
        pass
    
    @abstractmethod
    async def get_by_provider_id(self, provider_subscription_id: str) -> Optional[Any]:
        """Get subscription by provider's subscription ID."""
        pass
    
    @abstractmethod
    async def get_active_for_account(self, account_id: str) -> Optional[Any]:
        """Get active subscription for an account."""
        pass
    
    @abstractmethod
    async def create(self, data: Dict[str, Any]) -> Any:
        """Create a subscription."""
        pass
    
    @abstractmethod
    async def update(self, subscription_id: str, data: Dict[str, Any]) -> Any:
        """Update a subscription."""
        pass
    
    @abstractmethod
    async def cancel(self, subscription_id: str, reason: str = None) -> bool:
        """Cancel a subscription."""
        pass


class EntitlementResolver(ABC):
    """
    Abstract base class for entitlement resolution.
    
    Entitlements define what features a user/account has access to.
    """
    
    @abstractmethod
    async def has(
        self,
        account_id: str,
        feature_key: str
    ) -> bool:
        """
        Check if an account has access to a feature.
        
        Args:
            account_id: Account ID
            feature_key: Feature identifier
            
        Returns:
            bool: True if entitled
        """
        pass
    
    @abstractmethod
    async def get_entitlement(
        self,
        account_id: str,
        feature_key: str
    ) -> Optional[str]:
        """
        Get the entitlement value for a feature.
        
        Args:
            account_id: Account ID
            feature_key: Feature identifier
            
        Returns:
            str: Entitlement value (e.g., "1000" for quota, "true" for boolean)
        """
        pass
    
    @abstractmethod
    async def get_remaining_quota(
        self,
        account_id: str,
        feature_key: str
    ) -> int:
        """
        Get remaining quota for a feature.
        
        Args:
            account_id: Account ID
            feature_key: Feature identifier
            
        Returns:
            int: Remaining quota (-1 for unlimited)
        """
        pass
    
    @abstractmethod
    async def record_usage(
        self,
        account_id: str,
        feature_key: str,
        quantity: int = 1
    ) -> bool:
        """
        Record usage for a quota-based feature.
        
        Args:
            account_id: Account ID
            feature_key: Feature identifier
            quantity: Quantity to record
            
        Returns:
            bool: True if recorded successfully
        """
        pass