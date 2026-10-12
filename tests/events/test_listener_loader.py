"""
Tests for event listener auto-discovery.
"""
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
from types import ModuleType

import pytest

from swx_core.events import Listener
from swx_core.events.listener_loader import (
    discover_listeners,
    register_listener,
    load_listeners_from_path,
    load_all_listeners,
)


class MockListener(Listener):
    event = "test.event"
    priority = 10

    async def handle(self, payload):
        return payload


class MockWildcardListener(Listener):
    event = "user.*"
    priority = 5

    async def handle(self, payload):
        return payload


class MockHighPriorityListener(Listener):
    event = "high.priority.event"
    priority = 100

    async def handle(self, payload):
        return payload


class TestDiscoverListeners:
    def test_discovers_single_listener(self):
        module = ModuleType("test_module")
        module.TestListener = MockListener

        listeners = discover_listeners(module)

        assert len(listeners) == 1
        assert listeners[0] == MockListener

    def test_discovers_multiple_listeners(self):
        module = ModuleType("test_module")
        module.Listener1 = MockListener
        module.Listener2 = MockWildcardListener
        module.Listener3 = MockHighPriorityListener

        listeners = discover_listeners(module)

        assert len(listeners) == 3

    def test_ignores_base_listener_class(self):
        module = ModuleType("test_module")
        module.Listener = Listener
        module.MyListener = MockListener

        listeners = discover_listeners(module)

        assert Listener not in listeners
        assert MockListener in listeners

    def test_ignores_non_listener_classes(self):
        module = ModuleType("test_module")
        module.ListenerClass = MockListener
        module.NotAListener = MagicMock
        module.string_value = "not a class"

        listeners = discover_listeners(module)

        assert len(listeners) == 1
        assert listeners[0] == MockListener

    def test_empty_module_returns_empty_list(self):
        module = ModuleType("empty_module")

        listeners = discover_listeners(module)

        assert listeners == []


class TestRegisterListener:
    @pytest.fixture
    def mock_event_bus(self):
        return MagicMock()

    @patch("swx_core.events.listener_loader.event_bus")
    def test_registers_listener_with_event_bus(self, mock_event_bus):
        register_listener(MockListener)

        mock_event_bus.listen.assert_called_once()
        call_kwargs = mock_event_bus.listen.call_args[1]
        assert call_kwargs["event"] == "test.event"
        assert call_kwargs["priority"] == 10

    @patch("swx_core.events.listener_loader.event_bus")
    def test_registers_wildcard_listener(self, mock_event_bus):
        register_listener(MockWildcardListener)

        mock_event_bus.listen.assert_called_once()
        call_kwargs = mock_event_bus.listen.call_args[1]
        assert call_kwargs["event"] == "user.*"

    @patch("swx_core.events.listener_loader.event_bus")
    def test_creates_listener_instance(self, mock_event_bus):
        register_listener(MockListener)

        mock_event_bus.listen.assert_called_once()
        call_kwargs = mock_event_bus.listen.call_args[1]
        handler = call_kwargs["listener"]
        # Check method is passed (not class instance)
        assert callable(handler)


class TestLoadListenersFromPath:
    def test_handles_missing_directory_gracefully(self):
        listeners = load_listeners_from_path(
            base_path="/nonexistent/path",
            package_name="test_package"
        )

        assert listeners == 0

    def test_ignores_init_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            listeners_dir = tmpdir / "listeners"
            listeners_dir.mkdir(parents=True)

            init_file = listeners_dir / "__init__.py"
            init_file.write_text("# Init file\n")

            listeners = load_listeners_from_path(
                base_path=str(listeners_dir),
                package_name="test_package"
            )

            assert listeners == 0


class TestListenerPatterns:
    @patch("swx_core.events.listener_loader.event_bus")
    def test_wildcard_pattern_user_events(self, mock_event_bus):
        class UserListener(Listener):
            event = "user.*"
            priority = 10

            async def handle(self, payload):
                pass

        register_listener(UserListener)

        call_kwargs = mock_event_bus.listen.call_args[1]
        assert call_kwargs["event"] == "user.*"

    @patch("swx_core.events.listener_loader.event_bus")
    def test_wildcard_pattern_emergency_events(self, mock_event_bus):
        class EmergencyListener(Listener):
            event = "emergency.*"
            priority = 1

            async def handle(self, payload):
                pass

        register_listener(EmergencyListener)

        call_kwargs = mock_event_bus.listen.call_args[1]
        assert call_kwargs["event"] == "emergency.*"

    @patch("swx_core.events.listener_loader.event_bus")
    def test_specific_event_pattern(self, mock_event_bus):
        class UserCreatedListener(Listener):
            event = "user.created"
            priority = 10

            async def handle(self, payload):
                pass

        register_listener(UserCreatedListener)

        call_kwargs = mock_event_bus.listen.call_args[1]
        assert call_kwargs["event"] == "user.created"

    @patch("swx_core.events.listener_loader.event_bus")
    def test_priority_ordering(self, mock_event_bus):
        class HighPriorityListener(Listener):
            event = "test.event"
            priority = 100

            async def handle(self, payload):
                pass

        register_listener(HighPriorityListener)

        call_kwargs = mock_event_bus.listen.call_args[1]
        assert call_kwargs["priority"] == 100


class TestListenerDiscoveryIntegration:
    def test_listener_class_attributes_preserved(self):
        module = ModuleType("test_module")
        module.TestListener = MockListener

        listeners = discover_listeners(module)
        listener_class = listeners[0]

        assert listener_class.event == "test.event"
        assert listener_class.priority == 10

    def test_listener_inheritance_ignored(self):
        class IntermediateListener(Listener):
            pass

        class ConcreteListener(IntermediateListener):
            event = "concrete.event"
            priority = 5

            async def handle(self, payload):
                pass

        module = ModuleType("test_module")
        module.Intermediate = IntermediateListener
        module.Concrete = ConcreteListener

        listeners = discover_listeners(module)

        assert IntermediateListener not in listeners
        assert ConcreteListener in listeners


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
