"""CacheService
--------------
High-level cache interface with Redis primary and in-memory fallback.

Provides ``get()``, ``set()``, ``delete()``, and ``get_or_set()`` with
async factory support.  When Redis is unavailable, operations silently
fall back to an in-memory LRU cache so the application never crashes due
to cache failures.

``get_or_set(key, factory, ttl)`` is the primary API: check cache, call
the async factory on miss, store the result, and return it.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from swx_core.utils.cache import get_cache, CacheBackend

logger = logging.getLogger(__name__)


class CacheService:
    """Application-level cache with Redis primary and in-memory fallback.

    Usage::

        cache = CacheService()
        user = await cache.get_or_set(
            f"user:{user_id}",
            factory=lambda: fetch_user(user_id),
            ttl=300,
        )
    """

    def __init__(self, cache: CacheBackend | None = None) -> None:
        self._cache = cache or get_cache()

    async def get(self, key: str) -> Any | None:
        """Retrieve a value from cache. Returns ``None`` on miss or error."""
        try:
            return await self._cache.get(key)
        except Exception:
            logger.debug("Cache GET error for key=%s", key, exc_info=True)
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Store a value in cache. Returns ``True`` on success, ``False`` on error."""
        try:
            await self._cache.set(key, value, ttl=ttl)
            return True
        except Exception:
            logger.debug("Cache SET error for key=%s", key, exc_info=True)
            return False

    async def delete(self, key: str) -> bool:
        """Delete a key from cache. Returns ``True`` on success, ``False`` on error."""
        try:
            await self._cache.delete(key)
            return True
        except Exception:
            logger.debug("Cache DELETE error for key=%s", key, exc_info=True)
            return False

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[Any]],
        ttl: int = 3600,
    ) -> Any:
        """Get from cache, or compute via *factory* on miss and store the result.

        Args:
            key: Cache key.
            factory: Async callable that produces the value on cache miss.
            ttl: Time-to-live in seconds (default 1 hour).

        Returns:
            The cached or freshly-computed value.
        """
        cached = await self.get(key)
        if cached is not None:
            return cached

        value = await factory()
        await self.set(key, value, ttl=ttl)
        return value

    async def invalidate(self, *keys: str) -> int:
        """Delete multiple keys. Returns the count of successful deletions."""
        succeeded = 0
        for key in keys:
            if await self.delete(key):
                succeeded += 1
        return succeeded