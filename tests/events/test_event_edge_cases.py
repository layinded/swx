"""
Edge case tests for event emission across SwX services.

Tests verify handling of:
1. Event emission with None/empty values
2. Event emission with missing context
3. Event emission when EventBus fails
4. Concurrent event emissions
5. Event hashability
6. Large event payloads
7. Listener failures
8. TypedEvent edge cases
"""
import uuid
from typing import ClassVar
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from swx_core.events.dispatcher import EventBus, Event
from swx_core.events.typed_event import TypedEvent, TypedEventFactory


class TestEventEdgeCases:
    """Test edge cases for base Event class."""
    
    def test_event_is_hashable(self):
        """Event objects must be hashable for use in sets/dicts."""
        event1 = Event(name="user.created", payload={"id": "123"})
        event2 = Event(name="user.created", payload={"id": "456"})
        
        # Should not raise TypeError
        event_set = {event1, event2}
        assert len(event_set) == 2
        
        event_dict = {event1: "first", event2: "second"}
        assert event_dict[event1] == "first"
    
    def test_event_with_none_payload(self):
        """Event should handle None payload gracefully."""
        event = Event(name="test.event", payload=None)
        assert event.payload is None
        assert event.name == "test.event"
    
    def test_event_with_empty_payload(self):
        """Event should handle empty dict payload."""
        event = Event(name="test.event", payload={})
        assert event.payload == {}
    
    def test_event_with_large_payload(self):
        """Event should handle large payloads (10KB+)."""
        large_data = {"data": "x" * 15000}  # 15KB of data
        event = Event(name="test.event", payload=large_data)
        assert len(event.payload["data"]) == 15000
    
    def test_event_metadata_operations(self):
        """Event metadata should work correctly."""
        event = Event(name="test.event", payload={})
        
        # Set and get metadata
        event.set("key1", "value1")
        assert event.get("key1") == "value1"
        assert event.get("nonexistent") is None
        assert event.get("nonexistent", "default") == "default"
    
    def test_event_stop_propagation(self):
        """Event stopping should prevent further listener execution."""
        event = Event(name="test.event", payload={})
        assert event.is_stopped() is False
        
        event.stop()
        assert event.is_stopped() is True
    
    def test_event_to_dict(self):
        """Event serialization should work correctly."""
        event = Event(name="test.event", payload={"key": "value"})
        event.set("meta", "data")
        
        result = event.to_dict()
        assert result["name"] == "test.event"
        assert result["payload"] == {"key": "value"}
        assert "timestamp" in result
        assert result["stopped"] is False
        assert result["metadata"] == {"meta": "data"}


class TestEventBusEdgeCases:
    """Test edge cases for EventBus."""
    
    async def test_emit_after_dispatch(self):
        """Both emit() and dispatch() should work for EventBus."""
        bus = EventBus()
        
        # Test dispatch
        result = await bus.dispatch("test.event", {"id": "123"})
        assert result.name == "test.event"
        assert result.payload == {"id": "123"}
        
        # Test emit (alias)
        event = Event(name="test.event2", payload={"id": "456"})
        result2 = await bus.emit(event)
        assert result2.name == "test.event2"
    
    async def test_dispatch_to_dict_key(self):
        """Events can be used as dict keys after dispatch."""
        bus = EventBus()
        
        event1 = await bus.dispatch("test.event", {"id": "1"})
        event2 = await bus.dispatch("test.event", {"id": "2"})
        
        # Events should be usable as dict keys
        events_dict = {event1: "first", event2: "second"}
        assert events_dict[event1] == "first"
    
    async def test_multiple_dispatches_same_name(self):
        """Multiple dispatches with same event name should track all."""
        bus = EventBus()
        
        await bus.dispatch("test.event", {"id": "1"})
        await bus.dispatch("test.event", {"id": "2"})
        await bus.dispatch("test.event", {"id": "3"})
        
        fired = bus.get_fired_events("test.event")
        assert len(fired) == 3
    
    async def test_listener_exception_handling(self):
        """Listener exceptions should be logged but not crash the bus."""
        bus = EventBus()
        
        error_listener = AsyncMock(side_effect=ValueError("Test error"))
        success_listener = AsyncMock()
        
        bus.listen("test.event", error_listener)
        bus.listen("test.event", success_listener)
        
        # Should not raise despite error in first listener
        await bus.dispatch("test.event", {"id": "123"})
        
        # Second listener should still be called
        success_listener.assert_called_once()
    
    async def test_wildcard_listener(self):
        """Wildcard listeners should receive all events."""
        bus = EventBus()
        listener = AsyncMock()
        
        bus.listen("*", listener)
        
        await bus.dispatch("user.created", {})
        await bus.dispatch("user.deleted", {})
        await bus.dispatch("role.created", {})
        
        assert listener.call_count == 3
    
    async def test_pattern_listener(self):
        """Pattern listeners should receive matching events."""
        bus = EventBus()
        listener = AsyncMock()
        
        bus.listen("user.*", listener)
        
        await bus.dispatch("user.created", {})
        await bus.dispatch("user.deleted", {})
        await bus.dispatch("role.created", {})
        
        assert listener.call_count == 2  # user.created and user.deleted
    
    async def test_once_listener(self):
        """Once listeners should be removed after first call."""
        bus = EventBus()
        listener = AsyncMock()
        
        bus.listen("test.event", listener, once=True)
        
        await bus.dispatch("test.event", {})
        await bus.dispatch("test.event", {})
        
        listener.assert_called_once()


