"""
Event Dispatcher - Framework-level event system.

Provides:
- Sync and async listeners
- Wildcard listeners
- Event stopping
- Listener priorities
"""

from typing import Any, Callable, Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
import asyncio
import inspect

from swx_core.middleware.logging_middleware import logger


class EventPriority:
    """Listener priority levels."""
    HIGHEST = 100
    HIGH = 75
    NORMAL = 50
    LOW = 25
    LOWEST = 1


@dataclass
class Event:
    """
    Base event class.
    
    Events carry data through the application and can be stopped
    to prevent further listener execution.
    """
    name: str
    payload: Any = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    stopped: bool = False
    _metadata: Dict[str, Any] = field(default_factory=dict)
    
    def stop(self) -> None:
        """Stop event propagation."""
        self.stopped = True
    
    def is_stopped(self) -> bool:
        """Check if event propagation is stopped."""
        return self.stopped
    
    def set(self, key: str, value: Any) -> None:
        """Set metadata."""
        self._metadata[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get metadata."""
        return self._metadata.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
            "stopped": self.stopped,
            "metadata": self._metadata,
        }


@dataclass
class ListenerRegistration:
    """Registered listener details."""
    listener: Callable
    priority: int = 50
    queueable: bool = False
    queue_name: str = "default"
    async_listener: bool = False
    once: bool = False


class EventBus:
    """
    Central event dispatcher.
    
    Usage:
        # Dispatch events
        await event_bus.dispatch("user.registered", user=user)
        
        # Register listeners
        event_bus.listen("user.registered", send_welcome_email, priority=100)
        event_bus.listen("user.*", log_user_activity)  # Wildcard
        event_bus.listen("*", audit_all_events)  # All events
        
        # Queueable listener
        event_bus.listen("billing.payment_failed", notify_admin, queueable=True)
    """
    
    def __init__(self):
        self._listeners: Dict[str, List[ListenerRegistration]] = {}
        self._wildcard_listeners: List[ListenerRegistration] = []
        self._fired: Dict[str, List[Event]] = {}  # For testing
    
    # =====================
    # REGISTRATION
    # =====================
    
    def listen(
        self,
        event: str,
        listener: Callable,
        priority: int = EventPriority.NORMAL,
        queueable: bool = False,
        queue_name: str = "default",
        once: bool = False
    ) -> None:
        """
        Register an event listener.
        
        Args:
            event: Event name or pattern (supports wildcards with *)
            listener: Callable to handle the event
            priority: Higher priority = executed first
            queueable: If True, event is queued for async processing
            queue_name: Queue name for queueable listeners
            once: Remove listener after first invocation
        """
        registration = ListenerRegistration(
            listener=listener,
            priority=priority,
            queueable=queueable,
            queue_name=queue_name,
            async_listener=asyncio.iscoroutinefunction(listener),
            once=once
        )
        
        if event == "*" or "*" in event:
            self._wildcard_listeners.append(registration)
            self._wildcard_listeners.sort(key=lambda r: r.priority, reverse=True)
        else:
            if event not in self._listeners:
                self._listeners[event] = []
            self._listeners[event].append(registration)
            self._listeners[event].sort(key=lambda r: r.priority, reverse=True)
    
    def subscribe(self, event: str):
        """
        Decorator to register an event listener.
        
        Usage:
            @event_bus.subscribe("user.registered")
            def send_welcome_email(event):
                ...
        """
        def decorator(func: Callable) -> Callable:
            self.listen(event, func)
            return func
        return decorator
    
    def forget(self, event: str, listener: Callable) -> bool:
        """
        Remove a listener from an event.
        
        Args:
            event: Event name
            listener: The listener to remove
            
        Returns:
            bool: True if removed
        """
        removed = False
        
        if event in self._listeners:
            for reg in self._listeners[event][:]:
                if reg.listener == listener:
                    self._listeners[event].remove(reg)
                    removed = True
        
        for reg in self._wildcard_listeners[:]:
            if reg.listener == listener:
                self._wildcard_listeners.remove(reg)
                removed = True
        
        return removed
    
    def forget_all(self, event: str = None) -> None:
        """
        Remove all listeners from an event (or all events).
        
        Args:
            event: Event name (None for all events)
        """
        if event:
            self._listeners.pop(event, None)
        else:
            self._listeners.clear()
            self._wildcard_listeners.clear()
    
    def has_listeners(self, event: str) -> bool:
        """Check if event has listeners."""
        return bool(self._listeners.get(event)) or bool(self._wildcard_listeners)
    
    def get_listeners(self, event: str) -> List[ListenerRegistration]:
        """Get all listeners for an event."""
        listeners = list(self._listeners.get(event, []))
        listeners.extend(self._wildcard_listeners)
        return listeners
    
    # =====================
    # DISPATCH
    # =====================
    
    async def dispatch(
        self,
        event: str,
        payload: Any = None,
        **kwargs
    ) -> Event:
        """
        Dispatch an event to all listeners.
        
        Args:
            event: Event name
            payload: Event payload
            **kwargs: Additional event data
        
        Returns:
            Event object with metadata
        """
        # Create event object
        event_obj = Event(
            name=event,
            payload=payload,
            **kwargs
        )
        
        # Track fired events for testing
        if event not in self._fired:
            self._fired[event] = []
        self._fired[event].append(event_obj)
        
        # Get all listeners
        listeners = self._get_listeners_for_event(event)
        
        # Execute listeners
        to_remove = []
        for registration in listeners:
            if event_obj.is_stopped():
                break
            
            try:
                if registration.queueable:
                    await self._queue_listener(event_obj, registration)
                else:
                    await self._execute_listener(registration, event_obj)
                
                if registration.once:
                    to_remove.append(registration)
                    
            except Exception as e:
                logger.error(
                    f"Event listener error: {registration.listener.__name__} "
                    f"for event '{event}': {e}",
                    exc_info=True
                )
        
        # Remove one-time listeners
        for reg in to_remove:
            self._forget_registration(event, reg)
        
        return event_obj
    
    def dispatch_sync(
        self,
        event: str,
        payload: Any = None,
        **kwargs
    ) -> Event:
        """
        Dispatch event synchronously (blocking).
        
        Skips async and queueable listeners.
        """
        event_obj = Event(name=event, payload=payload, **kwargs)
        
        # Track for testing
        if event not in self._fired:
            self._fired[event] = []
        self._fired[event].append(event_obj)
        
        listeners = self._get_listeners_for_event(event)
        
        for registration in listeners:
            if event_obj.is_stopped():
                break
            
            if registration.queueable or registration.async_listener:
                continue
            
            try:
                registration.listener(event_obj)
            except Exception as e:
                logger.error(f"Sync event listener error: {e}", exc_info=True)
        
        return event_obj
    
    def _get_listeners_for_event(self, event: str) -> List[ListenerRegistration]:
        """Get all listeners for an event including wildcards."""
        listeners = list(self._listeners.get(event, []))
        
        # Add wildcard listeners that match
        for reg in self._wildcard_listeners:
            # For now, include all wildcard listeners
            # Pattern matching can be added later
            if reg not in listeners:
                listeners.append(reg)
        
        # Sort by priority
        listeners.sort(key=lambda r: r.priority, reverse=True)
        
        return listeners
    
    async def _execute_listener(
        self,
        registration: ListenerRegistration,
        event: Event
    ) -> Any:
        """Execute a listener."""
        if registration.async_listener:
            return await registration.listener(event)
        else:
            return registration.listener(event)
    
    async def _queue_listener(
        self,
        event: Event,
        registration: ListenerRegistration
    ) -> None:
        """Queue listener for async processing."""
        try:
            from swx_core.services.job.job_dispatcher import enqueue_job
            
            await enqueue_job(
                job_type="event.listener",
                payload={
                    "event_name": event.name,
                    "event_payload": event.payload,
                    "listener_module": registration.listener.__module__,
                    "listener_name": registration.listener.__name__,
                    "queue_name": registration.queue_name
                },
                tags=["event", event.name]
            )
        except ImportError:
            # Job system not available, execute synchronously
            await self._execute_listener(registration, event)
    
    def _forget_registration(self, event: str, registration: ListenerRegistration) -> None:
        """Remove a registration from an event."""
        if event in self._listeners and registration in self._listeners[event]:
            self._listeners[event].remove(registration)
        if registration in self._wildcard_listeners:
            self._wildcard_listeners.remove(registration)
    
    # =====================
    # TESTING HELPERS
    # =====================
    
    def assert_fired(self, event: str) -> None:
        """Assert that an event was fired (for testing)."""
        if event not in self._fired or not self._fired[event]:
            raise AssertionError(f"Event '{event}' was not fired")
    
    def assert_not_fired(self, event: str) -> None:
        """Assert that an event was not fired (for testing)."""
        if event in self._fired and self._fired[event]:
            raise AssertionError(f"Event '{event}' was fired")
    
    def assert_fired_times(self, event: str, times: int) -> None:
        """Assert that an event was fired a specific number of times."""
        fired_count = len(self._fired.get(event, []))
        if fired_count != times:
            raise AssertionError(
                f"Event '{event}' was fired {fired_count} times, expected {times}"
            )
    
    def get_fired_events(self, event: str = None) -> List[Event]:
        """Get fired events (for testing)."""
        if event:
            return self._fired.get(event, [])
        return [e for events in self._fired.values() for e in events]
    
    def clear_fired(self) -> None:
        """Clear fired events tracking."""
        self._fired.clear()


# Global event bus instance
event_bus = EventBus()