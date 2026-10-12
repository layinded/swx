"""
Event Debug Utilities.

Provides debugging and inspection tools for the event system.

Usage:
    from swx_core.events.debug import (
        list_all_listeners,
        test_pattern,
        trace_event,
        print_event_bus_status,
    )
    
    # List all registered listeners
    list_all_listeners()
    
    # Test if a pattern matches an event
    test_pattern("user.*", "user.created")  # True
    
    # Trace which listeners would receive an event
    trace_event("user.created")
    
    # Print full event bus status
    print_event_bus_status()
"""

from typing import Dict, List, Optional
from swx_core.events.dispatcher import event_bus, EventBus


def list_all_listeners() -> Dict[str, List[str]]:
    """
    Return all registered listeners grouped by event pattern.
    
    Returns:
        Dict mapping event patterns to list of listener names.
    """
    result = {}
    
    # Direct listeners
    for event, listeners in event_bus._listeners.items():
        result[event] = []
        for reg in listeners:
            listener_name = getattr(reg.listener, "__name__", str(reg.listener))
            result[event].append(
                f"{listener_name} (priority={reg.priority}, queueable={reg.queueable})"
            )
    
    # Wildcard listeners
    if event_bus._wildcard_listeners:
        result["*wildcards*"] = []
        for reg in event_bus._wildcard_listeners:
            listener_name = getattr(reg.listener, "__name__", str(reg.listener))
            result["*wildcards*"].append(
                f"{listener_name} (pattern={reg.pattern}, priority={reg.priority})"
            )
    
    return result


def test_pattern(pattern: str, event_name: str) -> bool:
    """
    Test if an event name matches a pattern.
    
    Patterns:
        - "*" matches all events
        - "user.*" matches "user.created", "user.deleted", etc.
        - "*.created" matches "user.created", "role.created", etc.
    
    Args:
        pattern: The pattern to test
        event_name: The event name to match
        
    Returns:
        True if the event name matches the pattern, False otherwise.
    """
    temp_bus = EventBus()
    return temp_bus._matches_pattern(event_name, pattern)


def trace_event(event_name: str) -> List[str]:
    """
    Trace which listeners would receive an event.
    
    Shows the execution order (by priority) of listeners that would
    handle the given event, including wildcard pattern matches.
    
    Args:
        event_name: The event to trace
        
    Returns:
        List of listener names in execution order (highest priority first).
    """
    listeners = event_bus._get_listeners_for_event(event_name)
    result = []
    
    for reg in listeners:
        listener_name = getattr(reg.listener, "__name__", str(reg.listener))
        match_type = "exact" if reg not in event_bus._wildcard_listeners else "wildcard"
        result.append(
            f"{listener_name} (priority={reg.priority}, match={match_type}, "
            f"queueable={reg.queueable})"
        )
    
    return result


def print_event_bus_status() -> None:
    """
    Print a comprehensive status report of the event bus.
    
    Shows:
    - Total listener count
    - Direct event listeners by event name
    - Wildcard pattern listeners
    - Recent fired events (for testing)
    """
    print("=" * 60)
    print("EVENT BUS STATUS")
    print("=" * 60)
    
    # Count listeners
    direct_count = sum(len(listeners) for listeners in event_bus._listeners.values())
    wildcard_count = len(event_bus._wildcard_listeners)
    total_count = direct_count + wildcard_count
    
    print(f"\nTotal Listeners: {total_count}")
    print(f"  - Direct listeners: {direct_count}")
    print(f"  - Wildcard listeners: {wildcard_count}")
    
    # Direct listeners
    if event_bus._listeners:
        print("\nDIRECT LISTENERS:")
        for event, listeners in sorted(event_bus._listeners.items()):
            print(f"\n  Event: '{event}' ({len(listeners)} listener(s))")
            for reg in sorted(listeners, key=lambda r: r.priority, reverse=True):
                listener_name = getattr(reg.listener, "__name__", str(reg.listener))
                print(f"    - {listener_name}")
                print(f"      Priority: {reg.priority}, Queueable: {reg.queueable}, Once: {reg.once}")
    
    # Wildcard listeners
    if event_bus._wildcard_listeners:
        print("\nWILDCARD LISTENERS:")
        for reg in sorted(event_bus._wildcard_listeners, key=lambda r: r.priority, reverse=True):
            listener_name = getattr(reg.listener, "__name__", str(reg.listener))
            print(f"  - {listener_name}")
            print(f"    Pattern: {reg.pattern}")
            print(f"    Priority: {reg.priority}, Queueable: {reg.queueable}")
    
    # Show pattern matching examples
    if event_bus._wildcard_listeners:
        print("\nPATTERN MATCHING EXAMPLES:")
        test_events = ["user.created", "user.deleted", "role.created", "order.paid"]
        for test_event in test_events:
            matching = trace_event(test_event)
            if matching:
                print(f"\n  Event: '{test_event}'")
                for match in matching:
                    print(f"    -> {match}")
    
    # Recent fired events
    if event_bus._fired:
        print("\nRECENT FIRED EVENTS (testing buffer):")
        for event, events in list(event_bus._fired.items())[-5:]:
            print(f"  - '{event}': {len(events)} time(s)")
    
    print("\n" + "=" * 60)


def get_listener_count(event: Optional[str] = None) -> int:
    """
    Get the count of registered listeners.
    
    Args:
        event: Optional event name to count specific listeners.
               If None, returns total count including wildcards.
    
    Returns:
        Number of matching listeners.
    """
    if event:
        return len(event_bus.get_listeners(event))
    else:
        direct_count = sum(len(listeners) for listeners in event_bus._listeners.values())
        wildcard_count = len(event_bus._wildcard_listeners)
        return direct_count + wildcard_count


def verify_listener_registered(listener_class_name: str) -> bool:
    """
    Verify if a listener class has been registered.
    
    Args:
        listener_class_name: Name of the listener class to find.
        
    Returns:
        True if the listener is registered, False otherwise.
    """
    all_listeners = list_all_listeners()
    
    for event, listener_list in all_listeners.items():
        for listener_info in listener_list:
            if listener_class_name in listener_info:
                return True
    
    return False