"""
SwX Contracts - Abstraction Layer

This module defines the public interface contracts for the SwX framework.
User code can depend on these interfaces without depending on internal implementations.

Contracts are stable across minor versions. Breaking changes only in major versions.
"""

from swx_core.contracts.auth import (
    AuthGuard,
    AuthenticatedUser,
    TokenProvider,
    PasswordHasher,
)
from swx_core.contracts.billing import (
    BillingProvider,
    SubscriptionRepository,
    EntitlementResolver,
)
from swx_core.contracts.container import (
    ContainerInterface,
    ServiceProviderInterface,
)
from swx_core.contracts.events import (
    EventBusInterface,
    EventInterface,
    ListenerInterface,
)
from swx_core.contracts.cache import CacheDriver
from swx_core.contracts.rate_limit import RateLimiterInterface
from swx_core.contracts.jobs import JobQueueInterface
from swx_core.contracts.webhook import WebhookHandlerInterface

__all__ = [
    # Auth
    "AuthGuard",
    "AuthenticatedUser",
    "TokenProvider",
    "PasswordHasher",
    # Billing
    "BillingProvider",
    "SubscriptionRepository",
    "EntitlementResolver",
    # Container
    "ContainerInterface",
    "ServiceProviderInterface",
    # Events
    "EventBusInterface",
    "EventInterface",
    "ListenerInterface",
    # Cache
    "CacheDriver",
    # Rate Limit
    "RateLimiterInterface",
    # Jobs
    "JobQueueInterface",
    # Webhook
    "WebhookHandlerInterface",
]