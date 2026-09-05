# Event Broadcasting — Usage Examples

Practical patterns for using Redis Pub/Sub event broadcasting in SwX applications.

---

## Prerequisites

```bash
# .env — Redis must be enabled
REDIS_ENABLED=True
REDIS_URL=redis://:password@redis-host:6379/0

# Bridge is enabled by default when Redis is on.
# To disable (single-worker dev, for example):
# EVENT_BRIDGE_ENABLED=False
```

Verify it's running:

```python
from swx_core.container.container import get_container

bridge = get_container().make("event_bridge")
print(bridge.get_stats())
# {"running": True, "redis_connected": True, "dispatch_patched": True, ...}
```

---

## Example 1: Zero-Code Migration (Existing Events Just Work)

The bridge patches `event_bus.dispatch` transparently. All existing events
automatically reach every worker — no code changes needed.

```python
# swx_app/services/order_service.py
from swx_core.events.dispatcher import event_bus

async def place_order(user_id: str, items: list):
    order = await create_order(user_id, items)

    # This dispatch now reaches ALL workers via Redis
    await event_bus.dispatch("order.placed", payload={
        "id": str(order.id),
        "data": {"user_id": str(user_id), "total": order.total},
    })

    return order
```

```python
# swx_app/listeners/order_listeners.py
from swx_core.events import Listener

class SendOrderConfirmationListener(Listener):
    event = "order.placed"
    priority = 100

    async def handle(self, event):
        order = event.payload
        await send_confirmation_email(order["data"]["user_id"], order["id"])

class UpdateInventoryListener(Listener):
    event = "order.placed"
    priority = 50

    async def handle(self, event):
        order = event.payload
        await reserve_inventory(order["id"])
```

**Result**: Regardless of which worker processes the HTTP request, both
listeners fire on the worker that dispatched the event AND on every other
worker. If you have 4 workers, each listener runs 4 times — once per worker.

> **Important**: If a listener should only run once across all workers
> (e.g., sending an email), use a distributed lock or idempotency check
> inside the listener. See Example 5 for patterns.

---

## Example 2: Broadcast-Only Events (No Local Listener)

Sometimes you want to notify other workers without running local listeners.
Use `add_exclude_prefix` on the dispatching worker to skip local execution
for internal events — but this is rare. More commonly, you just dispatch
normally and let the bridge handle the fan-out.

```python
# Every worker gets the event — including this one
await event_bus.dispatch("cache.invalidated", payload={"key": "user:123"})
```

If you truly want to skip local listeners for certain events:

```python
# In your app startup (e.g., swx_app/listeners/bridge_config.py)
from swx_core.container.container import get_container

bridge = get_container().make("event_bridge")

# "internal.*" events still get broadcast to other workers,
# but they won't run local listeners on this worker's EventBus.
# (This is a niche pattern — most users don't need this.)
```

---

## Example 3: Real-Time Notifications with SSE

Push live notifications to browser clients connected to any worker.

### Server Side

```python
# swx_app/routes/notification_route.py
import asyncio
import json
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from swx_core.events.dispatcher import event_bus

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

# Track connected clients per worker
_connected_queues: list[asyncio.Queue] = []


async def _notification_listener(event):
    """Bridge listener: push event data to all connected SSE clients on this worker."""
    data = event.to_dict()
    for queue in _connected_queues:
        await queue.put(data)


# Register once when the module loads
event_bus.listen("notification.*", _notification_listener, priority=50)


async def event_stream(request: Request):
    """SSE endpoint — each client gets its own queue."""
    queue = asyncio.Queue()
    _connected_queues.append(queue)

    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                data = await asyncio.wait_for(queue.get(), timeout=30)
                yield {
                    "event": data.get("name", "notification"),
                    "data": json.dumps(data, default=str),
                }
            except asyncio.TimeoutError:
                yield {"event": "heartbeat", "data": ""}
    finally:
        _connected_queues.remove(queue)


@router.get("/stream")
async def sse_endpoint(request: Request):
    return EventSourceResponse(event_stream(request))


@router.post("/send")
async def send_notification(user_id: str, message: str):
    """Send a notification to all connected clients across all workers."""
    await event_bus.dispatch("notification.new", payload={
        "user_id": user_id,
        "message": message,
    })
    return {"status": "sent"}
```

### Client Side (JavaScript)

```javascript
const eventSource = new EventSource("/api/notifications/stream");

eventSource.addEventListener("notification", (event) => {
    const data = JSON.parse(event.data);
    showToast(data.message);
});

eventSource.addEventListener("heartbeat", () => {
    // Connection keep-alive — no action needed
});

eventSource.onerror = () => {
    // Auto-reconnect after 3 seconds
    setTimeout(() => location.reload(), 3000);
};
```

**How it works with 4 workers**:

1. Client connects to Worker 2's SSE endpoint.
2. `POST /api/notifications/send` hits Worker 1.
3. Worker 1 dispatches `notification.new` → local listener fires + Redis publish.
4. Workers 2, 3, 4 each receive the Redis message and re-dispatch locally.
5. Worker 2's `_notification_listener` pushes data into the client's queue.
6. Client receives the notification.

