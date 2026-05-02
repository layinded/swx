"""
Authentication Contracts.

Defines the interfaces for authentication guards, token providers, and user representation.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AuthenticatedUser:
    """
    Representation of an authenticated user.
    
    This is the standardized user object returned by all guards.
    """
    id: str
    email: str
    type: str = "user"  # "user", "admin", "api_key", "system"
    roles: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    is_superuser: bool = False
    is_active: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def has_role(self, role: str) -> bool:
        """Check if user has a specific role."""
        return role in self.roles or self.is_superuser
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission."""
        return permission in self.permissions or self.is_superuser
    
    def has_any_role(self, *roles: str) -> bool:
        """Check if user has any of the specified roles."""
        return any(role in self.roles for role in roles) or self.is_superuser
    
    def has_any_permission(self, *permissions: str) -> bool:
        """Check if user has any of the specified permissions."""
        return any(perm in self.permissions for perm in permissions) or self.is_superuser
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "email": self.email,
            "type": self.type,
            "roles": self.roles,
            "permissions": self.permissions,
            "is_superuser": self.is_superuser,
            "is_active": self.is_active,
            "metadata": self.metadata,
        }


class AuthGuard(ABC):
    """
    Abstract base class for authentication guards.
    
    Guards are responsible for authenticating requests and managing tokens.
    Multiple guards can be configured (JWT, API Key, Session, etc.).
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Get the guard name.
        
        Returns:
            str: Unique identifier for this guard (e.g., "jwt", "api_key")
        """
        pass
    
    @abstractmethod
    async def authenticate(self, request: Any) -> Optional[AuthenticatedUser]:
        """
        Authenticate a request and return the authenticated user.
        
        Args:
            request: The HTTP request object
            
        Returns:
            AuthenticatedUser if authentication succeeds, None otherwise
        """
        pass
    
    @abstractmethod
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """
        Validate a token and return its payload.
        
        Args:
            token: The token string to validate
            
        Returns:
            Dict containing the token payload
            
        Raises:
            InvalidTokenError: If token is invalid or expired
        """
        pass
    
    @abstractmethod
    async def create_token(
        self,
        user: Any,
        audience: str = None,
        **claims
    ) -> str:
        """
        Create a token for a user.
        
        Args:
            user: The user instance
            audience: Token audience (default: guard default)
            **claims: Additional claims to include in token
            
        Returns:
            str: The generated token
        """
        pass
    
    @abstractmethod
    async def revoke_token(self, token: str) -> bool:
        """
        Revoke a token.
        
        Args:
            token: The token to revoke
            
        Returns:
            bool: True if revocation succeeded
        """
        pass
    
    async def revoke_all_tokens_for_user(self, user_id: str) -> bool:
        """
        Revoke all tokens for a user.
        
        Args:
            user_id: The user ID
            
        Returns:
            bool: True if revocation succeeded
        """
        # Default implementation does nothing
        # Override in guards that support this
        return False


class TokenProvider(ABC):
    """
    Abstract base class for token providers.
    
    Token providers handle the low-level token operations.
    """
    
    @abstractmethod
    async def encode(self, payload: Dict[str, Any]) -> str:
        """Encode a payload into a token."""
        pass
    
    @abstractmethod
    async def decode(self, token: str) -> Dict[str, Any]:
        """Decode a token into its payload."""
        pass
    
    @abstractmethod
    async def is_revoked(self, token: str) -> bool:
        """Check if a token is revoked."""
        pass
    
    @abstractmethod
    async def revoke(self, token: str, ttl_seconds: int = None) -> bool:
        """Revoke a token."""
        pass


class PasswordHasher(ABC):
    """
    Abstract base class for password hashing.
    """
    
    @abstractmethod
    def hash(self, password: str) -> str:
        """Hash a password."""
        pass
    
    @abstractmethod
    def verify(self, password: str, hashed: str) -> bool:
        """Verify a password against a hash."""
        pass
    
    @abstractmethod
    def needs_rehash(self, hashed: str) -> bool:
        """Check if a hash needs to be rehashed."""
        pass