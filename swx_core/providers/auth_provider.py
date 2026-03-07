"""
Authentication Service Provider.

Registers authentication services including:
- Guard manager
- JWT guard
- API key guard
- Token blacklist
"""

from swx_core.providers.base import ServiceProvider


class AuthServiceProvider(ServiceProvider):
    """Register authentication services."""
    
    priority = 20  # After database
    
    def register(self) -> None:
        """Register auth bindings."""
        # Token blacklist (singleton)
        self.singleton("auth.token_blacklist", self._create_token_blacklist)
        
        # Guards
        self.singleton("auth.jwt_guard", self._create_jwt_guard)
        self.singleton("auth.api_key_guard", self._create_api_key_guard)
        
        # Guard manager (singleton)
        self.singleton("auth.guard_manager", self._create_guard_manager)
        
        # Default guard (alias)
        self.alias("auth.guard", "auth.jwt_guard")
    
    def boot(self) -> None:
        """Configure guards from settings."""
        from swx_core.container.container import get_container
        from swx_core.config.settings import settings
        
        container = get_container()
        manager = container.make("auth.guard_manager")
        
        # Get guard configuration
        guards_config = getattr(settings, "AUTH_GUARDS", {
            "api": "jwt",
            "admin": "jwt",
            "internal": "api_key",
        })
        
        # Register guards
        if "jwt" in guards_config.values():
            jwt_guard = container.make("auth.jwt_guard")
            manager.register("jwt", jwt_guard)
        
        if "api_key" in guards_config.values():
            api_key_guard = container.make("auth.api_key_guard")
            manager.register("api_key", api_key_guard)
        
        # Set default guard
        default_guard = getattr(settings, "DEFAULT_AUTH_GUARD", "jwt")
        if manager.has_guard(default_guard):
            manager.set_default(default_guard)
    
    def _create_token_blacklist(self, app):
        """Create token blacklist."""
        from swx_core.security.token_blacklist import RedisTokenBlacklist
        from swx_core.config.settings import settings
        
        # Try to get Redis client
        redis_client = None
        if app.bound("redis.client"):
            redis_client = app.make("redis.client")
        
        if redis_client:
            return RedisTokenBlacklist(
                redis_client=redis_client,
                prefix="revoked_tokens:",
                user_prefix="user_revoked:"
            )
        
        # Fallback to in-memory for development
        from swx_core.security.token_blacklist import InMemoryTokenBlacklist
        return InMemoryTokenBlacklist()
    
    def _create_jwt_guard(self, app):
        """Create JWT guard."""
        from swx_core.guards.jwt_guard import JWTGuard
        from swx_core.config.settings import settings
        
        token_blacklist = app.make("auth.token_blacklist")
        
        return JWTGuard(
            secret_key=settings.SECRET_KEY,
            algorithm=getattr(settings, 'PASSWORD_SECURITY_ALGORITHM', 'HS256'),
            access_token_expire=getattr(settings, 'ACCESS_TOKEN_EXPIRE_MINUTES', 10080),
            refresh_token_expire=getattr(settings, 'REFRESH_TOKEN_EXPIRE_DAYS', 30),
            token_blacklist=token_blacklist,
        )
    
    def _create_api_key_guard(self, app):
        """Create API key guard."""
        from swx_core.guards.api_key_guard import APIKeyGuard
        
        # API key repository would be injected if available
        key_repository = None
        if app.bound("api_key.repository"):
            key_repository = app.make("api_key.repository")
        
        cache = None
        if app.bound("cache"):
            cache = app.make("cache")
        
        return APIKeyGuard(
            header_name="X-API-Key",
            query_param="api_key",
            key_repository=key_repository,
            cache=cache,
        )
    
    def _create_guard_manager(self, app):
        """Create guard manager."""
        from swx_core.guards.guard_manager import GuardManager
        from swx_core.config.settings import settings
        
        default_guard = getattr(settings, "DEFAULT_AUTH_GUARD", "jwt")
        return GuardManager(default_guard=default_guard)