"""
Event Listeners.

Base classes for event listeners.
"""

from abc import ABC, abstractmethod
from typing import Optional
from swx_core.events.dispatcher import Event


class Listener(ABC):
    """
    Abstract base class for event listeners.
    
    Usage:
        class SendWelcomeEmail(Listener):
            event = "user.registered"
            priority = 100
            
            async def handle(self, event):
                user = event.payload
                await send_email(user.email, "Welcome!")
    """
    
    @property
    @abstractmethod
    def event(self) -> str:
        """Event name or pattern this listener handles."""
        pass
    
    @property
    def priority(self) -> int:
        """Listener priority. Higher = executes first."""
        return 50
    
    @property
    def queueable(self) -> bool:
        """Whether this listener should be queued."""
        return False
    
    @property
    def queue(self) -> str:
        """Queue name for queueable listeners."""
        return "default"
    
    @abstractmethod
    async def handle(self, event: Event) -> None:
        """Handle the event."""
        pass
    
    def should_queue(self, event: Event) -> bool:
        """Determine if the listener should be queued."""
        return self.queueable
    
    def failed(self, event: Event, exception: Exception) -> None:
        """Handle a failure."""
        pass


class QueueableListener(Listener):
    """
    Base class for queueable listeners.
    
    Queueable listeners are processed asynchronously via the job queue.
    """
    
    @property
    def queueable(self) -> bool:
        return True
    
    @property
    def queue(self) -> str:
        return self.__class__.__name__.lower().replace("listener", "")


def listen(event: str, priority: int = 50, queueable: bool = False):
    """
    Decorator to create a listener from a function.
    
    Usage:
        @listen("user.registered", priority=100)
        async def send_welcome_email(event):
            user = event.payload
            await send_email(user.email, "Welcome!")
    """
    from swx_core.events.dispatcher import event_bus
    
    def decorator(func):
        event_bus.listen(event, func, priority=priority, queueable=queueable)
        return func
    
    return decorator