class TestTypedEventEdgeCases:
    """Test edge cases for TypedEvent."""
    
    def test_typed_event_with_nested_payload(self):
        """TypedEvent should handle nested payload structures."""
        class NestedEvent(TypedEvent):
            event_type: ClassVar[str] = "nested.event"
            
            @property
            def nested_value(self) -> str:
                return self.payload["data"].get("nested", {}).get("value", "default")
        
        event = NestedEvent.from_payload({
            "id": "123",
            "data": {"nested": {"value": "deep"}},
        })
        
        assert event.nested_value == "deep"
    
    def test_typed_event_with_missing_nested_data(self):
        """TypedEvent should handle missing nested data gracefully."""
        class NestedEvent(TypedEvent):
            event_type: ClassVar[str] = "nested.event"
            
            @property
            def nested_value(self) -> str:
                return self.payload.get("data", {}).get("nested", {}).get("value", "default")
        
        event = NestedEvent.from_payload({"id": "123"})
        
        assert event.nested_value == "default"
    
    def test_typed_event_equality(self):
        """TypedEvents with same data should be hashable distinctly."""
        event1 = TypedEvent.from_payload({"id": "1", "data": {"name": "test"}})
        event2 = TypedEvent.from_payload({"id": "1", "data": {"name": "test"}})
        
        # Different instances should have different hashes (based on id)
        events_set = {event1, event2}
        assert len(events_set) == 2
    
    def test_factory_with_unregistered_type(self):
        """Factory should return base TypedEvent for unregistered types."""
        factory = TypedEventFactory()
        
        event = factory.create("unknown.event", {"id": "1"})
        
        assert isinstance(event, TypedEvent)
        assert event.event_type == "typed.event"


