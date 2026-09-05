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

        from swx_core.container.container import get_container
        from swx_core.events.redis_bridge import RedisEventBridge
        from swx_core.middleware.logging_middleware import logger

        container = get_container()

        if not container.bound("event_bridge"):
            return

        bridge: RedisEventBridge = container.make("event_bridge")
        bridge.patch_dispatch()
        logger.info("EventBus dispatch patched for Redis broadcasting")

    def _create_bridge(self, app) -> object:
        """Create and configure the RedisEventBridge instance."""
        from swx_core.config.settings import settings
        from swx_core.events.dispatcher import event_bus
        from swx_core.events.redis_bridge import RedisEventBridge
        from swx_core.middleware.logging_middleware import logger

        redis_client = app.make("redis.client")
        app_name = settings.PROJECT_NAME.lower().replace(" ", "_") if settings.PROJECT_NAME else "swx"

        bridge = RedisEventBridge(
            event_bus=event_bus,
            redis_client=redis_client,
            channel_prefix=settings.EVENT_BRIDGE_CHANNEL_PREFIX,
            app_name=app_name,
        )

        logger.info(
            "Redis event bridge created (channel_prefix=%s, app_name=%s)",
            settings.EVENT_BRIDGE_CHANNEL_PREFIX,
            app_name,
        )

        return bridge