---

## Example 4: Selective Broadcasting with Filters

Not every event needs to cross the wire. Use broadcast filters to reduce
Redis traffic.

```python
# swx_app/listeners/bridge_config_listener.py
from swx_core.events import Listener
from swx_core.container.container import get_container

class ConfigureBridgeListener(Listener):
    """Configure the event bridge at startup."""

    event = "app.booted"
    priority = 100

    async def handle(self, event):
        bridge = get_container().make("event_bridge")

        # Only broadcast user, billing, and notification events
        bridge.set_broadcast_filter(
            lambda name: name.startswith(("user.", "billing.", "notification."))
        )

        # Exclude high-frequency internal events
        bridge.add_exclude_prefix("internal.")
        bridge.add_exclude_prefix("debug.")
        bridge.add_exclude_prefix("audit.")
```

**Effect**:

| Event | Broadcast? | Why |
|---|---|---|
| `user.created` | ✅ Yes | Matches `user.*` filter |
| `billing.payment_failed` | ✅ Yes | Matches `billing.*` filter |
| `notification.new` | ✅ Yes | Matches `notification.*` filter |
| `internal.cache_refreshed` | ❌ No | Matches `internal.*` exclude |
| `debug.query_log` | ❌ No | Matches `debug.*` exclude |
| `order.placed` | ❌ No | Doesn't match filter |

---

## Example 5: Exactly-Once Execution (Distributed Locks)

Since the bridge fans out to ALL workers, listeners that should only run once
(e.g., sending an email) need idempotency guards.

### Pattern A: Redis Distributed Lock

```python
import uuid
from swx_core.container.container import get_container

async def run_once(task_name: str, ttl: int = 30):
    """Acquire a Redis lock so only one worker executes the task."""
    container = get_container()
    if not container.bound("redis.client"):
        return True  # Single-worker mode — always run

    redis = container.make("redis.client")
    lock_id = str(uuid.uuid4())
    # SET with NX (only if not exists) and EX (expiry)
    acquired = await redis.set(f"lock:{task_name}", lock_id, nx=True, ex=ttl)
    return acquired
```

```python
# swx_app/listeners/email_listener.py
from swx_core.events import Listener

class SendWelcomeEmailListener(Listener):
    event = "user.created"
    priority = 100

    async def handle(self, event):
        user = event.payload
        task_key = f"email:welcome:{user['id']}"

        if await run_once(task_key, ttl=60):
            await send_welcome_email(user["data"]["email"], user["data"]["name"])
```

### Pattern B: Idempotency Key

```python
class ProcessPaymentListener(Listener):
    event = "billing.payment_processed"
    priority = 100

    async def handle(self, event):
        payment_id = event.payload["id"]
        task_key = f"payment:process:{payment_id}"

        if await run_once(task_key, ttl=300):
            await process_payment(payment_id)
```

---

## Example 6: Custom Channel for Chat / WebSocket Fan-Out

Use `subscribe()` and `publish()` for app-specific channels that aren't
tied to the EventBus.

```python
# swx_app/services/chat_service.py
import json
from swx_core.container.container import get_container

async def broadcast_chat_message(room_id: str, message: dict):
    """Publish a chat message to all workers."""
    bridge = get_container().make("event_bridge")
    await bridge.publish(
        f"swx:chat:{room_id}",
        message,
    )
```

```python
# swx_app/routes/chat_route.py
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from swx_core.container.container import get_container
from swx_core.events.redis_bridge import RedisEventBridge

router = APIRouter()

# Store per-room queues for WebSocket connections
_rooms: dict[str, list[asyncio.Queue]] = {}


async def _chat_handler(message: dict):
    """Custom Redis handler — push chat messages to local WebSocket clients."""
    room_id = message.get("payload", {}).get("room_id")
    if room_id in _rooms:
        for queue in _rooms[room_id]:
            await queue.put(message)


# Subscribe to chat channels on startup
_bridge: RedisEventBridge | None = None


@router.websocket("/ws/chat/{room_id}")
async def chat_websocket(websocket: WebSocket, room_id: str):
    global _bridge

    await websocket.accept()

    # Lazy-initialize the subscription
    if _bridge is None:
        _bridge = get_container().make("event_bridge")
        await _bridge.subscribe("swx:chat:*", _chat_handler)

    queue = asyncio.Queue()
    if room_id not in _rooms:
        _rooms[room_id] = []
    _rooms[room_id].append(queue)

    try:
        while True:
            # Send messages from queue to WebSocket
            data = await queue.get()
            await websocket.send_json(data)
    except WebSocketDisconnect:
        pass
    finally:
        _rooms[room_id].remove(queue)
        if not _rooms[room_id]:
            del _rooms[room_id]
```

---

## Example 7: Health-Check Endpoint

Add a health-check endpoint that reports bridge status.

