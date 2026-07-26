"""
Runtime Cache — L1/L2 Redis-backed cache for feature flags and settings.

L1: process-local dict with timestamp-based TTL (no Redis round-trip)
L2: Redis with structured key naming for cross-process invalidation

Key format: {env}:{app}:{scope}:{resource}:{identifier}:{version}

Backward compatible: FEATURE_FLAG_CACHE_ENABLED=False (default) = no caching.
Backward compatible: SETTINGS_CACHE_ENABLED=False (default) = no caching.
"""

import json
import logging
from typing import Any, Optional

from swx_core.config.settings import settings
from swx_core.auth.auth_cache import _L1Cache, _build_key, _build_prefix

logger = logging.getLogger(__name__)


class RuntimeCache:
    """Two-level (L1 process-local + L2 Redis) cache for runtime configuration.

    Gracefully degrades when Redis is unavailable — falls back to L1 only.
    """

    def __init__(self, scope: str, ttl: int, l1_max: int = 500):
        self._scope = scope
        self._ttl = ttl
        self._l1 = _L1Cache(max_entries=l1_max)
        self._redis = None

    async def _get_redis(self):
        if self._redis is not None:
            return self._redis
        try:
            from swx_core.container.container import get_container
            container = get_container()
            if container.bound("redis.client"):
                self._redis = container.make("redis.client")
                return self._redis
        except Exception:
            pass
        return None

    async def get_value(self, key: str) -> Optional[Any]:
        """Get a cached value by key."""
        cache_key = _build_key(self._scope, "config", key)
        result = self._l1.get(cache_key)
        if result is not None:
            return result

        redis = await self._get_redis()
        if redis is None:
            return None
        try:
            raw = await redis.get(cache_key)
            if raw is None:
                return None
            data = json.loads(raw) if isinstance(raw, str) else raw
            self._l1.set(cache_key, data, self._ttl)
            return data
        except Exception as exc:
            logger.warning("Runtime cache L2 get failed for %s: %s", cache_key, exc)
            return None

    async def set_value(self, key: str, value: Any) -> None:
        """Set a cached value."""
        cache_key = _build_key(self._scope, "config", key)
        self._l1.set(cache_key, value, self._ttl)

        redis = await self._get_redis()
        if redis is None:
            return
        try:
            serialized = json.dumps(value) if not isinstance(value, str) else value
            await redis.setex(cache_key, self._ttl, serialized)
        except Exception as exc:
            logger.warning("Runtime cache L2 set failed for %s: %s", cache_key, exc)

    async def invalidate(self, key: str) -> None:
        """Invalidate a specific cached key."""
        cache_key = _build_key(self._scope, "config", key)
        self._l1.delete(cache_key)

        redis = await self._get_redis()
        if redis is None:
            return
        try:
            await redis.delete(cache_key)
        except Exception as exc:
            logger.warning("Runtime cache L2 delete failed for %s: %s", cache_key, exc)

    async def invalidate_all(self) -> None:
        """Invalidate all cached entries for this scope."""
        full_prefix = _build_prefix(self._scope, "config")
        self._l1.delete_by_prefix(full_prefix)

        redis = await self._get_redis()
        if redis is None:
            return
        try:
            keys = await redis.keys(f"{full_prefix}*")
            if keys:
                await redis.delete(*keys)
        except Exception as exc:
            logger.warning("Runtime cache L2 bulk delete failed: %s", exc)


# Feature flag cache instance
feature_flag_cache = RuntimeCache(
    scope="feature_flag",
    ttl=settings.FEATURE_FLAG_CACHE_TTL,
    l1_max=settings.FEATURE_FLAG_CACHE_L1_MAX_ENTRIES,
)

# Settings cache instance
settings_cache = RuntimeCache(
    scope="settings",
    ttl=settings.SETTINGS_CACHE_TTL,
    l1_max=settings.SETTINGS_CACHE_L1_MAX_ENTRIES,
)


async def get_cached_feature_flag(flag_key: str) -> Optional[bool]:
    """Get a feature flag from cache. Returns None if not cached."""
    return await feature_flag_cache.get_value(f"flag:{flag_key}")


async def set_cached_feature_flag(flag_key: str, value: bool) -> None:
    """Set a feature flag in cache."""
    await feature_flag_cache.set_value(f"flag:{flag_key}", value)


async def invalidate_feature_flag(flag_key: str) -> None:
    """Invalidate a specific feature flag cache entry."""
    await feature_flag_cache.invalidate(f"flag:{flag_key}")


async def invalidate_all_feature_flags() -> None:
    """Invalidate all feature flag cache entries."""
    await feature_flag_cache.invalidate_all()


async def get_cached_setting(key: str) -> Optional[Any]:
    """Get a setting from cache. Returns None if not cached."""
    return await settings_cache.get_value(f"setting:{key}")


async def set_cached_setting(key: str, value: Any) -> None:
    """Set a setting in cache."""
    await settings_cache.set_value(f"setting:{key}", value)


async def invalidate_cached_setting(key: str) -> None:
    """Invalidate a specific setting cache entry."""
    await settings_cache.invalidate(f"setting:{key}")


async def invalidate_all_settings() -> None:
    """Invalidate all cached settings."""
    await settings_cache.invalidate_all()
