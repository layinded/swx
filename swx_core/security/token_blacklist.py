"""
Token Blacklist - Redis-backed token revocation system.

Provides token revocation for JWT-based authentication with:
- Token revocation by JTI
- User-level token revocation
- TTL sync with token expiration
"""

import hashlib
from typing import Optional, Set
from datetime import datetime, timezone, timedelta


class TokenBlacklist:
    """
    Base token blacklist interface.
    
    Implement this interface to provide different storage backends.
    """
    
    async def revoke(self, token_id: str, ttl_seconds: int) -> None:
        """
        Revoke a token.
        
        Args:
            token_id: Token identifier (JTI or hash)
            ttl_seconds: Time to live in seconds
        """
        raise NotImplementedError
    
    async def is_revoked(self, token: str) -> bool:
        """
        Check if token is revoked.
        
        Args:
            token: Full token string
            
        Returns:
            bool: True if revoked
        """
        raise NotImplementedError
    
    async def is_revoked_by_jti(self, jti: str) -> bool:
        """
        Check if JTI is revoked.
        
        Args:
            jti: Token JTI
            
        Returns:
            bool: True if revoked
        """
        raise NotImplementedError
    
    async def revoke_user_tokens(self, user_id: str, ttl_seconds: int = None) -> None:
        """
        Revoke all tokens for a user.
        
        Args:
            user_id: User ID
            ttl_seconds: Time to live in seconds
        """
        raise NotImplementedError
    
    async def is_user_revoked(self, user_id: str, token_iat: datetime) -> bool:
        """
        Check if user's tokens issued before a time are revoked.
        
        Args:
            user_id: User ID
            token_iat: Token issued-at time
            
        Returns:
            bool: True if user's tokens are revoked
        """
        raise NotImplementedError


class RedisTokenBlacklist(TokenBlacklist):
    """
    Redis-backed token blacklist.
    
    Features:
    - O(1) lookup time
    - Automatic expiration via TTL
    - User-level revocation with timestamp
    """
    
    def __init__(
        self,
        redis_client,
        prefix: str = "revoked_tokens:",
        user_prefix: str = "user_revoked:"
    ):
        """
        Initialize Redis token blacklist.
        
        Args:
            redis_client: Async Redis client
            prefix: Key prefix for token revocations
            user_prefix: Key prefix for user revocations
        """
        self.redis = redis_client
        self.prefix = prefix
        self.user_prefix = user_prefix
    
    async def revoke(self, token_id: str, ttl_seconds: int) -> None:
        """
        Revoke a token by its ID.
        
        Args:
            token_id: Token identifier (JTI or hash)
            ttl_seconds: Time to live in seconds
        """
        key = f"{self.prefix}{token_id}"
        await self.redis.setex(key, ttl_seconds, "1")
    
    async def revoke_token(self, token: str, payload: dict = None) -> None:
        """
        Revoke a token by its full string or payload.
        
        Args:
            token: Full token string
            payload: Decoded token payload (optional, for efficiency)
        """
        if payload:
            jti = payload.get("jti") or payload.get("sub")
            exp = payload.get("exp")
        else:
            jti = hashlib.sha256(token.encode()).hexdigest()
            exp = None
        
        # Calculate TTL
        if exp:
            ttl = max(1, int(exp - datetime.now(timezone.utc).timestamp()))
        else:
            ttl = 2592000  # 30 days default
        
        await self.revoke(jti, ttl)
    
    async def is_revoked(self, token: str, payload: dict = None) -> bool:
        """
        Check if a token is revoked.
        
        Args:
            token: Full token string
            payload: Decoded token payload (optional)
            
        Returns:
            bool: True if revoked
        """
        if payload:
            jti = payload.get("jti") or payload.get("sub")
            user_id = payload.get("sub")
            iat = payload.get("iat")
        else:
            jti = hashlib.sha256(token.encode()).hexdigest()
            user_id = None
            iat = None
        
        # Check if token JTI is revoked
        key = f"{self.prefix}{jti}"
        if await self.redis.exists(key):
            return True
        
        # Check if user's tokens are revoked
        if user_id:
            revoked_at = await self.redis.get(f"{self.user_prefix}{user_id}")
            if revoked_at:
                # Token issued before user revocation?
                if iat:
                    try:
                        iat_dt = datetime.fromtimestamp(iat, tz=timezone.utc)
                        revoked_dt = datetime.fromisoformat(revoked_at)
                        if iat_dt < revoked_dt:
                            return True
                    except (ValueError, TypeError):
                        pass
        
        return False
    
    async def is_revoked_by_jti(self, jti: str) -> bool:
        """
        Check if a JTI is revoked.
        
        Args:
            jti: Token JTI
            
        Returns:
            bool: True if revoked
        """
        key = f"{self.prefix}{jti}"
        return bool(await self.redis.exists(key))
    
    async def revoke_user_tokens(
        self,
        user_id: str,
        ttl_seconds: int = None
    ) -> None:
        """
        Revoke all tokens for a user.
        
        Stores a timestamp; all tokens issued before this are revoked.
        
        Args:
            user_id: User ID
            ttl_seconds: Time to live (default 30 days)
        """
        if ttl_seconds is None:
            ttl_seconds = 2592000  # 30 days
        
        key = f"{self.user_prefix}{user_id}"
        now = datetime.now(timezone.utc).isoformat()
        
        await self.redis.setex(key, ttl_seconds, now)
    
    async def is_user_revoked(self, user_id: str, token_iat: datetime) -> bool:
        """
        Check if user's tokens issued before a time are revoked.
        
        Args:
            user_id: User ID
            token_iat: Token issued-at time
            
        Returns:
            bool: True if revoked
        """
        revoked_at = await self.redis.get(f"{self.user_prefix}{user_id}")
        
        if not revoked_at:
            return False
        
        try:
            revoked_dt = datetime.fromisoformat(revoked_at)
            return token_iat < revoked_dt
        except (ValueError, TypeError):
            return False
    
    async def get_revoked_users(self) -> Set[str]:
        """
        Get all users with revoked tokens.
        
        Returns:
            Set of user IDs
        """
        keys = await self.redis.keys(f"{self.user_prefix}*")
        return {k.replace(self.user_prefix, "") for k in keys}
    
    async def clear_revoked_user(self, user_id: str) -> None:
        """
        Clear revocation for a user.
        
        Args:
            user_id: User ID
        """
        key = f"{self.user_prefix}{user_id}"
        await self.redis.delete(key)
    
    async def get_revoked_count(self) -> int:
        """
        Get count of revoked tokens.
        
        Returns:
            int: Count of revoked tokens
        """
        keys = await self.redis.keys(f"{self.prefix}*")
        return len(keys)


