"""
Tests for TypedEvent base class and factory.

Tests verify:
1. TypedEvent base class functionality
2. Property accessors work correctly
3. Factory registration and retrieval
4. Decorator registration
5. Pre-built typed events
"""
import pytest
from typing import ClassVar

from swx_core.events.typed_event import (
    TypedEvent,
    TypedEventFactory,
    register_typed_event,
    create_typed_event,
)
from swx_core.events.typed_events import (
    UserCreatedEvent,
    UserUpdatedEvent,
    RoleCreatedEvent,
    TeamMemberAddedEvent,
)


class TestTypedEventBase:
    async def test_typed_event_from_payload(self):
        payload = {
            "id": "user-123",
            "data": {"email": "test@example.com", "full_name": "Test User"},
            "context": {"user_type": "patient", "hospital_id": "hosp-456"},
        }
        
        event = TypedEvent.from_payload(payload)
        
        assert event.name == "typed.event"
        assert event.id == "user-123"
        assert event.data == {"email": "test@example.com", "full_name": "Test User"}
        assert event.context == {"user_type": "patient", "hospital_id": "hosp-456"}

    async def test_typed_event_properties(self):
        payload = {
            "id": "test-id",
            "data": {"key": "value"},
            "context": {"ctx": "data"},
        }
        
        event = TypedEvent.from_payload(payload)
        
        assert event.id == "test-id"
        assert event.data == {"key": "value"}
        assert event.context == {"ctx": "data"}
        assert event.old_values == {}
        assert event.new_values == {}

    async def test_update_event_properties(self):
        payload = {
            "id": "test-id",
            "old_values": {"name": "old"},
            "new_values": {"name": "new"},
            "context": {"updated_by": "admin"},
        }
        
        event = TypedEvent.from_payload(payload)
        
        assert event.old_values == {"name": "old"}
        assert event.new_values == {"name": "new"}


class TestTypedEventFactory:
    async def test_factory_register_and_create(self):
        factory = TypedEventFactory()
        
        class CustomEvent(TypedEvent):
            event_type: ClassVar[str] = "custom.event"
        
        factory.register(CustomEvent)
        
        payload = {"id": "test", "data": {}}
        event = factory.create("custom.event", payload)
        
        assert isinstance(event, CustomEvent)
        assert event.event_type == "custom.event"

    async def test_factory_returns_base_when_not_registered(self):
        factory = TypedEventFactory()
        
        payload = {"id": "test", "data": {}}
        event = factory.create("unknown.event", payload)
        
        assert isinstance(event, TypedEvent)

    async def test_factory_is_registered(self):
        factory = TypedEventFactory()
        
        class CustomEvent(TypedEvent):
            event_type: ClassVar[str] = "custom.event"
        
        factory.register(CustomEvent)
        
        assert factory.is_registered("custom.event")
        assert not factory.is_registered("unknown.event")

    async def test_factory_get(self):
        factory = TypedEventFactory()
        
        class CustomEvent(TypedEvent):
            event_type: ClassVar[str] = "custom.event"
        
        factory.register(CustomEvent)
        
        retrieved = factory.get("custom.event")
        assert retrieved == CustomEvent
        
        unknown = factory.get("unknown.event")
        assert unknown is None


class TestRegisterTypedEventDecorator:
    async def test_decorator_registers_event(self):
        @register_typed_event
        class DecoratedEvent(TypedEvent):
            event_type: ClassVar[str] = "decorated.event"
        
        event = create_typed_event("decorated.event", {"id": "test", "data": {}})
        
        assert isinstance(event, DecoratedEvent)


class TestPreBuiltTypedEvents:
    async def test_user_created_event(self):
        payload = {
            "id": "user-123",
            "data": {
                "email": "test@example.com",
                "full_name": "Test User",
                "auth_provider": "google",
            },
            "context": {
                "user_type": "patient",
                "hospital_id": "hosp-456",
            },
        }
        
        event = UserCreatedEvent.from_payload(payload)
        
        assert event.event_type == "user.created"
        assert event.user_id == "user-123"
        assert event.email == "test@example.com"
        assert event.full_name == "Test User"
        assert event.auth_provider == "google"
        assert event.user_type == "patient"

    async def test_user_updated_event(self):
        payload = {
            "id": "user-123",
            "old_values": {"email": "old@example.com", "full_name": "Old Name"},
            "new_values": {"email": "new@example.com", "full_name": "New Name"},
            "context": {"updated_by": "admin"},
        }
        
        event = UserUpdatedEvent.from_payload(payload)
        
        assert event.event_type == "user.updated"
        assert event.user_id == "user-123"
        assert event.old_email == "old@example.com"
        assert event.new_email == "new@example.com"
        assert event.old_full_name == "Old Name"
        assert event.new_full_name == "New Name"

    async def test_role_created_event(self):
        payload = {
            "id": "role-123",
            "data": {
                "name": "admin",
                "description": "Administrator role",
            },
            "context": {"created_by": "superadmin"},
        }
        
        event = RoleCreatedEvent.from_payload(payload)
        
        assert event.event_type == "role.created"
        assert event.role_id == "role-123"
        assert event.role_name == "admin"
        assert event.description == "Administrator role"

    async def test_team_member_added_event(self):
        payload = {
            "id": "member-123",
            "data": {
                "team_id": "team-456",
                "user_id": "user-789",
                "role_id": "role-abc",
            },
            "context": {"added_by": "manager"},
        }
        
        event = TeamMemberAddedEvent.from_payload(payload)
        
        assert event.event_type == "team.member_added"
        assert event.member_id == "member-123"
        assert event.team_id == "team-456"
        assert event.user_id == "user-789"
        assert event.role_id == "role-abc"


class TestTypedEventWithMissingFields:
    async def test_user_created_with_missing_optional_fields(self):
        payload = {
            "id": "user-123",
            "data": {"email": "test@example.com"},
        }
        
        event = UserCreatedEvent.from_payload(payload)
        
        assert event.event_type == "user.created"
        assert event.user_id == "user-123"
        assert event.email == "test@example.com"
        assert event.full_name == ""
        assert event.auth_provider == "local"
        assert event.user_type == "standard"

    async def test_event_with_empty_context(self):
        payload = {
            "id": "test",
            "data": {"key": "value"},
        }
        
        event = TypedEvent.from_payload(payload)
        
        assert event.context == {}
        assert event.id == "test"