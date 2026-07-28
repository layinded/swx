# API Key Scoping

**Version:** 1.0.0  
**Last Updated:** 2026-07-28

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Database Models](#database-models)
4. [Scope Pattern](#scope-pattern)
5. [Key Lifecycle](#key-lifecycle)
6. [API Endpoints](#api-endpoints)
7. [Events](#events)
8. [Best Practices](#best-practices)

---

## Overview

SwX-API includes fine-grained API key scoping with resource-level permissions, key rotation with grace periods, and usage analytics.

- **SHA-256 hashing** — Keys are stored as hashes, never in plaintext
- **Key prefix** — First 8 characters visible for identification without exposing full key
- **Resource:action scopes** — e.g., `billing:read`, `users:write`, `*:*`
- **Wildcard `*`** — Grants all actions for a resource or all resources
- **Rate limit overrides** — Per-key rate limits that override plan defaults
- **Key rotation** — Grace period for old key during rotation
- **Usage analytics** — Track per-key request counts and last used timestamps

---

## Configuration

```python
API_KEY_ENABLED: bool = True
API_KEY_DEFAULT_EXPIRY_DAYS: int = 90
API_KEY_ROTATION_GRACE_HOURS: int = 24
API_KEY_DEFAULT_RATE_LIMIT: int = 60
API_KEY_CACHE_TTL: int = 300
```

---

## Database Models

### `swx_api_key`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `name` | String(100) | Descriptive name |
| `key_prefix` | String(8) | First 8 chars for identification (indexed) |
| `hashed_key` | String(64) | SHA-256 hash (unique, indexed) |
| `user_id` | UUID | FK to swx_users (indexed) |
| `is_active` | Boolean | Active flag |
| `expires_at` | DateTime | Optional expiry |
| `last_used_at` | DateTime | Last usage timestamp |
| `rate_limit_override` | Integer | Requests per minute override |
| `metadata_` | JSONB | Key metadata |

### `swx_api_key_scope`

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Primary key |
| `api_key_id` | UUID | FK to swx_api_key (indexed) |
| `resource` | String(50) | Resource name (indexed) |
| `action` | String(50) | Action name (indexed) |
| `is_active` | Boolean | Active flag |

---

## Scope Pattern

Scopes follow the `resource:action` pattern:

| Scope | Description |
|---|---|
| `billing:read` | Read billing data |
| `billing:write` | Modify billing data |
| `users:read` | Read user data |
| `users:*` | All user operations |
| `*:*` | Full access (admin key) |

Wildcard `*` in action grants all actions for that resource. Wildcard `*` in resource grants access to all resources.

---

## Key Lifecycle

### Create
```python
from swx_core.services.auth.api_key_service import create_api_key
from swx_core.models.api_key_scope import ApiKeyCreate

response = await create_api_key(session, user_id, ApiKeyCreate(
    name="Production API",
    scopes=[{"resource": "billing", "action": "read"}, {"resource": "users", "action": "*"}],
    rate_limit_override=100
))
# response.raw_key is the ONLY time the full key is available
# Store it securely — it cannot be retrieved again
```

### Rotate
```python
from swx_core.services.auth.api_key_service import rotate_api_key

response = await rotate_api_key(session, old_key_id, user_id)
# Old key gets a grace period (default 24 hours)
# New key inherits same scopes and name
```

### Revoke
```python
from swx_core.services.auth.api_key_service import revoke_api_key

await revoke_api_key(session, key_id, user_id)
# Key is deactivated immediately
```

### Validate
```python
from swx_core.services.auth.api_key_service import validate_api_key

key_info = await validate_api_key(session, raw_key)
# Returns ApiKeyPublic or None if invalid/expired
```

---

## API Endpoints

### Admin Endpoints (`/admin/api-keys`)

| Method | Path | Description |
|---|---|---|
| GET | `/admin/api-keys` | List all API keys (filter by user) |
| GET | `/admin/api-keys/{id}` | Get key details with scopes |
| POST | `/admin/api-keys/{id}/revoke` | Revoke a key |
| GET | `/admin/api-keys/{id}/analytics` | Get usage analytics |

### User Endpoints (`/user/api-keys`)

| Method | Path | Description |
|---|---|---|
| GET | `/user/api-keys` | List own API keys |
| POST | `/user/api-keys` | Create new API key |
| GET | `/user/api-keys/{id}` | Get key details |
| POST | `/user/api-keys/{id}/rotate` | Rotate key |
| DELETE | `/user/api-keys/{id}` | Revoke own key |
| PUT | `/user/api-keys/{id}/scopes` | Update scopes |

---

## Events

| Event | Payload | Trigger |
|---|---|---|
| `api_key.created` | key_id, user_id, name, key_prefix | Key created |
| `api_key.rotated` | old_key_id, new_key_id, user_id | Key rotated |
| `api_key.revoked` | key_id, user_id | Key revoked |
| `api_key.scope_changed` | key_id | Scopes added/removed |

---

## Best Practices

1. **Store the raw key immediately** — It's shown once on creation and cannot be retrieved
2. **Use minimal scopes** — Follow least-privilege; only grant what's needed
3. **Set expiration dates** — Default is 90 days; rotate regularly
4. **Use rate limit overrides** — Prevent any single key from overwhelming your API
5. **Monitor analytics** — Check `last_used_at` and request counts for inactive keys
6. **Rotate on compromise** — Use rotation instead of revoke+create to maintain scope continuity