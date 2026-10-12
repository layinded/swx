"""
Tests for BaseService event_context and before_emit/after_emit hooks.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock
import pytest

from swx_core.services.base import BaseService
from swx_core.events import EventBus, Event


class MockModel:
    def __init__(self, id=None, name="test", value=0):
        self.id = id or uuid.uuid4()
        self.name = name
        self.value = value


class MockRepository:
    def __init__(self):
        self.model = MockModel
    
    async def create(self, data):
        return MockModel(**data)
    
    async def find_by_id(self, id):
        return MockModel(id=id)
    
    async def update(self, id, data):
        return MockModel(id=id, **data)
    
    async def delete(self, id):
        return True
    
    async def soft_delete(self, id):
        return MockModel(id=id)
    
    async def restore(self, id):
        return MockModel(id=id)
    
    async def create_many(self, data_list):
        return [MockModel(**d) for d in data_list]


class TestableService(BaseService):
    def __init__(self):
        super().__init__(repository=MockRepository())
        self.event_bus = EventBus()


class TestEventContext:
    async def test_create_with_event_context(self):
        service = TestableService()
        event_bus_mock = MagicMock()
        event_bus_mock.emit = AsyncMock()
        service.event_bus = event_bus_mock

        context = {
            "user_type": "patient",
            "hospital_id": "hospital-uuid",
        }

        await service.create(
            data={"name": "test", "value": 100},
            event_context=context,
        )

        event_bus_mock.emit.assert_called_once()
        event = event_bus_mock.emit.call_args[0][0]
        
        assert event.name == "mockmodel.created"
        assert event.payload["context"] == context

    async def test_create_without_event_context(self):
        service = TestableService()
        event_bus_mock = MagicMock()
        event_bus_mock.emit = AsyncMock()
        service.event_bus = event_bus_mock

        await service.create(data={"name": "test"})

        event = event_bus_mock.emit.call_args[0][0]
        assert "context" not in event.payload

    async def test_create_emit_event_false(self):
        service = TestableService()
        event_bus_mock = MagicMock()
        event_bus_mock.emit = AsyncMock()
        service.event_bus = event_bus_mock

        await service.create(
            data={"name": "test"},
            emit_event=False,
            event_context={"key": "value"},
        )

        event_bus_mock.emit.assert_not_called()

    async def test_update_with_event_context(self):
        service = TestableService()
        event_bus_mock = MagicMock()
        event_bus_mock.emit = AsyncMock()
        service.event_bus = event_bus_mock

        await service.update(
            id=uuid.uuid4(),
            data={"name": "new_name"},
            event_context={"updated_by": "admin"},
        )

        event = event_bus_mock.emit.call_args[0][0]
        assert event.payload["context"] == {"updated_by": "admin"}

    async def test_delete_with_event_context(self):
        service = TestableService()
        event_bus_mock = MagicMock()
        event_bus_mock.emit = AsyncMock()
        service.event_bus = event_bus_mock

        await service.delete(id=uuid.uuid4(), event_context={"deleted_by": "admin"})

        event = event_bus_mock.emit.call_args[0][0]
        assert event.payload["context"] == {"deleted_by": "admin"}


class TestBeforeEmitHook:
    async def test_before_emit_enhances_payload(self):
        class EnhancedService(TestableService):
            async def before_emit(self, event_name, payload, instance):
                if event_name == "mockmodel.created":
                    payload["context"] = {
                        **payload.get("context", {}),
                        "enhanced": True,
                    }
                return payload

        service = EnhancedService()
        event_bus_mock = MagicMock()
        event_bus_mock.emit = AsyncMock()
        service.event_bus = event_bus_mock

        await service.create(
            data={"name": "test"},
            event_context={"original": "context"},
        )

        event = event_bus_mock.emit.call_args[0][0]
        assert event.payload["context"]["original"] == "context"
        assert event.payload["context"]["enhanced"] is True


class TestAfterEmitHook:
    async def test_after_emit_is_called_after_event(self):
        after_emit_called = []

        class AfterEmitService(TestableService):
            async def after_emit(self, event_name, payload, instance):
                after_emit_called.append(event_name)

        service = AfterEmitService()
        event_bus_mock = MagicMock()
        event_bus_mock.emit = AsyncMock()
        service.event_bus = event_bus_mock

        await service.create(data={"name": "test"})

        assert len(after_emit_called) == 1
        assert after_emit_called[0] == "mockmodel.created"


class TestHookChaining:
    async def test_before_and_after_hooks_both_called(self):
        call_order = []

        class ChainedService(TestableService):
            async def before_emit(self, event_name, payload, instance):
                call_order.append("before_emit")
                return payload

            async def after_emit(self, event_name, payload, instance):
                call_order.append("after_emit")

        service = ChainedService()
        event_bus_mock = MagicMock()
        event_bus_mock.emit = AsyncMock()
        service.event_bus = event_bus_mock

        await service.create(data={"name": "test"})

        assert call_order == ["before_emit", "after_emit"]


class TestBackwardCompatibility:
    async def test_create_without_event_context_works(self):
        service = TestableService()
        event_bus_mock = MagicMock()
        event_bus_mock.emit = AsyncMock()
        service.event_bus = event_bus_mock

        result = await service.create(data={"name": "test"})

        assert result is not None
        event_bus_mock.emit.assert_called_once()

    async def test_hooks_default_to_noop(self):
        service = TestableService()
        event_bus_mock = MagicMock()
        event_bus_mock.emit = AsyncMock()
        service.event_bus = event_bus_mock

        result = await service.create(data={"name": "test"}, event_context={"key": "value"})

        assert result is not None
        event_bus_mock.emit.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
