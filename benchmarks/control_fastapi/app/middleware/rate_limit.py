"""
Control FastAPI Project - Rate Limiting Middleware
Manual in-memory rate limiter for benchmarking against SwX.
"""

import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests: int = 100
    window: int = 60  # seconds
    burst_limit: int = 10


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._configs: Dict[str, RateLimitConfig] = {}
    
    def set_config(self, key: str, config: RateLimitConfig) -> None:
        """Set rate limit config for a key."""
        self._configs[key] = config
    
    def check_rate_limit(
        self,
        identifier: str,
        key: str = "default"
    ) -> tuple[bool, dict]:
        """
        Check if request is within rate limit.
        Returns (allowed, headers)
        """
        config = self._configs.get(key, RateLimitConfig())
        now = time.time()
        window_start = now - config.window
        
        # Get requests in current window
        requests = self._requests[identifier]
        requests = [r for r in requests if r > window_start]
        self._requests[identifier] = requests
        
        # Check limit
        if len(requests) >= config.requests:
            # Calculate retry-after
            oldest = min(requests) if requests else now
            retry_after = int(oldest + config.window - now) + 1
            
            return False, {
                "X-RateLimit-Limit": str(config.requests),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + config.window)),
                "Retry-After": str(retry_after)
            }
        
        # Add current request
        requests.append(now)
        
        remaining = config.requests - len(requests)
        return True, {
            "X-RateLimit-Limit": str(config.requests),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(now + config.window))
        }
    
    def reset(self, identifier: str = None) -> None:
        """Reset rate limit counters."""
        if identifier:
            self._requests.pop(identifier, None)
        else:
            self._requests.clear()


# Global rate limiter
rate_limiter = RateLimiter()

# Default configuration
rate_limiter.set_config("default", RateLimitConfig(requests=100, window=60))
rate_limiter.set_config("auth", RateLimitConfig(requests=5, window=60))
rate_limiter.set_config("api", RateLimitConfig(requests=1000, window=3600))


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""
    
    async def dispatch(self, request: Request, call_next):
        # Skip for health checks
        if request.url.path in ["/health", "/", "/docs", "/openapi.json"]:
            return await call_next(request)
        
        # Get identifier (IP or user ID)
        client_ip = request.client.host if request.client else "unknown"
        user_id = getattr(request.state, "user_id", None)
        identifier = user_id or client_ip
        
        # Get rate limit key from path
        path = request.url.path
        if "/auth/" in path:
            key = "auth"
        elif "/api/" in path:
            key = "api"
        else:
            key = "default"
        
        # Check rate limit
        allowed, headers = rate_limiter.check_rate_limit(identifier, key)
        
        if not allowed:
            return HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
                headers=headers
            )
        
        response = await call_next(request)
        
        # Add rate limit headers
        for key, value in headers.items():
            response.headers[key] = value
        
        return response
