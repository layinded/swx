"""
Guards package initialization.
"""

from swx_core.guards.base import BaseGuard, AuthenticatedUser
from swx_core.guards.jwt_guard import JWTGuard, TokenAudience
from swx_core.guards.api_key_guard import APIKeyGuard
from swx_core.guards.guard_manager import GuardManager
from swx_core.guards.service_token_guard import ServicePrincipal, ServiceTokenDep
from swx_core.guards.combined_auth_guard import AuthenticatedUserDep, OptionalAuthenticatedUserDep

__all__ = [
    "APIKeyGuard",
    "AuthenticatedUser",
    "AuthenticatedUserDep",
    "BaseGuard",
    "GuardManager",
    "JWTGuard",
    "OptionalAuthenticatedUserDep",
    "ServicePrincipal",
    "ServiceTokenDep",
    "TokenAudience",
]