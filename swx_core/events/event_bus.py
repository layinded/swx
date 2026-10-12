"""
Event Bus for Team Invitation Events.

This module provides a simple event bus for emitting team invitation events
that can be consumed by external systems (e.g., FastPII integration).
"""
from swx_core.events.dispatcher import event_bus, Event

__all__ = ["event_bus", "Event"]