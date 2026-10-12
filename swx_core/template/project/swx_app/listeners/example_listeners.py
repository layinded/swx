"""
Example Event Listeners

This module demonstrates how to create event listeners in SwX.
Listeners are automatically discovered and registered during bootstrap.

Listener Types:
1. Listener class - Auto-discovered from swx_app/listeners/
2. @listen decorator - Manual registration via decorator
3. event_bus.listen() - Direct registration

Pattern Matching:
- "user.created" - Exact match
- "user.*" - Match all user events (user.created, user.deleted, etc.)
- "*.created" - Match all created events
- "*" - Match all events
"""

from swx_core.events import Listener, event_bus, listen


class UserEventListener(Listener):
    """
    Example listener for user-related events.
    
    This listener uses the wildcard pattern "user.*" which matches:
    - user.created
    - user.updated
    - user.deleted
    - user.password_changed
    - etc.
    """
    
    event = "user.*"
    priority = 80
    
    async def handle(self, event):
        """
        Handle user events.
        
        Args:
            event: Event object with name and payload
        """
        from swx_core.middleware.logging_middleware import logger
        
        event_type = event.name.split(".")[-1]
        user_id = event.payload.get("id")
        
        logger.info(f"[UserEventListener] User event: {event.name}, ID: {user_id}")
        
        if event.name == "user.created":
            await self._on_user_created(event)
        elif event.name == "user.updated":
            await self._on_user_updated(event)
        elif event.name == "user.deleted":
            await self._on_user_deleted(event)
    
    async def _on_user_created(self, event):
        """Handle user creation event."""
        user_data = event.payload.get("data", {})
        context = event.payload.get("context", {})
        
    async def _on_user_updated(self, event):
        """Handle user update event."""
        old_values = event.payload.get("old_values", {})
        new_values = event.payload.get("new_values", {})
        
    async def _on_user_deleted(self, event):
        """Handle user deletion event."""
        pass


class SendWelcomeEmailListener(Listener):
    """
    Example listener that sends welcome emails.
    
    This uses an exact event match "user.created" and has
    a higher priority than UserEventListener (90 > 80),
    so it runs first.
    """
    
    event = "user.created"
    priority = 90
    
    async def handle(self, event):
        """Send welcome email to new user."""
        from swx_core.middleware.logging_middleware import logger
        
        user_data = event.payload.get("data", {})
        user_email = user_data.get("email")
        user_id = event.payload.get("id")
        
        logger.info(f"[SendWelcomeEmailListener] Sending welcome email to {user_email}")
        


class AuditLogListener(Listener):
    """
    Example audit listener that logs all events.
    
    Uses the "*" pattern to match ALL events in the system.
    Priority is lowest (1) so it runs after all other listeners.
    """
    
    event = "*"
    priority = 1
    
    async def handle(self, event):
        """Log all events for audit purposes."""
        from swx_core.middleware.logging_middleware import logger
        
        logger.info(
            f"[AuditLogListener] Event: {event.name}, "
            f"Payload: {event.payload}, "
            f"Timestamp: {event.timestamp}"
        )


@listen("role.created", priority=100)
async def log_role_creation(event):
    """
    Example of using the @listen decorator.
    
    This function is automatically registered as a listener
    for "role.created" events when the module is imported.
    """
    from swx_core.middleware.logging_middleware import logger
    
    role_id = event.payload.get("id")
    role_data = event.payload.get("data", {})
    
    logger.info(f"[Decorator Listener] Role created: {role_data.get('name')} (ID: {role_id})")


"""
MANUAL REGISTRATION EXAMPLE:

If you need to register listeners manually (outside of auto-discovery),
you can do so in your main.py startup:

    from swx_core.events import event_bus
    from swx_app.listeners.user_listener import UserEventListener
    
    @app.on_event("startup")
    async def register_listeners():
        listener = UserEventListener()
        event_bus.listen(
            listener.event,
            listener.handle,
            priority=listener.priority
        )

DECORATOR REGISTRATION EXAMPLE:

    from swx_core.events import listen
    
    @listen("user.created", priority=100)
    async def send_welcome_email(event):
        user = event.payload
        await send_email(user["email"], "Welcome!")
"""