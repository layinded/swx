"""
Event Contracts.

Defines interfaces for the event dispatcher and listeners.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum


class EventPriority(IntEnum):
    """Listener priority levels."""
    HIGHEST = 100
    HIGH = 75
    NORMAL = 50
    LOW = 25
    LOWEST = 1


@dataclass
class EventInterface:
    """
    Base event interface.
    
    Events carry data through the application.
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


class ListenerInterface(ABC):
    """
    Abstract interface for event listeners.
    """
    
    @property
    @abstractmethod
    def event(self) -> str:
        """
        Event name or pattern this listener handles.
        
        Supports wildcards: "user.*", "*"
        
        Returns:
            str: Event name or pattern
        """
        pass
    
    @property
    def priority(self) -> int:
        """
        Listener priority. Higher priority executes first.
        
        Returns:
            int: Priority value
        """
        return EventPriority.NORMAL
    
    @property
    def queueable(self) -> bool:
        """
        Whether this listener should be queued.
        
        Returns:
            bool: True if queueable
        """
        return False
    
    @property
    def queue(self) -> str:
        """
        Queue name for queueable listeners.
        
        Returns:
            str: Queue name
        """
        return "default"
    
    @abstractmethod
    async def handle(self, event: EventInterface) -> None:
        """
        Handle the event.
        
        Args:
            event: The event instance
        """
        pass
    
    def should_queue(self, event: EventInterface) -> bool:
        """
        Determine if the listener should be queued for this event.
        
        Args:
            event: The event instance
            
        Returns:
            bool: True if should queue
        """
        return self.queueable
    
    def failed(self, event: EventInterface, exception: Exception) -> None:
        """
        Handle a failure.
        
        Args:
            event: The event instance
            exception: The exception that occurred
        """
        pass


class EventBusInterface(ABC):
    """
    Abstract interface for the event dispatcher.
    """
    
    @abstractmethod
    def listen(
        self,
        event: str,
        listener: Callable,
        priority: int = EventPriority.NORMAL,
        queueable: bool = False
    ) -> None:
        """
        Register an event listener.
        
        Args:
            event: Event name or pattern
            listener: Callable to handle the event
            priority: Listener priority
            queueable: Whether to queue the listener
        """
        pass
    
    @abstractmethod
    def forget(self, event: str, listener: Callable) -> bool:
        """
        Remove a listener.
        
        Args:
            event: Event name
            listener: The listener to remove
            
        Returns:
            bool: True if removed
        """
        pass
    
    @abstractmethod
    async def dispatch(
        self,
        event: str,
        payload: Any = None,
        **kwargs
    ) -> EventInterface:
        """
        Dispatch an event.
        
        Args:
            event: Event name
            payload: Event payload
            **kwargs: Additional event data
            
        Returns:
            EventInterface: The dispatched event
        """
        pass
    
    @abstractmethod
    async def dispatch_sync(
        self,
        event: str,
        payload: Any = None,
        **kwargs
    ) -> EventInterface:
        """
        Dispatch event synchronously.
        
        Args:
            event: Event name
            payload: Event payload
            **kwargs: Additional event data
            
        Returns:
            EventInterface: The dispatched event
        """
        pass
    
    @abstractmethod
    def has_listeners(self, event: str) -> bool:
        """
        Check if event has listeners.
        
        Args:
            event: Event name
            
        Returns:
            bool: True if has listeners
        """
        pass
    
    @abstractmethod
    def get_listeners(self, event: str) -> List[Callable]:
        """
        Get all listeners for an event.
        
        Args:
            event: Event name
            
        Returns:
            List[Callable]: List of listeners
        """
        pass