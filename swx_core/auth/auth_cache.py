"""
Auth Cache — L1/L2 Redis-backed cache for user and admin lookups.

L1: process-local dict with timestamp-based TTL (no Redis round-trip)
L2: Redis with structured key naming for cross-process invalidation

Key format: {env}:{app}:{scope}:{resource}:{identifier}:{version}

Backward compatible: USER_CACHE_ENABLED=False (default) = no caching.
"""

import time
import logging
from typing import Optional, Dict, Any, List
from uuid import UUID

from swx_core.utils.json import dumps as swx_dumps, loads as swx_loads

from swx_core.config.settings import settings

logger = logging.getLogger(__name__)


def _build_key(scope: str, resource: str, identifier: str, version: str = "v1") -> str:
    env = settings.ENVIRONMENT
    app = settings.PROJECT_NAME.lower().replace(" ", "_") if settings.PROJECT_NAME else "swx"
    return f"{env}:{app}:{scope}:{resource}:{identifier}:{version}"


def _build_prefix(scope: str, resource: str) -> str:
    env = settings.ENVIRONMENT
    app = settings.PROJECT_NAME.lower().replace(" ", "_") if settings.PROJECT_NAME else "swx"
    return f"{env}:{app}:{scope}:{resource}:"


class _L1Cache:
    """Process-local cache with timestamp-based TTL and max-entries eviction."""

    def __init__(self, max_entries: int = 1000):
        self._store: Dict[str, tuple[Any, float]] = {}
        self._max_entries = max_entries

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any, ttl: int) -> None:
        if len(self._store) >= self._max_entries and key not in self._store:
            oldest_key = next(iter(self._store))
            del self._store[oldest_key]
        self._store[key] = (value, time.monotonic() + ttl)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

    def delete_by_prefix(self, prefix: str) -> None:
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._store[k]


