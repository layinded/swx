"""
Rate Limiter Contract.

Defines the interface for rate limiting drivers.
"""

from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime
from dataclasses import dataclass


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    limit: int
    remaining: int
    reset_at: datetime
    retry_after: Optional[int] = None


class RateLimiterInterface(ABC):
    """
    Abstract interface for rate limiters.
    
    Implement this interface to add support for different rate limiting backends.
    """
    
    @abstractmethod
    async def check_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60
    ) -> RateLimitResult:
        """
        Check if a request is within rate limit.
        
        Args:
            key: Rate limit key (e.g., "user:123:api")
            limit: Maximum requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            RateLimitResult with allowed status
        """
        pass
    
    @abstractmethod
    async def increment(self, key: str, window_seconds: int = 60) -> int:
        """
        Increment the counter for a key.
        
        Args:
            key: Rate limit key
            window_seconds: Time window in seconds
            
        Returns:
            int: New count
        """
        pass
    
    @abstractmethod
    async def get_usage(self, key: str) -> int:
        """
        Get current usage count for a key.
        
        Args:
            key: Rate limit key
            
        Returns:
            int: Current count
        """
        pass
    
    @abstractmethod
    async def reset(self, key: str) -> bool:
        """
        Reset the counter for a key.
        
        Args:
            key: Rate limit key
            
        Returns:
            bool: True if reset
        """
        pass
    
    @abstractmethod
    async def get_reset_time(self, key: str) -> Optional[datetime]:
        """
        Get when the rate limit resets.
        
        Args:
            key: Rate limit key
            
        Returns:
            datetime: Reset time, None if not found
        """
        pass
    
    @abstractmethod
    async def block(
        self,
        key: str,
        seconds: int
    ) -> bool:
        """
        Block a key for a period.
        
        Args:
            key: Rate limit key
            seconds: Block duration in seconds
            
        Returns:
            bool: True if blocked
        """
        pass
    
    @abstractmethod
    async def is_blocked(self, key: str) -> bool:
        """
        Check if a key is blocked.
        
        Args:
            key: Rate limit key
            
        Returns:
            bool: True if blocked
        """
        pass