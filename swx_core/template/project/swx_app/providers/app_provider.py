"""
{{project_title}} - Application Service Provider.

Override core services or add custom bindings here.
"""

from swx_core.providers.base import ServiceProvider


class AppServiceProvider(ServiceProvider):
    """
    Main application service provider for customizations.
    
    Override any core service:
    
        def register(self):
            # Use custom rate limiter
            self.singleton("rate_limiter", MyCustomRateLimiter)
            
            # Use custom billing provider
            self.singleton("billing.provider", MyCustomBillingProvider)
            
            # Add custom guards
            self.singleton("auth.custom_guard", MyCustomGuard)
    """
    
    priority = 1000  # Run last to override core services
    
    def register(self) -> None:
        """User service overrides go here."""
        pass
    
    def boot(self) -> None:
        """Post-registration configuration."""
        pass