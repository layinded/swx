"""
Listener Auto-Discovery
-----------------------
Automatically discovers and registers Listener subclasses from listener modules.

This module scans listener directories and auto-registers all Listener subclasses
with the global event_bus, following the same pattern as model/service/repository discovery.

Functions:
- `load_all_listeners()`: Load and register both core and app listeners
- `discover_listeners()`: Find all Listener subclasses in a module
"""

import inspect
from typing import List, Type

from swx_core.events.dispatcher import event_bus
from swx_core.events.listener import Listener
from swx_core.middleware.logging_middleware import logger
from swx_core.config.discovery import discovery


def discover_listeners(module) -> List[Type[Listener]]:
    """
    Find all Listener subclasses in a module.
    
    Args:
        module: The module to scan for Listener subclasses
        
    Returns:
        List of Listener classes found in the module
    """
    listeners = []
    
    for name in dir(module):
        obj = getattr(module, name)
        
        # Check if it's a class and a Listener subclass (but not Listener itself)
        if (
            inspect.isclass(obj)
            and issubclass(obj, Listener)
            and obj is not Listener
            and not inspect.isabstract(obj)
        ):
            listeners.append(obj)
    
    return listeners


def register_listener(listener_class: Type[Listener]) -> None:
    """
    Register a Listener class with the event bus.
    
    Args:
        listener_class: The Listener subclass to register
    """
    try:
        # Create an instance of the listener
        # Note: If listener requires constructor args, this will fail gracefully
        instance = listener_class()
        
        # Get listener configuration
        event_name = instance.event
        priority = instance.priority
        queueable = instance.queueable
        queue_name = instance.queue
        
        # Determine the handler method
        if hasattr(instance, 'handle'):
            handler = instance.handle
        else:
            logger.warning(f"Listener {listener_class.__name__} has no handle() method")
            return
        
        # Register with event bus
        event_bus.listen(
            event=event_name,
            listener=handler,
            priority=priority,
            queueable=queueable,
            queue_name=queue_name,
        )
        
        logger.info(f"Registered listener: {listener_class.__name__} -> '{event_name}' (priority={priority})")
        
    except Exception as e:
        logger.error(f"Failed to register listener {listener_class.__name__}: {e}")


def load_listeners_from_path(base_path: str, package_name: str) -> int:
    """
    Load listeners from a specific path.
    
    Args:
        base_path: Directory path to scan for listener modules
        package_name: Python package name for imports
        
    Returns:
        Number of listeners registered
    """
    from swx_core.utils.loader import dynamic_import
    from pathlib import Path
    
    path = Path(base_path)
    if not path.exists():
        return 0
    
    registered_count = 0
    
    # Import all modules in the listeners directory
    modules = dynamic_import(base_path, package_name, recursive=True)
    
    for module_name, module in modules.items():
        # Skip __init__.py and non-listener modules
        if module_name.endswith('.__init__'):
            continue
            
        # Find all Listener subclasses in this module
        listeners = discover_listeners(module)
        
        for listener_class in listeners:
            register_listener(listener_class)
            registered_count += 1
    
    return registered_count


def load_all_listeners() -> None:
    """
    Load and register all listeners from core and app directories.
    
    This should be called during application startup, after models and services
    are loaded but before the application starts handling requests.
    
    Listener directories scanned:
    - swx_core/events/listeners/ (core listeners)
    - swx_app/listeners/ (app listeners)
    
    Example listener structure:
        swx_app/
        └── listeners/
            ├── __init__.py
            ├── user_listeners.py      # Contains UserCreatedListener
            └── billing_listeners.py   # Contains PaymentSuccessListener
    
    Example listener class:
        class SendWelcomeEmailListener(Listener):
            event = "user.created"
            priority = 100
            
            async def handle(self, event):
                user = event.payload
                await send_email(user.email, "Welcome!")
    """
    total_registered = 0
    
    # Load core listeners from swx_core/events/listeners/
    core_listeners_path = discovery.core_base / "events" / "listeners"
    if core_listeners_path.exists():
        count = load_listeners_from_path(
            str(core_listeners_path),
            "swx_core.events.listeners"
        )
        if count:
            print(f"Registered {count} core listeners")
            total_registered += count
    
    # Load app listeners from swx_app/listeners/
    if discovery.app_exists():
        app_listeners_path = discovery.app_base / "listeners"
        if app_listeners_path.exists():
            count = load_listeners_from_path(
                str(app_listeners_path),
                f"{discovery.app_name}.listeners"
            )
            if count:
                print(f"Registered {count} app listeners")
                total_registered += count
    
    if total_registered == 0:
        print("No listeners found to register")
    else:
        print(f"Total listeners registered: {total_registered}")