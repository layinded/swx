"""
Core Providers Package.
"""

from swx_core.providers.database_provider import DatabaseServiceProvider
from swx_core.providers.auth_provider import AuthServiceProvider
from swx_core.providers.rate_limit_provider import RateLimitServiceProvider
from swx_core.providers.event_provider import EventServiceProvider
from swx_core.providers.billing_provider import BillingServiceProvider

__all__ = [
    "DatabaseServiceProvider",
    "AuthServiceProvider",
    "RateLimitServiceProvider",
    "EventServiceProvider",
    "BillingServiceProvider",
]

# Provider registration order (lower = earlier)
CORE_PROVIDERS = [
    DatabaseServiceProvider,   # priority 10
    EventServiceProvider,      # priority 15
    AuthServiceProvider,       # priority 20
    RateLimitServiceProvider,  # priority 30
    BillingServiceProvider,    # priority 40
]