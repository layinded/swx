"""
SwX Service Providers.

Providers are the primary way to register services in the container.
They follow Laravel's service provider pattern.

Lifecycle:
1. register() - Register bindings in container
2. boot() - Perform actions after all providers registered

Usage:
    class AuthServiceProvider(ServiceProvider):
        def register(self):
            self.singleton("auth.guard", JWTGuard)
            self.bind("token_provider", JWTTokenProvider)
        
        def boot(self):
            # Configure after all providers registered
            pass
"""

from abc import ABC, abstractmethod
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from swx_core.container.container import Container


class ServiceProvider(ABC):
    """
    Base class for all service providers.
    
    Providers are the primary way to register services in the container.
    They follow a two-phase lifecycle:
    
    1. register() - Called first, all providers register their bindings
    2. boot() - Called after all registrations, safe to resolve services
    
    Example:
        class DatabaseServiceProvider(ServiceProvider):
            priority = 10  # Register early
            
            def register(self):
                self.singleton("db.engine", self._create_engine)
                self.singleton("db.session_factory", self._create_session_factory)
                self.scoped("db.session", self._create_session)
            
            def boot(self):
                # Run migrations, etc.
                pass
    """
    
    # Provider registration order (lower = earlier)
    priority: int = 100
    
    # Whether to defer loading until a provided service is needed
    defer: bool = False
    
    # Dependencies (other providers that must register first)
    depends: List[str] = []
    
    def __init__(self, app: "Container"):
        """
        Initialize the provider.
        
        Args:
            app: The service container
        """
        self.app = app
    
    @abstractmethod
    def register(self) -> None:
        """
        Register services in the container.
        
        IMPORTANT: Do NOT resolve services here - only bind.
        Resolving in register() can cause circular dependency issues.
        """
        pass
    
    def boot(self) -> None:
        """
        Boot the provider after all providers have registered.
        
        Safe to resolve services here.
        """
        pass
    
    def provides(self) -> List[str]:
        """
        List services this provider provides.
        
        Used for deferred loading. If defer=True, the provider
        will only be loaded when one of these services is needed.
        
        Returns:
            List of service names this provider provides
        """
        return []
    
    def when(self) -> List[str]:
        """
        Specify environments where this provider should be loaded.
        
        Returns:
            List of environment names (e.g., ["production", "staging"])
        """
        return []
    
    # =====================
    # HELPER METHODS
    # =====================
    
    def bind(self, abstract: str, concrete: any) -> None:
        """
        Register a transient binding.
        
        Args:
            abstract: Service name
            concrete: Implementation
        """
        self.app.bind(abstract, concrete)
    
    def singleton(self, abstract: str, concrete: any) -> None:
        """
        Register a singleton binding.
        
        Args:
            abstract: Service name
            concrete: Implementation
        """
        self.app.singleton(abstract, concrete)
    
    def scoped(self, abstract: str, concrete: any) -> None:
        """
        Register a scoped binding.
        
        Args:
            abstract: Service name
            concrete: Implementation
        """
        self.app.scoped(abstract, concrete)
    
    def instance(self, abstract: str, instance: any) -> None:
        """
        Bind an existing instance.
        
        Args:
            abstract: Service name
            instance: The instance
        """
        self.app.instance(abstract, instance)
    
    def when_needs(self, when_abstract: str) -> "ContextualBindingHelper":
        """
        Start contextual binding.
        
        Usage:
            self.when_needs("BillingService").needs("Cache").give(RedisCache)
        
        Args:
            when_abstract: Service that needs the contextual binding
            
        Returns:
            ContextualBindingHelper for chaining
        """
        return ContextualBindingHelper(self.app, when_abstract)
    
    def alias(self, abstract: str, alias: str) -> None:
        """
        Create an alias for a binding.
        
        Args:
            abstract: Original service name
            alias: Alias name
        """
        self.app.alias(abstract, alias)
    
    def tag(self, name: str, abstracts: List[str]) -> None:
        """
        Tag multiple bindings.
        
        Args:
            name: Tag name
            abstracts: Service names to tag
        """
        self.app.tag(name, abstracts)
    
    def extend(self, abstract: str, callback: any) -> None:
        """
        Extend a resolved service.
        
        Args:
            abstract: Service name
            callback: Function that receives instance and returns modified instance
        """
        self.app.extend(abstract, callback)


class ContextualBindingHelper:
    """Helper for contextual binding chaining."""
    
    def __init__(self, app: "Container", when_abstract: str):
        self.app = app
        self.when_abstract = when_abstract
        self.needs_abstract: str = None
    
    def needs(self, abstract: str) -> "ContextualBindingHelper":
        """Specify the dependency that needs contextual binding."""
        self.needs_abstract = abstract
        return self
    
    def give(self, concrete: any) -> None:
        """Define the concrete implementation for this context."""
        if self.needs_abstract:
            self.app._add_contextual(
                self.when_abstract,
                self.needs_abstract,
                concrete
            )


class ProviderRegistry:
    """
    Registry for managing service providers.
    
    Handles registration, ordering, and booting of providers.
    """
    
    def __init__(self, app: "Container"):
        self.app = app
        self._providers: List[ServiceProvider] = []
        self._registered: List[str] = []
        self._booted: bool = False
    
    def register(self, provider_class: type) -> None:
        """
        Register a provider class.
        
        Args:
            provider_class: The provider class (not instance)
        """
        provider_name = provider_class.__name__
        
        if provider_name in self._registered:
            return
        
        provider = provider_class(self.app)
        self._providers.append(provider)
        self._registered.append(provider_name)
        
        # Register bindings
        provider.register()
    
    def register_all(self, provider_classes: List[type]) -> None:
        """
        Register multiple provider classes.
        
        Providers are sorted by priority before registration.
        
        Args:
            provider_classes: List of provider classes
        """
        # Sort by priority (lower = earlier)
        sorted_providers = sorted(
            provider_classes,
            key=lambda p: getattr(p, 'priority', 100)
        )
        
        for provider_class in sorted_providers:
            self.register(provider_class)
    
    def boot(self) -> None:
        """
        Boot all registered providers.
        
        This is called after all providers have been registered.
        """
        if self._booted:
            return
        
        # Sort by priority
        sorted_providers = sorted(
            self._providers,
            key=lambda p: p.priority
        )
        
        for provider in sorted_providers:
            provider.boot()
        
        self._booted = True
    
    def get_providers(self) -> List[ServiceProvider]:
        """Get all registered providers."""
        return self._providers.copy()
    
    def is_booted(self) -> bool:
        """Check if providers have been booted."""
        return self._booted