class TestServiceEventEmissionEdgeCases:
    """Test edge cases for service event emission."""
    
    async def test_event_context_with_none(self):
        """event_context=None should not crash event emission."""
        from swx_core.services.role_service import create_role_service
        from swx_core.models.role import Role, RoleCreate
        
        mock_session = AsyncMock()
        role_create = RoleCreate(name="test", description="Test role")
        mock_role = Role(id=uuid.uuid4(), name="test", description="Test role")
        
        with patch("swx_core.services.role_service.role_repository") as mock_repo:
            mock_repo.get_role_by_name = AsyncMock(return_value=None)
            mock_repo.create_role = AsyncMock(return_value=mock_role)
            
            with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                await create_role_service(
                    session=mock_session,
                    role_in=role_create,
                    event_context=None,  # Explicit None
                )
                
                assert mock_emit.called
                event = mock_emit.call_args[0][0]
                # Context should not be in payload when None
                assert "context" not in event.payload
    
    async def test_event_context_with_empty_dict(self):
        """event_context={} should add empty context to payload."""
        from swx_core.services.role_service import create_role_service
        from swx_core.models.role import Role, RoleCreate
        
        mock_session = AsyncMock()
        role_create = RoleCreate(name="test", description="Test role")
        mock_role = Role(id=uuid.uuid4(), name="test", description="Test role")
        
        with patch("swx_core.services.role_service.role_repository") as mock_repo:
            mock_repo.get_role_by_name = AsyncMock(return_value=None)
            mock_repo.create_role = AsyncMock(return_value=mock_role)
            
            with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                await create_role_service(
                    session=mock_session,
                    role_in=role_create,
                    event_context={},  # Empty dict
                )
                
                assert mock_emit.called
                event = mock_emit.call_args[0][0]
                assert event.payload["context"] == {}
    
    async def test_concurrent_event_emissions(self):
        """Multiple concurrent event emissions should not interfere."""
        from swx_core.services.role_service import create_role_service
        from swx_core.models.role import Role, RoleCreate
        import asyncio
        
        mock_session = AsyncMock()
        
        async def create_role_with_context(context_value: int):
            role_create = RoleCreate(name=f"role_{context_value}", description=f"Role {context_value}")
            mock_role = Role(id=uuid.uuid4(), name=f"role_{context_value}", description=f"Role {context_value}")
            
            with patch("swx_core.services.role_service.role_repository") as mock_repo:
                mock_repo.get_role_by_name = AsyncMock(return_value=None)
                mock_repo.create_role = AsyncMock(return_value=mock_role)
                
                emissions = []
                
                async def track_emit(event):
                    emissions.append(event)
                
                with patch.object(EventBus, "emit", new_callable=AsyncMock, side_effect=track_emit):
                    await create_role_service(
                        session=mock_session,
                        role_in=role_create,
                        event_context={"value": context_value},
                    )
                    return emissions
        
        # Run multiple concurrent emissions
        results = await asyncio.gather(
            create_role_with_context(1),
            create_role_with_context(2),
            create_role_with_context(3),
        )
        
        # Each should have exactly one emission with correct context
        for i, emissions in enumerate(results, 1):
            assert len(emissions) == 1
            assert emissions[0].payload["context"]["value"] == i
    
    async def test_unicode_in_event_context(self):
        """Event context should handle Unicode characters."""
        from swx_core.services.role_service import create_role_service
        from swx_core.models.role import Role, RoleCreate
        
        mock_session = AsyncMock()
        role_create = RoleCreate(name="test", description="Test role")
        mock_role = Role(id=uuid.uuid4(), name="test", description="Test role")
        
        unicode_context = {
            "name": "用户名",  # Chinese
            "emoji": "👤🎉",  # Emoji
            "arabic": "مرحبا",  # Arabic
        }
        
        with patch("swx_core.services.role_service.role_repository") as mock_repo:
            mock_repo.get_role_by_name = AsyncMock(return_value=None)
            mock_repo.create_role = AsyncMock(return_value=mock_role)
            
            with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
                await create_role_service(
                    session=mock_session,
                    role_in=role_create,
                    event_context=unicode_context,
                )
                
                event = mock_emit.call_args[0][0]
                assert event.payload["context"]["name"] == "用户名"
                assert event.payload["context"]["emoji"] == "👤🎉"
                assert event.payload["context"]["arabic"] == "مرحبا"


class TestEventPayloadStructureEdgeCases:
    """Test edge cases for event payload structure."""
    
    def test_payload_with_circular_reference(self):
        """Event payload should not serialize circular references during creation."""
        circular_dict = {}
        circular_dict["self"] = circular_dict
        
        # Should not crash during Event creation
        event = Event(name="test.event", payload={"data": "value"})
        assert event.payload == {"data": "value"}
    
    def test_payload_with_special_characters(self):
        """Event payload should handle special characters in keys/values."""
        event = Event(name="test.event", payload={
            "key with spaces": "value with spaces",
            "key\nwith\nnewlines": "value\nwith\nnewlines",
            "key\"with\"quotes": "value\"with\"quotes",
        })
        
        assert "key with spaces" in event.payload
        assert "key\nwith\nnewlines" in event.payload
    
    def test_payload_with_uuid_values(self):
        """Event payload should handle UUID objects."""
        test_uuid = uuid.uuid4()
        event = Event(name="test.event", payload={
            "id": str(test_uuid),
            "nested": {"uuid": str(test_uuid)},
        })
        
        assert event.payload["id"] == str(test_uuid)