class InMemoryTokenBlacklist(TokenBlacklist):
    """
    In-memory token blacklist for development/testing.
    
    NOT suitable for production with multiple workers.
    """
    
    def __init__(self):
        self._revoked: Set[str] = set()
        self._user_revoked: dict = {}  # user_id -> revoked_at timestamp
    
    async def revoke(self, token_id: str, ttl_seconds: int) -> None:
        """Revoke a token."""
        self._revoked.add(token_id)
    
    async def is_revoked(self, token: str, payload: dict = None) -> bool:
        """Check if token is revoked."""
        if payload:
            jti = payload.get("jti") or payload.get("sub")
            user_id = payload.get("sub")
            iat = payload.get("iat")
        else:
            jti = hashlib.sha256(token.encode()).hexdigest()
            user_id = None
            iat = None
        
        if jti in self._revoked:
            return True
        
        if user_id and user_id in self._user_revoked:
            if iat:
                iat_dt = datetime.fromtimestamp(iat, tz=timezone.utc)
                revoked_dt = self._user_revoked[user_id]
                if iat_dt < revoked_dt:
                    return True
        
        return False
    
    async def is_revoked_by_jti(self, jti: str) -> bool:
        """Check if JTI is revoked."""
        return jti in self._revoked
    
    async def revoke_user_tokens(
        self,
        user_id: str,
        ttl_seconds: int = None
    ) -> None:
        """Revoke all tokens for a user."""
        self._user_revoked[user_id] = datetime.now(timezone.utc)
    
    async def is_user_revoked(self, user_id: str, token_iat: datetime) -> bool:
        """Check if user's tokens are revoked."""
        if user_id not in self._user_revoked:
            return False
        return token_iat < self._user_revoked[user_id]
    
    def clear(self) -> None:
        """Clear all revocations."""
        self._revoked.clear()
        self._user_revoked.clear()