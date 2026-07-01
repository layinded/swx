"""
Typed Event Base Classes

Provides type-safe event classes with IDE autocomplete support.
Based on industrial patterns from bubus, domubus, and modern Python event libraries.

Usage:
    from swx_core.events.typed_event import TypedEvent
    
    class UserCreatedEvent(TypedEvent):
        event_type: ClassVar[str] = "user.created"
        
        @property
        def user_id(self) -> str:
            return self.payload["id"]
        
        @property
        def email(self) -> str:
            return self.payload["data"]["email"]
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Dict, Optional
from uuid import uuid4

from swx_core.events.dispatcher import Event


@dataclass
class TypedEvent:
    """
    Type-safe event base class with convenient accessors.
    
    Note: This is a separate dataclass from Event to avoid inheritance issues.
    It wraps an Event instance rather than inheriting.
    
    Example:
        class UserCreatedEvent(TypedEvent):
            event_type: ClassVar[str] = "user.created"
            
            @property
            def user_id(self) -> str:
                return self.payload["id"]
            
            @property
            def email(self) -> str:
                return self.payload["data"]["email"]
        
        # Create from raw payload
        event = UserCreatedEvent.from_payload({
            "id": "abc123",
            "data": {"email": "user@example.com"},
            "context": {"user_type": "patient"}
        })
        
        # Type-safe access
        print(event.user_id)  # "abc123"
        print(event.email)    # "user@example.com"
    """
    
    event_type: ClassVar[str] = "typed.event"
    name: str
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    stopped: bool = False
    
    def __hash__(self) -> int:
        """Make TypedEvent hashable for use in sets and dict keys."""
        return hash((self.name, id(self.payload), self.timestamp))
    
    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "TypedEvent":
        """
        Create a typed event from a raw payload dictionary.
        
        Args:
            payload: Raw event payload with id, data, and optional context.
            
        Returns:
            TypedEvent instance with convenient accessors.
        """
        return cls(
            name=cls.event_type,
            payload=payload,
        )
    
    @property
    def id(self) -> str:
        """Get the resource ID from the payload."""
        return self.payload.get("id", "")
    
    @property
    def data(self) -> Dict[str, Any]:
        """Get the data dictionary from the payload."""
        return self.payload.get("data", {})
    
    @property
    def context(self) -> Dict[str, Any]:
        """Get the context dictionary from the payload."""
        return self.payload.get("context", {})
    
    @property
    def old_values(self) -> Dict[str, Any]:
        """Get old values for update events."""
        return self.payload.get("old_values", {})
    
    @property
    def new_values(self) -> Dict[str, Any]:
        """Get new values for update events."""
        return self.payload.get("new_values", {})


class TypedEventFactory:
    """
    Factory for creating typed events from raw payloads.
    
    Registry pattern that maps event types to typed event classes.
    
    Usage:
        factory = TypedEventFactory()
        
        # Register typed event classes
        factory.register(UserCreatedEvent)
        factory.register(UserUpdatedEvent)
        
        # Create typed event from raw payload
        raw_payload = {"id": "abc", "data": {"email": "user@example.com"}}
        typed_event = factory.create("user.created", raw_payload)
        
        # Type-safe access
        print(typed_event.email)  # IDE autocomplete works!
    """
    
    def __init__(self):
        self._registry: Dict[str, type[TypedEvent]] = {}
    
    def register(self, event_class: type[TypedEvent]) -> None:
        """
        Register a typed event class.
        
        Args:
            event_class: TypedEvent subclass with event_type defined.
        """
        self._registry[event_class.event_type] = event_class
    
    def create(self, event_type: str, payload: Dict[str, Any]) -> TypedEvent:
        """
        Create a typed event from event type and payload.
        
        Args:
            event_type: Event type string (e.g., "user.created").
            payload: Raw event payload.
            
        Returns:
            TypedEvent instance (or base Event if type not registered).
        """
        event_class = self._registry.get(event_type, TypedEvent)
        return event_class.from_payload(payload)
    
    def get(self, event_type: str) -> Optional[type[TypedEvent]]:
        """
        Get the registered event class for a type.
        
        Args:
            event_type: Event type string.
            
        Returns:
            TypedEvent subclass or None if not registered.
        """
        return self._registry.get(event_type)
    
    def is_registered(self, event_type: str) -> bool:
        """Check if an event type is registered."""
        return event_type in self._registry


# Global factory instance
_typed_event_factory = TypedEventFactory()


def register_typed_event(event_class: type[TypedEvent]) -> type[TypedEvent]:
    """
    Decorator to register a typed event class.
    
    Usage:
        @register_typed_event
        class UserCreatedEvent(TypedEvent):
            event_type: ClassVar[str] = "user.created"
            
            @property
            def user_id(self) -> str:
                return self.payload["id"]
    """
    _typed_event_factory.register(event_class)
    return event_class


def create_typed_event(event_type: str, payload: Dict[str, Any]) -> TypedEvent:
    """
    Create a typed event using the global factory.
    
    Args:
        event_type: Event type string (e.g., "user.created").
        payload: Raw event payload.
        
    Returns:
        TypedEvent instance.
    """
    return _typed_event_factory.create(event_type, payload)