class AuthCache:
    """Two-level (L1 process-local + L2 Redis) cache for auth lookups.

    Gracefully degrades when Redis is unavailable — falls back to L1 only.
    """

    def __init__(self, scope: str, ttl: int, l1_max: int = 1000):
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

    def _serialize_user(self, user_dict: Dict[str, Any]) -> str:
        """Serialize user dict to JSON, stripping hashed_password."""
        safe = {k: v for k, v in user_dict.items() if k != "hashed_password"}
        return swx_dumps(safe)

    def _deserialize_user(self, raw: str) -> Dict[str, Any]:
        return swx_loads(raw)

    async def get_profile(self, identifier: str) -> Optional[Dict[str, Any]]:
        key = _build_key(self._scope, "profile", identifier)
        result = self._l1.get(key)
        if result is not None:
            return result

        redis = await self._get_redis()
        if redis is None:
            return None
        try:
            raw = await redis.get(key)
            if raw is None:
                return None
            data = self._deserialize_user(raw) if isinstance(raw, str) else raw
            self._l1.set(key, data, self._ttl)
            return data
        except Exception as exc:
            logger.warning("Auth cache L2 get failed for %s: %s", key, exc)
            return None

    async def set_profile(self, identifier: str, user_dict: Dict[str, Any]) -> None:
        key = _build_key(self._scope, "profile", identifier)
        data = {k: v for k, v in user_dict.items() if k != "hashed_password"}
        self._l1.set(key, data, self._ttl)

        redis = await self._get_redis()
        if redis is None:
            return
        try:
            serialized = self._serialize_user(user_dict)
            await redis.setex(key, self._ttl, serialized)
        except Exception as exc:
            logger.warning("Auth cache L2 set failed for %s: %s", key, exc)

    async def invalidate_profile(self, identifier: str) -> None:
        key = _build_key(self._scope, "profile", identifier)
        self._l1.delete(key)

        redis = await self._get_redis()
        if redis is None:
            return
        try:
            await redis.delete(key)
        except Exception as exc:
            logger.warning("Auth cache L2 delete failed for %s: %s", key, exc)

    async def invalidate_profile_by_prefix(self, prefix: str) -> None:
        full_prefix = _build_key(self._scope, "profile", prefix)
        self._l1.delete_by_prefix(full_prefix)

        redis = await self._get_redis()
        if redis is None:
            return
        try:
            keys = await redis.keys(f"{full_prefix}*")
            if keys:
                await redis.delete(*keys)
        except Exception as exc:
            logger.warning("Auth cache L2 prefix delete failed: %s", exc)

    async def get_permissions(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        key = _build_key(self._scope, "permissions", user_id)
        result = self._l1.get(key)
        if result is not None:
            return result

        redis = await self._get_redis()
        if redis is None:
            return None
        try:
            raw = await redis.get(key)
            if raw is None:
                return None
            data = swx_loads(raw) if isinstance(raw, str) else raw
            self._l1.set(key, data, settings.USER_PERMISSIONS_CACHE_TTL)
            return data
        except Exception as exc:
            logger.warning("Auth cache L2 permissions get failed for %s: %s", key, exc)
            return None

    async def set_permissions(self, user_id: str, permissions: List[Dict[str, Any]]) -> None:
        key = _build_key(self._scope, "permissions", user_id)
        perm_ttl = settings.USER_PERMISSIONS_CACHE_TTL
        self._l1.set(key, permissions, perm_ttl)

        redis = await self._get_redis()
        if redis is None:
            return
        try:
            serialized = swx_dumps(permissions)
            await redis.setex(key, perm_ttl, serialized)
        except Exception as exc:
            logger.warning("Auth cache L2 permissions set failed for %s: %s", key, exc)

    async def invalidate_permissions(self, user_id: str) -> None:
        key = _build_key(self._scope, "permissions", user_id)
        self._l1.delete(key)

        redis = await self._get_redis()
        if redis is None:
            return
        try:
            await redis.delete(key)
        except Exception as exc:
            logger.warning("Auth cache L2 permissions delete failed for %s: %s", key, exc)


user_auth_cache = AuthCache(
    scope="user",
    ttl=settings.USER_CACHE_TTL,
    l1_max=settings.USER_CACHE_L1_MAX_ENTRIES,
)

admin_auth_cache = AuthCache(
    scope="admin",
    ttl=settings.ADMIN_CACHE_TTL,
    l1_max=settings.USER_CACHE_L1_MAX_ENTRIES,
)


async def invalidate_user_cache(user_id: UUID | str, email: str) -> None:
    """Invalidate all cached data for a user (profile + permissions)."""
    uid = str(user_id)
    await user_auth_cache.invalidate_profile(uid)
    await user_auth_cache.invalidate_profile(email)
    await user_auth_cache.invalidate_permissions(uid)


async def invalidate_user_permissions(user_id: UUID | str) -> None:
    """Invalidate cached permissions for a user."""
    uid = str(user_id)
    await user_auth_cache.invalidate_permissions(uid)


async def invalidate_admin_cache(admin_id: UUID | str, email: str) -> None:
    """Invalidate all cached data for an admin user (profile)."""
    aid = str(admin_id)
    await admin_auth_cache.invalidate_profile(aid)
    await admin_auth_cache.invalidate_profile(email)


async def invalidate_all_permissions() -> None:
    """Invalidate all cached permission entries (L1 + L2).

    Used when role-permission mappings change, since we cannot
    efficiently determine which users are affected without a DB query.
    """
    full_prefix = _build_prefix("user", "permissions")
    user_auth_cache._l1.delete_by_prefix(full_prefix)
    redis = await user_auth_cache._get_redis()
    if redis is not None:
        try:
            keys = await redis.keys(f"{full_prefix}*")
            if keys:
                await redis.delete(*keys)
        except Exception as exc:
            logger.warning("Auth cache L2 bulk permissions delete failed: %s", exc)


# ---------------------------------------------------------------------------
# Role Cache
# ---------------------------------------------------------------------------

_role_cache = AuthCache(
    scope="user",
    ttl=settings.USER_CACHE_TTL,
    l1_max=settings.USER_CACHE_L1_MAX_ENTRIES,
)


async def get_cached_roles(user_id: str) -> Optional[List[Dict[str, Any]]]:
    """Get cached roles for a user. Returns None if not cached."""
    key = _build_key("user", "roles", user_id)
    result = _role_cache._l1.get(key)
    if result is not None:
        return result

    redis = await _role_cache._get_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(key)
        if raw is None:
            return None
        data = swx_loads(raw) if isinstance(raw, str) else raw
        _role_cache._l1.set(key, data, settings.USER_CACHE_TTL)
        return data
    except Exception as exc:
        logger.warning("Role cache L2 get failed for %s: %s", key, exc)
        return None


async def set_cached_roles(user_id: str, roles: List[Dict[str, Any]]) -> None:
    """Cache roles for a user."""
    key = _build_key("user", "roles", user_id)
    _role_cache._l1.set(key, roles, settings.USER_CACHE_TTL)

    redis = await _role_cache._get_redis()
    if redis is None:
        return
    try:
        serialized = swx_dumps(roles)
        await redis.setex(key, settings.USER_CACHE_TTL, serialized)
    except Exception as exc:
        logger.warning("Role cache L2 set failed for %s: %s", key, exc)


async def invalidate_user_roles(user_id: UUID | str) -> None:
    """Invalidate cached roles for a user."""
    uid = str(user_id)
    key = _build_key("user", "roles", uid)
    _role_cache._l1.delete(key)

    redis = await _role_cache._get_redis()
    if redis is None:
        return
    try:
        await redis.delete(key)
    except Exception as exc:
        logger.warning("Role cache L2 delete failed for %s: %s", key, exc)


async def invalidate_all_roles() -> None:
    """Invalidate all cached role entries (L1 + L2).

    Used when role definitions change, affecting all users with that role.
    """
    full_prefix = _build_prefix("user", "roles")
    _role_cache._l1.delete_by_prefix(full_prefix)
    redis = await _role_cache._get_redis()
    if redis is not None:
        try:
            keys = await redis.keys(f"{full_prefix}*")
            if keys:
                await redis.delete(*keys)
        except Exception as exc:
            logger.warning("Role cache L2 bulk roles delete failed: %s", exc)
