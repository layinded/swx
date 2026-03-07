"""
Cache Contract.

Defines the interface for cache drivers.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, List


class CacheDriver(ABC):
    """
    Abstract interface for cache drivers.
    
    Implement this interface to add support for different cache backends
    (Redis, Memcached, file, etc.).
    """
    
    @abstractmethod
    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get a value from cache.
        
        Args:
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached value or default
        """
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """
        Set a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (None for no expiry)
            
        Returns:
            bool: True if successful
        """
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete a value from cache.
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if deleted
        """
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists.
        
        Args:
            key: Cache key
            
        Returns:
            bool: True if exists
        """
        pass
    
    @abstractmethod
    async def increment(self, key: str, amount: int = 1) -> int:
        """
        Increment a cached value.
        
        Args:
            key: Cache key
            amount: Amount to increment
            
        Returns:
            int: New value
        """
        pass
    
    @abstractmethod
    async def decrement(self, key: str, amount: int = 1) -> int:
        """
        Decrement a cached value.
        
        Args:
            key: Cache key
            amount: Amount to decrement
            
        Returns:
            int: New value
        """
        pass
    
    @abstractmethod
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            Dict: Key-value pairs (only found keys)
        """
        pass
    
    @abstractmethod
    async def set_many(self, items: Dict[str, Any], ttl: int = None) -> bool:
        """
        Set multiple values in cache.
        
        Args:
            items: Key-value pairs
            ttl: Time to live in seconds
            
        Returns:
            bool: True if successful
        """
        pass
    
    @abstractmethod
    async def delete_many(self, keys: List[str]) -> bool:
        """
        Delete multiple values from cache.
        
        Args:
            keys: List of cache keys
            
        Returns:
            bool: True if successful
        """
        pass
    
    @abstractmethod
    async def clear(self) -> bool:
        """
        Clear all cache.
        
        Returns:
            bool: True if successful
        """
        pass
    
    @abstractmethod
    async def get_ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL for a key.
        
        Args:
            key: Cache key
            
        Returns:
            int: Remaining TTL in seconds, None if no expiry or not found
        """
        pass
    
    @abstractmethod
    async def remember(self, key: str, callback: callable, ttl: int = None) -> Any:
        """
        Get from cache or store callback result.
        
        Args:
            key: Cache key
            callback: Async callable to get value if not cached
            ttl: Time to live in seconds
            
        Returns:
            Cached or callback value
        """
        pass