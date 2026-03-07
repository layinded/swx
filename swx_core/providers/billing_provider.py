"""
Billing Service Provider.

Registers billing services including:
- Billing provider (Stripe)
- Subscription service
- Entitlement resolver
"""

from swx_core.providers.base import ServiceProvider


class BillingServiceProvider(ServiceProvider):
    """Register billing services."""
    
    priority = 40  # After auth
    
    def register(self) -> None:
        """Register billing bindings."""
        # Billing provider (singleton, overridable)
        self.singleton("billing.provider", self._create_billing_provider)
        
        # Subscription service (scoped per request)
        self.scoped("billing.subscription_service", self._create_subscription_service)
        
        # Entitlement resolver (scoped per request)
        self.scoped("billing.entitlement_resolver", self._create_entitlement_resolver)
        
        # Feature registry (singleton)
        self.singleton("billing.feature_registry", self._create_feature_registry)
        
        # Aliases
        self.alias("billing.provider", "BillingProvider")
    
    def boot(self) -> None:
        """Boot billing services."""
        from swx_core.container.container import get_container
        
        container = get_container()
        
        # Register default features
        if container.bound("billing.feature_registry"):
            registry = container.make("billing.feature_registry")
            self._register_default_features(registry)
    
    def _create_billing_provider(self, app):
        """
        Create billing provider based on configuration.
        
        Users can override this in swx_app/providers/app_provider.py:
        
            class AppServiceProvider(ServiceProvider):
                def register(self):
                    self.singleton("billing.provider", MyCustomBillingProvider)
        """
        from swx_core.config.settings import settings
        
        # Check for Stripe configuration
        stripe_api_key = getattr(settings, "STRIPE_API_KEY", None)
        stripe_webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None)
        
        if stripe_api_key:
            from swx_core.services.billing.stripe_provider import StripeProvider
            return StripeProvider(
                api_key=stripe_api_key,
                webhook_secret=stripe_webhook_secret or "whsec_mock"
            )
        
        # Return mock provider if no billing configured
        return MockBillingProvider()
    
    def _create_subscription_service(self, app):
        """Create subscription service."""
        from swx_core.services.billing.subscription_service import SubscriptionService
        return SubscriptionService
    
    def _create_entitlement_resolver(self, app):
        """Create entitlement resolver."""
        from swx_core.services.billing.entitlement_resolver import EntitlementResolver
        
        # Needs session
        if app.bound("db.session"):
            session = app.make("db.session")
            return EntitlementResolver(session)
        
        return EntitlementResolver
    
    def _create_feature_registry(self, app):
        """Create feature registry."""
        from swx_core.services.billing.feature_registry import FeatureRegistry
        return FeatureRegistry()
    
    def _register_default_features(self, registry) -> None:
        """Register default features."""
        from swx_core.services.billing.feature_registry import FeatureType
        
        # Register common features
        registry.register(
            key="api_requests",
            name="API Requests",
            feature_type=FeatureType.QUOTA,
            default_value="1000",
            description="Monthly API request limit"
        )
        
        registry.register(
            key="team_members",
            name="Team Members",
            feature_type=FeatureType.QUOTA,
            default_value="5",
            description="Maximum team members"
        )
        
        registry.register(
            key="advanced_analytics",
            name="Advanced Analytics",
            feature_type=FeatureType.BOOLEAN,
            default_value="false",
            description="Access to advanced analytics"
        )
        
        registry.register(
            key="priority_support",
            name="Priority Support",
            feature_type=FeatureType.BOOLEAN,
            default_value="false",
            description="Priority support access"
        )


class MockBillingProvider:
    """Mock billing provider for development/testing."""
    
    @property
    def name(self) -> str:
        return "mock"
    
    async def create_customer(self, email: str, name: str = None, metadata: dict = None) -> str:
        return f"mock_customer_{email}"
    
    async def create_checkout_session(
        self, customer_id: str, plan_id: str, success_url: str, cancel_url: str
    ) -> str:
        return "https://mock-checkout.example.com"
    
    async def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> bool:
        return True
    
    def verify_webhook(self, payload: bytes, signature: str) -> dict:
        return {"type": "mock.event", "data": {}}