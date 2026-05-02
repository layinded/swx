"""
Built-in Events package initialization.
"""

from swx_core.events.events.auth_events import (
    UserRegistered,
    UserLoggedIn,
    UserLoggedOut,
    UserPasswordChanged,
    UserDeactivated,
    UserActivated,
    UserRoleChanged,
    TokenRevoked,
    AUTH_EVENTS,
)

__all__ = [
    "UserRegistered",
    "UserLoggedIn",
    "UserLoggedOut",
    "UserPasswordChanged",
    "UserDeactivated",
    "UserActivated",
    "UserRoleChanged",
    "TokenRevoked",
    "AUTH_EVENTS",
]