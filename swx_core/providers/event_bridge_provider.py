"""
Event Bridge Service Provider.

Wires the Redis Pub/Sub bridge into the IoC container and patches
the global EventBus so that ``dispatch()`` automatically broadcasts
to all workers when Redis is available.

This provider is a no-op when ``REDIS_ENABLED=False`` or
``EVENT_BRIDGE_ENABLED=False``.
"""

from swx_core.providers.base import ServiceProvider


class EventBridgeServiceProvider(ServiceProvider):
    """Register the Redis event bridge for cross-worker broadcasting."""

    priority = 35  # After RateLimitServiceProvider (30) so redis.client is available

    def register(self) -> None:
        """Register the event bridge as a singleton in the container."""
        from swx_core.config.settings import settings

        if not settings.REDIS_ENABLED or not settings.EVENT_BRIDGE_ENABLED:
            return

        # Only register if redis.client is also registered (RateLimitServiceProvider
        # may have skipped it if Redis connection fails). The actual Redis client
        # resolution happens at boot time, but we guard here to avoid registering
        # a binding that will fail to resolve.
        if not self.app.bound("redis.client"):
            return

        self.singleton("event_bridge", self._create_bridge)

    def boot(self) -> None:
        """
        Patch EventBus.dispatch to broadcast via Redis.

        Done at boot time (after all providers registered) so
        ``redis.client`` is available for resolution.
        """
        from swx_core.config.settings import settings

        if not settings.REDIS_ENABLED or not settings.EVENT_BRIDGE_ENABLED:
            return

        from swx_core.events.redis_bridge import RedisEventBridge
        from swx_core.middleware.logging_middleware import logger

        if not self.app.bound("event_bridge"):
            logger.debug("Event bridge not registered — Redis client unavailable or bridge disabled.")
            return

        try:
            bridge: RedisEventBridge = self.app.make("event_bridge")
        except Exception as exc:
            logger.warning("Failed to create Redis event bridge, falling back to in-process events: %s", exc)
            return

        if bridge is None:
            logger.debug("Event bridge is None — Redis client unavailable, skipping dispatch patch.")
            return

        bridge.patch_dispatch()
        logger.info("EventBus dispatch patched for Redis broadcasting")

    def _create_bridge(self, app) -> object:
        """Create and configure the RedisEventBridge instance."""
        from swx_core.config.settings import settings
        from swx_core.events.dispatcher import event_bus
        from swx_core.events.redis_bridge import RedisEventBridge
        from swx_core.middleware.logging_middleware import logger

        # Resolve redis.client — may be None if the connection failed
        if not app.bound("redis.client"):
            logger.warning("Redis client not bound — event bridge will operate in local-only mode.")
            return None

        redis_client = app.make("redis.client")
        if redis_client is None:
            logger.warning("Redis client is None (connection failed) — event bridge will operate in local-only mode.")
            return None

        bridge = RedisEventBridge(
            event_bus=event_bus,
            redis_client=redis_client,
            channel_prefix=settings.EVENT_BRIDGE_CHANNEL_PREFIX,
            app_name=RedisEventBridge.default_app_name(settings.PROJECT_NAME),
        )

        logger.info(
            "Redis event bridge created (channel_prefix=%s, app_name=%s)",
            settings.EVENT_BRIDGE_CHANNEL_PREFIX,
            bridge._app_name,
        )

        return bridge