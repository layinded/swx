# Event System with Auto-Discovery

SwX-Core provides a powerful event system with automatic listener discovery, following Laravel's EventServiceProvider pattern.

## Overview

The event system allows you to:
- **Emit events** from services using `BaseService` (automatic CRUD events)
- **Create listeners** that respond to events
- **Auto-register listeners** during bootstrap (no manual registration needed)

## Quick Start

### 1. Create a Listener

Create listeners in `swx_app/listeners/`:

```python
# swx_app/listeners/user_listeners.py
from swx_core.events import Listener

class SendWelcomeEmailListener(Listener):
    event = "user.created"
    priority = 100

    async def handle(self, event):
        user = event.payload
        await send_welcome_email(user.email, user.name)

class LogUserActivityListener(Listener):
    event = "user.*"
    priority = 10

    async def handle(self, event):
        await log_activity(event.name, event.payload)
```

### 2. That's It!

Listeners are auto-registered during bootstrap. No manual registration needed.

## Event Patterns

### Specific Events

```python
class UserCreatedListener(Listener):
    event = "user.created"

    async def handle(self, event):
        user = event.payload
```

### Wildcard Events

```python
class UserActivityListener(Listener):
    event = "user.*"

    async def handle(self, event):
        if event.name == "user.created":
            await handle_user_created(event.payload)
        elif event.name == "user.deleted":
            await handle_user_deleted(event.payload)
```

### All Events

```python
class AuditListener(Listener):
    event = "*"
    priority = 1

    async def handle(self, event):
        await audit_log(event.name, event.payload)
```

## Listener Locations

SwX-Core scans these directories for listeners:

| Directory | Purpose |
|-----------|---------|
| `swx_core/events/listeners/` | Core framework listeners |
| `swx_app/listeners/` | Application listeners |

## Listener Properties

```python
class MyListener(Listener):
    event = "my.event"
    priority = 50
    queueable = False
    queue = "default"

    async def handle(self, event):
        pass
```

| Property | Type | Description |
|----------|------|-------------|
| `event` | str | Event name or pattern (supports `*` wildcard) |
| `priority` | int | Higher = executed first (default: 50) |
| `queueable` | bool | If True, runs in background queue |
| `queue` | str | Queue name for queueable listeners |

## Emitting Events

### Automatic (CRUD Events)

`BaseService` automatically emits events:

```python
# BaseService handles CRUD operations and emits events
user = await user_service.create(user_data)
# Events: "user.created"

user = await user_service.update(user.id, update_data)
# Events: "user.updated"

await user_service.delete(user.id)
# Events: "user.deleted"
```

### Manual (Custom Events)

```python
from swx_core.events import event_bus

async def process_order(order_id: int):
    order = await get_order(order_id)
    
    await event_bus.emit("order.processing", payload=order)
    
    processed = await do_processing(order)
    
    await event_bus.emit("order.completed", payload=processed)
```

## Priority-Based Execution

Listeners execute by priority (highest first):

```python
class HighPriorityListener(Listener):
    event = "user.created"
    priority = 100

    async def handle(self, event):
        await send_welcome_email(event.payload)

class NormalPriorityListener(Listener):
    event = "user.created"
    priority = 50

    async def handle(self, event):
        await log_user_creation(event.payload)

class LowPriorityListener(Listener):
    event = "user.created"
    priority = 10

    async def handle(self, event):
        await update_analytics(event.payload)
```

Execution order: `HighPriorityListener` → `NormalPriorityListener` → `LowPriorityListener`

## Queueable Listeners

For long-running tasks, use queueable listeners:

```python
class SendReportListener(Listener):
    event = "report.generate"
    priority = 50
    queueable = True
    queue = "reports"

    async def handle(self, event):
        report = await generate_large_report(event.payload)
        await send_report_email(report)
```

Queueable listeners are handled by the background job system.

## Directory Structure

```
swx_app/
├── listeners/
│   ├── __init__.py
│   ├── user_listeners.py
│   ├── order_listeners.py
│   └── notification_listeners.py
│
│   # Each file can contain multiple listeners
```

## Complete Example

