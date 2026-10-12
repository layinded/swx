"""
Control FastAPI Project - Event System
Manual observer pattern for benchmarking against SwX.
"""

from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio
from collections import defaultdict


class EventPriority(Enum):
    """Event listener priority."""
    HIGHEST = 0
    HIGH = 25
    NORMAL = 50
    LOW = 75
    LOWEST = 100


@dataclass
class EventListener:
    """Event listener definition."""
    handler: Callable
    priority: EventPriority = EventPriority.NORMAL
    async: bool = False


class Event:
    """Base event class."""
    def __init__(self, name: str, payload: Dict[str, Any] = None):
        self.name = name
        self.payload = payload or {}
        self._stopped = False
    
    def stop_propagation(self) -> None:
        """Stop event propagation."""
        self._stopped = True
    
    @property
    def is_stopped(self) -> bool:
        return self._stopped


class EventDispatcher:
    """Manual event dispatcher - observer pattern."""
    
    def __init__(self):
        self._listeners: Dict[str, List[EventListener]] = defaultdict(list)
        self._wildcard_listeners: List[EventListener] = []
    
    def listen(
        self,
        event_name: str,
        handler: Callable,
        priority: EventPriority = EventPriority.NORMAL,
        async_handler: bool = False
    ) -> None:
        """Register an event listener."""
        listener = EventListener(handler=handler, priority=priority, async=async_handler)
        
        if '*' in event_name:
            self._wildcard_listeners.append(listener)
        else:
            self._listeners[event_name].append(listener)
            # Sort by priority
            self._listeners[event_name].sort(key=lambda l: l.priority.value)
    
    def once(self, event_name: str, handler: Callable) -> None:
        """Register a one-time listener."""
        async def wrapper(event: Event):
            handler(event)
            self._listeners[event_name] = [
                l for l in self._listeners[event_name] 
                if l.handler != wrapper
            ]
        
        self.listen(event_name, wrapper)
    
    def emit(self, event_name: str, payload: Dict[str, Any] = None) -> None:
        """Emit a synchronous event."""
        event = Event(event_name, payload)
        
        # Get specific listeners
        listeners = self._listeners.get(event_name, [])
        
        # Get wildcard listeners
        for listener in self._wildcard_listeners:
            pattern = listener.handler.__name__.replace('_listener', '').replace('_handler', '')
            if pattern in event_name or pattern == '*':
                listeners.append(listener)
        
        # Execute listeners
        for listener in listeners:
            if event.is_stopped:
                break
            
            try:
                if listener.async:
                    # For sync emit, run in thread pool
                    asyncio.get_event_loop().run_in_executor(None, listener.handler, event)
                else:
                    listener.handler(event)
            except Exception as e:
                # Log error but continue
                print(f"Event handler error: {e}")
    
    async def dispatch(self, event_name: str, payload: Dict[str, Any] = None) -> None:
        """Emit an asynchronous event."""
        event = Event(event_name, payload)
        
        # Get specific listeners
        listeners = self._listeners.get(event_name, [])
        
        # Get wildcard listeners
        for listener in self._wildcard_listeners:
            pattern = listener.handler.__name__.replace('_listener', '').replace('_handler', '')
            if pattern in event_name or pattern == '*':
                listeners.append(listener)
        
        # Execute listeners
        for listener in listeners:
            if event.is_stopped:
                break
            
            try:
                if asyncio.iscoroutinefunction(listener.handler):
                    await listener.handler(event)
                else:
                    listener.handler(event)
            except Exception as e:
                print(f"Event handler error: {e}")
    
    def remove_listener(self, event_name: str, handler: Callable) -> None:
        """Remove a specific listener."""
        self._listeners[event_name] = [
            l for l in self._listeners[event_name]
            if l.handler != handler
        ]
    
    def clear(self, event_name: str = None) -> None:
        """Clear listeners."""
        if event_name:
            self._listeners.pop(event_name, None)
        else:
            self._listeners.clear()
            self._wildcard_listeners.clear()
    
    def has_listeners(self, event_name: str) -> bool:
        """Check if event has listeners."""
        return len(self._listeners.get(event_name, [])) > 0


# Global event dispatcher
event_dispatcher = EventDispatcher()


# Convenience functions
def on(event_name: str, priority: EventPriority = EventPriority.NORMAL):
    """Decorator to register event listener."""
    def decorator(func: Callable):
        event_dispatcher.listen(event_name, func, priority)
        return func
    return decorator


def emit(event_name: str, payload: Dict[str, Any] = None) -> None:
    """Emit a synchronous event."""
    event_dispatcher.emit(event_name, payload)


async def dispatch(event_name: str, payload: Dict[str, Any] = None) -> None:
    """Emit an asynchronous event."""
    await event_dispatcher.dispatch(event_name, payload)
