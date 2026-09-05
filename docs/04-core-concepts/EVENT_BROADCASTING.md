# Event Broadcasting (Redis Pub/Sub)

Cross-worker event broadcasting enables events dispatched on one worker process to be received by listeners on **all** workers. This is essential for multi-process deployments (e.g., `uvicorn --workers 4` or Gunicorn) where each worker has its own in-memory `EventBus`.

## How It Works

```
Worker 1: event_bus.dispatch("user.registered", payload={...})
  ├─ Local listeners fire immediately (in-process)
  └─ Published to Redis channel: swx:events:user.registered
                    │
                Redis Server
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   Worker 1    Worker 2    Worker 3
   (ignored,   (local     (local
    _source=    dispatch)  dispatch)
    "redis")
```

1. **Local dispatch** runs first — zero latency for the originating worker.
2. **Redis publish** fans out to all subscribed workers.
3. **Loop prevention** — events received from Redis carry `_broadcast_source="redis"` and are not re-published.

## Configuration

| Setting | Default | Description |
|---|---|---|
| `REDIS_ENABLED` | `True` | Required. Redis must be enabled for the bridge to activate. |
| `EVENT_BRIDGE_ENABLED` | `True` | Enable/disable cross-worker broadcasting. Set to `False` to keep events in-process only. |
| `EVENT_BRIDGE_CHANNEL_PREFIX` | `swx:events` | Redis channel prefix. Useful for isolating environments (e.g., `staging:events`). |

```bash
# .env — minimal config (bridge is enabled by default when Redis is on)
REDIS_ENABLED=True
REDIS_URL=redis://:password@redis-host:6379/0

# Disable the bridge (events stay in-process only)
EVENT_BRIDGE_ENABLED=False

# Custom channel prefix for multi-tenant isolation
EVENT_BRIDGE_CHANNEL_PREFIX=myapp:staging:events
```

## Automatic Activation

The bridge activates automatically when both `REDIS_ENABLED` and `EVENT_BRIDGE_ENABLED` are `True`. No code changes needed — your existing `event_bus.dispatch()` calls broadcast across workers:

```python
from swx_core.events.dispatcher import event_bus

# This now reaches ALL workers via Redis:
await event_bus.dispatch("user.registered", payload={"user_id": str(user.id)})
```

## Extending the Bridge

### Filtering Which Events Get Broadcast

Not all events need cross-worker delivery (e.g., internal framework events). Use the broadcast filter:

```python
from swx_core.container.container import get_container

bridge = get_container().make("event_bridge")

# Only broadcast user.* and billing.* events
bridge.set_broadcast_filter(
    lambda name: name.startswith(("user.", "billing."))
)
```

### Excluding Event Prefixes

```python
bridge.add_exclude_prefix("internal.")
bridge.add_exclude_prefix("debug.")

# These stay local-only:
await event_bus.dispatch("internal.cache_refreshed", ...)
await event_bus.dispatch("debug.query_log", ...)
```

### Custom Redis Channels

For app-specific real-time features (SSE, WebSocket fan-out, notifications):

```python
from swx_core.events.redis_bridge import RedisEventBridge

bridge = get_container().make("event_bridge")

# Subscribe to a custom channel pattern
async def on_notification(message):
    # message = {"event": "...", "payload": {...}, "ts": 1234567890.0}
    await push_to_sse_clients(message)

await bridge.subscribe("swx:notifications:*", on_notification)

# Publish to a custom channel
await bridge.publish("swx:notifications:urgent", {"text": "Server restarting in 5 min"})

# Unsubscribe when done
await bridge.unsubscribe("swx:notifications:*", on_notification)
```

### SSE Integration (Real-Time Updates)

```python
from sse_starlette.sse import EventSourceResponse
import asyncio
import json

async def event_stream(request: Request):
    queue = asyncio.Queue()

    async def on_event(event):
        await queue.put(event.to_dict())

    # Register listener
    event_bus.listen("notification.*", on_event)
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                data = await asyncio.wait_for(queue.get(), timeout=30)
                yield {"event": "notification", "data": json.dumps(data)}
            except asyncio.TimeoutError:
                yield {"event": "heartbeat", "data": ""}
    finally:
        event_bus.forget("notification.*", on_event)

@router.get("/events/stream")
async def sse_endpoint(request: Request):
    return EventSourceResponse(event_stream(request))
```

With the Redis bridge active, a notification dispatched on Worker 1 reaches SSE clients connected to **any** worker.

### Health Check

```python
bridge = get_container().make("event_bridge")
stats = bridge.get_stats()
# {
#   "running": True,
#   "redis_connected": True,
#   "channel_prefix": "swx:events",
#   "app_name": "swx",
#   "custom_patterns": [],
#   "exclude_prefixes": ["internal."],
#   "has_broadcast_filter": True,
#   "dispatch_patched": True,
# }
```

## Architecture Decisions

| Decision | Rationale |
|---|---|
| Local listeners fire first | Lowest latency for the originating worker |
| `_broadcast_source="redis"` marker | Prevents infinite loops — events from Redis aren't re-published |
| Pattern subscription (`swx:events:*`) | New event types are automatically picked up without config |
| Graceful Redis failure | If Redis is down, local events still work — just not cross-worker |
| Auto-reconnect | Subscriber retries after 5s if the Redis connection drops |
| Patching `dispatch()` | Transparent — no code changes to existing event dispatching |

## Multi-Worker Deployment

```bash
# Production with 4 workers
uvicorn swx_core.main:app --workers 4 --bind 0.0.0.0:8001

# Or with Gunicorn
gunicorn swx_core.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8001
```

Each worker starts its own Redis subscriber. Events dispatched on any worker reach all workers within milliseconds.