### User Registration Flow

```python
# swx_app/listeners/user_listeners.py
from swx_core.events import Listener

class SendWelcomeEmailListener(Listener):
    event = "user.created"
    priority = 100

    async def handle(self, event):
        user = event.payload
        await send_email(
            to=user.email,
            subject="Welcome!",
            body=f"Hi {user.name}, welcome to our platform!"
        )

class SetupUserDefaultsListener(Listener):
    event = "user.created"
    priority = 90

    async def handle(self, event):
        user = event.payload
        await create_default_settings(user.id)
        await assign_default_role(user.id)

class AuditUserCreationListener(Listener):
    event = "user.created"
    priority = 10

    async def handle(self, event):
        await audit_log(
            action="user.created",
            user_id=event.payload.id,
            timestamp=event.timestamp
        )
```

### Order Processing

```python
# swx_app/listeners/order_listeners.py
from swx_core.events import Listener

class ProcessOrderListener(Listener):
    event = "order.placed"
    priority = 100

    async def handle(self, event):
        order = event.payload
        await validate_order(order)
        await reserve_inventory(order)

class SendOrderConfirmationListener(Listener):
    event = "order.placed"
    priority = 50

    async def handle(self, event):
        order = event.payload
        await send_order_confirmation_email(order)

class UpdateAnalyticsListener(Listener):
    event = "order.*"
    priority = 10

    async def handle(self, event):
        if event.name == "order.placed":
            await track_purchase(event.payload)
        elif event.name == "order.cancelled":
            await track_cancellation(event.payload)
```

## Event Payloads

```python
class MyListener(Listener):
    event = "user.created"

    async def handle(self, event):
        user = event.payload
        timestamp = event.timestamp
        event_name = event.name
        
        if event.is_stopped():
            return
        
        # Stop propagation
        event.stop()
```

## Manual Listener Registration

If you need to register listeners manually:

```python
from swx_core.events import event_bus, Listener

class CustomListener(Listener):
    event = "custom.event"

    async def handle(self, event):
        pass

# Manual registration
event_bus.listen(
    event="custom.event",
    listener=CustomListener().handle,
    priority=50
)
```

## Using the Decorator

```python
from swx_core.events import event_bus

@event_bus.subscribe("user.created")
async def send_welcome_email(event):
    user = event.payload
    await send_email(user.email, "Welcome!")
```

## Testing Listeners

```python
import pytest
from swx_core.events import event_bus, Listener

class TestListener(Listener):
    event = "test.event"
    priority = 10

    async def handle(self, event):
        return event.payload

@pytest.mark.asyncio
async def test_listener_registration():
    listener = TestListener()
    
    event_bus.listen(
        event="test.event",
        listener=listener.handle,
        priority=10
    )
    
    events = await event_bus.emit("test.event", payload={"key": "value"})
    assert len(events) == 1
    assert events[0].payload == {"key": "value"}
```

## Best Practices

### 1. Use Priority Wisely

- Use higher priority for critical listeners (emails, notifications)
- Use lower priority for non-critical tasks (analytics, logging)

### 2. Keep Listeners Focused

```python
class SendWelcomeEmailListener(Listener):
    event = "user.created"
    priority = 100

    async def handle(self, event):
        user = event.payload
        await send_welcome_email(user)
```

### 3. Use Wildcards for Related Events

```python
class UserActivityListener(Listener):
    event = "user.*"

    async def handle(self, event):
        if event.name.startswith("user."):
            await log_user_activity(event.name, event.payload)
```

### 4. Make Listeners Idempotent

```python
class IdempotentListener(Listener):
    event = "payment.processed"

    async def handle(self, event):
        payment_id = event.payload["id"]
        
        if await already_processed(payment_id):
            return
        
        await process_payment(payment_id)
        await mark_as_processed(payment_id)
```

### 5. Handle Errors Gracefully

```python
class ErrorTolerantListener(Listener):
    event = "notification.send"

    async def handle(self, event):
        try:
            await send_notification(event.payload)
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            await queue_for_retry(event.payload)
```

## API Reference

### Listener Class