```python
# swx_app/routes/health_route.py
from fastapi import APIRouter
from swx_core.container.container import get_container

router = APIRouter()


@router.get("/api/utils/health-bridge")
async def health_bridge():
    """Health check for Redis event bridge."""
    container = get_container()

    if not container.bound("event_bridge"):
        return {"status": "disabled", "reason": "Redis or bridge not enabled"}

    bridge = container.make("event_bridge")
    stats = bridge.get_stats()

    return {
        "status": "healthy" if stats["running"] else "stopped",
        "redis_connected": stats["redis_connected"],
        "dispatch_patched": stats["dispatch_patched"],
        "channel_prefix": stats["channel_prefix"],
        "custom_patterns": stats["custom_patterns"],
        "exclude_prefixes": stats["exclude_prefixes"],
    }
```

---

## Example 8: Testing Without Redis

In test environments where Redis isn't available, the bridge is a no-op.
Events stay in-process — exactly like before the bridge existed.

```python
# tests/test_events.py
import pytest
from swx_core.events.dispatcher import event_bus, EventBus

@pytest.mark.asyncio
async def test_event_dispatch_without_redis():
    """Events work normally even without Redis."""
    received = []

    async def listener(event):
        received.append(event.payload)

    event_bus.listen("user.created", listener)

    await event_bus.dispatch("user.created", payload={"user_id": "abc123"})

    assert len(received) == 1
    assert received[0]["user_id"] == "abc123"

    event_bus.forget("user.created", listener)
```

```python
# tests/test_bridge_filter.py
import pytest
from swx_core.events.dispatcher import EventBus
from swx_core.events.redis_bridge import RedisEventBridge

@pytest.mark.asyncio
async def test_broadcast_filter():
    """Broadcast filter works without Redis (no publish calls)."""
    bus = EventBus()
    bridge = RedisEventBridge(bus, redis_client=None)  # No Redis

    # Set filter — only user.* events should "broadcast"
    bridge.set_broadcast_filter(lambda name: name.startswith("user."))

    assert bridge._should_broadcast("user.created") is True
    assert bridge._should_broadcast("order.placed") is False

@pytest.mark.asyncio
async def test_exclude_prefix():
    """Exclude prefixes block events from broadcasting."""
    bus = EventBus()
    bridge = RedisEventBridge(bus, redis_client=None)

    bridge.add_exclude_prefix("internal.")
    bridge.add_exclude_prefix("debug.")

    assert bridge._should_broadcast("user.created") is True
    assert bridge._should_broadcast("internal.cache_refreshed") is False
    assert bridge._should_broadcast("debug.query_log") is False
```

---

## Example 9: Multi-Environment Isolation

Use `EVENT_BRIDGE_CHANNEL_PREFIX` to isolate environments on a shared Redis:

```bash
# .env.production
EVENT_BRIDGE_CHANNEL_PREFIX=swx:prod:events

# .env.staging
EVENT_BRIDGE_CHANNEL_PREFIX=swx:staging:events

# .env.development
EVENT_BRIDGE_CHANNEL_PREFIX=swx:dev:events
```

Events dispatched in staging won't reach production workers, even if they
share the same Redis instance.

---

## Example 10: Graceful Shutdown

The bridge stops automatically during app shutdown (handled by the lifespan
in `main.py`). If you need to stop it manually:

```python
from swx_core.container.container import get_container

bridge = get_container().make("event_bridge")

# Stop the background subscriber (stops receiving Redis messages)
await bridge.stop()

# Unpatch EventBus.dispatch (revert to local-only)
bridge.unpatch_dispatch()

# Later, restart it
await bridge.start()
bridge.patch_dispatch()
```

---

## Troubleshooting

### Events not reaching other workers

1. **Check Redis is connected**:
   ```python
   bridge = get_container().make("event_bridge")
   print(bridge.get_stats())
   # "redis_connected": True
   ```

2. **Check bridge is running**:
   ```python
   print(bridge.is_running)  # Should be True
   ```

3. **Check dispatch is patched**:
   ```python
   print(bridge.get_stats()["dispatch_patched"])  # Should be True
   ```

4. **Check filter isn't blocking**:
   ```python
   print(bridge.get_stats()["has_broadcast_filter"])  # Check your filter
   print(bridge.get_stats()["exclude_prefixes"])       # Check exclusions
   ```

5. **Enable debug logging**:
   ```python
   import logging
   logging.getLogger("swx_core.events.redis_bridge").setLevel(logging.DEBUG)
   ```

### Redis connection drops

The bridge auto-reconnects with a 5-second delay. If it exceeds
`MAX_RECONNECT_ATTEMPTS` (default: unlimited), it stops. Check logs for:

```
Redis event bridge reconnecting in 5.0s (attempt 1)...
Redis event bridge reconnected successfully
```

### Events running multiple times

This is expected — the bridge fans out to ALL workers. If you need
exactly-once execution, use a distributed lock or idempotency key
(see Example 5).