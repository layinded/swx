"""
Built-in Authentication Events.
"""

from swx_core.events.dispatcher import Event, event_bus
from datetime import datetime
from typing import Any, Optional


class UserRegistered(Event):
    """Fired when a user registers."""
    
    def __init__(
        self,
        user_id: str,
        email: str,
        auth_provider: str = "local",
        **kwargs
    ):
        super().__init__(
            name="user.registered",
            payload={
                "user_id": user_id,
                "email": email,
                "auth_provider": auth_provider,
                "registered_at": datetime.utcnow().isoformat()
            },
            **kwargs
        )


class UserLoggedIn(Event):
    """Fired when a user logs in."""
    
    def __init__(
        self,
        user_id: str,
        email: str,
        ip_address: str = None,
        user_agent: str = None,
        auth_method: str = None,
        **kwargs
    ):
        super().__init__(
            name="user.logged_in",
            payload={
                "user_id": user_id,
                "email": email,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "auth_method": auth_method,
                "logged_in_at": datetime.utcnow().isoformat()
            },
            **kwargs
        )


class UserLoggedOut(Event):
    """Fired when a user logs out."""
    
    def __init__(self, user_id: str, **kwargs):
        super().__init__(
            name="user.logged_out",
            payload={"user_id": user_id},
            **kwargs
        )


class UserPasswordChanged(Event):
    """Fired when a user changes password."""
    
    def __init(
        self,
        user_id: str,
        revoked_sessions: int = 0,
        **kwargs
    ):
        super().__init__(
            name="user.password_changed",
            payload={
                "user_id": user_id,
                "revoked_sessions": revoked_sessions,
                "changed_at": datetime.utcnow().isoformat()
            },
            **kwargs
        )


class UserDeactivated(Event):
    """Fired when a user is deactivated."""
    
    def __init__(
        self,
        user_id: str,
        reason: str = None,
        deactivated_by: str = None,
        **kwargs
    ):
        super().__init__(
            name="user.deactivated",
            payload={
                "user_id": user_id,
                "reason": reason,
                "deactivated_by": deactivated_by,
                "deactivated_at": datetime.utcnow().isoformat()
            },
            **kwargs
        )


class UserActivated(Event):
    """Fired when a user is activated."""
    
    def __init__(self, user_id: str, **kwargs):
        super().__init__(
            name="user.activated",
            payload={"user_id": user_id},
            **kwargs
        )


class UserRoleChanged(Event):
    """Fired when a user's role is changed."""
    
    def __init(
        self,
        user_id: str,
        old_roles: list,
        new_roles: list,
        changed_by: str = None,
        **kwargs
    ):
        super().__init__(
            name="user.role_changed",
            payload={
                "user_id": user_id,
                "old_roles": old_roles,
                "new_roles": new_roles,
                "changed_by": changed_by,
                "changed_at": datetime.utcnow().isoformat()
            },
            **kwargs
        )


class TokenRevoked(Event):
    """Fired when a token is revoked."""
    
    def __init(
        self,
        token_id: str,
        user_id: str = None,
        reason: str = None,
        **kwargs
    ):
        super().__init__(
            name="token.revoked",
            payload={
                "token_id": token_id,
                "user_id": user_id,
                "reason": reason,
                "revoked_at": datetime.utcnow().isoformat()
            },
            **kwargs
        )


# Register core events
AUTH_EVENTS = [
    "user.registered",
    "user.logged_in",
    "user.logged_out",
    "user.password_changed",
    "user.deactivated",
    "user.activated",
    "user.role_changed",
    "token.revoked",
]