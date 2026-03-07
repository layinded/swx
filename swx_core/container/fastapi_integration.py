"""
SwX FastAPI Integration.

Provides dependency injection for FastAPI routes using the container.
"""

from typing import Type, TypeVar, Callable, Optional
from fastapi import Depends, Request

from swx_core.container.container import Container, get_container

T = TypeVar('T')


def inject(abstract: str) -> Callable:
    """
    Create a FastAPI dependency that resolves from container.
    
    Usage:
        @router.get("/users")
        async def get_users(
            user_service: UserService = Depends(inject("user_service"))
        ):
            return await user_service.list_users()
    
    Args:
        abstract: Service name to resolve
        
    Returns:
        FastAPI dependency callable
    """
    async def dependency(request: Request) -> any:
        # Get container from app state
        container = getattr(request.app.state, "container", get_container())
        return container.make(abstract)
    
    return Depends(dependency)


def inject_class(cls: Type[T]) -> Callable:
    """
    Create a FastAPI dependency that resolves a class from container.
    
    Usage:
        @router.get("/users")
        async def get_users(
            user_service: UserService = Depends(inject_class(UserService))
        ):
            return await user_service.list_users()
    
    Args:
        cls: Class to resolve
        
    Returns:
        FastAPI dependency callable
    """
    async def dependency(request: Request) -> T:
        container = getattr(request.app.state, "container", get_container())
        abstract = cls.__name__
        
        if container.bound(abstract):
            return container.make(abstract)
        
        # Try to auto-resolve
        return container._build_class(cls)
    
    return Depends(dependency)


def scoped_inject(abstract: str) -> Callable:
    """
    Create a FastAPI dependency with scoped lifecycle.
    
    The service is created once per request.
    
    Args:
        abstract: Service name to resolve
        
    Returns:
        FastAPI dependency callable
    """
    async def dependency(request: Request) -> any:
        container = getattr(request.app.state, "container", get_container())
        
        # Use request state for scoping
        if not hasattr(request.state, "_scoped_services"):
            request.state._scoped_services = {}
        
        if abstract in request.state._scoped_services:
            return request.state._scoped_services[abstract]
        
        # Create new scoped instance within request scope
        async with container.async_scope():
            instance = container.make(abstract)
            request.state._scoped_services[abstract] = instance
            return instance
    
    return Depends(dependency)


def container_dependency(request: Request) -> Container:
    """
    Get the container from request.
    
    Usage:
        @router.get("/users")
        async def get_users(container: Container = Depends(container_dependency)):
            user_service = container.make("user_service")
            return await user_service.list_users()
    
    Returns:
        Container instance
    """
    return getattr(request.app.state, "container", get_container())


class ContainerMiddleware:
    """
    Middleware to set up container scope for each request.
    
    Usage:
        app.add_middleware(ContainerMiddleware)
    """
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        container = get_container()
        
        async with container.async_scope():
            await self.app(scope, receive, send)


def setup_container(app, providers: list = None) -> Container:
    """
    Set up the container and register providers.
    
    Args:
        app: FastAPI application
        providers: List of provider classes to register
        
    Returns:
        Configured container
    """
    from swx_core.providers.base import ProviderRegistry
    
    container = get_container()
    app.state.container = container
    
    registry = ProviderRegistry(container)
    
    # Core providers (in order)
    core_providers = _get_core_providers()
    registry.register_all(core_providers)
    
    # User providers
    if providers:
        registry.register_all(providers)
    else:
        user_providers = _discover_user_providers()
        registry.register_all(user_providers)
    
    # Boot all providers
    registry.boot()
    
    return container


def _get_core_providers() -> list:
    """Get core provider classes."""
    providers = []
    
    # Import core providers
    try:
        from swx_core.providers.database_provider import DatabaseServiceProvider
        providers.append(DatabaseServiceProvider)
    except ImportError:
        pass
    
    try:
        from swx_core.providers.auth_provider import AuthServiceProvider
        providers.append(AuthServiceProvider)
    except ImportError:
        pass
    
    try:
        from swx_core.providers.rate_limit_provider import RateLimitServiceProvider
        providers.append(RateLimitServiceProvider)
    except ImportError:
        pass
    
    try:
        from swx_core.providers.event_provider import EventServiceProvider
        providers.append(EventServiceProvider)
    except ImportError:
        pass
    
    return providers


def _discover_user_providers() -> list:
    """Discover user-defined providers in app/providers/."""
    import pkgutil
    from swx_core.config.discovery import discovery
    
    providers = []
    providers_path = discovery.app_providers_path
    
    if not providers_path.exists():
        return providers
    
    for finder, name, is_pkg in pkgutil.iter_modules([str(providers_path)]):
        if name.endswith("_provider") or name == "app_provider":
            try:
                module = __import__(f"{discovery.app_providers_module}.{name}", fromlist=[name])
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        attr.__name__.endswith("Provider") and
                        attr.__module__ == module.__name__):
                        providers.append(attr)
            except ImportError:
                pass
    
    return providers