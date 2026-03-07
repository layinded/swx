"""
Rate Limiter
------------
Redis-backed rate limiting with token bucket and sliding window algorithms.

Features:
- Identity-aware limits
- Billing-aware limits
- Feature-aware limits
- Endpoint-aware limits
- Atomic operations
- Fail-closed behavior
"""

import time
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone
from enum import Enum

from swx_core.middleware.logging_middleware import logger


class LimitWindow(str, Enum):
    """Rate limit time windows."""
    MINUTE = "1m"
    HOUR = "1h"
    DAY = "24h"


class RateLimitResult:
    """Result of a rate limit check."""
    def __init__(
        self,
        allowed: bool,
        limit: int,
        remaining: int,
        reset_at: datetime,
        retry_after: Optional[int] = None
    ):
        self.allowed = allowed
        self.limit = limit
        self.remaining = remaining
        self.reset_at = reset_at
        self.retry_after = retry_after


class RateLimiter:
    """
    Redis-backed rate limiter using sliding window algorithm.
    
    Uses atomic Redis operations to ensure thread-safety across
    multiple workers/instances.
    """
    
    def __init__(self, redis_client=None):
        """
        Initialize rate limiter.
        
        Args:
            redis_client: Redis client (aioredis or redis.asyncio)
        """
        self.redis = redis_client
        self._window_seconds = {
            LimitWindow.MINUTE: 60,
            LimitWindow.HOUR: 3600,
            LimitWindow.DAY: 86400,
        }
    
    async def check_limit(
        self,
        key: str,
        limit: int,
        window: LimitWindow = LimitWindow.MINUTE
    ) -> RateLimitResult:
        """
        Check if request is within rate limit.
        
        Uses sliding window algorithm with atomic Redis operations.
        
        Args:
            key: Redis key for this limit (e.g., "rate_limit:user:123:api_requests:read:1m")
            limit: Maximum requests allowed in window
            window: Time window (1m, 1h, 24h)
        
        Returns:
            RateLimitResult with allowed status and metadata
        """
        if not self.redis:
            # Fail closed: if Redis unavailable, deny
            logger.warning("Redis unavailable, rate limit check denied (fail-closed)")
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=datetime.now(timezone.utc),
                retry_after=self._window_seconds[window]
            )
        
        try:
            window_seconds = self._window_seconds[window]
            now = time.time()
            window_start = now - window_seconds
            
            # Use sliding window: count requests in current window
            # Redis key stores sorted set with timestamps as scores
            pipe = self.redis.pipeline()
            
            # Remove expired entries (older than window)
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(now): now})
            
            # Set expiration
            pipe.expire(key, window_seconds)
            
            results = await pipe.execute()
            current_count = results[1]  # Count before adding current request
            
            # Check if limit exceeded
            allowed = current_count < limit
            remaining = max(0, limit - current_count - 1) if allowed else 0
            
            # Calculate reset time
            reset_at = datetime.fromtimestamp(now + window_seconds, tz=timezone.utc)
            retry_after = int(window_seconds) if not allowed else None
            
            return RateLimitResult(
                allowed=allowed,
                limit=limit,
                remaining=remaining,
                reset_at=reset_at,
                retry_after=retry_after
            )
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}", exc_info=True)
            # Fail closed
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                reset_at=datetime.now(timezone.utc),
                retry_after=self._window_seconds[window]
            )
    
    async def get_usage(
        self,
        key: str,
        window: LimitWindow = LimitWindow.MINUTE
    ) -> int:
        """
        Get current usage count for a limit key.
        
        Args:
            key: Redis key
            window: Time window
        
        Returns:
            Current usage count
        """
        if not self.redis:
            return 0
        
        try:
            window_seconds = self._window_seconds[window]
            now = time.time()
            window_start = now - window_seconds
            
            # Remove expired entries
            await self.redis.zremrangebyscore(key, 0, window_start)
            
            # Count current requests
            count = await self.redis.zcard(key)
            return count
            
        except Exception as e:
            logger.error(f"Error getting usage: {e}", exc_info=True)
            return 0
    
    def _build_key(
        self,
        actor_type: str,
        actor_id: str,
        feature: str,
        endpoint_class: str,
        window: LimitWindow
    ) -> str:
        """Build Redis key for rate limit."""
        return f"rate_limit:{actor_type}:{actor_id}:{feature}:{endpoint_class}:{window.value}"


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def set_rate_limiter(limiter: RateLimiter) -> None:
    """Set the global rate limiter instance."""
    global _rate_limiter
    _rate_limiter = limiter
