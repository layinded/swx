"""Tenant Config Cache
--------------------
Three-tier configuration cache for tenant/team/org settings.

L1 — per-process in-memory dict (sub-ms reads)
L2 — shared Redis cache (sub-5ms reads)
L3 — DB via SettingsService (sub-30ms reads)

L1 consistency: Redis pub/sub invalidation broadcasts ``invalidate:<key>``
messages to all workers so they drop their L1 entry.  This is eventually
consistent — a brief stale read is possible between DB write and pub/sub
delivery.

Usage::

    from swx_core.services.cache.tenant_config_cache import tenant_config

    value = await tenant_config.get(session, "billing.plan", default="free")
    await tenant_config.invalidate("billing.plan")
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from swx_core.utils.cache import get_cache

logger = logging.getLogger(__name__)

_L1_PREFIX = "tcfg:l1:"
_L2_PREFIX = "tcfg:"
_L1_TTL_SECONDS = 300  # 5 minutes for in-process L1
_INVALIDATE_CHANNEL = "tcfg:invalidate"


class _L1Cache:
    """Per-process in-memory cache with TTL and size bound."""

    _MAX_ENTRIES = 10_000

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._timestamps: dict[str, float] = {}

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [k for k, ts in self._timestamps.items() if now - ts > _L1_TTL_SECONDS]
        for k in expired:
            self._store.pop(k, None)
            del self._timestamps[k]

    def get(self, key: str) -> tuple[Any, bool]:
        import time

        ts = self._timestamps.get(key, 0)
        if time.monotonic() - ts > _L1_TTL_SECONDS:
            self._store.pop(key, None)
            self._timestamps.pop(key, None)
            return None, False
        return self._store.get(key), True

    def set(self, key: str, value: Any) -> None:
        import time

        if len(self._store) >= self._MAX_ENTRIES:
            self._evict_expired()
        self._store[key] = value
        self._timestamps[key] = time.monotonic()

    def delete(self, key: str) -> None:
        self._store.pop(key, None)
        self._timestamps.pop(key, None)


class TenantConfigCache:
    """Three-tier tenant configuration cache.

    Args:
        l2_ttl: Redis TTL in seconds (default 1 hour).
    """

    def __init__(self, l2_ttl: int = 3600) -> None:
        self._l1 = _L1Cache()
        self._l2_ttl = l2_ttl
        self._pubsub_ready = False

    async def get(self, session: AsyncSession, key: str, default: Any = None) -> Any:
        """Look up *key* through L1 → L2 → L3, caching at each level."""
        # L1
        value, hit = self._l1.get(key)
        if hit:
            return value

        # L2
        cache = get_cache()
        try:
            l2_value = await cache.get(f"{_L2_PREFIX}{key}")
            if l2_value is not None:
                self._l1.set(key, l2_value)
                return l2_value
        except Exception:
            logger.debug("L2 cache miss for key=%s", key, exc_info=True)

        # L3
        from swx_core.services.settings_service import get_setting
        from swx_core.models.system_config import SettingValueType

        db_value = await get_setting(session, key, default=default)
        if db_value is not None:
            self._l1.set(key, db_value)
            try:
                await cache.set(f"{_L2_PREFIX}{key}", db_value, ttl=self._l2_ttl)
            except Exception:
                logger.debug("L2 cache set failed for key=%s", key, exc_info=True)
            return db_value

        return default

    async def invalidate(self, key: str) -> None:
        """Remove *key* from all cache levels and broadcast invalidation."""
        self._l1.delete(key)
        cache = get_cache()
        try:
            await cache.delete(f"{_L2_PREFIX}{key}")
        except Exception:
            logger.debug("L2 cache delete failed for key=%s", key, exc_info=True)
        await self._broadcast_invalidation(key)

    async def _broadcast_invalidation(self, key: str) -> None:
        """Publish invalidation message via Redis pub/sub."""
        cache = get_cache()
        try:
            redis_client = getattr(cache, "_client", None)
            if redis_client is None and hasattr(cache, "_get_client"):
                redis_client = await cache._get_client()
            if redis_client is not None and hasattr(redis_client, "publish"):
                await redis_client.publish(_INVALIDATE_CHANNEL, json.dumps({"key": key}))
        except Exception:
            logger.debug("Pub/sub invalidation failed for key=%s", key, exc_info=True)

    async def subscribe_invalidations(self) -> None:
        """Subscribe to Redis pub/sub for L1 invalidation (call once at startup)."""
        if self._pubsub_ready:
            return
        cache = get_cache()
        try:
            redis_client = getattr(cache, "_client", None)
            if redis_client is None and hasattr(cache, "_get_client"):
                redis_client = await cache._get_client()
            if redis_client is not None and hasattr(redis_client, "subscribe"):
                pubsub = redis_client.pubsub()
                await pubsub.subscribe(_INVALIDATE_CHANNEL)
                self._pubsub_ready = True
                asyncio_mod = __import__("asyncio")
                asyncio_mod.create_task(self._listen_pubsub(pubsub))
                logger.info("Tenant config cache subscribed to invalidation channel")
        except Exception:
            logger.debug("Pub/sub subscription failed", exc_info=True)

    async def _listen_pubsub(self, pubsub: Any) -> None:
        """Background listener that drops L1 entries on invalidation messages.

        Reconnects on connection errors instead of dying permanently.
        """
        while self._pubsub_ready:
            try:
                async for message in pubsub.listen():
                    if message["type"] != "message":
                        continue
                    try:
                        data = json.loads(message["data"])
                        key = data.get("key")
                        if key:
                            self._l1.delete(key)
                    except (json.JSONDecodeError, KeyError):
                        continue
            except asyncio.CancelledError:
                break
            except Exception:
                logger.debug("Pub/sub listener error, reconnecting in 5s...", exc_info=True)
                import asyncio as _asyncio
                await _asyncio.sleep(5.0)


tenant_config = TenantConfigCache()
"""Module-level singleton. Import and use from anywhere."""