"""
Typed Event Examples

Pre-built typed events for common SwX operations.
"""
from typing import ClassVar
from swx_core.events.typed_event import TypedEvent, register_typed_event


@register_typed_event
class UserCreatedEvent(TypedEvent):
    """Typed event for user creation."""
    event_type: ClassVar[str] = "user.created"
    
    @property
    def user_id(self) -> str:
        return self.payload["id"]
    
    @property
    def email(self) -> str:
        return self.payload["data"]["email"]
    
    @property
    def full_name(self) -> str:
        return self.payload["data"].get("full_name", "")
    
    @property
    def auth_provider(self) -> str:
        return self.payload["data"].get("auth_provider", "local")
    
    @property
    def user_type(self) -> str:
        return self.context.get("user_type", "standard")


@register_typed_event
class UserUpdatedEvent(TypedEvent):
    """Typed event for user updates."""
    event_type: ClassVar[str] = "user.updated"
    
    @property
    def user_id(self) -> str:
        return self.payload["id"]
    
    @property
    def old_email(self) -> str:
        return self.old_values.get("email", "")
    
    @property
    def new_email(self) -> str:
        return self.new_values.get("email", "")
    
    @property
    def old_full_name(self) -> str:
        return self.old_values.get("full_name", "")
    
    @property
    def new_full_name(self) -> str:
        return self.new_values.get("full_name", "")


@register_typed_event
class UserPasswordChangedEvent(TypedEvent):
    """Typed event for password changes."""
    event_type: ClassVar[str] = "user.password_changed"
    
    @property
    def user_id(self) -> str:
        return self.payload["id"]
    
    @property
    def email(self) -> str:
        return self.payload["data"]["email"]


@register_typed_event
class UserDeletedEvent(TypedEvent):
    """Typed event for user deletion."""
    event_type: ClassVar[str] = "user.deleted"
    
    @property
    def user_id(self) -> str:
        return self.payload["id"]
    
    @property
    def email(self) -> str:
        return self.payload["data"]["email"]


# Role Events

@register_typed_event
class RoleCreatedEvent(TypedEvent):
    """Typed event for role creation."""
    event_type: ClassVar[str] = "role.created"
    
    @property
    def role_id(self) -> str:
        return self.payload["id"]
    
    @property
    def role_name(self) -> str:
        return self.payload["data"]["name"]
    
    @property
    def description(self) -> str:
        return self.payload["data"].get("description", "")


@register_typed_event
class RoleUpdatedEvent(TypedEvent):
    """Typed event for role updates."""
    event_type: ClassVar[str] = "role.updated"
    
    @property
    def role_id(self) -> str:
        return self.payload["id"]
    
    @property
    def old_role_name(self) -> str:
        return self.old_values.get("name", "")
    
    @property
    def new_role_name(self) -> str:
        return self.new_values.get("name", "")


@register_typed_event
class RoleDeletedEvent(TypedEvent):
    """Typed event for role deletion."""
    event_type: ClassVar[str] = "role.deleted"
    
    @property
    def role_id(self) -> str:
        return self.payload["id"]
    
    @property
    def role_name(self) -> str:
        return self.payload["data"]["name"]


# Team Events

@register_typed_event
class TeamCreatedEvent(TypedEvent):
    """Typed event for team creation."""
    event_type: ClassVar[str] = "team.created"
    
    @property
    def team_id(self) -> str:
        return self.payload["id"]
    
    @property
    def team_name(self) -> str:
        return self.payload["data"]["name"]
    
    @property
    def description(self) -> str:
        return self.payload["data"].get("description", "")


@register_typed_event
class TeamMemberAddedEvent(TypedEvent):
    """Typed event for team member addition."""
    event_type: ClassVar[str] = "team.member_added"
    
    @property
    def member_id(self) -> str:
        return self.payload["id"]
    
    @property
    def team_id(self) -> str:
        return self.payload["data"]["team_id"]
    
    @property
    def user_id(self) -> str:
        return self.payload["data"]["user_id"]
    
    @property
    def role_id(self) -> str:
        return self.payload["data"]["role_id"]


# Permission Events

@register_typed_event
class PermissionCreatedEvent(TypedEvent):
    """Typed event for permission creation."""
    event_type: ClassVar[str] = "permission.created"
    
    @property
    def permission_id(self) -> str:
        return self.payload["id"]
    
    @property
    def name(self) -> str:
        return self.payload["data"]["name"]
    
    @property
    def description(self) -> str:
        return self.payload["data"].get("description", "")


# Policy Events

@register_typed_event
class PolicyCreatedEvent(TypedEvent):
    """Typed event for policy creation."""
    event_type: ClassVar[str] = "policy.created"
    
    @property
    def policy_id(self) -> str:
        return self.payload["id"]
    
    @property
    def name(self) -> str:
        return self.payload["data"]["name"]


__all__ = [
    "UserCreatedEvent",
    "UserUpdatedEvent",
    "UserPasswordChangedEvent",
    "UserDeletedEvent",
    "RoleCreatedEvent",
    "RoleUpdatedEvent",
    "RoleDeletedEvent",
    "TeamCreatedEvent",
    "TeamMemberAddedEvent",
    "PermissionCreatedEvent",
    "PolicyCreatedEvent",
]