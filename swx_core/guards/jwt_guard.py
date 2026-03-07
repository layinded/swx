"""
JWT Authentication Guard.

Implements JWT-based authentication with token blacklisting support.
"""

import jwt
import uuid
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from enum import Enum
from fastapi import Request, HTTPException, status

from swx_core.guards.base import BaseGuard, AuthenticatedUser
from swx_core.config.settings import settings
from swx_core.middleware.logging_middleware import logger


class TokenBlacklistUnavailableError(Exception):
    """Raised when token blacklist is unavailable in strict mode."""
    pass


class TokenAudience(str, Enum):
    """Token audience types."""
    USER = "user"
    ADMIN = "admin"
    SYSTEM = "system"
    API_KEY = "api_key"


class JWTGuard(BaseGuard):
    """
    JWT-based authentication guard.
    
    Features:
    - Multiple audiences (user, admin, system, api_key)
    - Token blacklisting via Redis
    - Refresh tokens
    - JTI-based revocation
    - User-level token revocation
    - FAIL-CLOSED security on blacklist errors
    """
    
    def __init__(
        self,
        secret_key: str = None,
        algorithm: str = None,
        access_token_expire: int = None,
        refresh_token_expire: int = None,
        token_blacklist = None,
        default_audience: str = TokenAudience.USER,
        strict_blacklist: bool = True
    ):
        """
        Initialize JWT Guard.
        
        Args:
            secret_key: JWT signing key (default: from settings)
            algorithm: JWT algorithm (default: HS256)
            access_token_expire: Access token expiry in minutes
            refresh_token_expire: Refresh token expiry in days
            token_blacklist: TokenBlacklist implementation for revocation
            default_audience: Default token audience
            strict_blacklist: If True and no blacklist configured, deny all tokens.
                              Production MUST use True. Development can use False.
        """
        self.secret_key = secret_key or settings.SECRET_KEY
        self.algorithm = algorithm or getattr(settings, 'PASSWORD_SECURITY_ALGORITHM', 'HS256')
        self.access_token_expire = access_token_expire or getattr(settings, 'ACCESS_TOKEN_EXPIRE_MINUTES', 10080)
        self.refresh_token_expire = refresh_token_expire or getattr(settings, 'REFRESH_TOKEN_EXPIRE_DAYS', 30)
        self.token_blacklist = token_blacklist
        self.default_audience = default_audience
        self.strict_blacklist = strict_blacklist
        
        # P0 Security: Validate blacklist configuration
        if self.strict_blacklist and self.token_blacklist is None:
            env = getattr(settings, 'ENVIRONMENT', 'production').lower()
            if env not in ('development', 'test', 'testing', 'local'):
                raise TokenBlacklistUnavailableError(
                    "Token blacklist is required in production. "
                    "Provide a TokenBlacklist implementation or set strict_blacklist=False "
                    "only for development/testing."
                )
            logger.warning(
                "Token blacklist not configured in %s environment. "
                "Revoked tokens will NOT be blocked. Configure Redis for production.",
                env
            )
    
    @property
    def name(self) -> str:
        return "jwt"
    
    async def authenticate(self, request: Request) -> Optional[AuthenticatedUser]:
        """
        Authenticate request via JWT token.
        
        Extraction order:
        1. Authorization header (Bearer token)
        2. Query parameter (token=)
        3. Cookie (access_token)
        
        Security: FAIL-CLOSED on blacklist errors.
        """
        token = await self._extract_token(request)
        
        if not token:
            return None
        
        # Check revocation with FAIL-CLOSED security
        if self.token_blacklist:
            try:
                is_revoked = await self.token_blacklist.is_revoked(token)
                if is_revoked:
                    logger.warning(
                        f"Revoked token used from {request.client.host if request.client else 'unknown'}"
                    )
                    return None
            except Exception as e:
                # P0 Security: Fail-closed on blacklist errors
                # In production, we MUST deny requests when we can't verify revocation
                logger.error(f"Token blacklist check failed: {e}. Denying request for security.")
                if self.strict_blacklist:
                    return None
                # In development/test mode, log but continue (not recommended for production)
                logger.warning("Token blacklist unavailable. Continuing in non-strict mode.")
        elif self.strict_blacklist:
            # No blacklist configured in strict mode - deny all
            logger.error("Token blacklist not configured in strict mode. Denying request.")
            return None
        
        try:
            # Determine audience from request path
            audience = self._determine_audience(request)
            payload = await self.validate_token(token)
            
            # Verify audience
            token_audience = payload.get("aud")
            if token_audience and token_audience != audience:
                # Token may be valid for a different audience
                # This is acceptable for admin tokens on user endpoints
                if not (token_audience == TokenAudience.ADMIN and audience == TokenAudience.USER):
                    return None
            
            return self._build_user(payload)
            
        except jwt.InvalidTokenError as e:
            logger.debug(f"Token validation failed: {e}")
            return None
        except TokenBlacklistUnavailableError:
            # Re-raise configuration errors
            raise
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate JWT token."""
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise jwt.InvalidTokenError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise jwt.InvalidTokenError(f"Invalid token: {e}")
    
    async def create_token(
        self,
        user: Any,
        audience: str = None,
        scopes: list = None,
        **claims
    ) -> str:
        """Create a JWT token for user."""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self.access_token_expire)
        
        audience = audience or self.default_audience
        
        payload = {
            "sub": str(user.id),
            "email": getattr(user, 'email', ''),
            "aud": audience,
            "exp": expire.timestamp(),
            "iat": now.timestamp(),
            "jti": str(uuid.uuid4()),
        }
        
        # Add roles and permissions
        if hasattr(user, 'roles'):
            payload["roles"] = [r.name if hasattr(r, 'name') else r for r in user.roles]
        
        if hasattr(user, 'permissions'):
            payload["permissions"] = [p.name if hasattr(p, 'name') else p for p in user.permissions]
        
        if hasattr(user, 'is_superuser'):
            payload["super"] = user.is_superuser
        
        if hasattr(user, 'is_active'):
            payload["active"] = user.is_active
        
        if scopes:
            payload["scope"] = " ".join(scopes)
        
        # Add extra claims
        payload.update(claims)
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    async def create_refresh_token(
        self,
        user: Any,
        audience: str = None
    ) -> str:
        """Create a refresh token."""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=self.refresh_token_expire)
        
        audience = audience or self.default_audience
        
        payload = {
            "sub": str(user.id),
            "aud": audience,
            "exp": expire.timestamp(),
            "iat": now.timestamp(),
            "jti": str(uuid.uuid4()),
            "type": "refresh"
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    async def revoke_token(self, token: str) -> bool:
        """Revoke a token by adding to blacklist."""
        if not self.token_blacklist:
            logger.warning("Attempted to revoke token but no blacklist configured")
            return False
        
        try:
            payload = await self.validate_token(token)
            jti = payload.get("jti") or hashlib.sha256(token.encode()).hexdigest()
            exp = payload.get("exp")
            
            if exp:
                ttl = max(1, int(exp - datetime.now(timezone.utc).timestamp()))
                await self.token_blacklist.revoke(jti, ttl)
            else:
                # Default TTL of 30 days
                await self.token_blacklist.revoke(jti, 2592000)
            
            return True
        except Exception as e:
            logger.error(f"Failed to revoke token: {e}")
            return False
    
    async def revoke_all_tokens_for_user(self, user_id: str) -> bool:
        """Revoke all tokens for a user."""
        if not self.token_blacklist:
            logger.warning("Attempted to revoke user tokens but no blacklist configured")
            return False
        
        try:
            await self.token_blacklist.revoke_user_tokens(user_id, ttl_seconds=2592000)
            return True
        except Exception as e:
            logger.error(f"Failed to revoke user tokens: {e}")
            return False
    
    async def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Create a new access token from refresh token."""
        try:
            payload = await self.validate_token(refresh_token)
            
            if payload.get("type") != "refresh":
                return None
            
            # Check if refresh token is revoked
            if self.token_blacklist:
                jti = payload.get("jti")
                if jti:
                    try:
                        if await self.token_blacklist.is_revoked_by_jti(jti):
                            return None
                    except Exception:
                        # Fail-closed on blacklist errors in strict mode
                        if self.strict_blacklist:
                            logger.error("Blacklist check failed during token refresh. Denying.")
                            return None
            
            # Create new access token
            user_id = payload.get("sub")
            audience = payload.get("aud", self.default_audience)
            
            # Create minimal user object
            class MinimalUser:
                def __init__(self, id):
                    self.id = id
                    self.email = ""
                    self.roles = []
                    self.permissions = []
                    self.is_superuser = False
                    self.is_active = True
            
            return await self.create_token(MinimalUser(user_id), audience=audience)
            
        except jwt.InvalidTokenError:
            return None
    
    async def _extract_token(self, request: Request) -> Optional[str]:
        """Extract token from request."""
        # 1. Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        
        # 2. Query parameter
        token = request.query_params.get("token")
        if token:
            return token
        
        # 3. Cookie
        if hasattr(request, "cookies"):
            return request.cookies.get("access_token")
        
        return None
    
    def _determine_audience(self, request: Request) -> str:
        """Determine token audience from request path."""
        path = request.url.path
        
        if path.startswith("/api/admin") or path.startswith("/admin"):
            return TokenAudience.ADMIN
        
        return TokenAudience.USER
    
    def _build_user(self, payload: Dict[str, Any]) -> AuthenticatedUser:
        """Build authenticated user from token payload."""
        return AuthenticatedUser(
            id=payload.get("sub"),
            email=payload.get("email", ""),
            type=payload.get("aud", TokenAudience.USER),
            roles=payload.get("roles", []),
            permissions=payload.get("permissions", []),
            is_superuser=payload.get("super", False),
            is_active=payload.get("active", True),
            metadata=payload
        )