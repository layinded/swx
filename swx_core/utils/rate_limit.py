"""
Rate Limiting Decorators
------------------------
Decorators for API rate limiting.
"""

import functools
import time
import hashlib
from typing import Callable, Optional, Dict, Any
from functools import wraps

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

from fastapi import Request, HTTPException, status
from swx_core.middleware.logging_middleware import logger


class RateLimitExceeded(HTTPException):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": "60"},
        )


class RateLimiter:
    """
    Rate limiter implementation.
    
    Supports:
    - In-memory rate limiting (for development)
    - Redis-based rate limiting (for production)
    - Multiple rate limit windows (per minute, per hour, per day)
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        prefix: str = "rate_limit:",
    ):
        """
        Initialize rate limiter.
        
        Args:
            redis_url: Redis connection URL (optional)
            prefix: Key prefix for Redis
        """
        self.prefix = prefix
        self._redis: Optional[redis.Redis] = None
        self._redis_url = redis_url
        self._memory_store: Dict[str, Dict[str, Any]] = {}
    
    async def _get_redis(self) -> Optional[redis.Redis]:
        """Get Redis client."""
        if not REDIS_AVAILABLE or not self._redis_url:
            return None
        
        if self._redis is None:
            self._redis = redis.from_url(self._redis_url)
        
        return self._redis
    
    def _make_key(self, identifier: str, action: str) -> str:
        """Create rate limit key."""
        return f"{self.prefix}{identifier}:{action}"
    
    async def is_allowed(
        self,
        identifier: str,
        action: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """
        Check if request is allowed.
        
        Args:
            identifier: Unique identifier (e.g., IP address, user ID)
            action: Action name (e.g., "api_call", "login")
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, remaining_requests, retry_after_seconds)
        """
        key = self._make_key(identifier, action)
        current_time = time.time()
        window_start = current_time - window_seconds
        
        # Try Redis first
        redis_client = await self._get_redis()
        
        if redis_client:
            return await self._check_redis(redis_client, key, max_requests, window_seconds, current_time)
        else:
            return await self._check_memory(key, max_requests, window_seconds, current_time, window_start)
    
    async def _check_redis(
        self,
        redis_client: redis.Redis,
        key: str,
        max_requests: int,
        window_seconds: int,
        current_time: float,
    ) -> tuple[bool, int, int]:
        """Check rate limit using Redis."""
        # Use sliding window algorithm
        window_start = current_time - window_seconds
        
        # Remove old entries
        await redis_client.zremrangebyscore(key, 0, window_start)
        
        # Count current requests
        count = await redis_client.zcard(key)
        
        if count >= max_requests:
            # Get oldest request time to calculate retry-after
            oldest = await redis_client.zrange(key, 0, 0, withscores=True)
            retry_after = int(oldest[0][1] + window_seconds - current_time) if oldest else window_seconds
            return False, 0, max(1, retry_after)
        
        # Add current request
        await redis_client.zadd(key, {str(current_time): current_time})
        await redis_client.expire(key, window_seconds)
        
        return True, max_requests - count - 1, 0
    
    async def _check_memory(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
        current_time: float,
        window_start: float,
    ) -> tuple[bool, int, int]:
        """Check rate limit using in-memory store."""
        if key not in self._memory_store:
            self._memory_store[key] = {"timestamps": []}
        
        # Remove old entries
        self._memory_store[key]["timestamps"] = [
            ts for ts in self._memory_store[key]["timestamps"]
            if ts > window_start
        ]
        
        count = len(self._memory_store[key]["timestamps"])
        
        if count >= max_requests:
            oldest = min(self._memory_store[key]["timestamps"])
            retry_after = int(oldest + window_seconds - current_time)
            return False, 0, max(1, retry_after)
        
        # Add current request
        self._memory_store[key]["timestamps"].append(current_time)
        
        return True, max_requests - count - 1, 0
    
    async def reset(self, identifier: str, action: str) -> None:
        """Reset rate limit for identifier."""
        key = self._make_key(identifier, action)
        
        redis_client = await self._get_redis()
        if redis_client:
            await redis_client.delete(key)
        else:
            self._memory_store.pop(key, None)


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def set_rate_limiter(limiter: RateLimiter) -> None:
    """Set the global rate limiter instance."""
    global _rate_limiter
    _rate_limiter = limiter


def rate_limit(
    max_requests: int = 100,
    window_seconds: int = 60,
    identifier_func: Optional[Callable] = None,
    action: str = "default",
):
    """
    Decorator to rate limit a function.
    
    Usage:
        @rate_limit(max_requests=10, window_seconds=60)
        async def expensive_operation(user_id: str):
            return {"result": "success"}
        
        @rate_limit(max_requests=5, window_seconds=60, identifier_func=lambda req: req.client.host)
        async def api_endpoint(request: Request):
            return {"data": "value"}
    
    Args:
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds
        identifier_func: Function to extract identifier from request
        action: Action name for rate limit key
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get identifier
            if identifier_func:
                # Find request in args or kwargs
                request = None
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break
                if request is None:
                    request = kwargs.get("request")
                
                if request:
                    identifier = identifier_func(request)
                else:
                    identifier = "anonymous"
            else:
                # Use first arg as identifier
                identifier = str(args[0]) if args else "anonymous"
            
            # Check rate limit
            limiter = get_rate_limiter()
            allowed, remaining, retry_after = await limiter.is_allowed(
                identifier=identifier,
                action=action,
                max_requests=max_requests,
                window_seconds=window_seconds,
            )
            
            if not allowed:
                raise RateLimitExceeded(
                    detail=f"Rate limit exceeded. Try again in {retry_after} seconds."
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def rate_limit_by_ip(
    max_requests: int = 100,
    window_seconds: int = 60,
    action: str = "api",
):
    """
    Decorator to rate limit by IP address.
    
    Usage:
        @rate_limit_by_ip(max_requests=100, window_seconds=60)
        async def public_endpoint(request: Request):
            return {"data": "value"}
    """
    def identifier_func(request: Request) -> str:
        return request.client.host if request.client else "unknown"
    
    return rate_limit(
        max_requests=max_requests,
        window_seconds=window_seconds,
        identifier_func=identifier_func,
        action=action,
    )


def rate_limit_by_user(
    max_requests: int = 100,
    window_seconds: int = 60,
    action: str = "api",
):
    """
    Decorator to rate limit by user ID.
    
    Usage:
        @rate_limit_by_user(max_requests=50, window_seconds=60)
        async def protected_endpoint(request: Request, user: User = Depends(get_current_user)):
            return {"data": "value"}
    """
    def identifier_func(request: Request) -> str:
        # Try to get user from request state
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "id"):
            return str(user.id)
        return "anonymous"
    
    return rate_limit(
        max_requests=max_requests,
        window_seconds=window_seconds,
        identifier_func=identifier_func,
        action=action,
    )


