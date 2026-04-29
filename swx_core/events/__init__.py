"""
Events package initialization.
"""

from swx_core.events.dispatcher import (
    EventBus,
    Event,
    EventPriority,
    event_bus,
)
from swx_core.events.listener import Listener, QueueableListener
from swx_core.events.listener_loader import (
    discover_listeners,
    register_listener,
    load_listeners_from_path,
    load_all_listeners,
)
from swx_core.events.debug import (
    list_all_listeners,
    test_pattern,
    trace_event,
    print_event_bus_status,
    get_listener_count,
    verify_listener_registered,
)

__all__ = [
    # Core classes
    "EventBus",
    "Event",
    "EventPriority",
    "Listener",
    "QueueableListener",
    
    # Global instance
    "event_bus",
    
    # Listener discovery
    "discover_listeners",
    "register_listener",
    "load_listeners_from_path",
    "load_all_listeners",
    
    # Debug utilities
    "list_all_listeners",
    "test_pattern",
    "trace_event",
    "print_event_bus_status",
    "get_listener_count",
    "verify_listener_registered",
]