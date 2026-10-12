# SwX v2.0.0 Extension Guide

**Version:** 2.0.0  
**Last Updated:** 2026-02-28

This guide documents the supported extension points in SwX and shows complete, runnable examples.

## Table of Contents

1. [Service Container Extension](#1-service-container-extension)
2. [Custom Service Providers](#2-custom-service-providers)
3. [Custom Guards](#3-custom-guards)
4. [Custom Middleware](#4-custom-middleware)
5. [Event System Extension](#5-event-system-extension)
6. [Plugin Development](#6-plugin-development)

---

## Conventions Used In This Guide

- Container bindings are keyed by `str` service IDs (for example: `"cache"`, `"auth.guard_manager"`).
- Constructor injection (auto-wiring) resolves by *type name* (for example, an annotation `cache: CacheDriver` resolves the key `"CacheDriver"`).
- If you want both patterns, create an alias (for example, bind `"cache"` and alias it as `"CacheDriver"`).
- Scoped bindings are only stable inside a scope: `with container.scope():` or `async with container.async_scope():`.

Imports referenced in this guide come from these modules:

```python
from swx_core.container.container import Container, get_container
from swx_core.providers.base import ServiceProvider, ProviderRegistry
from swx_core.providers.core_providers import CORE_PROVIDERS
from swx_core.container.fastapi_integration import inject, ContainerMiddleware
```

---

## 1. Service Container Extension

SwX ships with a Laravel-style IoC container: `swx_core/container/container.py`.

### 1.1 Custom Bindings (bind, singleton, scoped)

- `bind(abstract, concrete)`: transient (new instance per `make()`)
- `singleton(abstract, concrete)`: singleton (same instance)
- `scoped(abstract, concrete)`: scoped (same instance inside a scope)

Complete runnable example:

```python
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from swx_core.container.container import Container


class CacheDriver:
    async def get(self, key: str, default: Any = None) -> Any:
        raise NotImplementedError

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        raise NotImplementedError


@dataclass
class InMemoryCache(CacheDriver):
    _store: dict[str, Any]

    async def get(self, key: str, default: Any = None) -> Any:
        return self._store.get(key, default)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        self._store[key] = value
        return True


class RequestId:
    def __init__(self) -> None:
        self.value = id(self)


async def main() -> None:
    c = Container()

    # transient: new cache each time
    c.bind("cache.transient", lambda _c: InMemoryCache(_store={}))

    # singleton: shared cache
    c.singleton("cache", lambda _c: InMemoryCache(_store={}))

    # scoped: one per scope
    c.scoped("request_id", lambda _c: RequestId())

    a = c.make("cache.transient")
    b = c.make("cache.transient")
    assert a is not b

    s1 = c.make("cache")
    s2 = c.make("cache")
    assert s1 is s2

    async with c.async_scope():
        r1 = c.make("request_id")
        r2 = c.make("request_id")
        assert r1 is r2

    async with c.async_scope():
        r3 = c.make("request_id")
        assert r3 is not r1


if __name__ == "__main__":
    asyncio.run(main())
```

### 1.2 Factory Functions

Any callable that is not a class is treated as a factory. SwX passes the container as the first argument.

```python
from swx_core.container.container import Container


class Settings:
    def __init__(self, env: str) -> None:
        self.env = env


container = Container()
container.singleton("settings", lambda c: Settings(env="production"))
settings = container.make("settings")
```

### 1.3 Aliases (Recommended for Type-Based Injection)

If you prefer binding with stable service IDs (like `"cache"`) but still want type-name constructor injection, alias the type name to the service ID.

```python
from swx_core.container.container import Container


class CacheDriver:
    pass


class InMemoryCache(CacheDriver):
    pass


container = Container()
container.singleton("cache", InMemoryCache)
container.alias("cache", "CacheDriver")  # resolve "CacheDriver" -> "cache"
```

### 1.4 Contextual Bindings

SwX supports contextual bindings via `when(...).needs(...).give(...)`.

In current SwX builds, contextual bindings are only applied when the container can determine a resolution context. The most reliable approach is to construct the *context owner* via a factory and resolve its dependencies explicitly.

Complete runnable example:

```python
from __future__ import annotations

from swx_core.container.container import Container


class Cache:
    pass


class RedisCache(Cache):
    pass


class MemoryCache(Cache):
    pass


class ServiceWithCache:
    def __init__(self, cache: Cache) -> None:
        self.cache = cache


def service_factory(c: Container) -> ServiceWithCache:
    # Establish context while resolving dependencies.
    c._build_stack.append("service_with_cache")  # internal; keep this pattern isolated
    try:
        cache = c.make("cache")
    finally:
        c._build_stack.pop()
    return ServiceWithCache(cache)


container = Container()
container.bind("cache", RedisCache)
container.when("service_with_cache").needs("cache").give(MemoryCache)
container.bind("service_with_cache", service_factory)

direct_cache = container.make("cache")
svc = container.make("service_with_cache")

assert isinstance(direct_cache, RedisCache)
assert isinstance(svc.cache, MemoryCache)
```

### 1.5 Tagged Bindings

Tagging groups multiple bindings under a tag name.

```python
from swx_core.container.container import Container


class HandlerA:
    name = "a"


class HandlerB:
    name = "b"


container = Container()
container.bind("handler.a", HandlerA)
container.bind("handler.b", HandlerB)
container.tag("handlers", ["handler.a", "handler.b"])

handlers = container.tagged("handlers")
assert [h.name for h in handlers] == ["a", "b"]
```

### 1.6 Resolution Callbacks (resolving, after_resolving) and Extenders

- `resolving(abstract, callback)`: runs before resolution
- `after_resolving(abstract, callback)`: runs after resolution
- `extend(abstract, extender)`: lets you wrap/modify the resolved instance

Notes:

- Callbacks receive the container instance (not the resolved object).
- Extenders receive `(instance, container)` and must return the instance.

Complete runnable example:

```python
from __future__ import annotations

from swx_core.container.container import Container


class Cache:
    def __init__(self) -> None:
        self.prefix = ""


def mark_resolving(c: Container) -> None:
    # You can observe/trigger side effects here.
    # Keep it idempotent; it may run many times.
    c.instance("telemetry.cache.resolving_called", True)


def add_prefix(cache: Cache, c: Container) -> Cache:
    cache.prefix = "swx:"
    return cache


container = Container()
container.singleton("cache", Cache)
container.resolving("cache", mark_resolving)
container.extend("cache", add_prefix)

cache = container.make("cache")
assert cache.prefix == "swx:"
assert container.make("telemetry.cache.resolving_called") is True
```

---

## 2. Custom Service Providers

Providers are the canonical way to register services into the container.

### 2.1 Provider Interface/Contract

- Base class: `swx_core/providers/base.py` `ServiceProvider`
- Contract: `swx_core/contracts/container.py` `ServiceProviderInterface`

Provider lifecycle:

- `register()`: bind services only; do not resolve other services
- `boot()`: run post-registration work; safe to resolve services

### 2.2 Register and Boot

Minimal provider:

```python
from swx_core.providers.base import ServiceProvider


class ExampleService:
    pass


class ExampleServiceProvider(ServiceProvider):
    priority = 900

    def register(self) -> None:
        self.singleton("example", ExampleService)

    def boot(self) -> None:
        _ = self.app.make("example")
```

### 2.3 Deferred Providers

SwX includes `defer`/`provides()` on the provider base, but core bootstrapping does not automatically defer provider registration.

Two practical patterns:

1. Use lazy bindings: bind factories that do heavy work only when resolved.
2. Create your own plugin/provider loader that reads a manifest and registers provider classes only when enabled.

### 2.4 Provider Discovery

You can register providers explicitly using the registry:

```python
from swx_core.container.container import get_container
from swx_core.providers.base import ProviderRegistry
from swx_core.providers.core_providers import CORE_PROVIDERS


container = get_container()
registry = ProviderRegistry(container)
registry.register_all(CORE_PROVIDERS)
registry.boot()
```

FastAPI integration (request scoping) is available via `swx_core/container/fastapi_integration.py`:

```python
from fastapi import FastAPI
from swx_core.container.fastapi_integration import ContainerMiddleware


app = FastAPI()
app.add_middleware(ContainerMiddleware)
```

### 2.5 Example: CacheServiceProvider

This provider binds a cache driver and exposes it under both `"cache"` and `"CacheDriver"`.

Create `swx_app/providers/cache_provider.py`:

```python
from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as aioredis

from typing import Any, Optional, Protocol

from swx_core.config.settings import settings
from swx_core.providers.base import ServiceProvider


class CacheDriver(Protocol):
    async def get(self, key: str, default: Any = None) -> Any: ...
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool: ...


class RedisCacheDriver(CacheDriver):
    def __init__(self, client: aioredis.Redis, prefix: str = "swx:") -> None:
        self.client = client
        self.prefix = prefix

    def _k(self, key: str) -> str:
        return f"{self.prefix}{key}"

    async def get(self, key: str, default: Any = None) -> Any:
        raw = await self.client.get(self._k(key))
        if raw is None:
            return default
        return json.loads(raw)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        raw = json.dumps(value).encode("utf-8")
        if ttl is None:
            await self.client.set(self._k(key), raw)
        else:
            await self.client.setex(self._k(key), ttl, raw)
        return True

    async def delete(self, key: str) -> bool:
        await self.client.delete(self._k(key))
        return True

    async def exists(self, key: str) -> bool:
        return bool(await self.client.exists(self._k(key)))

    async def increment(self, key: str, amount: int = 1) -> int:
        return int(await self.client.incrby(self._k(key), amount))

    async def decrement(self, key: str, amount: int = 1) -> int:
        return int(await self.client.decrby(self._k(key), amount))

    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        if not keys:
            return {}
        values = await self.client.mget([self._k(k) for k in keys])
        out: dict[str, Any] = {}
        for k, v in zip(keys, values):
            if v is not None:
                out[k] = json.loads(v)
        return out

    async def set_many(self, items: dict[str, Any], ttl: Optional[int] = None) -> bool:
        if not items:
            return True
        pipe = self.client.pipeline()
        for k, v in items.items():
            raw = json.dumps(v).encode("utf-8")
            if ttl is None:
                pipe.set(self._k(k), raw)
            else:
                pipe.setex(self._k(k), ttl, raw)
        await pipe.execute()
        return True

    async def delete_many(self, keys: list[str]) -> bool:
        if keys:
            await self.client.delete(*[self._k(k) for k in keys])
        return True

    async def clear(self) -> bool:
        # Scope clears are app-specific; consider deleting keys by prefix.
        return False

    async def get_ttl(self, key: str) -> Optional[int]:
        ttl = await self.client.ttl(self._k(key))
        if ttl is None or ttl < 0:
            return None
        return int(ttl)

    async def remember(self, key: str, callback: callable, ttl: Optional[int] = None) -> Any:
        existing = await self.get(key, default=None)
        if existing is not None:
            return existing
        value = await callback()
        await self.set(key, value, ttl=ttl)
        return value


class CacheServiceProvider(ServiceProvider):
    priority = 50

    def register(self) -> None:
        self.singleton("redis.client", self._create_redis)
        self.singleton("cache", self._create_cache)

        # Enable constructor injection by type name.
        self.alias("cache", "CacheDriver")

    def boot(self) -> None:
        # Example: warm a cache key after all providers register.
        cache: CacheDriver = self.app.make("cache")

        async def warm() -> None:
            await cache.set("boot.warmed", {"ok": True}, ttl=60)

        # Fire-and-forget is app-specific; keep boot() synchronous.

    def _create_redis(self, app):
        url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
        return aioredis.from_url(url, decode_responses=False)

    def _create_cache(self, app):
        client = app.make("redis.client")
        return RedisCacheDriver(client)
```

Register it by adding a provider file under `swx_app/providers/` and registering via your container bootstrap (see Section 2.4).

---

## 3. Custom Guards

Guards implement request authentication. The core contract is `swx_core/guards/base.py` `BaseGuard`.

### 3.1 BaseGuard Interface

Required members:

- `name: str` property
- `authenticate(request) -> Optional[AuthenticatedUser]`
- `validate_token(token) -> Dict[str, Any]`
- `create_token(user, **claims) -> str`
- `revoke_token(token) -> bool`

### 3.2 GuardManager Registration

Guards are registered into `GuardManager` (`swx_core/guards/guard_manager.py`). In core SwX, this happens in `swx_core/providers/auth_provider.py`.

You can register your own guards from an application provider.

### 3.3 Example: APIKeyGuard

SwX includes `APIKeyGuard` at `swx_core/guards/api_key_guard.py`. To enable it, ensure it is registered with the guard manager (core provider does this based on settings).

### 3.4 Example: OAuthGuard (Opaque Token Introspection)

This guard validates an OAuth2 opaque access token by calling an introspection endpoint.

Create `swx_app/guards/oauth_guard.py`:

```python
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
from fastapi import Request

from swx_core.guards.base import BaseGuard, AuthenticatedUser


class OAuthGuard(BaseGuard):
    def __init__(
        self,
        introspection_url: str,
        client_id: str,
        client_secret: str,
        audience: str = "api",
        header_name: str = "Authorization",
    ) -> None:
        self.introspection_url = introspection_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.audience = audience
        self.header_name = header_name

    @property
    def name(self) -> str:
        return "oauth"

    async def authenticate(self, request: Request) -> Optional[AuthenticatedUser]:
        token = self._extract_bearer(request)
        if not token:
            return None

        try:
            payload = await self.validate_token(token)
        except Exception:
            return None

        if not payload.get("active"):
            return None

        sub = str(payload.get("sub") or payload.get("user_id") or "")
        if not sub:
            return None

        scopes = payload.get("scope", "")
        permissions = scopes.split() if isinstance(scopes, str) else []

        return AuthenticatedUser(
            id=sub,
            email=str(payload.get("email") or ""),
            type="oauth",
            roles=list(payload.get("roles") or []),
            permissions=permissions,
            is_superuser=bool(payload.get("super", False)),
            is_active=True,
            metadata={"issuer": payload.get("iss"), "aud": payload.get("aud")},
        )

    async def validate_token(self, token: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                self.introspection_url,
                data={"token": token, "token_type_hint": "access_token"},
                auth=(self.client_id, self.client_secret),
                headers={"Accept": "application/json"},
            )
            resp.raise_for_status()
            return dict(resp.json())

    async def create_token(self, user: Any, audience: str = None, **claims) -> str:
        raise NotImplementedError("OAuthGuard does not mint tokens")

    async def revoke_token(self, token: str) -> bool:
        return False

    def _extract_bearer(self, request: Request) -> Optional[str]:
        raw = request.headers.get(self.header_name, "")
        if not raw.lower().startswith("bearer "):
            return None
        token = raw[7:].strip()
        return token or None
```

Register it from a provider, for example `swx_app/providers/custom_auth_provider.py`:

```python
from swx_core.providers.base import ServiceProvider
from swx_core.config.settings import settings

from swx_app.guards.oauth_guard import OAuthGuard


class CustomAuthProvider(ServiceProvider):
    priority = 25

    def register(self) -> None:
        self.singleton(
            "auth.oauth_guard",
            lambda app: OAuthGuard(
                introspection_url=settings.OAUTH_INTROSPECTION_URL,
                client_id=settings.OAUTH_CLIENT_ID,
                client_secret=settings.OAUTH_CLIENT_SECRET,
            ),
        )

    def boot(self) -> None:
        manager = self.app.make("auth.guard_manager")
        manager.register("oauth", self.app.make("auth.oauth_guard"))
```

Use from routes:

```python
from fastapi import APIRouter, Depends, Request

from swx_core.guards.guard_manager import get_current_user
from swx_core.guards.base import AuthenticatedUser


router = APIRouter()


@router.get("/me")
async def me(user: AuthenticatedUser = Depends(get_current_user)):
    return user.to_dict() if user else {"authenticated": False}
```

---

## 4. Custom Middleware

SwX supports two middleware patterns:

1. Standard FastAPI/Starlette middleware (`app.add_middleware(...)`).
2. SwX dynamic middleware loader: any module under `swx_core/middleware/` or `swx_app/middleware/` that defines `apply_middleware(app: FastAPI)` will be discovered and applied by `swx_core/utils/loader.py`.

### 4.1 Middleware Pattern

For custom middleware that should load automatically, create `swx_app/middleware/<name>.py` and define `apply_middleware(app)`.

### 4.2 Request/Response Hooks and Error Handling

Middleware typically:

- inspects/modifies the incoming `Request`
- calls `call_next(request)`
- inspects/modifies the outgoing `Response`
- catches exceptions and returns a safe error response

### 4.3 Example: RateLimitMiddleware

This example rate-limits by client IP (in-memory) and demonstrates response headers and error handling.

Create `swx_app/middleware/rate_limit_middleware.py`:

```python
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Tuple

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


@dataclass
class Bucket:
    reset_at: float
    remaining: int


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limit: int = 60, window_seconds: int = 60):
        super().__init__(app)
        self.limit = limit
        self.window_seconds = window_seconds
        self._buckets: Dict[str, Bucket] = {}

    async def dispatch(self, request: Request, call_next):
        try:
            key = (request.client.host if request.client else "unknown")
            now = time.time()
            b = self._buckets.get(key)

            if b is None or now >= b.reset_at:
                b = Bucket(reset_at=now + self.window_seconds, remaining=self.limit)
                self._buckets[key] = b

            if b.remaining <= 0:
                retry_after = max(0, int(b.reset_at - now))
                resp = JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "rate_limit_exceeded",
                        "message": "Too many requests",
                        "retry_after": retry_after,
                    },
                )
                resp.headers["Retry-After"] = str(retry_after)
                resp.headers["X-RateLimit-Limit"] = str(self.limit)
                resp.headers["X-RateLimit-Remaining"] = "0"
                resp.headers["X-RateLimit-Reset"] = str(int(b.reset_at))
                return resp

            b.remaining -= 1
            response = await call_next(request)

            response.headers["X-RateLimit-Limit"] = str(self.limit)
            response.headers["X-RateLimit-Remaining"] = str(b.remaining)
            response.headers["X-RateLimit-Reset"] = str(int(b.reset_at))
            return response

        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": "middleware_error", "message": str(e)},
            )


def apply_middleware(app: FastAPI) -> None:
    app.add_middleware(RateLimitMiddleware, limit=120, window_seconds=60)
```

---

## 5. Event System Extension

SwX ships a framework-level event bus at `swx_core/events/dispatcher.py`.

### 5.1 Custom Events

You can dispatch by string name, or create an `Event` subclass.

```python
from swx_core.events.dispatcher import Event


class OrderPlaced(Event):
    def __init__(self, order_id: str, user_id: str):
        super().__init__(
            name="order.placed",
            payload={"order_id": order_id, "user_id": user_id},
        )
```

### 5.2 Event Listeners

You can register:

- functions via `event_bus.listen(...)`
- function listeners via `@event_bus.subscribe(...)`
- class-based listeners under `swx_app/listeners/` (discovered by `swx_core/bootstrap.py` `register_event_listeners()`)

### 5.3 Priority-Based Dispatch

Higher priority runs first.

```python
from swx_core.events.dispatcher import event_bus, EventPriority


def audit_first(event):
    event.set("audited", True)


def business_logic(event):
    if not event.get("audited"):
        raise RuntimeError("Expected audit_first to run")


event_bus.listen("order.placed", business_logic, priority=EventPriority.NORMAL)
event_bus.listen("order.placed", audit_first, priority=EventPriority.HIGHEST)
```

### 5.4 Async Listeners

- If your listener is `async def`, SwX awaits it.
- If you mark it `queueable=True`, SwX enqueues a job (`job_type="event.listener"`) and falls back to in-process execution if the job system is unavailable.

```python
from swx_core.events.dispatcher import event_bus


async def send_email(event):
    # do IO
    return None


event_bus.listen("order.placed", send_email, priority=50, queueable=True, queue_name="emails")
```

### 5.5 Wildcard Patterns

Listeners registered with `"*"` or any pattern containing `"*"` are treated as wildcard listeners.

Current behavior: wildcard listeners receive all events (pattern filtering is not enforced by the dispatcher). If you need prefix filtering, do it inside the listener.

```python
from swx_core.events.dispatcher import event_bus


async def audit_user_events(event):
    if not event.name.startswith("user."):
        return
    # audit event.payload


event_bus.listen("user.*", audit_user_events, priority=1)
```

---

## 6. Plugin Development

SwX includes CLI support for managing plugins via a manifest:

- `swx plugin:list`
- `swx plugin:enable <name>`
- `swx plugin:disable <name>`
- `swx plugin:install <url>`

The CLI writes `swx_app/plugins/manifest.json`.

### 6.1 Plugin Manifest Structure

Core CLI-created shape:

```json
{
  "plugins": {
    "example": {
      "url": "https://example.com/repo-or-package",
      "version": "1.0.0",
      "installed_at": "2026-02-28T00:00:00"
    }
  },
  "enabled": ["example"],
  "version": "1.0.0"
}
```

Recommended additions for runtime loading:

```json
{
  "plugins": {
    "example": {
      "version": "1.0.0",
      "swx_version": ">=2.0.0,<3.0.0",
      "provider": "swx_app.plugins.example.plugin:ExamplePluginProvider",
      "config": {
        "rate_limit": {"limit": 100, "window_seconds": 60}
      }
    }
  },
  "enabled": ["example"],
  "version": "1.0.0"
}
```

### 6.2 Plugin Discovery

SwX CLI installs plugins into `swx_app/plugins/<name>/`.

For runtime discovery, you load enabled plugin providers from the manifest and register them into your container/provider registry.

### 6.3 Plugin Lifecycle Hooks

SwX providers already give you two lifecycle hooks:

- `register()` for bindings
- `boot()` for post-registration setup

If you want additional lifecycle hooks, implement them in the plugin module (for example `on_enable(container)`) and call them from your plugin loader.

### 6.4 Plugin Configuration

Recommended pattern: store config in the manifest under `plugins.<name>.config` and bind it into the container as an instance.

Example binding key: `"plugin.<name>.config"`.

### 6.5 Example Plugin

Plugin layout:

```text
swx_app/
  plugins/
    manifest.json
    example/
      __init__.py
      plugin.py
      middleware.py
```

Create `swx_app/plugins/example/middleware.py`:

```python
from __future__ import annotations

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware


class AddHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Plugin-Example"] = "1"
        return resp


def apply_middleware(app: FastAPI) -> None:
    app.add_middleware(AddHeaderMiddleware)
```

Create `swx_app/plugins/example/plugin.py`:

```python
from __future__ import annotations

from swx_core.providers.base import ServiceProvider


class ExamplePluginProvider(ServiceProvider):
    priority = 950

    def register(self) -> None:
        # Expose a simple service
        self.instance("plugin.example.name", "example")

    def boot(self) -> None:
        # Register an event listener
        from swx_core.events.dispatcher import event_bus

        async def on_any_event(event):
            # Example: ignore most events
            return None

        event_bus.listen("*", on_any_event, priority=1)
```

Create a plugin loader `swx_app/plugins/loader.py`:

```python
from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

from swx_core.container.container import Container
from swx_core.providers.base import ProviderRegistry
from swx_core.providers.core_providers import CORE_PROVIDERS


def _import_symbol(dotted: str):
    # "pkg.mod:Symbol"
    module_path, symbol = dotted.split(":", 1)
    mod = import_module(module_path)
    return getattr(mod, symbol)


def load_plugins(container: Container, manifest_path: str = "swx_app/plugins/manifest.json") -> None:
    path = Path(manifest_path)
    if not path.exists():
        return

    manifest = json.loads(path.read_text(encoding="utf-8"))
    enabled = set(manifest.get("enabled", []))
    plugins: dict[str, Any] = dict(manifest.get("plugins", {}))

    registry = ProviderRegistry(container)
    registry.register_all(CORE_PROVIDERS)

    for name, info in plugins.items():
        if name not in enabled:
            continue

        provider_path = info.get("provider") or f"swx_app.plugins.{name}.plugin:{name.title().replace('_', '')}PluginProvider"
        provider_cls = _import_symbol(provider_path)

        # Make plugin config available as an instance.
        container.instance(f"plugin.{name}.config", dict(info.get("config", {})))
        registry.register(provider_cls)

        # Optional extra hook.
        hook = info.get("on_enable")
        if hook:
            fn = _import_symbol(hook)
            fn(container)

    registry.boot()
```

Integrate loader in your FastAPI startup (example `swx_app/main.py`):

```python
from fastapi import FastAPI

from swx_core.container.container import get_container
from swx_core.container.fastapi_integration import ContainerMiddleware
from swx_app.plugins.loader import load_plugins


app = FastAPI()
app.add_middleware(ContainerMiddleware)

container = get_container()
app.state.container = container
load_plugins(container)
```

If you also want plugin middleware to be applied via SwX's dynamic loader, place plugin middleware modules under `swx_app/middleware/` (or call `apply_middleware(app)` from your plugin provider's `boot()` if you control app startup).
