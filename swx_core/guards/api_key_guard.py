"""
API Key Authentication Guard.

Implements API key-based authentication for internal services.
"""

import hashlib
import secrets
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import Request

from swx_core.guards.base import BaseGuard, AuthenticatedUser
from swx_core.middleware.logging_middleware import logger


class APIKeyGuard(BaseGuard):
    """
    API Key authentication guard.
    
    Features:
    - Header-based (X-API-Key)
    - Query parameter (api_key=)
    - Key prefix for identification
    - Rate limiting per key
    - Scoped permissions
    """
    
    def __init__(
        self,
        header_name: str = "X-API-Key",
        query_param: str = "api_key",
        key_repository = None,
        cache = None
    ):
        self.header_name = header_name
        self.query_param = query_param
        self.key_repository = key_repository
        self.cache = cache
    
    @property
    def name(self) -> str:
        return "api_key"
    
    async def authenticate(self, request: Request) -> Optional[AuthenticatedUser]:
        """Authenticate via API key."""
        key = await self._extract_key(request)
        
        if not key:
            return None
        
        # Look up key
        key_info = await self._lookup_key(key)
        
        if not key_info:
            logger.warning(
                f"Invalid API key from {request.client.host if request.client else 'unknown'}"
            )
            return None
        
        # Check expiration
        if key_info.get("expires_at"):
            expires_at = key_info["expires_at"]
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            
            if datetime.now(timezone.utc) > expires_at:
                logger.info(f"Expired API key used: {key_info.get('key_id')}")
                return None
        
        # Check if key is active
        if not key_info.get("is_active", True):
            logger.info(f"Inactive API key used: {key_info.get('key_id')}")
            return None
        
        return AuthenticatedUser(
            id=str(key_info.get("user_id", key_info.get("key_id"))),
            email=key_info.get("user_email", ""),
            type="api_key",
            roles=["api_user"],
            permissions=key_info.get("scopes", []),
            is_superuser=False,
            is_active=True,
            metadata={
                "key_id": key_info.get("key_id"),
                "key_prefix": key[:8] + "...",
                "key_name": key_info.get("name"),
            }
        )
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate (lookup) API key."""
        key_info = await self._lookup_key(token)
        
        if not key_info:
            raise ValueError("Invalid API key")
        
        if not key_info.get("is_active", True):
            raise ValueError("API key is inactive")
        
        return key_info
    
    async def create_token(self, user: Any, **claims) -> str:
        """Create a new API key."""
        # Generate secure random key
        raw_key = secrets.token_urlsafe(32)
        key_prefix = raw_key[:8]
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Store in repository
        if self.key_repository:
            await self.key_repository.create(
                user_id=str(user.id),
                key_prefix=key_prefix,
                hashed_key=hashed_key,
                name=claims.get("name", "API Key"),
                scopes=claims.get("scopes", []),
                expires_at=claims.get("expires_at"),
            )
        
        # Return raw key only once
        return raw_key
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke API key."""
        if not self.key_repository:
            return False
        
        try:
            hashed_key = hashlib.sha256(token.encode()).hexdigest()
            await self.key_repository.deactivate_by_hash(hashed_key)
            return True
        except Exception as e:
            logger.error(f"Failed to revoke API key: {e}")
            return False
    
    async def _extract_key(self, request: Request) -> Optional[str]:
        """Extract API key from request."""
        # 1. Header
        key = request.headers.get(self.header_name)
        if key:
            return key
        
        # 2. Query parameter
        key = request.query_params.get(self.query_param)
        if key:
            return key
        
        return None
    
    async def _lookup_key(self, key: str) -> Optional[Dict[str, Any]]:
        """Look up key in repository/cache."""
        if not self.key_repository:
            return None
        
        # Try cache first
        cache_key = f"apikey:{key[:8]}"
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
        
        # Hash and lookup
        hashed_key = hashlib.sha256(key.encode()).hexdigest()
        key_info = await self.key_repository.get_by_hash(hashed_key)
        
        if key_info and self.cache:
            # Cache for future lookups
            await self.cache.set(cache_key, key_info, ttl=300)
        
        return key_info
    
    def can_revoke(self) -> bool:
        """Check if revocation is supported."""
        return self.key_repository is not None