def rate_limit_by_api_key(
    max_requests: int = 1000,
    window_seconds: int = 60,
    action: str = "api",
):
    """
    Decorator to rate limit by API key.
    
    Usage:
        @rate_limit_by_api_key(max_requests=1000, window_seconds=60)
        async def api_endpoint(request: Request):
            return {"data": "value"}
    """
    def identifier_func(request: Request) -> str:
        # Try to get API key from headers
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "")
        if api_key.startswith("ApiKey "):
            api_key = api_key[7:]
        return api_key or "anonymous"
    
    return rate_limit(
        max_requests=max_requests,
        window_seconds=window_seconds,
        identifier_func=identifier_func,
        action=action,
    )


# Dependency for FastAPI
async def check_rate_limit(
    request: Request,
    max_requests: int = 100,
    window_seconds: int = 60,
    action: str = None,
):
    """
    FastAPI dependency to check rate limit.
    
    Usage:
        @router.get("/endpoint")
        async def endpoint(
            request: Request,
            _: None = Depends(check_rate_limit)
        ):
            return {"data": "value"}
    """
    if action is None:
        action = f"{request.method}:{request.url.path}"
    
    limiter = get_rate_limiter()
    identifier = request.client.host if request.client else "unknown"
    
    allowed, remaining, retry_after = await limiter.is_allowed(
        identifier=identifier,
        action=action,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
    
    if not allowed:
        raise RateLimitExceeded(
            detail=f"Rate limit exceeded. Try again in {retry_after} seconds."
        )
    
    # Add rate limit headers to response
    request.state.rate_limit_remaining = remaining
    request.state.rate_limit_reset = int(time.time()) + window_seconds