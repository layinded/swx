# Caching

**Version:** 2.11.0
**Last Updated:** 2026-08-03

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Auth Caching](#auth-caching)
4. [Feature Flag Caching](#feature-flag-caching)
5. [Role Caching](#role-caching)
6. [Settings Caching](#settings-caching)
7. [CacheService](#cacheservice)
8. [Tenant Config Cache](#tenant-config-cache)
9. [Configuration Reference](#configuration-reference)
10. [Invalidation Reference](#invalidation-reference)
11. [Redis Requirements](#redis-requirements)
12. [Best Practices](#best-practices)

---

## Overview

SwX-API provides **L1/L2 caching** for high-frequency lookups: auth, feature flags, roles, and runtime settings. All caches are **disabled by default** for backward compatibility and are enabled through environment variables.

### Why L1/L2?

| Layer | Location | Speed | Shared? | Use Case |
|---|---|---|---|---|
| **L1** | Process-local dict | ~0.001ms | No | Eliminates Redis round-trips for hot keys |
| **L2** | Redis | ~0.5ms | Yes | Shares cache across processes/workers |
| **DB** | PostgreSQL | ~5-50ms | Yes | Source of truth on cache miss |

### Flow

```
Request → L1 Cache → L2 Cache → Database
              ↓ hit        ↓ hit       ↓ miss
           return data  return data  query + populate L1+L2
```

When Redis is unavailable, caches **gracefully degrade** to L1-only and then fall back to the database.

---

## Architecture

### Key Naming

All cache keys follow this format: `{env}:{app}:{scope}:{resource}:{identifier}:{version}`

| Scope | Resource | Example Key |
|---|---|---|
| `user` | `profile` | `prod:nh:user:profile:user@example.com:v1` |
| `user` | `permissions` | `prod:nh:user:permissions:550e8400:v1` |
| `user` | `roles` | `prod:nh:user:roles:550e8400:v1` |
| `admin` | `profile` | `prod:nh:admin:profile:admin@example.com:v1` |
| `feature_flag` | `config` | `prod:nh:feature_flag:config:flag:dark_mode:v1` |
| `settings` | `config` | `prod:nh:settings:config:setting:auth.access_token_expire_minutes:v1` |

### Serialization

- **Profiles**: Core fields only (excludes `hashed_password`). UUIDs and datetimes serialized to strings.
- **Permissions**: `id`, `name`, `description`, `resource_type`, `action`
- **Roles**: `id`, `name`, `description`, `domain`, `is_system_role`
- **Feature flags**: Boolean values
- **Settings**: Raw values (int, bool, string, JSON)

---

## Auth Caching

Auth caching reduces database queries for authenticated requests that need user profiles, admin profiles, or permissions.

> **Detailed docs:** [AUTHENTICATION.md](./AUTHENTICATION.md#auth-caching)

### Cached Fields

**User profile** (excludes `hashed_password`):
`id`, `email`, `full_name`, `is_active`, `is_superuser`, `auth_provider`, `provider_id`, `avatar_url`, `preferred_language`, `tenant_id`, `created_at`, `updated_at`

**Admin profile** (excludes `hashed_password`):
`id`, `email`, `full_name`, `is_active`, `auth_provider`, `provider_id`, `created_at`

**User permissions**:
`id`, `name`, `description`, `resource_type`, `action`

### Enable Auth Caching

```env
# .env
USER_CACHE_ENABLED=true
ADMIN_CACHE_ENABLED=true
USER_CACHE_TTL=300
USER_PERMISSIONS_CACHE_TTL=120
ADMIN_CACHE_TTL=300
USER_CACHE_L1_MAX_ENTRIES=1000
```

### Manual Invalidation

```python
from swx_core.auth.auth_cache import (
    invalidate_user_cache,
    invalidate_user_permissions,
    invalidate_admin_cache,
    invalidate_all_permissions,
    invalidate_user_roles,
    invalidate_all_roles,
)

# Invalidate all cached data for a user (profile + permissions + roles)
await invalidate_user_cache(user_id="550e8400...", email="user@example.com")

# Invalidate only permissions for a user
await invalidate_user_permissions(user_id="550e8400...")

# Invalidate roles for a user
await invalidate_user_roles(user_id="550e8400...")

# Invalidate all cached data for an admin
await invalidate_admin_cache(admin_id="...", email="admin@example.com")

# Invalidate ALL cached permissions (bulk)
await invalidate_all_permissions()

# Invalidate ALL cached roles (bulk)
await invalidate_all_roles()
```

---

## Feature Flag Caching

Feature flags are runtime booleans stored in `swx_system_config` with keys like `feature.dark_mode`. Without caching, each `get_feature_flag()` call hits the database.

### How It Works

```python
from swx_core.services.settings_helper import get_feature_flag

# With FEATURE_FLAG_CACHE_ENABLED=True:
# L1 → L2 → Database (automatic)
flag = await get_feature_flag(session, "dark_mode", default=False)

# With FEATURE_FLAG_CACHE_ENABLED=False (default):
# Database only (backward compatible)
flag = await get_feature_flag(session, "dark_mode", default=False)
```

### Enable Feature Flag Caching

```env
# .env
FEATURE_FLAG_CACHE_ENABLED=true
FEATURE_FLAG_CACHE_TTL=300
FEATURE_FLAG_CACHE_L1_MAX_ENTRIES=200
```

### When Flags Are Cached

Feature flags are cached on **first read** after a `get_feature_flag()` call. The default TTL is 5 minutes, which suits flags that change infrequently.

### When Flags Are Invalidated

| Event | What Happens |
|---|---|
| Setting created with key `feature.*` | Specific flag cache entry invalidated |
| Setting updated with key `feature.*` | Specific flag cache entry invalidated |
| Any setting updated | Settings cache entry invalidated |

### Manual Invalidation

```python
from swx_core.utils.runtime_cache import (
    invalidate_feature_flag,
    invalidate_all_feature_flags,
)

# Invalidate a specific feature flag
await invalidate_feature_flag("dark_mode")

# Invalidate ALL feature flag caches
await invalidate_all_feature_flags()
```

---

## Role Caching

Role lookups via `get_user_roles()` query the database on every call. With caching enabled, roles are stored in L1/L2 after the first lookup.

### How It Works

```python
from swx_core.rbac.helpers import get_user_roles, has_role

# With USER_CACHE_ENABLED=True:
# First call: L1 miss → L2 miss → Database → populate L1+L2
# Second call: L1 hit → return immediately
roles = await get_user_roles(session, user_id)

# has_role() also benefits from role caching
if await has_role(session, user, "admin"):
    ...
```

### Enable Role Caching

Role caching is included with the user auth cache, so no separate setting is needed:

```env
# .env
USER_CACHE_ENABLED=true
USER_CACHE_TTL=300
```

Role cache entries use the same `USER_CACHE_TTL` as user profiles.

### Cached Fields

**User roles**:
`id`, `name`, `description`, `domain`, `is_system_role`

### When Roles Are Invalidated

| Event | What Happens |
|---|---|
| Role assigned to user | User's role cache + permission cache invalidated |
| Role removed from user | User's role cache + permission cache invalidated |
| Role updated | ALL role caches invalidated |
| Role deleted | ALL role caches invalidated |

### Manual Invalidation

```python
from swx_core.auth.auth_cache import invalidate_user_roles, invalidate_all_roles

# Invalidate roles for a specific user
await invalidate_user_roles(user_id="550e8400...")

# Invalidate ALL cached roles (bulk)
await invalidate_all_roles()
```

---

## Settings Caching

Runtime settings are stored in `swx_system_config` and accessed via `SettingsService`. The built-in in-memory cache (`_settings_cache`) already provides process-local caching with a 60-second TTL. The L1/L2 settings cache adds **cross-process sharing** via Redis.

### How It Works

```python
from swx_core.services.settings_helper import get_setting_cached

# With SETTINGS_CACHE_ENABLED=True:
# L1 → L2 → Database → populate L1+L2
value = await get_setting_cached(session, "auth.access_token_expire_minutes", default=10080)

# With SETTINGS_CACHE_ENABLED=False (default):
# Uses existing SettingsService in-memory cache only
value = await get_setting_cached(session, "auth.access_token_expire_minutes", default=10080)
```

### Enable Settings Caching

```env
# .env
SETTINGS_CACHE_ENABLED=true
SETTINGS_CACHE_TTL=60
SETTINGS_CACHE_L1_MAX_ENTRIES=500
```

> **Note:** The `SETTINGS_CACHE_TTL` defaults to 60 seconds, shorter than auth and flag caches so settings changes propagate faster.

### When Settings Are Invalidated

| Event | What Happens |
|---|---|
| Setting created | Settings cache entry invalidated |
| Setting updated | Settings cache entry invalidated |
| Feature flag setting updated | Both feature flag cache AND settings cache invalidated |

### Manual Invalidation

```python
from swx_core.utils.runtime_cache import (
    invalidate_cached_setting,
    invalidate_all_settings,
)

# Invalidate a specific setting
await invalidate_cached_setting("auth.access_token_expire_minutes")

# Invalidate ALL cached settings
await invalidate_all_settings()
```

---

## CacheService

`swx_core/services/cache/cache_service.py` provides a high-level cache interface with Redis primary and in-memory fallback. When Redis is unavailable, operations silently fall back to an in-memory LRU cache so the application never crashes due to cache failures.

### Usage

```python
from swx_core.services.cache.cache_service import CacheService

cache = CacheService()

# Get or compute (primary API)
user = await cache.get_or_set(
    f"user:{user_id}",
    factory=lambda: fetch_user(user_id),
    ttl=300,
)

# Direct operations
await cache.set("key", value, ttl=60)
result = await cache.get("key")
await cache.delete("key")
deleted_count = await cache.invalidate("key1", "key2", "key3")
```

### Methods

| Method | Description |
|---|---|
| `get(key)` | Retrieve a value. Returns `None` on miss or error |
| `set(key, value, ttl)` | Store a value. Returns `True` on success |
| `delete(key)` | Delete a key. Returns `True` on success |
| `get_or_set(key, factory, ttl)` | Get from cache, or compute via async factory on miss |
| `invalidate(*keys)` | Delete multiple keys. Returns count of successful deletions |

All methods swallow exceptions and log debug messages, making the cache fully resilient.

---

## Tenant Config Cache

`swx_core/services/cache/tenant_config_cache.py` provides a three-tier configuration cache for tenant/team/org settings:

| Layer | Location | Speed | Shared? |
|---|---|---|---|
| L1 | Per-process in-memory dict | Sub-ms | No |
| L2 | Redis | Sub-5ms | Yes |
| L3 | Database via `SettingsService` | Sub-30ms | Yes |

### L1 Consistency

Redis pub/sub broadcasts `invalidate:<key>` messages to all workers so they drop their L1 entry. This is eventually consistent — a brief stale read is possible between DB write and pub/sub delivery.

### Usage

```python
from swx_core.services.cache.tenant_config_cache import tenant_config

# Read-through: L1 → L2 → L3
value = await tenant_config.get(session, "billing.plan", default="free")

# Invalidate all levels + broadcast
await tenant_config.invalidate("billing.plan")
```

### Startup Integration

Subscribe to invalidation broadcasts at application startup:

```python
# In lifespan startup:
await tenant_config.subscribe_invalidations()
```

Module-level singleton: `tenant_config` — import and use from anywhere.

---

## Configuration Reference

All cache settings are in `.env` or environment variables:

### Auth Cache

| Setting | Default | Description |
|---|---|---|
| `USER_CACHE_ENABLED` | `false` | Enable L1/L2 cache for user auth lookups |
| `USER_CACHE_TTL` | `300` | TTL in seconds for cached user profiles (5 min) |
| `USER_PERMISSIONS_CACHE_TTL` | `120` | TTL in seconds for cached user permissions (2 min) |
| `USER_CACHE_L1_MAX_ENTRIES` | `1000` | Maximum entries in process-local L1 cache |
| `ADMIN_CACHE_ENABLED` | `false` | Enable L1/L2 cache for admin auth lookups |
| `ADMIN_CACHE_TTL` | `300` | TTL in seconds for cached admin profiles (5 min) |

### Feature Flag Cache

| Setting | Default | Description |
|---|---|---|
| `FEATURE_FLAG_CACHE_ENABLED` | `false` | Enable L1/L2 cache for feature flag lookups |
| `FEATURE_FLAG_CACHE_TTL` | `300` | TTL in seconds for cached feature flags (5 min) |
| `FEATURE_FLAG_CACHE_L1_MAX_ENTRIES` | `200` | Maximum entries in process-local L1 cache for feature flags |

### Settings Cache

| Setting | Default | Description |
|---|---|---|
| `SETTINGS_CACHE_ENABLED` | `false` | Enable L1/L2 cache for runtime settings lookups |
| `SETTINGS_CACHE_TTL` | `60` | TTL in seconds for cached settings (1 min) |
| `SETTINGS_CACHE_L1_MAX_ENTRIES` | `500` | Maximum entries in process-local L1 cache for settings |

---

## Invalidation Reference

Complete invalidation map for all caches:

| Event | Profile Cache | Permission Cache | Role Cache | Flag Cache | Settings Cache |
|---|---|---|---|---|---|
| User profile update | ✅ | — | — | — | — |
| Password change | ✅ | — | — | — | — |
| User deletion | ✅ | ✅ | ✅ | — | — |
| Role assigned to user | — | ✅ | ✅ | — | — |
| Role removed from user | — | ✅ | ✅ | — | — |
| Role updated | — | — | ✅ (all) | — | — |
| Role deleted | — | — | ✅ (all) | — | — |
| Permission ↔ role changed | — | ✅ (all) | — | — | — |
| Admin profile update | ✅ (admin) | — | — | — | — |
| Setting created (feature.*) | — | — | — | ✅ | ✅ |
| Setting updated (feature.*) | — | — | — | ✅ | ✅ |
| Setting created/updated (other) | — | — | — | — | ✅ |

---

## Redis Requirements

### Optional but Recommended

All caches **gracefully degrade** when Redis is unavailable:
- L1 cache continues to work (per-process only)
- Database queries happen on L1 miss
- Warnings logged when L2 operations fail

### Redis Configuration

```env
# .env — Redis is configured via the container settings
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
```

The cache uses the Redis client from the SwX service container (`swx_core.container.container.get_container()`). If Redis is not bound in the container, L2 is skipped silently.

### Key Count Estimation

For a deployment with 10,000 users, 50 roles, and 100 feature flags:

| Cache | Keys per User | Total Keys |
|---|---|---|
| User profiles | 2 (email + id) | 20,000 |
| User permissions | 1 | 10,000 |
| User roles | 1 | 10,000 |
| Admin profiles | 2 | ~100 |
| Feature flags | 1 each | ~100 |
| Settings | 1 each | ~200 |
| **Total** | | **~40,300** |

Memory estimate: ~20-50 MB for 10K users.

---

## Best Practices

### ✅ DO

- Enable `USER_CACHE_ENABLED` in production to reduce auth DB load
- Enable `FEATURE_FLAG_CACHE_ENABLED` if you check flags frequently
- Set `USER_PERMISSIONS_CACHE_TTL` shorter than `USER_CACHE_TTL` — permissions change more often than profiles
- Set `SETTINGS_CACHE_TTL` to 60s or less — settings changes should propagate quickly
- Use Redis in production for L2 cache sharing across workers
- Monitor Redis memory usage with the key estimates above

### ❌ DON'T

- Don't enable caching in development unless testing cache behavior — it can mask bugs
- Don't set TTLs above 600 seconds — stale data risk increases significantly
- Don't set `USER_CACHE_L1_MAX_ENTRIES` too low (under 100) — it causes frequent evictions
- Don't manually invalidate caches from route handlers — use the service layer hooks instead
- Don't cache `hashed_password` — it's excluded from serialization automatically

---

## Next Steps

- Read [Authentication](./AUTHENTICATION.md) for auth caching details
- Read [Settings](./SETTINGS.md) for runtime settings
- Read [RBAC](./RBAC.md) for role and permission system
- Read [Architecture](../03-architecture/ARCHITECTURE.md) for system design