```python
class Listener:
    event: str = ""
    priority: int = 50
    queueable: bool = False
    queue: str = "default"

    async def handle(self, event: Event) -> None:
        raise NotImplementedError
```

### EventBus Methods

```python
event_bus.listen(
    event: str,
    listener: Callable,
    priority: int = 50,
    queueable: bool = False,
    queue_name: str = "default",
    once: bool = False
) -> None

event_bus.subscribe(event: str) -> Callable

await event_bus.emit(
    event: str,
    payload: Any = None
) -> List[Event]

await event_bus.emit_async(
    event: str,
    payload: Any = None
```

---

## Troubleshooting

### Listeners Not Being Registered

**Symptom**: `event_bus.has_listeners("user.created")` returns `False`

**Check 1: Bootstrap Called**
```python
# Ensure bootstrap_app() is called
from swx_core import bootstrap
container = bootstrap(app)  # This registers listeners
```

**Check 2: Directory Structure**
```bash
ls -la swx_app/listeners/
# Should see __init__.py and listener files
```

**Check 3: Listener Class Requirements**
- Must inherit from `Listener`
- Must implement `async def handle(self, event)`
- Must not be abstract (no `@abstractmethod`)
- Must not be `Listener` class itself

**Check 4: Print Event Bus Status**
```python
from swx_core.events import print_event_bus_status
print_event_bus_status()
```

### Events Not Reaching Listeners

**Symptom**: Event dispatched but listeners don't execute

**Check 1: Pattern Matching**
```python
from swx_core.events import test_pattern

# Verify pattern matches
test_pattern("user.*", "user.created")  # Should be True
test_pattern("user.*", "role.created")   # Should be False
```

**Check 2: Trace Event Execution**
```python
from swx_core.events import trace_event

# See which listeners WOULD receive the event
trace_event("user.created")
# ['Listener1 (priority=100)', 'Listener2 (priority=50)', ...]
```

**Check 3: Enable Debug Logging**
```python
import logging
logging.getLogger("swx_core.events").setLevel(logging.DEBUG)
```

### Debug Utilities

SwX provides debug utilities to inspect the event system:

```python
from swx_core.events import (
    list_all_listeners,
    test_pattern,
    trace_event,
    print_event_bus_status,
    get_listener_count,
    verify_listener_registered,
)

# List all registered listeners
listeners = list_all_listeners()

# Test if a pattern matches an event
test_pattern("user.*", "user.created")  # True

# Trace which listeners would receive an event
trace_event("user.created")

# Print comprehensive event bus status
print_event_bus_status()

# Get total listener count
count = get_listener_count()

# Verify a specific listener is registered
verify_listener_registered("UserEventListener")  # True/False
```

### Manual Registration Workaround

If auto-discovery fails, register listeners manually:

```python
from swx_core.events import event_bus
from swx_app.listeners.user_listener import UserEventListener

@app.on_event("startup")
async def startup_event():
    listener = UserEventListener()
    event_bus.listen(
        listener.event,
        listener.handle,
        priority=listener.priority
    )
```

## Events Emitted by SwX

SwX services automatically emit these events:

| Service | Event Name | Trigger |
|---------|-----------|---------|
| auth_service | `user.created` | User registration |
| user_service | `user.updated` | Profile update |
| user_service | `user.password_changed` | Password change |
| user_service | `user.deleted` | User deletion |
| role_service | `role.created` | Role creation |
| role_service | `role.updated` | Role update |
| role_service | `role.deleted` | Role deletion |
| permission_service | `permission.created` | Permission creation |
| team_service | `team.created`, `team.member_added` | Team operations |

## Event Payload Structure

```python
# Create events
{
    "id": "uuid-string",
    "data": {"field": "value", ...},
    "context": {"user_id": "...", ...}  # Optional context
}

# Update events
{
    "id": "uuid-string",
    "old_values": {"field": "previous"},
    "new_values": {"field": "updated"},
    "context": {...}
}

# Delete events
{
    "id": "uuid-string",
    "data": {"name": "deleted-resource"},
    "context": {...}
}
```
) -> List[Event]
```
