"""
Event Service Provider.

Registers event bus and core event listeners.
"""

from swx_core.providers.base import ServiceProvider


class EventServiceProvider(ServiceProvider):
    """Register event services and core listeners."""
    
    priority = 15  # Register early for other providers to use
    
    def register(self) -> None:
        """Register event bindings."""
        from swx_core.events.dispatcher import event_bus
        
        # Event bus (singleton - global instance)
        self.singleton("events", event_bus)
        self.instance("EventBus", event_bus)
        self.instance("event_bus", event_bus)
    
    def boot(self) -> None:
        """Register core event listeners."""
        from swx_core.events.dispatcher import event_bus
        
        # Register core listeners for auth events
        self._register_auth_listeners(event_bus)
    
    def _register_auth_listeners(self, event_bus) -> None:
        """Register authentication event listeners."""
        # Password change - revoke tokens
        event_bus.listen(
            "user.password_changed",
            self._revoke_tokens_on_password_change,
            priority=100
        )
        
        # User deactivation - revoke all sessions
        event_bus.listen(
            "user.deactivated",
            self._revoke_sessions_on_deactivation,
            priority=100
        )
        
        # Audit all auth events
        event_bus.listen(
            "user.*",
            self._audit_auth_events,
            priority=1  # Low priority - run last
        )
    
    async def _revoke_tokens_on_password_change(self, event) -> None:
        """Revoke all tokens when password changes."""
        user_id = event.payload.get("user_id")
        if not user_id:
            return
        
        try:
            from swx_core.container.container import get_container
            container = get_container()
            
            if container.bound("auth.token_blacklist"):
                blacklist = container.make("auth.token_blacklist")
                await blacklist.revoke_user_tokens(user_id, ttl_seconds=2592000)
        except Exception as e:
            from swx_core.middleware.logging_middleware import logger
            logger.error(f"Failed to revoke tokens on password change: {e}")
    
    async def _revoke_sessions_on_deactivation(self, event) -> None:
        """Revoke all sessions when user is deactivated."""
        user_id = event.payload.get("user_id")
        if not user_id:
            return
        
        try:
            from swx_core.container.container import get_container
            container = get_container()
            
            if container.bound("auth.token_blacklist"):
                blacklist = container.make("auth.token_blacklist")
                await blacklist.revoke_user_tokens(user_id, ttl_seconds=2592000)
        except Exception as e:
            from swx_core.middleware.logging_middleware import logger
            logger.error(f"Failed to revoke sessions on deactivation: {e}")
    
    async def _audit_auth_events(self, event) -> None:
        """Log all auth events for audit."""
        from swx_core.middleware.logging_middleware import logger
        
        logger.info(
            f"Auth event: {event.name}",
            extra={
                "event_name": event.name,
                "user_id": event.payload.get("user_id"),
                "timestamp": event.timestamp.isoformat(),
            }
        )