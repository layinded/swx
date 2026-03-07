"""
SwX Application Bootstrap.

Registers all providers and boots the application with the service container.
Uses configurable discovery for app paths instead of hardcoded swx_app.
"""

from typing import List, Type, Optional

from swx_core.container.container import Container, get_container, set_container
from swx_core.providers.base import ServiceProvider
from swx_core.middleware.logging_middleware import logger
from swx_core.config.discovery import discovery


# Core providers (in registration order)
CORE_PROVIDERS = [
    "swx_core.providers.database_provider.DatabaseServiceProvider",
    "swx_core.providers.event_provider.EventServiceProvider",
    "swx_core.providers.auth_provider.AuthServiceProvider",
    "swx_core.providers.rate_limit_provider.RateLimitServiceProvider",
    "swx_core.providers.billing_provider.BillingServiceProvider",
]


def _load_provider_class(class_path: str) -> Type[ServiceProvider]:
    """
    Dynamically load a provider class.
    
    Args:
        class_path: Full module path to provider class
        
    Returns:
        Provider class
    """
    module_path, class_name = class_path.rsplit(".", 1)
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


def _discover_user_providers() -> List[str]:
    """
    Discover user-defined providers in app/providers/.
    
    Uses configurable discovery to find the providers directory.
    Returns empty list if app directory doesn't exist or no providers found.
    
    Returns:
        List of provider class paths
    """
    providers = []
    
    # Use configurable path instead of hardcoded swx_app/providers
    providers_path = discovery.app_providers_path
    
    if not providers_path.exists():
        logger.debug(f"App providers directory not found: {providers_path}")
        return providers
    
    import pkgutil
    for finder, name, is_pkg in pkgutil.iter_modules([str(providers_path)]):
        if name.endswith("_provider") or name == "app_provider":
            providers.append(f"{discovery.app_providers_module}.{name}")
    
    return providers


def bootstrap_app(
    app=None,
    providers: Optional[List[str]] = None,
    discover_user_providers: bool = True
) -> Container:
    """
    Bootstrap the application with all service providers.
    
    This is the main entry point for initializing the SwX framework.
    
    Args:
        app: FastAPI application instance (optional)
        providers: Optional list of additional provider paths
        discover_user_providers: Whether to auto-discover user providers
        
    Returns:
        Configured container instance
        
    Usage:
        # In main.py
        from swx_core.bootstrap import bootstrap_app
        
        app = FastAPI(lifespan=lifespan)
        container = bootstrap_app(app)
        
        # Later, access services
        from swx_core.container.container import get_container
        
        container = get_container()
        rate_limiter = container.make("rate_limiter")
    """
    # Create or get container
    container = get_container()
    
    # Store container in app state if provided
    if app is not None:
        app.state.container = container
    
    # Load core providers
    all_providers = CORE_PROVIDERS[:]
    
    # Add user providers (if app exists and discovery enabled)
    if discover_user_providers and discovery.app_exists():
        user_providers = _discover_user_providers()
        all_providers.extend(user_providers)
    
    # Add additional providers passed in
    if providers:
        all_providers.extend(providers)
    
    # Load provider classes
    provider_classes = []
    for provider_path in all_providers:
        try:
            provider_class = _load_provider_class(provider_path)
            provider_classes.append(provider_class)
        except Exception as e:
            logger.warning(f"Failed to load provider {provider_path}: {e}")
    
    # Sort by priority (lower = earlier)
    provider_classes.sort(key=lambda p: getattr(p, 'priority', 100))
    
    # Instantiate providers
    provider_instances = []
    for provider_class in provider_classes:
        try:
            provider = provider_class(container)
            provider_instances.append(provider)
        except Exception as e:
            logger.error(f"Failed to instantiate provider {provider_class.__name__}: {e}")
            continue
    
    # Phase 1: Register all bindings
    logger.info("Registering service providers...")
    for provider in provider_instances:
        try:
            provider.register()
            logger.debug(f"Registered: {provider.__class__.__name__}")
        except Exception as e:
            logger.error(f"Failed to register {provider.__class__.__name__}: {e}")
    
    # Phase 2: Boot all providers
    logger.info("Booting service providers...")
    for provider in provider_instances:
        try:
            provider.boot()
            logger.debug(f"Booted: {provider.__class__.__name__}")
        except Exception as e:
            logger.error(f"Failed to boot {provider.__class__.__name__}: {e}")
    
    logger.info(f"Application bootstrapped with {len(provider_instances)} providers")
    
    return container


def bootstrap(*args, **kwargs) -> Container:
    """Alias for bootstrap_app()."""
    return bootstrap_app(*args, **kwargs)


def register_webhook_routes(app) -> None:
    """
    Register webhook routes with the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    from swx_core.webhooks.stripe_webhook import router as stripe_webhook_router
    
    app.include_router(stripe_webhook_router)
    logger.info("Registered webhook routes")


def register_event_listeners(container: Container) -> None:
    """
    Register user event listeners from app/listeners/.
    
    Uses configurable discovery to find the listeners directory.
    Does nothing if app directory doesn't exist.
    
    Args:
        container: Container instance
    """
    from swx_core.events.dispatcher import event_bus
    from swx_core.events.listener import Listener
    import pkgutil
    
    # Use configurable path
    listeners_path = discovery.app_listeners_path
    
    if not listeners_path.exists():
        logger.debug(f"App listeners directory not found: {listeners_path}")
        return
    
    for finder, name, is_pkg in pkgutil.iter_modules([str(listeners_path)]):
        try:
            module = __import__(f"{discovery.app_listeners_module}.{name}", fromlist=[name])
            
            # Find Listener subclasses
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, Listener) and 
                    attr is not Listener):
                    
                    listener_instance = attr()
                    event_bus.listen(
                        listener_instance.event,
                        listener_instance.handle,
                        priority=getattr(listener_instance, 'priority', 50),
                        queueable=getattr(listener_instance, 'queueable', False)
                    )
                    logger.debug(f"Registered listener: {attr_name} for {listener_instance.event}")
                    
        except Exception as e:
            logger.warning(f"Failed to load listener {name}: {e}")


def get_registered_services() -> dict:
    """
    Get all registered services in the container.
    
    Returns:
        Dictionary of service names and their binding types
    """
    container = get_container()
    bindings = {}
    
    for name, binding in container.get_bindings().items():
        bindings[name] = binding.binding_type.value
    
    return bindings


def resolve(name: str):
    """
    Convenience function to resolve a service from the container.
    
    Args:
        name: Service name
        
    Returns:
        Resolved service instance
    """
    return get_container().make(name)