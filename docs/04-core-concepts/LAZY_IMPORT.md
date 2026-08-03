# Lazy Import Proxy

**Version:** 1.0.0  
**Last Updated:** 2026-08-03

---

## Table of Contents

1. [Overview](#overview)
2. [How It Works](#how-it-works)
3. [API Reference](#api-reference)
4. [Usage Examples](#usage-examples)

---

## Overview

The **Lazy Import Proxy** (`swx_core/utils/lazy.py`) defers module imports until first attribute access, avoiding circular imports and reducing startup time for heavy optional dependencies.

Key features:

- **Zero-import at module level** — the actual import happens on first use
- **Transparent proxy** — behaves like the imported object (callable, attribute access, bool checks)
- **Circular import solution** — use in place of top-level imports that cause cycles
- **Startup optimization** — heavy packages like `redis`, `cryptography` are only loaded when needed

---

## How It Works

```python
# Instead of:
import redis.asyncio
Redis = redis.asyncio.Redis  # Imports redis immediately

# Use lazy import:
from swx_core.utils.lazy import lazy_import
Redis = lazy_import("redis.asyncio", "Redis")
# redis is NOT imported until Redis() is called
```

The `_LazyProxy` class:

1. Stores `module_path` and `attr_name` on construction (no import)
2. On first `__getattr__` or `__call__`, calls `importlib.import_module()`
3. Caches the resolved target for all subsequent access
4. Proxies all attribute access, calls, `bool()`, `isinstance()`, and `issubclass()` checks

---

## API Reference

### `lazy_import(module_path: str, attr_name: str) -> _LazyProxy`

Create a lazy proxy that defers the import until first use.

| Parameter | Type | Description |
|---|---|---|
| `module_path` | `str` | Dotted module path (e.g., `"redis.asyncio"`) |
| `attr_name` | `str` | Attribute to import from the module (e.g., `"Redis"`) |

Returns a proxy object that behaves like the imported attribute.

### `_LazyProxy`

Internal proxy class with the following dunder methods:

- `__getattr__` — resolves the import and delegates attribute access
- `__call__` — resolves the import and calls the target
- `__repr__` — shows `<LazyProxy redis.asyncio.Redis>` before resolution, target repr after
- `__bool__` — resolves and returns `bool(target)`
- `__instancecheck__` — supports `isinstance(instance, proxy)`
- `__subclasscheck__` — supports `issubclass(subclass, proxy)`

---

## Usage Examples

### Avoiding Circular Imports

```python
# service_a.py — circular import with service_b.py
from swx_core.utils.lazy import lazy_import

# Instead of: from swx_core.services.service_b import ServiceB
ServiceB = lazy_import("swx_core.services.service_b", "ServiceB")

class ServiceA:
    def process(self):
        b = ServiceB()  # ServiceB is imported NOW, not at module level
        return b.handle()
```

### Deferring Heavy Dependencies

```python
from swx_core.utils.lazy import lazy_import

# These packages are only imported when first used
Redis = lazy_import("redis.asyncio", "Redis")
Fernet = lazy_import("cryptography.fernet", "Fernet")
```

### Debugging

```python
from swx_core.utils.lazy import lazy_import

Redis = lazy_import("redis.asyncio", "Redis")
print(Redis)       # <LazyProxy redis.asyncio.Redis>
Redis()            # Now redis.asyncio is imported
print(Redis)       # <class 'redis.asyncio.Redis'>
```