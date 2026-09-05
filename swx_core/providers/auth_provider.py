"""
Authentication Service Provider.

Registers authentication services including:
- Guard manager
- JWT guard
- API key guard
- Token blacklist

Guards are resolved lazily inside the ``_create_guard_manager`` factory
so that the dependency chain (guard_manager → jwt_guard → token_blacklist
→ redis.client) is only traversed at runtime, not during provider boot.
This avoids RecursionError when auth is booted before redis.
"""

import logging

from swx_core.providers.base import ServiceProvider

logger = logging.getLogger(__name__)


class AuthServiceProvider(ServiceProvider):
    """Register authentication services."""

    priority = 20  # After database

    def register(self) -> None:
        """Register auth bindings."""
        self.singleton("auth.token_blacklist", self._create_token_blacklist)
        self.singleton("auth.jwt_guard", self._create_jwt_guard)
        self.singleton("auth.api_key_guard", self._create_api_key_guard)
        self.singleton("auth.guard_manager", self._create_guard_manager)
        self.alias("auth.jwt_guard", "auth.guard")

    def boot(self) -> None:
        """No-op: guards are resolved lazily by the factory."""
        logger.info("AuthServiceProvider booted (guards resolve on first request)")

    def _create_token_blacklist(self, app):
        """Create token blacklist with graceful Redis fallback."""
        from swx_core.config.settings import settings
        from swx_core.security.token_blacklist import RedisTokenBlacklist

        redis_client = None
        if app.bound("redis.client"):
            try:
                redis_client = app.make("redis.client")
            except Exception:
                redis_client = None

        if redis_client:
            return RedisTokenBlacklist(
                redis_client=redis_client,
                prefix="revoked_tokens:",
                user_prefix="user_revoked:",
            )

        from swx_core.security.token_blacklist import InMemoryTokenBlacklist
        return InMemoryTokenBlacklist()

    def _create_jwt_guard(self, app):
        """Create JWT guard."""
        from swx_core.config.settings import settings
        from swx_core.guards.jwt_guard import JWTGuard

        token_blacklist = app.make("auth.token_blacklist")

        return JWTGuard(
            secret_key=settings.SECRET_KEY,
            algorithm=getattr(settings, "PASSWORD_SECURITY_ALGORITHM", "HS256"),
            access_token_expire=getattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", 15),
            refresh_token_expire=getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 30),
            token_blacklist=token_blacklist,
        )

    def _create_api_key_guard(self, app):
        """Create API key guard."""
        from swx_core.guards.api_key_guard import APIKeyGuard

        return APIKeyGuard(
            header_name="X-API-Key",
            query_param="api_key",
        )

    def _create_guard_manager(self, app):
        """Create guard manager and register configured guards.

        Resolves guards lazily: this factory only runs when
        ``container.make("auth.guard_manager")`` is first called (at
        runtime), by which point all providers have finished registering.
        """
        from swx_core.config.settings import settings
        from swx_core.guards.guard_manager import GuardManager

        default_guard = getattr(settings, "DEFAULT_AUTH_GUARD", "jwt")
        manager = GuardManager(default_guard=default_guard)

        guards_config = getattr(
            settings,
            "AUTH_GUARDS",
            {"api": "jwt", "admin": "jwt", "internal": "api_key"},
        )

        if "jwt" in guards_config.values() and app.bound("auth.jwt_guard"):
            try:
                manager.register("jwt", app.make("auth.jwt_guard"))
            except Exception as exc:
                logger.warning("Failed to resolve JWT guard: %s", exc)

        if "api_key" in guards_config.values() and app.bound("auth.api_key_guard"):
            try:
                manager.register("api_key", app.make("auth.api_key_guard"))
            except Exception as exc:
                logger.warning("Failed to resolve API key guard: %s", exc)

        if manager.has_guard(default_guard):
            manager.set_default(default_guard)

        return manager