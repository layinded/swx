"""
Redis Pub/Sub Bridge for Cross-Worker Event Broadcasting.

Extends the in-process EventBus to broadcast events across multiple
worker processes via Redis Pub/Sub. When Redis is enabled and the
bridge is active, every ``event_bus.dispatch()`` call:

1. Runs local in-process listeners immediately (zero latency).
2. Publishes the event to Redis so ALL workers receive it.

A background subscriber on each worker re-dispatches incoming Redis
messages locally — with a ``_source="redis"`` marker that prevents
infinite re-broadcast loops.

Usage (automatic when REDIS_ENABLED + EVENT_BRIDGE_ENABLED):

    from swx_core.events.dispatcher import event_bus

    # No code changes — dispatch as normal:
    await event_bus.dispatch("user.registered", payload={"user_id": user_id})

    # All workers receive the event, including this one.

Manual setup (e.g. in tests or standalone scripts):

    from swx_core.events.dispatcher import event_bus
    from swx_core.events.redis_bridge import RedisEventBridge

    bridge = RedisEventBridge(event_bus, redis_client=redis_client)
    await bridge.start()
    # ... use event_bus as normal ...
    await bridge.stop()

Extensibility — custom channels and filtering:

    # Publish to a custom channel (not via EventBus dispatch)
    await bridge.publish("custom.channel", {"key": "value"})

    # Subscribe to a custom channel pattern
    await bridge.subscribe("custom.*", my_handler)

    # Filter which events get broadcast:
    bridge.set_broadcast_filter(lambda name: not name.startswith("internal."))
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Awaitable, Callable, Coroutine, Dict, List, Optional, Set

from swx_core.middleware.logging_middleware import logger

# ── Marker ────────────────────────────────────────────────────────────
# Injected into kwargs by the bridge to prevent re-broadcast loops.
SOURCE_META_KEY = "_broadcast_source"
SOURCE_REDIS = "redis"


class RedisEventBridge:
    """
    Bridges the in-process :class:`EventBus` to Redis Pub/Sub.

    * **Publish**: wraps ``EventBus.dispatch`` so every local dispatch
      also publishes to Redis (unless the event originated from Redis).
    * **Subscribe**: a background task listens on Redis channels and
      re-dispatches incoming messages locally.
    * **Extensibility**: custom channels, custom handlers, broadcast
      filters, and exclude lists.
    """

    # ── Configurable defaults ─────────────────────────────────────────

    #: Default Redis key prefix for event channels.
    DEFAULT_CHANNEL_PREFIX = "swx:events"

    #: How many seconds to wait before reconnecting after a Redis error.
    RECONNECT_DELAY = 5.0

    #: Maximum reconnect attempts before giving up (None = unlimited).
    MAX_RECONNECT_ATTEMPTS: Optional[int] = None

    def __init__(
        self,
        event_bus: Any,
        redis_client: Any = None,
        channel_prefix: str = DEFAULT_CHANNEL_PREFIX,
        app_name: str = "swx",
    ) -> None:
        """
        Args:
            event_bus: The global :class:`EventBus` instance.
            redis_client: An ``redis.asyncio.Redis`` client (or compatible).
            channel_prefix: Prefix for Redis Pub/Sub channels.
            app_name: Application identifier (used in channel names).
        """
        self._event_bus = event_bus
        self._redis = redis_client
        self._channel_prefix = channel_prefix
        self._app_name = app_name
        self._pubsub: Any = None
        self._listener_task: Optional[asyncio.Task[None]] = None
        self._running = False
        self._reconnect_attempts = 0

        # Custom channel subscriptions: pattern -> list of handlers
        self._custom_handlers: Dict[str, List[Callable[..., Awaitable[None]]]] = {}

        # Broadcast filter: return True to broadcast, False to skip
        self._broadcast_filter: Optional[Callable[[str], bool]] = None

        # Events that should never be broadcast (prefix match)
        self._exclude_prefixes: Set[str] = set()

        # Reference to the original dispatch (before patching)
        self._original_dispatch: Optional[Callable[..., Coroutine[Any, Any, Any]]] = None

    # ── Properties ────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def redis_client(self) -> Any:
        return self._redis

    # ── Broadcast filtering ───────────────────────────────────────────

    def set_broadcast_filter(self, filter_fn: Callable[[str], bool]) -> None:
        """
        Set a filter function that decides which events get broadcast.

        The function receives the event name and returns ``True`` to
        broadcast or ``False`` to keep it local only.

        Args:
            filter_fn: A callable ``(event_name: str) -> bool``.

        Usage::

            # Only broadcast events starting with "user." or "billing."
            bridge.set_broadcast_filter(
                lambda name: name.startswith(("user.", "billing."))
            )
        """
        self._broadcast_filter = filter_fn

    def add_exclude_prefix(self, prefix: str) -> None:
        """
        Exclude events whose name starts with *prefix* from broadcasting.

        Excluded events still run locally — they are just not published
        to Redis.

        Args:
            prefix: Event name prefix to exclude (e.g. ``"internal."``).
        """
        self._exclude_prefixes.add(prefix)

    def remove_exclude_prefix(self, prefix: str) -> None:
        self._exclude_prefixes.discard(prefix)

    def _should_broadcast(self, event_name: str) -> bool:
        """Return True if *event_name* should be published to Redis."""
        for prefix in self._exclude_prefixes:
            if event_name.startswith(prefix):
                return False
        if self._broadcast_filter is not None:
            return self._broadcast_filter(event_name)
        return True

    # ── Publishing ────────────────────────────────────────────────────

    async def publish(self, event_name: str, payload: Any = None, **kwargs: Any) -> None:
        """
        Publish an event to Redis for cross-worker delivery.

        This is called automatically by the patched ``dispatch()`` but
        can also be used directly for custom channels.

        Args:
            event_name: The event/channel name.
            payload: Event payload (must be JSON-serialisable).
            **kwargs: Additional metadata.
        """
        if self._redis is None:
            return

        message: Dict[str, Any] = {
            "event": event_name,
            "payload": payload,
            "kwargs": {k: v for k, v in kwargs.items() if k != SOURCE_META_KEY},
            "source": self._app_name,
            "ts": time.time(),
        }

        channel = f"{self._channel_prefix}:{event_name}"
        try:
            serialized = json.dumps(message, default=str)
            await self._redis.publish(channel, serialized)
            logger.debug("Published event '%s' to Redis channel '%s'", event_name, channel)
        except Exception as exc:
            logger.warning("Failed to publish event '%s' to Redis: %s", event_name, exc)

    # ── Subscribing ────────────────────────────────────────────────────

    async def start(self) -> None:
        """
        Start the background Redis subscriber task.

        Safe to call multiple times — subsequent calls are no-ops.
        """
        if self._redis is None or self._running:
            return

        self._running = True
        self._reconnect_attempts = 0
        self._pubsub = self._redis.pubsub()
        pattern = f"{self._channel_prefix}:*"
        await self._pubsub.psubscribe(pattern)
        logger.info("Redis event bridge subscribed to pattern: %s", pattern)

        # Also subscribe custom channel patterns
        for custom_pattern in self._custom_handlers:
            await self._pubsub.psubscribe(custom_pattern)
            logger.info("Redis event bridge subscribed to custom pattern: %s", custom_pattern)

        self._listener_task = asyncio.create_task(self._listen_loop())
        logger.info("Redis event bridge started")

    async def stop(self) -> None:
        """
        Stop the background Redis subscriber task gracefully.

        Cancels the listener task and closes the Pub/Sub connection.
        """
        self._running = False

        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe()
                await self._pubsub.punsubscribe()
                await self._pubsub.close()
            except Exception as exc:
                logger.debug("Error closing Redis pubsub: %s", exc)
            self._pubsub = None

        logger.info("Redis event bridge stopped")

    async def subscribe(
        self,
        pattern: str,
        handler: Callable[..., Awaitable[None]],
    ) -> None:
        """
        Subscribe a handler to a custom Redis channel pattern.

        The handler receives the raw message dict ``{"event": ..., "payload": ..., "kwargs": ..., "ts": ...}``.

        If the bridge is already running, the pattern is subscribed
        immediately on Redis.

        Args:
            pattern: Redis Pub/Sub pattern (e.g. ``"swx:custom:*"``).
            handler: Async callable that receives the message dict.
        """
        if pattern not in self._custom_handlers:
            self._custom_handlers[pattern] = []
            # If already running, subscribe on Redis immediately
            if self._running and self._pubsub is not None:
                await self._pubsub.psubscribe(pattern)
                logger.info("Redis event bridge subscribed to custom pattern: %s", pattern)

        self._custom_handlers[pattern].append(handler)

    async def unsubscribe(self, pattern: str, handler: Callable[..., Awaitable[None]]) -> None:
        """
        Remove a handler from a custom Redis channel pattern.

        If no handlers remain for the pattern, the pattern is
        unsubscribed from Redis.
        """
        if pattern in self._custom_handlers:
            handlers = self._custom_handlers[pattern]
            self._custom_handlers[pattern] = [h for h in handlers if h != handler]
            if not self._custom_handlers[pattern]:
                del self._custom_handlers[pattern]
                if self._running and self._pubsub is not None:
                    await self._pubsub.punsubscribe(pattern)
                    logger.info("Redis event bridge unsubscribed from pattern: %s", pattern)

    # ── Dispatch patching ──────────────────────────────────────────────

    def patch_dispatch(self) -> None:
        """
        Patch ``event_bus.dispatch`` to also publish to Redis.

        The original dispatch is preserved and called first. Only
        events that pass the broadcast filter and don't carry the
        ``_broadcast_source="redis"`` marker are published.

        This is idempotent — calling it twice patches only once.
        """
        if self._original_dispatch is not None:
            # Already patched
            return

        self._original_dispatch = self._event_bus.dispatch
        bridge = self

        async def _broadcasting_dispatch(event: str, payload: Any = None, **kwargs: Any) -> Any:
            # 1. Run local in-process listeners FIRST
            assert bridge._original_dispatch is not None  # guaranteed by patch_dispatch
            event_obj = await bridge._original_dispatch(event, payload, **kwargs)

            # 2. If this event came from Redis, don't re-broadcast (loop prevention)
            source = kwargs.get(SOURCE_META_KEY)
            if source == SOURCE_REDIS:
                return event_obj

            # 3. Apply broadcast filter / exclude list
            if not bridge._should_broadcast(event):
                return event_obj

            # 4. Publish to Redis for cross-worker delivery
            await bridge.publish(event, payload, **kwargs)
            return event_obj

        self._event_bus.dispatch = _broadcasting_dispatch

    def unpatch_dispatch(self) -> None:
        if self._original_dispatch is not None:
            self._event_bus.dispatch = self._original_dispatch
            self._original_dispatch = None

    # ── Internal ──────────────────────────────────────────────────────

    async def _listen_loop(self) -> None:
        """Background loop that reads from Redis Pub/Sub and dispatches locally."""
        pubsub = self._pubsub
        if pubsub is None:
            return

        try:
            while self._running:
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    if message and message["type"] == "pmessage":
                        await self._handle_message(message)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.error("Redis event bridge listener error: %s", exc)
                    self._reconnect_attempts += 1
                    if (
                        self.MAX_RECONNECT_ATTEMPTS is not None
                        and self._reconnect_attempts >= self.MAX_RECONNECT_ATTEMPTS
                    ):
                        logger.critical(
                            "Redis event bridge exceeded max reconnect attempts (%d). Stopping.",
                            self.MAX_RECONNECT_ATTEMPTS,
                        )
                        self._running = False
                        break
                    logger.info(
                        "Redis event bridge reconnecting in %ss (attempt %d)...",
                        self.RECONNECT_DELAY,
                        self._reconnect_attempts,
                    )
                    await asyncio.sleep(self.RECONNECT_DELAY)
                    # Attempt to re-subscribe
                    try:
                        if self._pubsub is not None:
                            await self._pubsub.close()
                        self._pubsub = self._redis.pubsub()
                        pattern = f"{self._channel_prefix}:*"
                        await self._pubsub.psubscribe(pattern)
                        for custom_pattern in self._custom_handlers:
                            await self._pubsub.psubscribe(custom_pattern)
                        self._reconnect_attempts = 0  # Reset on successful reconnect
                        logger.info("Redis event bridge reconnected successfully")
                    except Exception as reconnect_exc:
                        logger.error("Redis event bridge reconnect failed: %s", reconnect_exc)
        except asyncio.CancelledError:
            logger.debug("Redis event bridge listener cancelled")
        except Exception as exc:
            logger.critical("Redis event bridge listener crashed: %s", exc)

    async def _handle_message(self, message: Dict[str, Any]) -> None:
        """
        Handle an incoming Redis Pub/Sub message.

        Routes the message to the local EventBus and/or any custom
        handlers registered for the channel pattern.
        """
        try:
            data = json.loads(message["data"])
            event_name = data.get("event")
            payload = data.get("payload")

            if not event_name:
                logger.warning("Received event without name from Redis: %s", message)
                return

            # 1. Re-dispatch locally with _source="redis" to prevent re-broadcast
            await self._event_bus.dispatch(
                event_name,
                payload=payload,
                **{SOURCE_META_KEY: SOURCE_REDIS},
            )
            logger.debug("Re-dispatched Redis event '%s' locally", event_name)

            # 2. Route to custom handlers
            channel_pattern = message.get("pattern", "")
            if channel_pattern in self._custom_handlers:
                for handler in self._custom_handlers[channel_pattern]:
                    try:
                        await handler(data)
                    except Exception as handler_exc:
                        logger.error(
                            "Custom handler error for pattern '%s': %s",
                            channel_pattern,
                            handler_exc,
                        )

        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Failed to parse Redis event message: %s", exc)

    # ── Convenience ────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """
        Return current bridge status and statistics.

        Useful for health-check endpoints and debugging.
        """
        return {
            "running": self._running,
            "redis_connected": self._redis is not None,
            "channel_prefix": self._channel_prefix,
            "app_name": self._app_name,
            "custom_patterns": list(self._custom_handlers.keys()),
            "exclude_prefixes": list(self._exclude_prefixes),
            "has_broadcast_filter": self._broadcast_filter is not None,
            "dispatch_patched": self._original_dispatch is not None,
        }