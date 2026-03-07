"""
Caching Utilities
-----------------
Caching decorators and utilities.
"""

import functools
import json
import hashlib
import asyncio
from typing import TypeVar, Callable, Optional, Any, Dict, Union
from datetime import timedelta
from functools import wraps

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from swx_core.middleware.logging_middleware import logger


T = TypeVar("T")


class CacheBackend:
    """Base cache backend interface."""
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        raise NotImplementedError
    
    async def set(self, key: str, value: Any, ttl: int = None) -> None:
        """Set value in cache."""
        raise NotImplementedError
    
    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        raise NotImplementedError
    
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        raise NotImplementedError
    
    async def clear(self) -> None:
        """Clear all cache."""
        raise NotImplementedError


class MemoryCache(CacheBackend):
    """In-memory cache backend (for development/testing)."""
    
    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, Any] = {}
        self._max_size = max_size
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            return self._cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: int = None) -> None:
        async with self._lock:
            if len(self._cache) >= self._max_size and key not in self._cache:
                # Remove oldest item
                self._cache.pop(next(iter(self._cache)))
            self._cache[key] = value
    
    async def delete(self, key: str) -> None:
        async with self._lock:
            self._cache.pop(key, None)
    
    async def exists(self, key: str) -> bool:
        async with self._lock:
            return key in self._cache
    
    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()


class RedisCache(CacheBackend):
    """Redis cache backend."""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0", prefix: str = "swx:"):
        if not REDIS_AVAILABLE:
            raise ImportError("Redis is not installed. Install with: pip install redis")
        
        self._redis_url = redis_url
        self._prefix = prefix
        self._client: Optional[redis.Redis] = None
    
    async def _get_client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self._redis_url)
        return self._client
    
    def _make_key(self, key: str) -> str:
        return f"{self._prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        client = await self._get_client()
        value = await client.get(self._make_key(key))
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    
    async def set(self, key: str, value: Any, ttl: int = None) -> None:
        client = await self._get_client()
        serialized = json.dumps(value) if not isinstance(value, (str, bytes)) else value
        if ttl:
            await client.setex(self._make_key(key), ttl, serialized)
        else:
            await client.set(self._make_key(key), serialized)
    
    async def delete(self, key: str) -> None:
        client = await self._get_client()
        await client.delete(self._make_key(key))
    
    async def exists(self, key: str) -> bool:
        client = await self._get_client()
        return await client.exists(self._make_key(key)) > 0
    
    async def clear(self) -> None:
        client = await self._get_client()
        # Only clear keys with our prefix
        keys = await client.keys(f"{self._prefix}*")
        if keys:
            await client.delete(*keys)


# Global cache instance
_cache: Optional[CacheBackend] = None


def get_cache() -> CacheBackend:
    """Get the global cache instance."""
    global _cache
    if _cache is None:
        # Default to memory cache
        _cache = MemoryCache()
    return _cache


def set_cache(cache: CacheBackend) -> None:
    """Set the global cache instance."""
    global _cache
    _cache = cache


def init_redis_cache(redis_url: str = "redis://localhost:6379/0", prefix: str = "swx:") -> None:
    """Initialize Redis cache backend."""
    global _cache
    _cache = RedisCache(redis_url=redis_url, prefix=prefix)


def cache_key(*args, **kwargs) -> str:
    """Generate a cache key from function arguments."""
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
    key_string = ":".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


def cached(
    ttl: int = 3600,
    key_prefix: str = "",
    key_builder: Optional[Callable] = None,
):
    """
    Decorator to cache function results.
    
    Usage:
        @cached(ttl=300, key_prefix="user")
        async def get_user(user_id: str):
            return await repository.find_by_id(user_id)
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
        key_builder: Custom key builder function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Build cache key
            if key_builder:
                key = key_builder(*args, **kwargs)
            else:
                key = f"{key_prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"
            
            # Try to get from cache
            cached_value = await cache.get(key)
            if cached_value is not None:
                logger.debug(f"Cache hit for key: {key}")
                return cached_value
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache.set(key, result, ttl=ttl)
            logger.debug(f"Cached result for key: {key}")
            
            return result
        
        return wrapper
    return decorator


def cache_result(
    key: str,
    ttl: int = 3600,
):
    """
    Decorator to cache with explicit key.
    
    Usage:
        @cache_result(key="all_users", ttl=600)
        async def get_all_users():
            return await repository.find_all()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Try to get from cache
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # Execute function
            result = await func(*args, **kwargs)
            
            # Cache result
            await cache.set(key, result, ttl=ttl)
            
            return result
        
        return wrapper
    return decorator


def invalidate_cache(key_pattern: str):
    """
    Decorator to invalidate cache after function execution.
    
    Usage:
        @invalidate_cache(key_pattern="user:*")
        async def update_user(user_id: str, data: dict):
            return await repository.update(user_id, data)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Execute function
            result = await func(*args, **kwargs)
            
            # Invalidate cache
            cache = get_cache()
            if isinstance(cache, RedisCache):
                client = await cache._get_client()
                keys = await client.keys(f"{cache._prefix}{key_pattern}")
                if keys:
                    await client.delete(*keys)
            else:
                # For memory cache, clear all matching keys
                await cache.clear()
            
            return result
        
        return wrapper
    return decorator


class CachedProperty:
    """
    Cached property descriptor.
    
    Usage:
        class User:
            @CachedProperty(ttl=3600)
            async def full_name(self):
                return f"{self.first_name} {self.last_name}"
    """
    
    def __init__(self, ttl: int = 3600):
        self.ttl = ttl
        self.attr_name = None
    
    def __set_name__(self, owner, name):
        self.attr_name = name
    
    def __get__(self, instance, owner):
        if instance is None:
            return self
        
        # Check if cached
        cache_attr = f"_cached_{self.attr_name}"
        if hasattr(instance, cache_attr):
            return getattr(instance, cache_attr)
        
        # Execute and cache
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            getattr(instance, f"_{self.attr_name}")()
        )
        setattr(instance, cache_attr, result)
        return result


def memoize(func: Callable) -> Callable:
    """
    Simple memoization decorator.
    
    Usage:
        @memoize
        async def expensive_computation(n: int):
            # Complex computation
            return result
    """
    cache: Dict[str, Any] = {}
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        key = cache_key(*args, **kwargs)
        if key in cache:
            return cache[key]
        
        result = await func(*args, **kwargs)
        cache[key] = result
        return result
    
    return wrapper