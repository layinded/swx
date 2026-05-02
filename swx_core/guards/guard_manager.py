"""
Guard Manager.

Manages multiple authentication guards and provides unified authentication.
"""

from typing import Dict, Optional, Any, List
from fastapi import Request

from swx_core.guards.base import BaseGuard, AuthenticatedUser
from swx_core.middleware.logging_middleware import logger


class GuardManager:
    """
    Manages multiple authentication guards.
    
    Usage:
        manager = GuardManager()
        manager.register("jwt", jwt_guard)
        manager.register("api_key", api_key_guard)
        
        # Get specific guard
        jwt_guard = manager.guard("jwt")
        
        # Authenticate with default guard
        user = await manager.authenticate(request)
        
        # Authenticate with specific guard
        user = await manager.authenticate(request, guard="api_key")
    """
    
    def __init__(self, default_guard: str = "jwt"):
        self._guards: Dict[str, BaseGuard] = {}
        self._default_guard = default_guard
    
    def register(self, name: str, guard: BaseGuard) -> None:
        """
        Register a guard.
        
        Args:
            name: Guard name
            guard: Guard instance
        """
        self._guards[name] = guard
        logger.info(f"Registered authentication guard: {name}")
    
    def guard(self, name: str = None) -> BaseGuard:
        """
        Get a guard by name.
        
        Args:
            name: Guard name (default: default guard)
            
        Returns:
            BaseGuard: The guard instance
            
        Raises:
            ValueError: If guard not found
        """
        name = name or self._default_guard
        
        if name not in self._guards:
            raise ValueError(f"Guard '{name}' not registered")
        
        return self._guards[name]
    
    def set_default(self, name: str) -> None:
        """
        Set the default guard.
        
        Args:
            name: Guard name
            
        Raises:
            ValueError: If guard not registered
        """
        if name not in self._guards:
            raise ValueError(f"Guard '{name}' not registered")
        
        self._default_guard = name
    
    async def authenticate(
        self,
        request: Request,
        guard: str = None
    ) -> Optional[AuthenticatedUser]:
        """
        Authenticate request using specified guard.
        
        If no guard specified, tries default guard first,
        then falls back to other registered guards.
        
        Args:
            request: HTTP request
            guard: Guard name (optional)
            
        Returns:
            AuthenticatedUser or None
        """
        if guard:
            return await self.guard(guard).authenticate(request)
        
        # Try default guard first
        user = await self.guard(self._default_guard).authenticate(request)
        if user:
            return user
        
        # Fall back to other guards
        for name, guard_instance in self._guards.items():
            if name != self._default_guard:
                try:
                    user = await guard_instance.authenticate(request)
                    if user:
                        return user
                except Exception as e:
                    logger.debug(f"Guard {name} authentication failed: {e}")
        
        return None
    
    async def create_token(
        self,
        user: Any,
        guard: str = None,
        **claims
    ) -> str:
        """
        Create token using specified guard.
        
        Args:
            user: User instance
            guard: Guard name
            **claims: Additional claims
            
        Returns:
            str: Token
        """
        return await self.guard(guard).create_token(user, **claims)
    
    async def revoke_token(
        self,
        token: str,
        guard: str = None
    ) -> bool:
        """
        Revoke token using specified guard.
        
        Args:
            token: Token to revoke
            guard: Guard name
            
        Returns:
            bool: True if revoked
        """
        return await self.guard(guard).revoke_token(token)
    
    async def revoke_all_tokens_for_user(
        self,
        user_id: str,
        guard: str = None
    ) -> bool:
        """
        Revoke all tokens for a user.
        
        Args:
            user_id: User ID
            guard: Guard name
            
        Returns:
            bool: True if revoked
        """
        guard_instance = self.guard(guard)
        
        if hasattr(guard_instance, 'revoke_all_tokens_for_user'):
            return await guard_instance.revoke_all_tokens_for_user(user_id)
        
        return False
    
    def registered_guards(self) -> List[str]:
        """List registered guards."""
        return list(self._guards.keys())
    
    def has_guard(self, name: str) -> bool:
        """Check if a guard is registered."""
        return name in self._guards
    
    def get_default_guard(self) -> str:
        """Get the default guard name."""
        return self._default_guard


# Dependency for FastAPI
async def get_guard_manager(request: Request) -> GuardManager:
    """
    FastAPI dependency to get the guard manager.
    
    Usage:
        @router.get("/protected")
        async def protected(
            manager: GuardManager = Depends(get_guard_manager)
        ):
            user = await manager.authenticate(request)
            ...
    """
    container = getattr(request.app.state, "container", None)
    
    if container and container.bound("auth.guard_manager"):
        return container.make("auth.guard_manager")
    
    # Fallback to creating new instance
    return GuardManager()


async def get_current_user(
    request: Request,
    guard_manager: GuardManager = None
) -> Optional[AuthenticatedUser]:
    """
    FastAPI dependency to get the current authenticated user.
    
    Usage:
        from swx_core.guards.guard_manager import get_current_user
        
        @router.get("/me")
        async def get_me(user: AuthenticatedUser = Depends(get_current_user)):
            return user.to_dict()
    """
    if guard_manager is None:
        guard_manager = await get_guard_manager(request)
    
    return await guard_manager.authenticate(request)